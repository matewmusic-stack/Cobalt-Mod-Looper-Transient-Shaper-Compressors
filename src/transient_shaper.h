/* Per-track transient shaper. A C translation of the Joebox 3.5.zi shaper
 * (BBEXTRA.BIN 0x0810E210), operation for operation, so it rounds the same:
 * fused multiply-adds where the original uses VFMA/VFNMS, VMAXNM/VMINNM
 * where it clamps, and the same exp2/log2 approximations. Tested against the
 * original in Unicorn (tests/test_transient.py).
 *
 * Detector: L+R summed, one-pole low cut, then three envelopes from the block
 * peak (4 samples): fast (hold then release), slow (follows fast up at the
 * Speed/Length rate, drops instantly) and peak (decays at the Length rate).
 * Gain in log2: Attack*(fast-slow) + Sustain*(peak-fast), clamped to
 * -4..+2.5 (-24..+15 dB), smoothed, mixed with dry and scaled by Output. */
#ifndef BB_TRANSIENT_SHAPER_H
#define BB_TRANSIENT_SHAPER_H
#include <stdint.h>
#define TS_MAGIC 0x54535431u
enum {TS_DIFFER=0,TS_PUNCH=1,TS_SMOOTH=2}; /* Joebox model names, same order */
/* Model, then Attack/Sustain -1..1, Speed/Length/Output/Mix 0..1 (Output
 * 0.5 is 0 dB; 0..1 spans -12..+12 dB). */
struct ts_params {uint32_t model;float attack,sustain,speed,length,output,mix;};
struct ts_state {float lp,fast,slow,peak,smooth,gain;int32_t hold;uint32_t magic,model;};
_Static_assert(sizeof(struct ts_state)==36,"transient state ABI");

#pragma GCC push_options
#pragma GCC optimize("fp-contract=off")
static inline float ts_fma(float a,float b,float c) {return __builtin_fmaf(a,b,c);}
static inline float ts_max(float a,float b) {return __builtin_fmaxf(a,b);}
static inline float ts_min(float a,float b) {return __builtin_fminf(a,b);}
static inline uint32_t ts_bits(float x) {union {float f;uint32_t u;} v={x};return v.u;}
static inline float ts_float(uint32_t u) {union {uint32_t u;float f;} v={u};return v.f;}
/* exp2 for |x|<=30: cubic on the fraction, integer part added to the
 * exponent. Negative x takes trunc(x-1), as the original does. */
static inline float ts_exp2_core(float x) {
    int i=x<0.f?(int)(x-1.f):(int)x;
    float f=x-(float)i;
    float p=ts_fma(f,ts_fma(f,ts_fma(f,.078625299f,.226196095f),.695178628f),1.f);
    return ts_float(ts_bits(p)+((uint32_t)i<<23));
}
static inline float ts_exp2(float x) {
    if(x< -30.f)return 9.31322575e-10f;
    if(x>30.f)return 1073741824.f;
    return ts_exp2_core(x);
}
static inline float ts_log2(float v) {
    uint32_t u=ts_bits(v);
    float m=ts_float((u&0x7fffffu)|0x3f800000u);
    float e=(float)(int)((u>>23)&0xffu)-128.f;
    return ts_fma(m,ts_fma(m,-.344848424f,2.02466583f),e)-.674877584f;
}

