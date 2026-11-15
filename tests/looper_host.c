/* Host checks for src/phrase_looper.h. Build and run:
 *   cc -std=c11 -O1 -Wall -Wextra -Werror -fsanitize=address,undefined \
 *      -DPHRASE_LOOPER -Isrc tests/looper_host.c -o build/looper_host -lm && build/looper_host
 */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "phrase_looper.h"

static int failures;
#define CHECK(c,...) do{if(!(c)){failures++;printf("FAIL %s:%d: ",__FILE__,__LINE__);printf(__VA_ARGS__);printf("\n");}}while(0)

#define N 32u
static struct granular g;
static struct phrase_looper p;
static float in_l[N],in_r[N],out_l[N],out_r[N];
static uint32_t sample;

static float input_at(uint32_t i) {return (float)(i%1000u)*.001f;}
static void block(uint32_t bpm_x10,uint32_t playing) {
    for(unsigned i=0;i<N;i++){in_l[i]=input_at(sample+i);in_r[i]=-in_l[i];out_l[i]=out_r[i]=9.f;}
    pl_render(&p,&g,bpm_x10,playing,in_l,in_r,out_l,out_r,N);
    sample+=N;
}
static void run(uint32_t frames,uint32_t bpm_x10,uint32_t playing) {for(uint32_t f=0;f<frames;f+=N)block(bpm_x10,playing);}
/* A pedal press as the UI sends it: 0 -> 1, then the M4 sets it back to 0. */
static void press(unsigned id) {pl_event(&p,id,1);pl_event(&p,id,0);}
#define B16 ((int16_t *)g.buffer)
static void setup(uint32_t cap) {
    float *buffer=calloc((size_t)cap*PL_FRAME/sizeof(float)+1u,sizeof(float));
    g_reset(&g,0,buffer);pl_reset(&p,0,cap);
    g.mode=1;g.density=2;g.freeze=0;
    pl_event(&p,LP_REC,0);pl_event(&p,LP_STOP,0);pl_event(&p,LP_CLEAR,0);
    sample=0;run(N*10u,1200,0);   /* let the 5 ms mode fade-in finish */
}

