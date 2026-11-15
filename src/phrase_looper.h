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
 * the buffer drops to 1 bar, then to the buffer length.
 *
 * Loop audio is stored as 16-bit stereo, scaled so +/-2.0 (overdub headroom)
 * fills the range: 4 bytes per frame. The hardware-tested 768,000-byte
 * Granular buffer therefore holds 192,000 frames (4 s: 2 bars at 120 BPM).
 * The other FX1 modes keep using the same buffer as their float ring. */
#ifndef BLUEBOX_PHRASE_LOOPER_H
#define BLUEBOX_PHRASE_LOOPER_H
#include <stdint.h>
#include "granular.h"

#define LP_STOP 0x1ba             /* new FX1 parameter: STOP button */
#define LP_REC G_REVERSE
#define LP_CLEAR G_SIZE
#define LP_STRETCH 0x1bb          /* experiment: 0 off, 1 varispeed, 2 keep pitch */
#define PL_MAGIC 0x504c4f32u
#define PL_TEMPO_MAGIC 0x504c5431u
#define PL_FS 48000u
#define PL_RAMP 240u              /* 5 ms declick at 48 kHz */
#define PL_CAP_MAX 384000u        /* 2 bars at 60 BPM */
#define PL_FRAME 4u               /* bytes per stereo 16-bit frame */
#define PL_BYTES (PL_CAP_MAX*PL_FRAME)
#define PL_SCALE 16384.f          /* +/-2.0 <-> +/-32767 */
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
    uint32_t free_kb;             /* arena free before the FX1 buffer (KiB), for TOOLS */
    uint32_t stretch;             /* 0 off, 1 varispeed, 2 keep pitch (experiment) */
};

/* Tempo-follow state, kept in SDRAM just after the loop audio (PLX_BYTES):
 * backup SRAM has no room left. Rebuilt whenever its magic is wrong. */
