/* FX1 Phrase Looper: replaces the Granular renderer in FX1 mode 1 when the
 * firmware is built with PHRASE_LOOPER. Original code; host-compilable.
 *
 * It reuses the Granular SDRAM buffer (allocated once at FX1 construction,
 * before FX2) and the Granular parameter ids, relabelled on the M4:
 *   G_POS     Dry/Wet   0..1000
 *   G_DENSITY Bars      1..2
 *   G_JITTER  Overdub   0..1000 (live input layered into the loop each pass)
 *   G_FREEZE  Sync      0/1     (on: wait for the sequencer to start)
 *   G_REVERSE Play      0/1     (on: record if empty, else play; off: stop)
 *   G_SIZE    Clear     0/1     (rising edge empties the loop)
 * Edges are only acted on after the first value has been observed, so a
 * project that loads with Play or Clear already on does not start recording.
 *
 * Loop length is Bars x one 4/4 bar at the project tempo, published by the
 * M4 into PL_TEMPO. Without a valid tempo it assumes 120 BPM. If the loop does
 * not fit the allocated buffer it drops to 1 bar, then to the buffer length. */
#ifndef BLUEBOX_PHRASE_LOOPER_H
#define BLUEBOX_PHRASE_LOOPER_H
#include <stdint.h>
#include "granular.h"

#define PL_MAGIC 0x504c4f31u
#define PL_TEMPO_MAGIC 0x504c5431u
#define PL_FS 48000u
#define PL_RAMP 240u              /* 5 ms declick at 48 kHz */
#define PL_CAP_MAX 384000u        /* 2 bars at 60 BPM, stereo float */
#define PL_BYTES (PL_CAP_MAX*2u*sizeof(float))
#define PL_RESERVE (4u*1024u*1024u) /* SDRAM left free for later consumers */
#define PL_DEFAULT_BPM_X10 1200u

enum {PL_EMPTY=0,PL_ARMED,PL_REC,PL_PLAY,PL_STOP};

/* M4 writes, M7 only reads (after invalidating its cache line). */
struct pl_tempo {
    uint32_t magic;
    int32_t raw_bpm;              /* project setting 0x85 as stored */
    uint32_t playing;             /* sequencer position moved recently */
    uint32_t seq;
    uint32_t pos,moved;           /* M4 bookkeeping */
    uint32_t spare[2];
};

/* M7 only. */
struct phrase_looper {
    uint32_t magic;
    void *owner;
    uint32_t cap;                 /* frames available in the buffer */
    uint32_t state;
    uint32_t len,pos;
    int32_t play_seen,clear_seen;  /* -1 until the first observation */
    uint32_t transport_seen;
    float gain,wet,overdub;        /* smoothed */
    uint32_t bpm_x10;              /* tempo used for the current loop */
    uint32_t seq;
    uint32_t spare[2];
};

/* Results reported to the caller, which owns the UI message queue. */
#define PL_ACK_CLEAR 1u            /* set Clear back to 0 */
#define PL_ACK_PLAY_OFF 2u         /* set Play back to 0 */

static inline void pl_reset(struct phrase_looper *p,void *owner,uint32_t cap) {
    uint32_t *w=(uint32_t *)p;
    for(unsigned i=0;i<sizeof(*p)/4;i++)w[i]=0;
    p->owner=owner;p->cap=cap;p->state=PL_EMPTY;
    p->play_seen=p->clear_seen=-1;
    p->bpm_x10=PL_DEFAULT_BPM_X10;
    p->magic=PL_MAGIC;
}

/* Accepts plain BPM, tenths or hundredths. 20..300 BPM is valid. */
static inline uint32_t pl_bpm_x10(int32_t raw) {
    if(raw>=20 && raw<=300)return (uint32_t)raw*10u;
    if(raw>300 && raw<=3000)return (uint32_t)raw;
    if(raw>3000 && raw<=30000)return (uint32_t)raw/10u;
    return PL_DEFAULT_BPM_X10;
}

/* Frames for the requested bars, reduced to fit the buffer. */
static inline uint32_t pl_length(uint32_t bpm_x10,int bars,uint32_t cap) {
    if(bpm_x10<200u)bpm_x10=200u;
    if(bpm_x10>3000u)bpm_x10=3000u;
    uint32_t bar=(PL_FS*60u*4u*10u)/bpm_x10;   /* 115,200,000/bpm_x10 */
    if(bars<1)bars=1;
    if(bars>2)bars=2;
    uint32_t len=bar*(uint32_t)bars;
    if(len>cap && bars>1)len=bar;
    if(len>cap)len=cap;
    return len;
}

/* In-place declick at both ends of a freshly recorded loop. */
static inline void pl_seal(float *buffer,uint32_t len) {
    uint32_t r=PL_RAMP;
    if(r>len/4u)r=len/4u;
    for(uint32_t i=0;i<r;i++) {
        float g=(float)i*(1.f/(float)PL_RAMP);
        float *a=buffer+2u*i,*b=buffer+2u*(len-1u-i);
        a[0]*=g;a[1]*=g;b[0]*=g;b[1]*=g;
    }
}

static inline void pl_start_capture(struct phrase_looper *p,const struct granular *g,uint32_t bpm_x10) {
    p->bpm_x10=bpm_x10;
    p->len=pl_length(bpm_x10,g->density,p->cap);
    p->pos=0;
    p->state=p->len>=PL_RAMP*4u?PL_REC:PL_EMPTY;
}

