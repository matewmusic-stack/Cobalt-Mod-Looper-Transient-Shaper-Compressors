/* FX1 Phrase Looper: replaces the Granular renderer in FX1 mode 1 when the
 * firmware is built with PHRASE_LOOPER. Original code; host-compilable.
 *
 * It reuses the Granular SDRAM buffer (allocated once at FX1 construction,
 * before FX2) and the Granular parameter ids, relabelled on the M4:
 *   G_DENSITY Bars    1..2       loop length in 4/4 bars at the project BPM
 *   G_POS     Level   0..1000    loop volume on the FX1 return
 *   G_JITTER  Dub     0..1000    overdub amount: live input layered while DUB
 *   G_FREEZE  Sync    0/1        on: REC waits for the sequencer to start
 *   G_REVERSE REC     button     empty: record; recording: close the loop now;
 *                                playing: overdub on/off; stopped: play
 *   LP_STOP   STOP    button     stop; when stopped, play from the start
 *   G_SIZE    CLEAR   button     empty the loop
 * REC, STOP and CLEAR are pedal-style buttons: a press is a change from 0 to
 * 1 in the FX1 event queue. The M4 sets them back to 0 right away, so they
 * never stay lit; a change back to 0 is not a press. Values seen before the
 * first one (project load) only latch.
 *
 * The FX1 return carries only the loop. The M4 mutes the tracks that feed
 * FX1 while the loop plays (PL_PLAY) and unmutes them otherwise, so the
 * source is heard while recording and overdubbing.
 *
 * Loop length uses the project tempo the M4 publishes in PL_TEMPO (BPM
 * setting 0x85, 40..250 BPM); without one, 120 BPM. A loop that does not fit
 * the buffer drops to 1 bar, then to the buffer length. */
#ifndef BLUEBOX_PHRASE_LOOPER_H
#define BLUEBOX_PHRASE_LOOPER_H
#include <stdint.h>
#include "granular.h"

#define LP_STOP 0x1ba             /* new FX1 parameter: STOP button */
#define LP_REC G_REVERSE
#define LP_CLEAR G_SIZE
#define PL_MAGIC 0x504c4f32u
#define PL_TEMPO_MAGIC 0x504c5431u
#define PL_FS 48000u
#define PL_RAMP 240u              /* 5 ms declick at 48 kHz */
#define PL_CAP_MAX 384000u        /* 2 bars at 60 BPM, stereo float */
#define PL_BYTES (PL_CAP_MAX*2u*sizeof(float))
#define PL_RESERVE (4u*1024u*1024u) /* SDRAM left free for later consumers */
#define PL_DEFAULT_BPM_X10 1200u

enum {PL_EMPTY=0,PL_ARMED,PL_REC,PL_PLAY,PL_STOP,PL_DUB};

/* M4 writes, M7 only reads (after invalidating its cache line). */
struct pl_tempo {
    uint32_t magic;
    int32_t raw_bpm;              /* project setting 0x85 as stored */
    uint32_t playing;             /* sequencer position moved recently */
    uint32_t seq;
    uint32_t pos,moved;           /* M4 bookkeeping */
    uint32_t muted;               /* M4: tracks the looper muted; bit 31 = applied */
    uint32_t spare;
};

/* M7 writes; the first 32 bytes (one cache line) are cleaned after every
 * block so the M4 can show the state and drive the auto-mute. */
struct phrase_looper {
    uint32_t magic;
    void *owner;
    uint32_t cap;                 /* frames available in the buffer */
    uint32_t state;
    uint32_t len,pos;
    uint32_t bars;                /* bars in the current loop (1..2) */
    uint32_t seq;
    /* -- second cache line: M7 only -- */
    int8_t last[3];               /* last REC/STOP/CLEAR value, -1 unknown */
    uint8_t presses;              /* bit 0 REC, 1 STOP, 2 CLEAR */
    uint32_t transport_seen;
    float gain,level,dub;         /* smoothed */
    uint32_t bpm_x10;             /* tempo used for the current loop */
    uint32_t spare[2];
};
#define PL_PRESS_REC 1u
#define PL_PRESS_STOP 2u
#define PL_PRESS_CLEAR 4u

