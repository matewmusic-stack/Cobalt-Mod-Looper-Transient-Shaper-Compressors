/* Host checks for src/phrase_looper.h. Build and run:
 *   cc -std=c11 -O1 -Wall -Wextra -Werror -fsanitize=address,undefined \
 *      -DPHRASE_LOOPER -Isrc tests/looper_host.c -o build/looper_host && build/looper_host
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
static uint32_t sample;            /* running input sample index */

/* Input: a ramp that encodes the sample index, so loop playback can be
 * checked against exactly what was recorded. */
static float input_at(uint32_t i) {return (float)(i%1000u)*.001f;}

static unsigned block(uint32_t bpm_x10,uint32_t playing) {
    for(unsigned i=0;i<N;i++){in_l[i]=input_at(sample+i);in_r[i]=-in_l[i];out_l[i]=out_r[i]=9.f;}
    unsigned ack=pl_render(&p,&g,bpm_x10,playing,in_l,in_r,out_l,out_r,N);
    sample+=N;
    return ack;
}
static void run(uint32_t frames,uint32_t bpm_x10,uint32_t playing) {
    for(uint32_t f=0;f<frames;f+=N)block(bpm_x10,playing);
}
static void setup(uint32_t cap) {
    float *buffer=calloc((size_t)cap*2u,sizeof(float));
    g_reset(&g,0,buffer);
    pl_reset(&p,0,cap);
    g.mode=1;g.position=1000;g.density=2;g.jitter=0;g.freeze=0;g.reverse=0;g.size=0;
    sample=0;
    block(1200,0); /* first observation latches Play/Clear */
}

int main(void) {
    /* Tempo parsing and lengths. */
    CHECK(pl_bpm_x10(120)==1200,"plain BPM");
    CHECK(pl_bpm_x10(1200)==1200,"tenths");
    CHECK(pl_bpm_x10(12000)==1200,"hundredths");
    CHECK(pl_bpm_x10(0)==PL_DEFAULT_BPM_X10,"invalid -> default");
    CHECK(pl_length(1200,2,PL_CAP_MAX)==192000u,"2 bars @120 = 4 s");
    CHECK(pl_length(1200,1,PL_CAP_MAX)==96000u,"1 bar @120 = 2 s");
    CHECK(pl_length(600,2,PL_CAP_MAX)==384000u,"2 bars @60 fills the cap");
    CHECK(pl_length(800,2,PL_CAP_MAX)==288000u,"2 bars @80");
    CHECK(pl_length(1200,2,G_CAP)==96000u,"fallback buffer drops to 1 bar");
    CHECK(pl_length(600,1,G_CAP)==G_CAP,"fallback buffer clamps to its length");

    /* Load with Play already on: no recording. */
    {
        float *buffer=calloc((size_t)PL_CAP_MAX*2u,sizeof(float));
        g_reset(&g,0,buffer);pl_reset(&p,0,PL_CAP_MAX);
        g.mode=1;g.position=1000;g.density=1;g.reverse=1;g.size=1;
        block(1200,0);
        CHECK(p.state==PL_EMPTY,"Play on at load does not record (state %u)",p.state);
        free(buffer);
    }

    /* Free capture, 1 bar at 120 BPM, then playback repeats the recording. */
    setup(PL_CAP_MAX);
    g.density=1;g.reverse=1;
    uint32_t start=sample;
    block(1200,0);
    CHECK(p.state==PL_REC,"Play starts recording at once with Sync off (state %u)",p.state);
    CHECK(p.len==96000u,"loop length 96000 (got %u)",p.len);
    run(96000u-N,1200,0);
    CHECK(p.state==PL_PLAY,"capture turns into playback after one bar (state %u)",p.state);
    /* Middle of the loop (away from the declick ramps) matches the input. */
    run(48000u,1200,0);                 /* now near loop position 48000 */
    block(1200,0);
    uint32_t loop_pos=(sample-N-start)%96000u;
    float want=input_at(start+loop_pos);
    CHECK(fabsf(out_l[0]-want)<1e-6f && fabsf(out_r[0]+want)<1e-6f,
          "playback matches recording at %u: %f vs %f",loop_pos,out_l[0],want);

    /* Dry/Wet 0 passes the input. */
    g.position=0;run(N*40u,1200,0);block(1200,0);
    CHECK(fabsf(out_l[N-1]-in_l[N-1])<1e-5f,"dry only passes input");
    g.position=1000;run(N*40u,1200,0);

    /* Stop fades to silence, Play resumes from the loop start. */
    g.reverse=0;run(N*20u,1200,0);block(1200,0);
    CHECK(p.state==PL_STOP && out_l[N-1]==0.f,"Stop is silent (state %u, %f)",p.state,out_l[N-1]);
    g.reverse=1;block(1200,0);
    CHECK(p.state==PL_PLAY && p.len==96000u,"Play resumes the kept loop");

    /* Clear empties the loop and acknowledges Clear and Play. */
    g.size=1;unsigned ack=block(1200,0);
    CHECK(p.state==PL_EMPTY && p.len==0,"Clear empties");
    CHECK(ack==(PL_ACK_CLEAR|PL_ACK_PLAY_OFF),"Clear acks Clear and Play (got %u)",ack);
    block(1200,0);
    CHECK(p.state==PL_EMPTY,"Play still on after Clear does not start a new take");
    g.size=0;g.reverse=0;block(1200,0);
    CHECK(p.state==PL_EMPTY,"stays empty after the UI resets the toggles");

    /* Sync on with the sequencer stopped: armed until it starts. */
    g.freeze=1;g.density=2;g.reverse=1;
    block(1200,0);
    CHECK(p.state==PL_ARMED,"Sync arms while stopped (state %u)",p.state);
    run(N*100u,1200,0);
    CHECK(p.state==PL_ARMED,"stays armed");
    block(1500,1);
    CHECK(p.state==PL_REC && p.len==153600u,"starts on sequencer start, 2 bars @150 (len %u)",p.len);
    /* Sync on while already playing: starts at once. */
    g.size=1;block(1200,1);g.size=0;g.reverse=0;block(1200,1);
    g.reverse=1;block(1200,1);
    CHECK(p.state==PL_REC,"Sync with the sequencer running starts at once (state %u)",p.state);

    /* Stop during capture keeps a usable partial loop. */
    run(10000u,1200,1);
    g.reverse=0;block(1200,1);
    CHECK(p.state==PL_STOP && p.len>=10000u && p.len<10100u,"partial capture kept (len %u)",p.len);

    /* Overdub layers input into the loop, bounded. */
    g.reverse=1;g.jitter=1000;block(1200,1);
    CHECK(p.state==PL_PLAY,"play after partial");
    run(p.len*30u,1200,1);
    float peak=0.f;
    for(uint32_t i=0;i<p.len*2u;i++){float a=fabsf(g.buffer[i]);if(a>peak)peak=a;}
    CHECK(peak<=2.f,"overdub stays within +-2 (peak %f)",peak);

    /* Leaving the mode fades out, then hands the ring back empty. */
    g.mode=0;run(N*10u,1200,1);
    CHECK(g.fade==0.f && p.state==PL_EMPTY && g.valid==0 && g.wr==0,"mode exit resets (fade %f state %u)",g.fade,p.state);

    printf(failures?"%d check(s) failed\n":"All looper checks passed\n",failures);
    return failures!=0;
}