#define PLX_MAGIC 0x504c5853u
#define PLX_BYTES 64u
#define PLX_G 2048u               /* keep pitch: grain length, 42.7 ms */
#define PLX_H (PLX_G/2u)          /* hop: two Hann grains overlap and sum to 1 */
#define PLX_D 240                 /* WSOLA search range, +/-5 ms */
#define PLX_L 256u                /* WSOLA match length */
struct pl_stretch {
    uint32_t magic;
    float src;                    /* fractional read position in the loop */
    float rate;                   /* playback rate now: current BPM / recorded BPM */
    uint32_t start[2],age[2];     /* keep pitch: grain source start and age */
    uint32_t hop;                 /* samples until the next grain */
    uint32_t next;                /* grain slot to start next */
    uint32_t last;                /* source start of the newest grain */
    /* WSOLA search for the next grain, spread over the blocks of one hop */
    uint32_t a_next,cont;         /* predicted analysis position, continuation */
    int32_t idx,best,cbest;       /* candidate index, best offset, coarse best */
    float best_v;
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
    if(id==LP_STRETCH){p->stretch=(uint32_t)g_clampi(value,0,2);return;}
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

static inline int16_t pl_q(float x) {
    float s=x*PL_SCALE;
    s=s>=0.f?s+.5f:s-.5f;                    /* round half away from zero */
    if(!(s>-32767.f))s=-32767.f;             /* also maps NaN to the floor */
    if(s>32767.f)s=32767.f;
    return (int16_t)s;
}
static inline float pl_f(int16_t q) {return (float)q*(1.f/PL_SCALE);}
/* In-place declick at both ends of a freshly recorded loop. */
static inline void pl_seal(int16_t *buffer,uint32_t len) {
    uint32_t r=PL_RAMP;
    if(r>len/4u)r=len/4u;
    for(uint32_t i=0;i<r;i++) {
        float g=(float)i*(1.f/(float)PL_RAMP);
        int16_t *a=buffer+2u*i,*b=buffer+2u*(len-1u-i);
        a[0]=pl_q(pl_f(a[0])*g);a[1]=pl_q(pl_f(a[1])*g);
        b[0]=pl_q(pl_f(b[0])*g);b[1]=pl_q(pl_f(b[1])*g);
    }
}

static inline void pl_start_capture(struct phrase_looper *p,const struct granular *g,uint32_t bpm_x10) {
    p->bpm_x10=bpm_x10;
    p->len=pl_length(bpm_x10,g->density,p->cap,&p->bars);
    p->pos=0;
    p->state=p->len>=PL_RAMP*4u?PL_REC:PL_EMPTY;
}
/* Close a take early: keep it as the loop if it is long enough. */
static inline void pl_close(struct phrase_looper *p,int16_t *buffer,uint32_t next) {
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
        case PL_REC:pl_close(p,(int16_t *)g->buffer,PL_STOP);break;
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
        case PL_REC:pl_close(p,(int16_t *)g->buffer,PL_PLAY);break;
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
/* ---- tempo follow (experiment) ---- */
static inline float pl_cos(float x) {        /* cos x, |x| <= pi/2, error < 3e-5 */
    float x2=x*x;
    return 1.f-x2*(.5f-x2*(1.f/24.f-x2*(1.f/720.f-x2*(1.f/40320.f))));
}
static inline float pl_hann(uint32_t age) {  /* 0.5 - 0.5 cos(2 pi age / G) */
    float t=(float)age*(1.f/(float)PLX_G);   /* 0..1 */
    float x=t*6.2831853f;                    /* 0..2pi */
    float c;
    if(x<1.5707963f)c=pl_cos(x);
    else if(x<4.7123890f)c=-pl_cos(x-3.1415927f);
    else c=pl_cos(x-6.2831853f);
    return .5f-.5f*c;
}
static inline uint32_t pl_wrap(int32_t i,uint32_t len) {
    while(i<0)i+=(int32_t)len;
    while((uint32_t)i>=len)i-=(int32_t)len;
    return (uint32_t)i;
}
static inline float pl_mono(const int16_t *b,uint32_t i) {return (float)b[2u*i]+(float)b[2u*i+1u];}
/* WSOLA: start a grain near src, at the offset whose start best matches the
 * natural continuation of the previous grain, so overlapping grains add in
 * phase. Normalized cross-correlation of the L+R sum over PLX_L frames.
 * Coarse search every 16 frames over +/-PLX_D, then every 2 frames around
 * the best: about 1,400 multiply-adds per grain (one grain every 21 ms). */
static inline float pl_match(const int16_t *b,uint32_t len,uint32_t ia,uint32_t ic) {
    float xy=0.f,yy=1.f;
    for(uint32_t k=0;k<PLX_L;k+=8u) {
        float y=pl_mono(b,ia),x=pl_mono(b,ic);
        xy+=x*y;yy+=y*y;
        ia+=8u;if(ia>=len)ia-=len;
        ic+=8u;if(ic>=len)ic-=len;
    }
    return (xy<0.f?-xy:xy)*xy/yy;               /* sign(xy) * xy^2 / yy, no sqrt */
}
/* Candidates: 31 coarse offsets every 16 frames over +/-PLX_D, then 15
 * fine ones every 2 frames around the coarse best. pl_search() tries a few
 * per block, so the search never loads a single block. */
#define PLX_COARSE 31
#define PLX_CAND (PLX_COARSE+15)
static inline void pl_search_begin(struct pl_stretch *x,uint32_t len,uint32_t start) {
    x->a_next=pl_wrap((int32_t)(x->src+x->rate*(float)PLX_H),len);
    x->cont=pl_wrap((int32_t)start+(int32_t)PLX_H,len);
    x->idx=0;x->best=0;x->cbest=0;x->best_v=-1e30f;
}
static inline void pl_search(struct pl_stretch *x,const int16_t *b,uint32_t len,int steps) {
    while(steps-- > 0 && x->idx<PLX_CAND) {
        int32_t d;
        if(x->idx<PLX_COARSE)d=-PLX_D+16*x->idx;
        else {
            if(x->idx==PLX_COARSE)x->cbest=x->best;
            d=x->cbest-14+2*(x->idx-PLX_COARSE);
            if(d<-PLX_D)d=-PLX_D;
            if(d>PLX_D)d=PLX_D;
        }
        float v=pl_match(b,len,pl_wrap((int32_t)x->a_next+d,len),x->cont);
        if(v>x->best_v){x->best_v=v;x->best=d;}
        x->idx++;
    }
}
static inline void pl_x_reset(struct pl_stretch *x,uint32_t pos) {
    x->src=(float)pos;x->age[0]=x->age[1]=PLX_G;x->hop=0;x->next=0;x->last=pos;
    x->idx=0;x->best=0;x->cbest=0;x->best_v=-1e30f;x->a_next=x->cont=pos;
}
/* One frame of a stretched loop at x->src, advancing by x->rate. */
static inline void pl_x_frame(struct phrase_looper *p,struct pl_stretch *x,int16_t *b,uint32_t len,float *l,float *r) {
    if(p->stretch==1u || len<PLX_G*4u) {
        /* Varispeed: 4-point cubic Hermite interpolation. */
        uint32_t i1=(uint32_t)x->src;if(i1>=len)i1=0;
        float f=x->src-(float)i1;
        uint32_t i0=i1?i1-1u:len-1u,i2=i1+1u<len?i1+1u:0u,i3=i2+1u<len?i2+1u:0u;
        for(unsigned c=0;c<2;c++) {
            float y0=pl_f(b[2u*i0+c]),y1=pl_f(b[2u*i1+c]),y2=pl_f(b[2u*i2+c]),y3=pl_f(b[2u*i3+c]);
            float c1=.5f*(y2-y0),c2=y0-2.5f*y1+2.f*y2-.5f*y3,c3=.5f*(y3-y0)+1.5f*(y1-y2);
            float y=((c3*f+c2)*f+c1)*f+y1;
            if(c)*r=y;else *l=y;
        }
    } else {
        /* Keep pitch: two Hann grains at speed 1, one started every PLX_H. */
        if(!x->hop) {
            uint32_t a=(uint32_t)x->src;if(a>=len)a=0;
            /* Offset from the search over the last hop (none for the first grain). */
            uint32_t s=x->age[x->next^1u]<PLX_G && x->idx>0?pl_wrap((int32_t)a+x->best,len):a;
            x->start[x->next]=s;x->age[x->next]=0;x->last=s;x->next^=1u;x->hop=PLX_H;
            pl_search_begin(x,len,s);
        }
        x->hop--;
        float sl=0.f,sr=0.f;
        for(unsigned k=0;k<2;k++)if(x->age[k]<PLX_G) {
            uint32_t i=x->start[k]+x->age[k];while(i>=len)i-=len;
            float w=pl_hann(x->age[k]);
            sl+=w*pl_f(b[2u*i]);sr+=w*pl_f(b[2u*i+1u]);
            x->age[k]++;
        }
        *l=sl;*r=sr;
    }
    x->src+=x->rate;
    if(x->src>=(float)len)x->src-=(float)len;
}

static inline void pl_render(struct phrase_looper *p,struct granular *g,uint32_t bpm_x10,uint32_t playing,
                             const float *in_l,const float *in_r,float *out_l,float *out_r,unsigned n) {
    int16_t *buffer=(int16_t *)g->buffer;
    if(!buffer)return;
    pl_controls(p,g,bpm_x10,playing);
    struct pl_stretch *x=(struct pl_stretch *)(void *)((uint8_t *)g->buffer+p->cap*PL_FRAME);
    if(x->magic!=PLX_MAGIC){pl_x_reset(x,p->pos);x->rate=1.f;x->magic=PLX_MAGIC;}
    unsigned stretch=p->stretch && p->len;
    if(stretch && (uint32_t)x->src!=p->pos)pl_x_reset(x,p->pos);  /* controls moved the loop */
    float rate_t=1.f;
    if(stretch && p->bpm_x10) {
        rate_t=(float)bpm_x10/(float)p->bpm_x10;
        if(rate_t<.5f)rate_t=.5f;
        if(rate_t>2.f)rate_t=2.f;
    }
    float drate=n?(rate_t-x->rate)/(float)n:0.f;
    if(stretch && p->stretch==2u && p->len>=PLX_G*4u)pl_search(x,buffer,p->len,2);
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
            buffer[2u*pos]=pl_q(in_l[i]);
            buffer[2u*pos+1u]=pl_q(in_r[i]);
            if(++pos>=len) {
                pl_seal(buffer,len);
                pos=0;state=PL_PLAY;p->seq++;
                pl_x_reset(x,0);
            }
        } else if(stretch && (state==PL_PLAY || state==PL_DUB || state==PL_STOP)) {
            x->rate+=drate;
            uint32_t w=(uint32_t)x->src;if(w>=len)w=0;
            pl_x_frame(p,x,buffer,len,&l,&r);
            if(state==PL_DUB && dub>0.f) {          /* layer at the read position */
                int16_t *s=buffer+2u*w;
                s[0]=pl_q(pl_f(s[0])+in_l[i]*dub);
                s[1]=pl_q(pl_f(s[1])+in_r[i]*dub);
            }
            pos=(uint32_t)x->src;if(pos>=len)pos=0;
        } else if((state==PL_PLAY || state==PL_DUB || state==PL_STOP) && len) {
            int16_t *s=buffer+2u*pos;
            l=pl_f(s[0]);r=pl_f(s[1]);
            if(state==PL_DUB && dub>0.f) {
                s[0]=pl_q(l+in_l[i]*dub);       /* pl_q saturates at +/-2.0 */
                s[1]=pl_q(r+in_r[i]*dub);
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
    if(state==PL_STOP && gain==0.f){pos=0;pl_x_reset(x,0);}
    if(!stretch || state==PL_REC)x->rate=rate_t;  /* follow at once when not stretching */
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
