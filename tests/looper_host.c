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
/* Simulated sequencer: song position (960 ticks/beat) moves while playing. */
static struct pl_song song={1,0};
static double song_t;
static uint32_t song_x10;   /* when set, the sequencer's real tempo (x10), else the looper's */
static void block(uint32_t bpm_x10,uint32_t playing) {
    for(unsigned i=0;i<N;i++){in_l[i]=input_at(sample+i);in_r[i]=-in_l[i];out_l[i]=out_r[i]=9.f;}
    song.ticks=(int32_t)song_t;
    pl_render(&p,&g,bpm_x10*10u,playing,&song,in_l,in_r,out_l,out_r,N);   /* the looper takes hundredths */
    if(playing)song_t+=N*(double)(song_x10?song_x10:bpm_x10)*10.0/300000.0;
    sample+=N;
}
static void run(uint32_t frames,uint32_t bpm_x10,uint32_t playing) {for(uint32_t f=0;f<frames;f+=N)block(bpm_x10,playing);}
/* A pedal press as the UI sends it: 0 -> 1, then the M4 sets it back to 0. */
static void press(unsigned id) {pl_event(&p,id,1);pl_event(&p,id,0);}
#define B16 ((int16_t *)g.buffer)
static void setup(uint32_t cap) {
    /* loop audio, then the tempo-follow state (PLX_BYTES), as the firmware allocates */
    float *buffer=calloc(((size_t)cap*PL_FRAME+PLT_BYTES)/sizeof(float),sizeof(float));
    g_reset(&g,0,buffer);pl_reset(&p,0,cap);
    g.mode=1;g.density=2;g.freeze=0;
    pl_event(&p,LP_REC,0);pl_event(&p,LP_STOP,0);pl_event(&p,LP_CLEAR,0);
    sample=0;run(N*10u,1200,0);   /* let the 5 ms mode fade-in finish */
}