static __attribute__((unused)) void ts_process(struct ts_state *s,const struct ts_params *p,float *l,float *r,int n) {
    if(!s || !p || !l || n<=0)return;
    uint32_t model=p->model;if(model>2)model=TS_DIFFER;
    float floor=model==TS_SMOOTH?1.00000011e-06f:.00100000005f;
    if(s->magic!=TS_MAGIC){s->fast=s->slow=s->peak=floor;s->gain=1.f;}
    else if(s->model!=model)s->fast=s->slow=s->peak=floor;
    if(s->magic!=TS_MAGIC || s->model!=model) {
        s->model=model;s->lp=0.f;s->smooth=0.f;s->hold=0;s->magic=TS_MAGIC;
    }
    float out=ts_exp2((p->output-.5f)*4.f);
    if(p->attack==0.f && p->sustain==0.f) {
        if(out==1.f)return;
        for(int i=0;i<n;i++){l[i]*=out;if(r)r[i]*=out;}
        return;
    }
    float scale,smooth,release,lowcut,attack_scale;int32_t hold;
    if(model==TS_PUNCH){scale=.35f;smooth=.153513312f;release=.994470716f;hold=36;lowcut=.0384548306f;attack_scale=1.8f;}
    else if(model==TS_SMOOTH){scale=2.f;smooth=.0407547951f;release=.997923017f;hold=0;lowcut=.0155575275f;attack_scale=1.2f;}
    else {scale=1.f;smooth=.153513312f;release=.997923017f;hold=120;lowcut=.0155575275f;attack_scale=1.2f;}
    float tau=scale*(ts_exp2(p->speed*-4.30000019f)*.0299999993f);
    float len=-.000120224584f/(ts_exp2(p->length*5.30000019f)*.0500000007f);
    float t=-.000120224584f/tau,rise,decay;
    if(t< -30.f)rise=1.f;
    else if(t>30.f)rise=-1073741824.f;
    else rise=1.f-ts_exp2_core(t);
    if(len< -30.f)decay=0.f;
    else if(len>30.f)decay=1073741824.f;
    else decay=1.f-(1.f-ts_exp2_core(len));
    float half=model==TS_SMOOTH?.5f:1.f;
    float lp=s->lp,fast=s->fast,slow=s->slow,peak=s->peak,sm=s->smooth,gain=s->gain;
    int32_t count=s->hold;
    float target=gain;
    int blocks=n>3?((n-4)&~3)+4:0;
    float attack=attack_scale*p->attack,mix=p->mix;
    for(int b=0;b<blocks;b+=4) {
        float level=0.f;
        for(int i=b;i<b+4;i++) {
            float x=l[i]+(r?r[i]:l[i]);
            lp=ts_fma(x-lp,lowcut,lp);
            float hp=x-lp;
            if(model==TS_SMOOTH){fast=ts_fma(ts_fma(hp,hp,-fast),.00690704584f,fast);level=fast;}
            else level=ts_max(__builtin_fabsf(hp),level);
        }
        if(model==TS_SMOOTH)fast=ts_max(floor,level);
        else if(fast<level){fast=level;count=hold;}
        else if(count>0)count--;
        else fast=ts_max(fast*release,floor);
        slow=fast>slow?ts_fma(fast-slow,rise,slow):fast;
        peak=ts_max(peak*decay,fast);
        float lf=ts_log2(fast),lpk=ts_log2(peak),ls=ts_log2(slow);
        float g=((lpk-lf)*p->sustain);
        g=ts_fma(lf-ls,attack,g)*half;
        g=ts_min(ts_max(g,-4.f),2.5f);
        sm=ts_fma(g-sm,smooth,sm);
        float e;
        if(sm< -30.f)e=-1.f;
        else if(sm>30.f)e=1073741824.f;
        else e=ts_exp2_core(sm)-1.f;
        target=ts_fma(mix,e,1.f)*out;
        /* Linear ramp to the new gain across the 4-sample block. */
        float step=(target-gain)*.25f;
        for(int i=b;i<b+4;i++) {
            gain=gain+step;
            l[i]=ts_min(ts_max(l[i]*gain,-4.f),4.f);
            if(r)r[i]=ts_min(ts_max(gain*r[i],-4.f),4.f);
        }
        gain=target;
    }
    for(int i=blocks;i<n;i++){l[i]*=target;if(r)r[i]*=target;}
    s->gain=target;s->lp=lp;s->fast=fast;s->slow=slow;s->peak=peak;s->smooth=sm;s->hold=count;
}
#pragma GCC pop_options
#endif