int main(void) {
    CHECK(pl_bpm_x10(120)==1200 && pl_bpm_x10(1200)==1200 && pl_bpm_x10(12000)==1200 && pl_bpm_x10(0)==PL_DEFAULT_BPM_X10,"tempo parsing");
    uint32_t bars=0;
    CHECK(pl_length(1200,2,PL_CAP_MAX,&bars)==192000u && bars==2,"2 bars @120");
    CHECK(pl_length(600,2,PL_CAP_MAX,&bars)==384000u && bars==2,"2 bars @60 fill the cap");
    CHECK(pl_length(400,2,PL_CAP_MAX,&bars)==288000u && bars==1,"too long: 1 bar");
    CHECK(pl_length(1200,2,G_BYTES/PL_FRAME,&bars)==192000u && bars==2,"tested 768 KB buffer holds 2 bars at 120 BPM in 16-bit");
    CHECK(pl_length(1000,2,G_BYTES/PL_FRAME,&bars)==115200u && bars==1,"... and 1 bar at 100 BPM");
    CHECK(pl_q(1.f)==16384 && pl_q(-2.5f)==-32767 && pl_q(2.5f)==32767 && pl_q(0.f/0.f)==-32767 && pl_f(pl_q(.123f))-.123f<1.f/PL_SCALE,"16-bit conversion: scale, saturation, rounding");
    CHECK(g.position==0,"static zero before setup");

    /* Defaults match the UI. */
    { struct granular d;g_reset(&d,0,0);CHECK(d.position==1000 && d.density==2 && d.jitter==1000 && d.size==0,"looper defaults"); }

    /* Values at load only latch: a saved REC=1 is not a press. */
    setup(PL_CAP_MAX);
    { struct phrase_looper q;pl_reset(&q,0,PL_CAP_MAX);pl_event(&q,LP_REC,1);CHECK(q.presses==0,"first value latches"); }
    /* A change back to 0 is not a press. */
    pl_event(&p,LP_REC,1);p.presses=0;pl_event(&p,LP_REC,0);CHECK(p.presses==0,"1->0 is not a press");

    /* REC: record 1 bar at 120 BPM, auto close into PLAY; output = loop only. */
    g.density=1;uint32_t start=sample;
    press(LP_REC);block(1200,0);
    CHECK(p.state==PL_REC && p.len==96000u && p.bars==1,"REC records 1 bar (state %u len %u)",p.state,p.len);
    CHECK(out_l[0]==0.f && out_l[N-1]==0.f,"FX1 return is silent while recording (source heard in its channel)");
    run(96000u-N,1200,0);
    CHECK(p.state==PL_PLAY && p.pos==0,"auto play after one bar");
    run(48000u,1200,0);block(1200,0);
    { uint32_t lp=(sample-N-start)%96000u;float want=input_at(start+lp);
      CHECK(out_l[0]==pl_f(pl_q(want)) && out_r[0]==pl_f(pl_q(-want)),"playback is the take, within one 16-bit step"); }

    /* Level scales the loop only. */
    g.position=500;block(1200,0);block(1200,0);
    { uint32_t lp=(sample-N-start)%96000u;CHECK(fabsf(out_l[0]-.5f*pl_f(pl_q(input_at(start+lp))))<1e-6f,"Level 50%% halves the loop"); }
    g.position=1000;block(1200,0);

    /* REC while playing: DUB adds input; REC again: back to PLAY. */
    int16_t before=B16[2u*50000u];
    press(LP_REC);block(1200,0);CHECK(p.state==PL_DUB,"REC while playing starts overdub");
    run(96000u,1200,0);
    CHECK(B16[2u*50000u]!=before,"overdub changed the loop");
    press(LP_REC);block(1200,0);CHECK(p.state==PL_PLAY,"REC again ends overdub");
    { int m=0;for(uint32_t i=0;i<96000u*2u;i++){int a=abs(B16[i]);if(a>m)m=a;}CHECK(m<=32767 && m>16384,"overdub saturates within +/-2.0 (peak %d)",m); }

    /* STOP / STOP: stop, then play from the start. REC when stopped plays too. */
    press(LP_STOP);block(1200,0);CHECK(p.state==PL_STOP,"STOP stops");
    run(N*20u,1200,0);CHECK(out_l[N-1]==0.f && p.pos==0,"stopped is silent, rewound");
    press(LP_STOP);block(1200,0);CHECK(p.state==PL_PLAY && p.pos==N,"STOP again plays from the start");
    press(LP_STOP);block(1200,0);press(LP_REC);block(1200,0);CHECK(p.state==PL_PLAY,"REC when stopped plays");

    /* CLEAR. */
    press(LP_CLEAR);block(1200,0);CHECK(p.state==PL_EMPTY && p.len==0,"CLEAR empties");
    run(N*10u,1200,0);CHECK(out_l[N-1]==0.f,"cleared is silent");

    /* REC during a take closes the loop early; STOP during a take keeps it stopped. */
    press(LP_REC);run(N*400u,1200,0);press(LP_REC);block(1200,0);
    CHECK(p.state==PL_PLAY && p.len==400u*N,"REC during a take closes the loop at %u",p.len);
    press(LP_CLEAR);block(1200,0);
    press(LP_REC);run(N*20u,1200,0);press(LP_REC);block(1200,0);
    CHECK(p.state==PL_EMPTY,"too-short take is dropped");
    press(LP_REC);run(N*400u,1200,0);press(LP_STOP);block(1200,0);
    CHECK(p.state==PL_STOP && p.len==400u*N,"STOP during a take keeps it stopped");
    press(LP_CLEAR);block(1200,0);

    /* Sync: armed while stopped, REC again cancels; starts on sequencer start. */
    g.freeze=1;g.density=2;
    press(LP_REC);block(1200,0);CHECK(p.state==PL_ARMED,"Sync arms while stopped");
    press(LP_REC);block(1200,0);CHECK(p.state==PL_EMPTY,"REC while armed cancels");
    press(LP_REC);block(1200,0);run(N*50u,1200,0);CHECK(p.state==PL_ARMED,"stays armed");
    block(1500,1);CHECK(p.state==PL_REC && p.len==153600u && p.bars==2,"starts on sequencer start: 2 bars @150");
    press(LP_STOP);block(1200,1);press(LP_CLEAR);block(1200,1);
    press(LP_REC);block(1200,1);CHECK(p.state==PL_REC,"Sync with the sequencer running starts at once");

    /* STOP and REC pressed in the same block: STOP wins. */
    press(LP_CLEAR);block(1200,1);press(LP_REC);block(1200,1);run(N*500u,1200,1);
    press(LP_REC);press(LP_STOP);block(1200,1);CHECK(p.state==PL_STOP,"simultaneous REC+STOP stops (state %u)",p.state);

    /* Leaving the mode fades out and drops the loop and the button history. */
    g.mode=0;run(N*10u,1200,1);
    CHECK(g.fade==0.f && p.state==PL_EMPTY && g.valid==0 && p.last[0]==-1,"mode exit resets");

    printf(failures?"%d check(s) failed\n":"All looper checks passed\n",failures);
    return failures!=0;
}
