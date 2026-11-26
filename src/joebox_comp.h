/* Per-track compressor: a C translation of the Joebox 3.5.zi master
 * compressor (BBEXTRA.BIN 0x0810F3C8), operation for operation, so it rounds
 * the same (fused multiply-adds where the original uses VFMA/VFMS). Glue,
 * Punch, Opto, Squash and Limit are one algorithm driven by the mode table
 * below (copied bit for bit from 0x0810F7EC). Tested against the original
 * in Unicorn (tests/test_comp.py).
 *
 * The one change: no lookahead. Joebox's Limit delays the audio 72 samples
 * (1.5 ms) so gain reduction starts before a peak; the other modes have no
 * delay. Here every mode, Limit included, runs the original's zero-delay
 * path, which is exactly what Joebox computes with that length set to 0.
 *
 * Detector: stereo RMS (one-pole on (L^2+R^2)/2) or stereo peak, in dB.
 * Gain computer: threshold, ratio, soft knee. Envelope in dB: attack
 * one-pole, release with a slow/fast split. Makeup, optional dry mix, then a
 * hard clip at +-0.9661 (-0.3 dBFS). Limit (ratio 0): the threshold is input
 * drive into a fixed -0.3 dB ceiling. */
#ifndef BB_JOEBOX_COMP_H
#define BB_JOEBOX_COMP_H
#include <stdint.h>
#define JC_MAGIC 0x434f4d31u
enum {JC_OFF=0,JC_STOCK=1,JC_GLUE=2,JC_PUNCH=3,JC_OPTO=4,JC_SQUASH=5,JC_LIMIT=6};
struct jc_state {uint32_t magic,mode;float env,rms;};
_Static_assert(sizeof(struct jc_state)==16,"compressor state ABI");
/* thr_off dB, ratio (0 = limiter), knee dB, attack, release fast, release
 * slow, slow below dB, rms coefficient (0 = peak), input gain, makeup, mix. */
static const uint32_t jc_table[5][11]={
    {0xc1900000u,0x40000000u,0x40c00000u,0x3f7f779cu,0x3f7ff259u,0x3f7ffdb9u,0x40000000u,0x3f7f779cu,0x3f800000u,0x3fb4cccdu,0x3f800000u}, /* Glue */
    {0xc1a00000u,0x40800000u,0x40400000u,0x3f7fd281u,0x3f7feef0u,0x3f7feef0u,0x00000000u,0x00000000u,0x3f800000u,0x3fcade01u,0x3f800000u}, /* Punch */
    {0xc1b00000u,0x40400000u,0x41200000u,0x3f7f779cu,0x3f7fe940u,0x3f7fff17u,0x40400000u,0x3f7fbbc5u,0x3f800000u,0x3fcade01u,0x3f800000u}, /* Opto */
    {0xc20c0000u,0x41a00000u,0x00000000u,0x3f758d71u,0x3f7fe940u,0x3f7fe940u,0x00000000u,0x00000000u,0x3f800000u,0x407eca58u,0x3f000000u}, /* Squash */
    {0xbe99999au,0x00000000u,0x00000000u,0x3f758d71u,0x3f7fe940u,0x3f7fe940u,0x00000000u,0x00000000u,0x3fff65feu,0x3f800000u,0x3f800000u}, /* Limit */
};

#pragma GCC push_options
#pragma GCC optimize("fp-contract=off")
static inline float jc_f(uint32_t u) {union {uint32_t u;float f;} v={u};return v.f;}
static inline uint32_t jc_u(float f) {union {float f;uint32_t u;} v={f};return v.u;}
static inline float jc_fma(float a,float b,float c) {return __builtin_fmaf(a,b,c);}
/* exp2 for x <= 30: quadratic on the fraction; negative x floors. */
static inline float jc_exp2(float x) {
    int i=(int)x;if(x<0.f)i-=1;
    float f=x-(float)i;
    float p=jc_fma(f,jc_fma(f,.343499988f,.656499982f),1.f);
    return jc_f(jc_u(p)+((uint32_t)i<<23));
}
static inline float jc_log2(float v) {
    uint32_t u=jc_u(v);
    float e=(float)((int)((u>>23)&0xffu)-128);
    float m=jc_f((u&0x7fffffu)|0x3f800000u);
    return jc_fma(m,jc_fma(m,-.344848424f,2.02466583f),e)-.674877584f;
}
static __attribute__((unused)) void jc_process(struct jc_state *s,unsigned mode,float thresh_db,float *l,float *r,int n) {
    if(mode<JC_GLUE || mode>JC_LIMIT)return;
    if(s->magic!=JC_MAGIC || s->mode!=mode){s->env=0.f;s->rms=0.f;s->mode=mode;s->magic=JC_MAGIC;}
    if(n<=0)return;
    const uint32_t *t=jc_table[mode-JC_GLUE];
    float thr=jc_f(t[0]),ratio=jc_f(t[1]),knee=jc_f(t[2]),attack=jc_f(t[3]),fast=jc_f(t[4]),slow=jc_f(t[5]);
    float split=jc_f(t[6]),rmsc=jc_f(t[7]),in=jc_f(t[8]),makeup=jc_f(t[9]),mix=jc_f(t[10]);
    if(ratio>0.f)thr=thr+thresh_db;
    else {
        float x=-(thresh_db*.166099995f);
        in=in*(x< -30.f?0.f:jc_exp2(x>30.f?30.f:x));
    }
    float env=s->env,rms=s->rms;
    for(int i=0;i<n;i++) {
        float L=in*l[i],R=in*r[i],level;
        if(rmsc>0.f) {
            float p=jc_fma(L,L,R*R);
            rms=jc_fma(-p,.5f,rms);rms=rms*rmsc;rms=jc_fma(p,.5f,rms);
            level=jc_log2(rms+9.99999996e-13f)*3.01029992f;
        } else {
            float a=L>=0.f?L:-L,b=R>=0.f?R:-R;
            level=jc_log2((a>b?a:b)+9.99999972e-10f)*6.02059984f;
        }
        float over=level-thr;
        float k=ratio>0.f?1.f/ratio-1.f:-1.f;
        float gr;
        if(knee>0.f) {
            float t2=over+over;
            if(!(t2>-knee))gr=0.f;
            else if(!(knee>t2))gr=over>0.f?over*k:0.f;
            else {
                float o=jc_fma(knee,.5f,over),q=o*k;
                q=q*o;gr=q/(knee+knee);
            }
        } else gr=over>0.f?over*k:0.f;
        float d=env-gr;
        if(gr<env)gr=jc_fma(d,attack,gr);
        else gr=jc_fma(d,split>gr-env?slow:fast,gr);
        env=gr;
        float x=env*.166099995f;
        float g=makeup*(x< -30.f?0.f:jc_exp2(x>30.f?30.f:x));
        float wl=g*L,wr=g*R;
        if(mix<1.f) {
            float dry=1.f-mix;
            wl=jc_fma(mix,wl,(L*dry)/in);
            wr=jc_fma(mix,wr,(R*dry)/in);
        }
        l[i]=wl>.966099977f?.966099977f:(-.966099977f>wl?-.966099977f:wl);
        r[i]=wr>.966099977f?.966099977f:(-.966099977f>wr?-.966099977f:wr);
    }
    s->env=env;s->rms=rms;
}
#pragma GCC pop_options
#endif