static inline void pl_reset(struct phrase_looper *p,void *owner,uint32_t cap) {
    uint32_t *w=(uint32_t *)p;
    for(unsigned i=0;i<sizeof(*p)/4;i++)w[i]=0;
    p->owner=owner;p->cap=cap;p->state=PL_EMPTY;
    p->last[0]=p->last[1]=p->last[2]=-1;
    p->bpm_x10=PL_DEFAULT_BPM_X10;
    p->magic=PL_MAGIC;
}
/* Forget button history (mode change, project load): next values latch. */
static inline void pl_drop(struct phrase_looper *p) {
    p->state=PL_EMPTY;p->len=p->pos=0;p->gain=0.f;
    p->last[0]=p->last[1]=p->last[2]=-1;p->presses=0;
}

/* Called for every FX1 parameter event, in queue order. */
static inline void pl_event(struct phrase_looper *p,unsigned id,int value) {
    int k=id==LP_REC?0:id==LP_STOP?1:id==LP_CLEAR?2:-1;
    if(k<0)return;
    int v=value!=0;
    if(p->last[k]==0 && v)p->presses|=(uint8_t)(1u<<k);
    p->last[k]=(int8_t)v;
}

/* Accepts plain BPM, tenths or hundredths. 20..300 BPM is valid. */
static inline uint32_t pl_bpm_x10(int32_t raw) {
    if(raw>=20 && raw<=300)return (uint32_t)raw*10u;
    if(raw>300 && raw<=3000)return (uint32_t)raw;
    if(raw>3000 && raw<=30000)return (uint32_t)raw/10u;
    return PL_DEFAULT_BPM_X10;
}

/* Frames for the requested bars, reduced to fit the buffer. */
static inline uint32_t pl_length(uint32_t bpm_x10,int bars,uint32_t cap,uint32_t *used_bars) {
    if(bpm_x10<200u)bpm_x10=200u;
    if(bpm_x10>3000u)bpm_x10=3000u;
    uint32_t bar=(PL_FS*60u*4u*10u)/bpm_x10;   /* 115,200,000/bpm_x10 */
    if(bars<1)bars=1;
    if(bars>2)bars=2;
    uint32_t len=bar*(uint32_t)bars;
    if(len>cap && bars>1){len=bar;bars=1;}
    if(len>cap)len=cap;
    if(used_bars)*used_bars=(uint32_t)bars;
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
    p->len=pl_length(bpm_x10,g->density,p->cap,&p->bars);
    p->pos=0;
    p->state=p->len>=PL_RAMP*4u?PL_REC:PL_EMPTY;
}
/* Close a take early: keep it as the loop if it is long enough. */
static inline void pl_close(struct phrase_looper *p,float *buffer,uint32_t next) {
    if(p->pos>=PL_RAMP*4u) {
        p->len=p->pos;p->pos=0;p->state=next;p->seq++;
        pl_seal(buffer,p->len);
    } else {p->state=PL_EMPTY;p->len=p->pos=0;}
}

/* Button presses and Sync, once per block before rendering. */
static inline void pl_controls(struct phrase_looper *p,const struct granular *g,uint32_t bpm_x10,uint32_t playing) {
    unsigned press=p->presses;p->presses=0;
    if(press&PL_PRESS_CLEAR){p->state=PL_EMPTY;p->len=p->pos=0;press=0;}
    if(press&PL_PRESS_STOP) {
        switch(p->state) {
        case PL_ARMED:p->state=PL_EMPTY;break;
        case PL_REC:pl_close(p,g->buffer,PL_STOP);break;
        case PL_PLAY:case PL_DUB:p->state=PL_STOP;break;
        case PL_STOP:if(p->len){p->state=PL_PLAY;p->pos=0;}break;
        default:break;
        }
        press&=~PL_PRESS_REC;      /* STOP wins over a simultaneous REC */
    }
    if(press&PL_PRESS_REC) {
        switch(p->state) {
        case PL_EMPTY:
            if(g->freeze && !playing)p->state=PL_ARMED;
            else pl_start_capture(p,g,bpm_x10);
            break;
        case PL_ARMED:p->state=PL_EMPTY;break;
        case PL_REC:pl_close(p,g->buffer,PL_PLAY);break;
        case PL_PLAY:p->state=PL_DUB;break;
        case PL_DUB:p->state=PL_PLAY;break;
        case PL_STOP:if(p->len){p->state=PL_PLAY;p->pos=0;}break;
        default:break;
        }
    }
    if(p->state==PL_ARMED && playing && !p->transport_seen)pl_start_capture(p,g,bpm_x10);
    p->transport_seen=playing;
}

