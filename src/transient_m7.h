/* Audio core: 12 per-track transient shapers in one boot-time SDRAM block.
 * The block is allocated by dly_construct (delay7), right after Shoegaze, from
 * the same bump allocator, and found by the gate (gate7) through a link in
 * the free backup-SRAM gap between the gate bank (ends 0x648) and the cue
 * state (0x660). Only the M7 reads or writes the link. */
#ifndef BB_TRANSIENT_M7_H
#define BB_TRANSIENT_M7_H
#include "transient_params.h"
#include "transient_shaper.h"
#include "joebox_comp.h"
/* Shaper state and settings, TRANSIENT on/off, then the page 4 compressor. */
struct ts_track {struct ts_state s;struct ts_params p;void *owner;uint32_t on;struct jc_state cs;uint32_t cmode;float cthresh;};
struct ts_link {uint32_t magic;struct ts_track *tracks;};
#define TL ((volatile struct ts_link *)0x38800650u)
#define TL_MAGIC 0x54534c31u
#define TS_ALLOC ((12u*sizeof(struct ts_track)+31u)&~31u)
_Static_assert(0x650+sizeof(struct ts_link)<=0x660,"transient link before cue state");

/* Joebox 3.5.zi BLACKBOX.bin 0x080F842C conversions, same rounding. */
static inline void ts_set(struct ts_params *p,unsigned id,int value) {
    value=ts_clamp(id,value);
    float v=(float)value*.00100000005f;
    switch(id) {
    case TS_MODEL:p->model=(uint32_t)value;break;
    case TS_ATTACK:p->attack=v;break;
    case TS_SUSTAIN:p->sustain=v;break;
    case TS_SPEED:p->speed=v;break;
    case TS_LENGTH:p->length=v;break;
    case TS_OUTPUT:p->output=__builtin_fmaf((float)value,4.15241011e-05f,.5f);break;
    case TS_MIX:p->mix=v;break;
    }
}
static inline void ts_event(struct ts_track *t,unsigned id,int value) {
    if(id==TS_ON)t->on=ts_clamp(id,value)!=0;
    else if(id==TC_MODE)t->cmode=(uint32_t)ts_clamp(id,value);
    else if(id==TC_THRESH) {
        /* Joebox 0x080F59F8: thousandths of a dB, clamped to -24..+12. */
        float x=(float)ts_clamp(id,value)*.00100000005f;
        t->cthresh=x< -24.f?-24.f:(x>12.f?12.f:x);
    }
    else ts_set(&t->p,id,value);
}
static inline void ts_track_reset(struct ts_track *t,void *owner) {
    static const struct {uint16_t id;int16_t value;} d[]=TS_DEFAULTS;
    t->owner=owner;t->s.magic=0;t->on=0;t->cs.magic=0;t->cmode=0;t->cthresh=0.f;
    for(unsigned i=0;i<sizeof(d)/sizeof(d[0]);i++)ts_set(&t->p,d[i].id,d[i].value);
}
/* Engaged with shaping or an Output gain other than 0 dB; otherwise exact bypass. */
static inline int ts_active(const struct ts_track *t) {
    const struct ts_params *p=&t->p;
    return t->on && (p->attack!=0.f || p->sustain!=0.f || p->output!=.5f);
}
#ifdef TS_ALLOCATOR
void ts_allocate(void) {
    TL->magic=0;TL->tracks=0;
    uint32_t cursor=*(volatile uint32_t *)0x24000004u;
    uint32_t limit=*(volatile uint32_t *)0x24000000u;
    if(cursor>=0xc0000000u && cursor<=limit && TS_ALLOC<=limit-cursor &&
       cursor<=0xc3400000u-TS_ALLOC) {
        struct ts_track *t=((void *(*)(unsigned))0x080412a5u)(TS_ALLOC);
        if(t) {
            for(unsigned i=0;i<12;i++)ts_track_reset(&t[i],0);
            TL->tracks=t;TL->magic=TL_MAGIC;
        }
    }
}
#endif
static inline struct ts_track *ts_track(unsigned ch,void *owner) {
    if(ch>=12 || TL->magic!=TL_MAGIC || !TL->tracks)return 0;
    struct ts_track *t=&TL->tracks[ch];
    if(t->owner!=owner)ts_track_reset(t,owner);
    return t;
}
#endif