int main(void) {
    CHECK(pl_bpm_x100(120)==12000 && pl_bpm_x100(1200)==12000 && pl_bpm_x100(12000)==12000 && pl_bpm_x100(0)==PL_DEFAULT_BPM_X100,"tempo parsing");
    CHECK(pl_tempo_x100(120,0)==12000 && pl_tempo_x100(120,9873)==9873 && pl_tempo_x100(120,1999)==12000 && pl_tempo_x100(120,30001)==12000,"MIDI clock tempo wins over the project BPM when valid");
    CHECK(pl_length(9873,1,PL_CAP_MAX,0)==1152000000u/9873u,"loop length from a fractional clock tempo (98.73 BPM)");
    uint32_t bars=0;
    CHECK(pl_length(12000,2,PL_CAP_MAX,&bars)==192000u && bars==2,"2 bars @120");
    CHECK(pl_length(6000,2,PL_CAP_MAX,&bars)==384000u && bars==2,"2 bars @60 fill the cap");
    CHECK(pl_length(4000,2,PL_CAP_MAX,&bars)==288000u && bars==1,"too long: 1 bar");
    CHECK(pl_length(12000,2,G_BYTES/PL_FRAME,&bars)==192000u && bars==2,"tested 768 KB buffer holds 2 bars at 120 BPM in 16-bit");
    CHECK(pl_length(10000,2,G_BYTES/PL_FRAME,&bars)==115200u && bars==1,"... and 1 bar at 100 BPM");
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
    { uint32_t k=0;while(p.state==PL_ARMED && k<8u){block(1500,1);k++;}
      CHECK(p.state==PL_REC && p.bars==2 && k<=2u,"starts on sequencer start, on its bar line, within 2 blocks: 2 bars @150 (%u)",k); }
    press(LP_STOP);block(1200,1);press(LP_CLEAR);block(1200,1);
    press(LP_REC);block(1200,1);CHECK(p.state==PL_ARMED,"with the sequencer running, REC waits for the next bar line");
    { struct phrase_looper keep=p;
      g.freeze=0;uint32_t k=0;while(p.state==PL_ARMED && k<200u){block(1200,0);k++;}
      CHECK(p.state==PL_REC && k<=PLS_STILL+2u,"sequencer stops while waiting, Sync off: records at once (%u blocks)",k);
      p=keep;g.freeze=1;song_t+=0.0; }
    { uint32_t k=0;while(p.state==PL_ARMED && k<4000u){block(1200,1);k++;}
      CHECK(p.state==PL_REC,"... and starts on it"); }

    /* STOP and REC pressed in the same block: STOP wins. */
    press(LP_CLEAR);block(1200,1);press(LP_REC);
    { uint32_t k=0;while(p.state!=PL_REC && k<4000u){block(1200,1);k++;} }
    run(N*500u,1200,1);
    press(LP_REC);press(LP_STOP);block(1200,1);CHECK(p.state==PL_STOP,"simultaneous REC+STOP stops (state %u)",p.state);

    /* Stretch: 1 bar at 120 BPM played at 128 BPM. Off keeps 96000 frames per
     * pass; Vari and Keep both advance the read position at 128/120. */
    for(unsigned mode=0;mode<3;mode++) {
        press(LP_CLEAR);g.freeze=0;g.density=1;
        run(N*(PLS_STILL+2u),1200,0);          /* the sequencer stop registers first */
        pl_event(&p,LP_STRETCH,(int)mode);
        press(LP_REC);run(96000u,1200,0);
        CHECK(p.state==PL_PLAY && p.len==96000u && p.stretch==mode,"stretch %u: 1-bar take",mode);
        uint32_t frames=0,wraps=0,last=p.pos;
        while(wraps<3u && frames<2000000u){block(1280,0);frames+=N;if(p.pos<last)wraps++;last=p.pos;}
        CHECK(wraps==3u,"stretch %u: the loop keeps wrapping (%u wraps)",mode,wraps);
        double per=(double)frames/3.0,want=mode?96000.0*120.0/128.0:96000.0;
        CHECK(fabs(per-want)<want*.002,"stretch %u at 128 BPM: about %.0f frames per pass (want %.0f)",mode,per,want);
        float pk=0.f;for(unsigned i=0;i<N;i++)if(fabsf(out_l[i])>pk)pk=fabsf(out_l[i]);
        CHECK(pk<=2.f && pk==pk,"stretch %u output finite and bounded",mode);
    }
    pl_event(&p,LP_STRETCH,0);

    /* Song-position lock: the sequencer runs at 120.6 BPM while the looper is
     * told 120 (0.5% off). Unlocked, that drifts ~480 samples per bar. */
    {
        struct pl_sync *sy=(struct pl_sync *)(void *)((uint8_t *)g.buffer+p.cap*PL_FRAME+PLX_BYTES);
        press(LP_CLEAR);g.freeze=0;g.density=1;pl_event(&p,LP_STRETCH,0);
        run(N*(PLS_STILL+2u),1200,0);
        song_t=1000.0;song_x10=1206u;            /* starts mid-bar */
        block(1200,1);block(1200,1);
        press(LP_REC);block(1200,1);
        CHECK(p.state==PL_ARMED,"sequencer running mid-bar: REC waits (ARMED)");
        uint32_t k=0;while(p.state==PL_ARMED && k<4000u){block(1200,1);k++;}
        CHECK(p.state==PL_REC && pl_mod(sy->start,PLQ_BAR)==0 && sy->start==PLQ_BAR,"take starts on the next bar line (tick %d)",(int)sy->start);
        while(p.state==PL_REC && k<20000u){block(1200,1);k++;}
        double bar=(double)PLQ_BAR/(12060.0/300000.0);   /* samples per bar at 120.6 */
        CHECK(p.state==PL_PLAY && (sy->flags&PLS_LOCKED) && sy->lt==(uint32_t)PLQ_BAR,"take closes on the bar line, locked to one bar of song time");
        CHECK(fabs((double)p.len-bar)<64.0,"take is one bar at the sequencer's real tempo: %u samples (want %.0f)",p.len,bar);
        uint32_t resets=0,last=p.pos;int worst=0;
        double end=song_t+20.0*PLQ_BAR;
        while(song_t<end) {
            block(1200,1);
            if(p.pos<last) {
                resets++;
                int ph=pl_mod((int32_t)song_t-sy->start,PLQ_BAR),d=ph<PLQ_BAR/2?ph:PLQ_BAR-ph;
                if(d>worst)worst=d;
            }
            last=p.pos;
        }
        CHECK(resets>=19u && resets<=20u,"Off: the loop restarts once per bar of song time (%u restarts in 20 bars)",resets);
        CHECK(worst<=4,"every restart lands within 4 ticks (0.1 ms) of the bar line after 20 bars (worst %d ticks)",worst);
        /* Vari locked: the read position follows the song phase exactly. */
        pl_event(&p,LP_STRETCH,1);int werr=0;
        for(unsigned b=0;b<3000u;b++) {
            block(1200,1);
            double ph=fmod(song_t-sy->start,(double)PLQ_BAR);
            double want=ph*(double)p.len/PLQ_BAR,e=fabs(want-(double)p.pos);
            if(e>(double)p.len/2)e=(double)p.len-e;
            if((int)e>werr)werr=(int)e;
        }
        CHECK(werr<=200,"Vari: play position stays within 200 samples (one block of ticks) of the song phase (worst %d)",werr);
        pl_event(&p,LP_STRETCH,0);song_x10=0u;
        run(N*(PLS_STILL+2u),1200,0);
    }

    /* External clock changes tempo: the bluebox BPM stays at 126 while the
     * master (and so the song position) goes 126 -> 128. The looper measures
     * the song position, so the next take is a true bar at 128 without
     * touching the bluebox BPM. */
    {
        struct pl_sync *sy=(struct pl_sync *)(void *)((uint8_t *)g.buffer+p.cap*PL_FRAME+PLX_BYTES);
        press(LP_CLEAR);g.freeze=0;g.density=2;pl_event(&p,LP_STRETCH,1);
        run(N*(PLS_STILL+2u),1260,0);
        song_t=0.0;song_x10=1260u;
        uint32_t k=0;while(song_t<4.0*PLQ_BAR+500.0 && k<40000u){block(1260,1);k++;}
        CHECK(abs((int)p.song_x100-12600)<=3,"song tempo measured at 126: %u",p.song_x100);
        press(LP_REC);while(p.state!=PL_PLAY && k<80000u){block(1260,1);k++;}
        double bar126=(double)PLQ_BAR*300000.0/12600.0;
        CHECK(p.state==PL_PLAY && (sy->flags&PLS_LOCKED) && fabs((double)p.len-2.0*bar126)<64.0,"2 bars at 126: %u samples (want %.0f)",p.len,2.0*bar126);
        song_x10=1280u;                          /* Blackbox switches to a project at 128 */
        uint32_t t0=k;
        while(abs((int)p.song_x100-12800)>3 && k<t0+40000u){block(1260,1);k++;}
        double beats=(double)(k-t0)*N*12800.0/300000.0/PLQ_BEAT;
        CHECK(abs((int)p.song_x100-12800)<=3 && beats<=8.0,"measured tempo reaches 128.00 within %.1f beats",beats);
        press(LP_CLEAR);block(1260,1);k++;press(LP_REC);
        while(p.state!=PL_PLAY && k<t0+200000u){block(1260,1);k++;}
        double bar128=(double)PLQ_BAR*300000.0/12800.0;
        CHECK(p.state==PL_PLAY && (sy->flags&PLS_LOCKED) && p.bars==2u && fabs((double)p.len-2.0*bar128)<64.0,
              "next take with the bluebox still at 126: 2 bars at 128, %u samples (want %.0f)",p.len,2.0*bar128);
        CHECK(abs((int)p.bpm_x100-12800)<=3,"the take's tempo is the measured 128 (%u), not the bluebox's 126",p.bpm_x100);
        /* Sequencer stops (the bluebox BPM still 126): a free Vari loop keeps
         * the measured 128, so it plays at its own length, not stretched. */
        song_x10=0u;run(N*(PLS_STILL+2u),1260,0);
        CHECK(abs((int)p.song_x100-12800)<=3,"stopped: the measured tempo is kept (%u)",p.song_x100);
        uint32_t frames=0,wraps=0,last=p.pos;
        while(wraps<3u && frames<2000000u){block(1260,0);if(wraps)frames+=N;if(p.pos<last)wraps++;last=p.pos;}
        CHECK(fabs((double)frames/2.0-(double)p.len)<(double)p.len*.002,"stopped: the loop keeps its own length (%.0f vs %u frames per pass)",(double)frames/2.0,p.len);
        /* Turning the bluebox BPM while stopped hands the tempo back to it. */
        block(1300,0);
        CHECK(p.song_x100==0u,"stopped, BPM changed: the measured tempo is dropped");
        pl_event(&p,LP_STRETCH,0);
        run(N*4u,1200,0);
    }

    /* Leaving the mode fades out and drops the loop and the button history. */
    g.mode=0;run(N*10u,1200,1);
    CHECK(g.fade==0.f && p.state==PL_EMPTY && g.valid==0 && p.last[0]==-1,"mode exit resets");

    printf(failures?"%d check(s) failed\n":"All looper checks passed\n",failures);
    return failures!=0;
}
