/* Per-track transient shaper settings (TRACK page 3). Shared by both cores.
 * Ids 0x1be..0x1c7: not defined by stock desktop 1.5.2 (its table ends at
 * 0x20a and leaves 0x1be..0x1f1 empty), not read by any stock code, and
 * after Cobalt's last id (0x1bd). Track settings lists hold 68 entries:
* stock 51 + Gate 1 + these 10 = 62. Saved values use Joebox's units. */
#ifndef BB_TRANSIENT_PARAMS_H
#define BB_TRANSIENT_PARAMS_H
#define TS_MODEL   0x1beu /* 0 Differ, 1 Punch, 2 Smooth */
#define TS_ATTACK  0x1bfu /* -1000..1000 = -100.0..+100.0 % */
#define TS_SUSTAIN 0x1c0u /* -1000..1000 */
#define TS_SPEED   0x1c1u /* 0..1000 */
#define TS_LENGTH  0x1c2u /* 0..1000 */
#define TS_OUTPUT  0x1c3u /* -12000..12000 mdB */
#define TS_MIX     0x1c4u /* 0..1000 */
#define TS_ON      0x1c5u /* 0 off, 1 on: the TRANSIENT button in the TRACK view */
#define TC_MODE    0x1c6u /* page 4 compressor: 0 Off, 1 Glue, 2 Punch, 3 Opto, 4 Squash, 5 Limit */
#define TC_THRESH  0x1c7u /* -24000..12000 mdB (Joebox Comp Thresh) */
#define TS_FIRST TS_MODEL
#define TS_LAST TC_THRESH
#define TS_ID(id) ((unsigned)(id)>=TS_FIRST && (unsigned)(id)<=TS_LAST)
/* Defaults: Attack and Sustain 0 with Output 0 dB is an exact bypass. */
#define TS_DEFAULTS {{TS_MODEL,0},{TS_ATTACK,0},{TS_SUSTAIN,0},{TS_SPEED,500},\
                     {TS_LENGTH,500},{TS_OUTPUT,0},{TS_MIX,1000},{TS_ON,0},\
                     {TC_MODE,0},{TC_THRESH,0}}
static inline int ts_clamp(unsigned id,int v) {
    int lo=0,hi=1000;
    if(id==TS_MODEL)hi=2;
    else if(id==TS_ON)hi=1;
    else if(id==TC_MODE)hi=5;
    else if(id==TC_THRESH){lo=-24000;hi=12000;}
    else if(id==TS_ATTACK || id==TS_SUSTAIN)lo=-1000;
    else if(id==TS_OUTPUT){lo=-12000;hi=12000;}
    return v<lo?lo:v>hi?hi:v;
}
#endif