/* Renders one block. in_* is the FX1 input copied before the native delay
 * ran; out_* holds the native delay output and receives the loop, crossfaded
 * with g->fade exactly as the Granular renderer did. When the mode is left
 * and the fade reaches zero, the shared ring is handed back empty. */
static inline void pl_render(struct phrase_looper *p,struct granular *g,uint32_t bpm_x10,uint32_t playing,
                             const float *in_l,const float *in_r,float *out_l,float *out_r,unsigned n) {
    float *buffer=g->buffer;
    if(!buffer)return;
    pl_controls(p,g,bpm_x10,playing);
    float target=g->mode?1.f:0.f,fade=g->fade;
    float level_t=(float)g_clampi(g->position,0,1000)*.001f;
    float dub_t=(float)g_clampi(g->jitter,0,1000)*.001f;
    float level=p->level,dub=p->dub,gain=p->gain;
    float dl=n?(level_t-level)/(float)n:0.f,dd=n?(dub_t-dub)/(float)n:0.f;
    uint32_t state=p->state,len=p->len,pos=p->pos;
    for(unsigned i=0;i<n;i++) {
        level+=dl;dub+=dd;
        float l=0.f,r=0.f;
        if(state==PL_REC) {
            buffer[2u*pos]=g_limit(in_l[i]);
            buffer[2u*pos+1u]=g_limit(in_r[i]);
            if(++pos>=len) {
                pl_seal(buffer,len);
                pos=0;state=PL_PLAY;p->seq++;
            }
        } else if((state==PL_PLAY || state==PL_DUB || state==PL_STOP) && len) {
            float *s=buffer+2u*pos;
            l=s[0];r=s[1];
            if(state==PL_DUB && dub>0.f) {
                float a=l+in_l[i]*dub,b=r+in_r[i]*dub;
                s[0]=a>2.f?2.f:a<-2.f?-2.f:a;
                s[1]=b>2.f?2.f:b<-2.f?-2.f:b;
            }
            if(++pos>=len)pos=0;
        }
        float gt=state==PL_PLAY || state==PL_DUB?1.f:0.f;
        if(gain<gt){gain+=1.f/(float)PL_RAMP;if(gain>gt)gain=gt;}
        else if(gain>gt){gain-=1.f/(float)PL_RAMP;if(gain<gt)gain=gt;}
        float yl=l*gain*level,yr=r*gain*level;
        if(fade<target){fade+=1.f/(float)PL_RAMP;if(fade>target)fade=target;}
        else if(fade>target){fade-=1.f/(float)PL_RAMP;if(fade<target)fade=target;}
        if(fade==1.f){out_l[i]=yl;out_r[i]=yr;}
        else {out_l[i]+=(yl-out_l[i])*fade;out_r[i]+=(yr-out_r[i])*fade;}
    }
    if(state==PL_STOP && gain==0.f)pos=0;
    p->state=state;p->len=len;p->pos=pos;
    p->level=level;p->dub=dub;p->gain=gain;
    g->fade=fade;
    if(!g->mode && fade==0.f) {
        /* Left the looper: the ring now holds loop audio, not history. */
        pl_drop(p);
        g->wr=g->valid=g->countdown=0;
        g->fb_l=g->fb_r=0.f;
        for(unsigned j=0;j<4;j++)g->grains[j].len=0;
    }
}
#endif