/* Control edges, once per block. */
static inline unsigned pl_controls(struct phrase_looper *p,const struct granular *g,uint32_t bpm_x10,uint32_t playing) {
    unsigned ack=0;
    int play=g->reverse!=0,clear=g->size!=0;
    if(p->clear_seen>=0 && clear && !p->clear_seen) {
        p->state=PL_EMPTY;p->len=p->pos=0;
        ack|=PL_ACK_CLEAR;
        /* Ask the UI to turn Play off, but take its current value as seen:
         * a new take needs Play off then on, whether or not the UI follows. */
        if(play)ack|=PL_ACK_PLAY_OFF;
        p->play_seen=play;
    }
    p->clear_seen=clear;
    if(p->play_seen>=0 && play!=p->play_seen) {
        if(play) {
            if(p->state==PL_EMPTY) {
                if(g->freeze && !playing)p->state=PL_ARMED;
                else pl_start_capture(p,g,bpm_x10);
            } else if(p->state==PL_STOP && p->len) {
                p->state=PL_PLAY;p->pos=0;
            }
        } else {
            if(p->state==PL_ARMED)p->state=PL_EMPTY;
            else if(p->state==PL_PLAY)p->state=PL_STOP;
            else if(p->state==PL_REC) {
                /* Stopped part-way: keep what was captured if it is usable. */
                if(p->pos>=PL_RAMP*4u) {
                    p->len=p->pos;p->pos=0;p->state=PL_STOP;p->seq++;
                    pl_seal(g->buffer,p->len);
                } else {p->state=PL_EMPTY;p->len=p->pos=0;}
            }
        }
    }
    p->play_seen=play;
    if(p->state==PL_ARMED && playing && !p->transport_seen)pl_start_capture(p,g,bpm_x10);
    p->transport_seen=playing;
    return ack;
}

/* Renders one block. in_* is the FX1 input copied before the native delay
 * ran; out_* holds the native delay output and receives the looper output,
 * crossfaded with g->fade exactly as the Granular renderer did. When the mode
 * is left and the fade reaches zero, the shared ring is handed back empty. */
static inline unsigned pl_render(struct phrase_looper *p,struct granular *g,uint32_t bpm_x10,uint32_t playing,
                                 const float *in_l,const float *in_r,float *out_l,float *out_r,unsigned n) {
    float *buffer=g->buffer;
    if(!buffer)return 0;
    unsigned ack=pl_controls(p,g,bpm_x10,playing);
    float target=g->mode?1.f:0.f,fade=g->fade;
    float wet_t=(float)g_clampi(g->position,0,1000)*.001f;
    float od_t=(float)g_clampi(g->jitter,0,1000)*.001f;
    float wet=p->wet,od=p->overdub,gain=p->gain;
    float dw=n?(wet_t-wet)/(float)n:0.f,dod=n?(od_t-od)/(float)n:0.f;
    uint32_t state=p->state,len=p->len,pos=p->pos;
    for(unsigned i=0;i<n;i++) {
        wet+=dw;od+=dod;
        float l=0.f,r=0.f;
        if(state==PL_REC) {
            buffer[2u*pos]=g_limit(in_l[i]);
            buffer[2u*pos+1u]=g_limit(in_r[i]);
            if(++pos>=len) {
                pl_seal(buffer,len);
                pos=0;state=PL_PLAY;p->seq++;
            }
        } else if((state==PL_PLAY || state==PL_STOP) && len) {
            float *s=buffer+2u*pos;
            l=s[0];r=s[1];
            if(state==PL_PLAY && od>0.f) {
                float a=l+in_l[i]*od,b=r+in_r[i]*od;
                s[0]=a>2.f?2.f:a<-2.f?-2.f:a;
                s[1]=b>2.f?2.f:b<-2.f?-2.f:b;
            }
            if(++pos>=len)pos=0;
        }
        float gt=state==PL_PLAY?1.f:0.f;
        if(gain<gt){gain+=1.f/(float)PL_RAMP;if(gain>gt)gain=gt;}
        else if(gain>gt){gain-=1.f/(float)PL_RAMP;if(gain<gt)gain=gt;}
        float yl=in_l[i]*(1.f-wet)+l*gain*wet;
        float yr=in_r[i]*(1.f-wet)+r*gain*wet;
        if(fade<target){fade+=1.f/(float)PL_RAMP;if(fade>target)fade=target;}
        else if(fade>target){fade-=1.f/(float)PL_RAMP;if(fade<target)fade=target;}
        if(fade==1.f){out_l[i]=yl;out_r[i]=yr;}
        else {out_l[i]+=(yl-out_l[i])*fade;out_r[i]+=(yr-out_r[i])*fade;}
    }
    if(state==PL_STOP && gain==0.f)pos=0;
    p->state=state;p->len=len;p->pos=pos;
    p->wet=wet;p->overdub=od;p->gain=gain;
    g->fade=fade;
    if(!g->mode && fade==0.f) {
        /* Left the looper: the ring now holds loop audio, not history. */
        p->state=PL_EMPTY;p->len=p->pos=0;p->gain=0.f;
        p->play_seen=p->clear_seen=-1;
        g->wr=g->valid=g->countdown=0;
        g->fb_l=g->fb_r=0.f;
        for(unsigned j=0;j<4;j++)g->grains[j].len=0;
    }
    return ack;
}
#endif
