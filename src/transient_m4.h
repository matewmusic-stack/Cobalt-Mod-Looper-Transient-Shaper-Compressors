/* TRANSIENT button, TRACK page 3 (shaper) and page 4 (compressor). On TRACK pages 1 and 2 the bottom-right
 * knob (the Gate's, beside OUT2) is the track's TRANSIENT on/off: tap it or
 * turn encoder 4 on page 2. Page 3 holds the shaper's settings.
 *
 * The TRACK screen is one native panel whose
 * eight bottom knobs never move; its page flag (+0xebbc) picks which four the
 * encoders turn: 0 left half (page 1), 1 right half (Sidechain page). Page 3
 * is flag 2 on the same panel while the app stays on its Sidechain page, so
 * the native encoder dispatch keeps the right-half mapping and touches never
 * switch halves. The eight knobs are rebound to the transient settings:
 *
 *      MODEL   OUTPUT  | ATTACK  SPEED       encoders: 1 Attack, 2 Sustain,
 *      MIX     (title) | SUSTAIN LENGTH                3 Speed, 4 Length
 *
 * Tapping Model, Output or Mix puts it on encoder 4; tapping Length returns
 * it. Values commit through the native model setter like the Gate. Any native
 * rebind (track change, page change, edits) goes through gate_track_bind,
 * which re-applies or undoes this binding from the page flag.
 *
 * Page 4 is flag 3 on the same panel: Comp mode on encoder 1, Thresh on
 * encoder 2; the other six knobs are blanked (disabled, drawn over). */
#include "transient_params.h"
/* Lives in the cue icon payload (the Cobalt M4 cave is full). It wraps the
 * Gate's own TRACK hooks, linked by address (build.sh --defsym). */
void gate_default(void *set,unsigned id,int value);
unsigned gate_turn(uint8_t *w,int delta);
unsigned gate_track_local(uint8_t *p,uint32_t *ev);
void gate_track_bind(uint8_t *p,uint8_t *info);
void gate_mix_setup(uint8_t *p,unsigned mode);
void *gate_mix_construct(uint8_t *p);
void gate_column(uint8_t *p,short *slot);
unsigned gate_mix_event(uint8_t *p,uint32_t *ev);
unsigned gate_mix_local(uint8_t *p,uint32_t *ev);
void pc_defs_hook(void *table,unsigned id,unsigned type,const char *label,int min,int max,const char *key);
extern const volatile uint32_t theme_knob_palette[35];
#define ts_fw_get ((int (*)(void *,unsigned))0x08120235u)
#define TS_STOCK_ADD ((void (*)(void *,unsigned,int))0x0812028fu)
#define TS_STOCK_DEF ((void (*)(void *,unsigned,unsigned,const char *,int,int,const char *))0x08134c8du)
#define TS_PANEL_VT 0x0814bb3cu
#define TS_FLAG(p) (*(volatile uint32_t *)((uint8_t *)(p)+0xebbc))
#define TS_PAGE3 2u
#define TS_PAGE4 3u
#define TS_TITLE 0xd6a8u
/* M4-only, the free line remainder after the Gate accel (0x1c0..0x1cf). */
struct ts_ui {uint32_t magic;uint16_t enc4;uint8_t off_mask,pad;int32_t fraction,saved;};
#define TSU ((volatile struct ts_ui *)0x388001d0u)
#define TSU_MAGIC 0x54535533u
_Static_assert(0x1d0+sizeof(struct ts_ui)<=0x1e0,"transient UI before cue view");
static const struct {uint16_t off,id;} ts_slots[]={
    {0xcf08,TS_ATTACK},{0xda78,TS_SUSTAIN},{0xd2d8,TS_SPEED},{0xde48,TS_LENGTH},
    {0xc398,TS_MODEL},{0xc768,TS_OUTPUT},{0xcb38,TS_MIX}};
static volatile struct ts_ui *ts_ui(void) {
    if(TSU->magic!=TSU_MAGIC){TSU->enc4=TS_LENGTH;TSU->off_mask=0;TSU->fraction=0;TSU->saved=0;TSU->magic=TSU_MAGIC;}
    unsigned e=TSU->enc4;
    if(e!=TS_LENGTH && e!=TS_MODEL && e!=TS_OUTPUT && e!=TS_MIX)TSU->enc4=TS_LENGTH;
    return TSU;
}
static int ts_mem(uint32_t a,uint32_t n) {
    return ram(a,n) || (a>=0x20000000u && n<=0x20000u && a<=0x20020000u-n);
}
/* The TRACK panel, only while it is the page on screen (the same current-page
 * word the Gate overlay uses). */
static uint8_t *ts_panel(void) {
    uint32_t root=APP_POINTER;
    if(!ts_mem(root,0x2b8))return 0;
    uint32_t p=*(volatile uint32_t *)(root+0x2b4);
    if(!ts_mem(p,0xec00u))return 0;
    return *(uint32_t *)p==TS_PANEL_VT?(uint8_t *)p:0;
}
static int ts_page3(uint8_t *p) {return p && TS_FLAG(p)==TS_PAGE3;}
static int ts_page4(uint8_t *p) {return p && TS_FLAG(p)==TS_PAGE4;}
/* All eight bottom knobs; bit i of off_mask: knob i disabled by us. */
static const uint16_t ts_all[8]={0xc398,0xc768,0xcb38,0xd6a8,0xcf08,0xd2d8,0xda78,0xde48};
static void ts_restore(uint8_t *p) {
    volatile struct ts_ui *u=ts_ui();
    for(unsigned i=0;i<8;i++)if(u->off_mask>>i&1u)p[ts_all[i]+0x2d4]=0;
    u->off_mask=0;
}
static void ts_blank(uint8_t *p,unsigned off) {
    volatile struct ts_ui *u=ts_ui();
    for(unsigned i=0;i<8;i++)if(ts_all[i]==off && !p[off+0x2d4]){p[off+0x2d4]=1;u->off_mask|=(uint8_t)(1u<<i);}
    ((void (*)(void *,unsigned))0x0812788du)(p+off,0);
}
static uint8_t *ts_knob(uint8_t *p,unsigned id) {
    for(unsigned i=0;i<sizeof(ts_slots)/sizeof(ts_slots[0]);i++)
        if(ts_slots[i].id==id)return p+ts_slots[i].off;
    return 0;
}
static int ts_value(unsigned ch,unsigned id) {
    return ts_clamp(id,ts_fw_get((uint8_t *)0x300173d0u+0xc08+ch*0x30,id));
}
/* Lit knobs are the four the encoders turn. */
static void ts_highlight(uint8_t *p) {
    unsigned e=ts_ui()->enc4;
    for(unsigned i=0;i<sizeof(ts_slots)/sizeof(ts_slots[0]);i++) {
        unsigned id=ts_slots[i].id;
        ((void (*)(void *,unsigned))0x0812788du)(p+ts_slots[i].off,
            id==TS_ATTACK || id==TS_SUSTAIN || id==TS_SPEED || id==e);
    }
    ((void (*)(void *,unsigned))0x0812788du)(p+TS_TITLE,0);
}
/* The left-half knobs carry fixed names (VOL, PAN, GAIN) that the native
 * constructor copies into a text buffer at +0xf8 (0x081325ca..0x0813261e);
 * the right-half knobs show their setting's own label. Page 3 rebinds VOL,
 * PAN and GAIN to Model, Output and Mix, so it renames them, and every other
 * page puts the stock names back. */
static void ts_label(uint8_t *w,const char *t) {
    char *d=(char *)w+0xf8;unsigned i=0;
    for(;t[i] && i<15u;i++)d[i]=t[i];
    d[i]=0;w[0x9c]=1;
}
static void ts_labels(uint8_t *p) {
    int pg3=ts_page3(p);
    ts_label(p+0xc398,pg3?"MODEL":"VOL");
    ts_label(p+0xc768,pg3?"OUTPUT":"PAN");
    ts_label(p+0xcb38,pg3?"MIX":"GAIN");
}
/* Every frame: any path that changes the page flag without our rebind (seen
 * on hardware: MODEL/OUTPUT/MIX left on the TRACK view) is corrected here.
 * Only a label that differs is rewritten, so nothing is redrawn needlessly. */
static int ts_label_is(const uint8_t *w,const char *t) {
    const char *d=(const char *)w+0xf8;unsigned i=0;
    for(;t[i];i++)if(d[i]!=t[i])return 0;
    return d[i]==0;
}
static void ts_labels_sync(uint8_t *p) {
    int pg3=ts_page3(p);
    static const uint16_t o[3]={0xc398,0xc768,0xcb38};
    static const char *const n[2][3]={{"VOL","PAN","GAIN"},{"MODEL","OUTPUT","MIX"}};
    for(unsigned i=0;i<3;i++)if(!ts_label_is(p+o[i],n[pg3][i]))ts_label(p+o[i],n[pg3][i]);
}
/* After the native (and Gate) binding of channel ch. */
static void ts_track_bind(uint8_t *p,unsigned ch) {
    ts_restore(p);
    ts_labels(p);
    if(ch<12 && ts_page4(p)) {
        static const uint16_t c[2][2]={{0xcf08,TC_MODE},{0xda78,TC_THRESH}};
        for(unsigned i=0;i<8;i++)if(ts_all[i]!=0xcf08 && ts_all[i]!=0xda78)ts_blank(p,ts_all[i]);
        for(unsigned i=0;i<2;i++) {
            uint8_t *w=p+c[i][0];
            ((void (*)(void *,unsigned,int,unsigned))0x08127b85u)(w,c[i][1],ts_value(ch,c[i][1]),1);
            *(uint16_t *)(w+0x32)=(uint16_t)ch;w[0x2d4]=0;w[0x30]=0;
            ((void (*)(void *,unsigned))0x0812788du)(w,1);
        }
        return;
    }
    if(!ts_page3(p) || ch>=12) {
        if(ch>=12)return;
        /* Pages 1 and 2: the Gate's knob becomes TRANSIENT on/off. */
        uint8_t *w=p+0xde48;
        ((void (*)(void *,unsigned,int,unsigned))0x08127b85u)(w,TS_ON,ts_value(ch,TS_ON),1);
        *(uint16_t *)(w+0x32)=(uint16_t)ch;w[0x2d4]=0;w[0x30]=0;
        return;
    }
    for(unsigned i=0;i<sizeof(ts_slots)/sizeof(ts_slots[0]);i++) {
        uint8_t *w=p+ts_slots[i].off;
        ((void (*)(void *,unsigned,int,unsigned))0x08127b85u)(w,ts_slots[i].id,ts_value(ch,ts_slots[i].id),1);
        *(uint16_t *)(w+0x32)=(uint16_t)ch;w[0x2d4]=0;w[0x30]=0;
    }
    /* The spare knob is the page title: no touch or turn, drawn over. */
    ts_blank(p,TS_TITLE);
    ts_highlight(p);
}
static void ts_commit(uint16_t ch,unsigned id,int value) {
    if(ch>=12 || !TS_ID(id))return;
    ((void (*)(void *,uint16_t *,unsigned,int,unsigned))0x08124b45u)
        ((void *)0x300173d0u,&ch,id,ts_clamp(id,value),0);
}
/* Model and Comp: notched travel, one step per 256 units (as FX selectors). */
static unsigned ts_turn_list(uint8_t *w,int delta) {
    volatile struct ts_ui *u=ts_ui();
    unsigned id=*(uint16_t *)(w+0x94);int max=ts_clamp(id,99);
    int old=ts_clamp(id,*(int *)(w+0x98));
    if(u->saved!=old || (delta<0 && u->fraction>0) || (delta>0 && u->fraction<0))u->fraction=0;
    if(delta>1000)delta=1000;
    if(delta< -1000)delta=-1000;
    int total=u->fraction+delta,step=total/256,next=old+step;
    if(next<0)next=0;
    if(next>max)next=max;
    u->fraction=total-step*256;
    if((next==max && total>0)||(next==0 && total<0))u->fraction=0;
    unsigned result=0;
    if(next!=old) {
        unsigned ch=*(uint16_t *)(w+0x32);
        uint32_t ev[6]={0x6e,0x08148664u,ch,id,(uint32_t)next,0};
        ((void (*)(void *,void *))0x0813a415u)(w,ev);
        ((void (*)(void *,unsigned,int,unsigned))0x08127b85u)(w,id,next,1);
        result=1;
    }
    u->saved=*(int *)(w+0x98);
    return result;
}
/* Set TRANSIENT on/off through the same child edit path as a knob. */
static void ts_switch(uint8_t *w,int on) {
    if(*(uint16_t *)(w+0x94)!=TS_ON || *(int *)(w+0x98)==on)return;
    uint32_t ev[6]={0x6e,0x08148664u,*(uint16_t *)(w+0x32),TS_ON,(uint32_t)on,0};
    ((void (*)(void *,void *))0x0813a415u)(w,ev);
    ((void (*)(void *,unsigned,int,unsigned))0x08127b85u)(w,TS_ON,on,1);
}
/* Encoder turn on the TRACK panel. Returns 1 and sets *result when handled. */
static int ts_turn(uint8_t *w,int delta,unsigned *result) {
    uint8_t *p=ts_panel();
    if(!p || (uint32_t)(w-p)>0xec00u)return 0;
    if(!ts_page3(p) && !ts_page4(p)) {
        if(w!=p+0xde48 || *(uint16_t *)(w+0x94)!=TS_ON)return 0;
        if(delta)ts_switch(w,delta>0);
        *result=delta!=0;return 1;
    }
    if(ts_page3(p) && w==p+0xde48)w=ts_knob(p,ts_ui()->enc4);
    if(!w || w[0x30] || w[0x2d4] || !TS_ID(*(uint16_t *)(w+0x94))){*result=0;return 1;}
    unsigned id=*(uint16_t *)(w+0x94);
    *result=id==TS_MODEL || id==TC_MODE?ts_turn_list(w,delta)
        :((unsigned (*)(void *,int))0x08127d51u)(w,delta);
    return 1;
}
/* Child events on the TRACK panel: commit edits, and on page 3 a touch
 * (0x16a, knob id at +12) picks encoder 4 instead of switching halves. */
static int ts_local(uint8_t *p,uint32_t *ev) {
    unsigned type=(uint16_t)ev[0];
    if(type==0x16a && !ts_page3(p) && *(uint16_t *)((uint8_t *)ev+12)==TS_ON) {
        uint8_t *w=p+0xde48;
        if(*(uint16_t *)(w+0x94)==TS_ON)ts_switch(w,!*(int *)(w+0x98));
        return 1;
    }
    if(type==0x16a && ts_page3(p)) {
        unsigned id=*(uint16_t *)((uint8_t *)ev+12);
        if(id==TS_LENGTH || id==TS_MODEL || id==TS_OUTPUT || id==TS_MIX) {
            ts_ui()->enc4=(uint16_t)id;ts_highlight(p);
        }
        return 1;
    }
    if(type!=0x6e && type!=0x3c && type!=0x3d)return 0;
    unsigned id=type==0x6e?ev[3]:ev[4];
    if(!TS_ID(id))return 0;
    ts_commit((uint16_t)ev[2],id,(int)(type==0x6e?ev[4]:ev[3]));
    return 1;
}
/* Hook wrappers. Each runs the Gate's original first or falls through to it. */
void ts_gate_track_bind(uint8_t *p,uint8_t *info) {
    gate_track_bind(p,info);
    ts_track_bind(p,*(uint16_t *)(info+4));
}
unsigned ts_gate_turn(uint8_t *w,int delta) {
    unsigned handled;
    return ts_turn(w,delta,&handled)?handled:gate_turn(w,delta);
}
unsigned ts_track_local(uint8_t *p,uint32_t *ev) {
    return ts_local(p,ev)?0:gate_track_local(p,ev);
}
void ts_gate_default(void *set,unsigned id,int value) {
    gate_default(set,id,value);
    /* Transient and compressor settings: 51 stock + Gate + 10 = 62 of 68 entries. */
    static const struct {uint16_t id;int16_t value;} d[]=TS_DEFAULTS;
    for(unsigned i=0;i<sizeof(d)/sizeof(d[0]);i++)TS_STOCK_ADD(set,d[i].id,d[i].value);
}
void ts_defs(void *table,unsigned id,unsigned type,const char *label,int min,int max,const char *key) {
    pc_defs_hook(table,id,type,label,min,max,key);
    TS_STOCK_DEF(table,TS_MODEL,1,"Model:",0,2,"tsmodel");
    TS_STOCK_DEF(table,TS_ATTACK,8,"Attack:",-1000,1000,"tsattack");
    TS_STOCK_DEF(table,TS_SUSTAIN,8,"Sustain:",-1000,1000,"tssustain");
    TS_STOCK_DEF(table,TS_SPEED,8,"Speed:",0,1000,"tsspeed");
    TS_STOCK_DEF(table,TS_LENGTH,8,"Length:",0,1000,"tslength");
    TS_STOCK_DEF(table,TS_OUTPUT,7,"Output:",-12000,12000,"tsoutput");
    TS_STOCK_DEF(table,TS_MIX,8,"Mix:",0,1000,"tsmix");
    TS_STOCK_DEF(table,TS_ON,4,"Transient:",0,1,"tson");
    TS_STOCK_DEF(table,TC_MODE,1,"Comp:",0,5,"tcmode");
    TS_STOCK_DEF(table,TC_THRESH,7,"Thresh:",-24000,12000,"tcthresh");
}
/* MIXER: the Gate's sends-page button selects the TRANSIENT on/off column
 * (selector table entry 0x0814b7f4 now names TS_ON). The native column binds
 * and draws it like the other on/off columns; the labels are renamed and its
 * edits commit per track. Main (12) has no shaper: its edits are dropped. */
#define TS_SET_TEXT ((void (*)(void *,const char *))0x0813820du)
void ts_mix_setup(uint8_t *p,unsigned mode) {
    gate_mix_setup(p,mode);
    TS_SET_TEXT(p+0xc3a4,"Trans");
}
void *ts_mix_construct(uint8_t *p) {
    void *result=gate_mix_construct(p);
    TS_SET_TEXT(p+0xbfe4,"TS");      /* seventh button, about 45 px */
    return result;
}
/* Column binding: native for the tracks; Main's TRANSIENT is disabled (N/A),
 * as the Gate column did, because Main has no shaper. */
void ts_column(uint8_t *p,short *slot) {
    uint8_t *k=p+0xbe0+12*0xd98+0x8f0;
    if(*slot==12 && *(uint16_t *)(k+0x94)==TS_ON)k[0x2d4]=0;
    gate_column(p,slot);
    if(*slot!=12 || *(uint16_t *)(p+0xbca0)!=TS_ON)return;
    uint8_t *w=p+0xbe0+12*0xd98;
    ((void (*)(void *,unsigned))0x0812d72fu)(w,1);
    ((void (*)(void *,unsigned))0x0812d507u)(w,0);
    k[0x2d4]=1;
    ((void (*)(void *,const char *))0x0813fe4bu)(k+0xa0,"N/A");
}
/* MIXER encoders on the Trans column: the native dispatch would also turn its
 * base bindings (Vol), as it did for the Gate. Route them like the Gate did,
 * with the native bank mapping: right turns the track on, left off. */
unsigned ts_mix_event(uint8_t *p,uint32_t *ev) {
    if((uint16_t)ev[0]!=0x32 || *(uint16_t *)(p+0xbca0)!=TS_ON)return gate_mix_event(p,ev);
    int index=(int16_t)ev[3],delta=(int)ev[4];
    if(p[0xbcc0])index=index<0?-((-index)&1):(index&1);
    int ch=index+2 * *(int *)(p+0xbcbc);
    if(ch>=0 && ch<12 && delta) {
        ts_commit((uint16_t)ch,TS_ON,delta>0);
        ((void (*)(void *,unsigned,int,unsigned))0x08127b85u)(p+0xbe0+(unsigned)ch*0xd98+0x8f0,TS_ON,delta>0,1);
    }
    return 0;
}
unsigned ts_mix_local(uint8_t *p,uint32_t *ev) {
    unsigned type=(uint16_t)ev[0];
    if(type==0x6e || type==0x3c || type==0x3d) {
        unsigned id=type==0x6e?ev[3]:ev[4];
        if(TS_ID(id)) {
            ts_commit((uint16_t)ev[2],id,(int)(type==0x6e?ev[4]:ev[3]));
            return 0;
        }
    }
    return gate_mix_local(p,ev);
}
/* The whole TRACK button (native handler 0x08123ad8; 0x08123a9e is MIXER).
 * Stock: app pages 5/6 are the TRACK view (0x8c events; 5 and 6 are only the
 * knob focus halves), page 22 is the Side Chain envelope screen, and TRACK
 * toggles view <-> Side Chain. The cycle becomes
 *   TRACK view -> Side Chain -> page 3 (shaper) -> page 4 (comp) -> TRACK view
 * Page 3 is the TRACK view panel with its flag at 2. From Side Chain we ask
 * the native switch for the remembered view page and mark it pending; the
 * native page change then sets the panel's flag (ts_subpage), and pending
 * turns that into 2. */
struct ts_key {uint8_t pending,pad[3];};
#define TSK ((volatile struct ts_key *)0x388001f0u)
_Static_assert(0x1f0+sizeof(struct ts_key)<=0x200,"page 3 pending flag before delay types");
#define TS_SET_PAGE ((void (*)(void *,unsigned,unsigned,unsigned))0x08122509u)
#define TS_SIDECHAIN 22u
void ts_track_key(uint8_t *app) {
    unsigned page=app[0x739a],view=app[0x739d];
    if(view!=5u && view!=6u)view=5u;
    uint8_t *p=ts_panel();
    if(page==TS_SIDECHAIN){TSK->pending=1;TS_SET_PAGE(app,view,0,0);return;}   /* Side Chain -> page 3 */
    TSK->pending=0;
    if(page==5u || page==6u) {
        unsigned flag=p?TS_FLAG(p):0u;
        if(flag==TS_PAGE3) {                                                  /* page 3 -> page 4 */
            ((void (*)(void *,unsigned))0x081327cdu)(p,TS_PAGE4);
            ts_gate_track_bind(p,p+0xbc98);
        }
        else if(flag==TS_PAGE4)TS_SET_PAGE(app,page,0,0);                    /* page 4 -> TRACK view */
        else TS_SET_PAGE(app,TS_SIDECHAIN,0,0);                               /* view -> Side Chain */
        return;
    }
    TS_SET_PAGE(app,view,0,0);                                                /* from elsewhere: native */
}
/* The native TRACK view change sets the panel's flag (0x081345fe, event 0x8c):
 * a pending page 3 wins over either half. */
void ts_subpage(uint8_t *p,unsigned sub) {
    if(TSK->pending){TSK->pending=0;sub=TS_PAGE3;}
    ((void (*)(void *,unsigned))0x081327cdu)(p,sub);
}

/* Drawing: the Model name and the page title, each inside its own knob
 * rectangle (2 px native border kept, as the Gate control). 5x7 glyphs from
 * the Gate font, only the letters used here. */
static const struct {char c;uint8_t r[7];} ts_font[]={
    {'4',{2,6,10,18,31,2,2}},
    {'A',{14,17,17,31,17,17,17}},
    {'B',{30,17,17,30,17,17,30}},{'C',{14,17,16,16,16,17,14}},
    {'D',{30,17,17,17,17,17,30}},
    {'E',{31,16,16,30,16,16,31}},
    {'H',{17,17,17,31,17,17,17}},
    {'F',{31,16,16,30,16,16,16}},
    {'G',{14,17,16,23,17,17,15}},
    {'I',{14,4,4,4,4,4,14}},
    {'K',{17,18,20,24,20,18,17}},
    {'L',{16,16,16,16,16,16,31}},
    {'M',{17,27,21,21,17,17,17}},
    {'N',{17,25,25,21,19,19,17}},
    {'O',{14,17,17,17,17,17,14}},
    {'P',{30,17,17,30,16,16,16}},
    {'Q',{14,17,17,17,21,18,13}},{'R',{30,17,17,30,20,18,17}},
    {'S',{15,16,16,14,1,1,30}},
    {'T',{31,4,4,4,4,4,4}},
    {'U',{17,17,17,17,17,17,14}},
    {'V',{17,17,17,17,17,10,4}},
    {'X',{17,17,10,4,10,17,17}}
};
static void ts_rect(uint8_t *px,unsigned fmt,unsigned bpp,int x,int y,int w,int h,uint32_t color) {
    for(int r=0;r<h;r++)for(int c=0;c<w;c++)pixel(px+((unsigned)(y+r)*320u+(unsigned)(x+c))*bpp,fmt,color);
}
static void ts_text(uint8_t *px,unsigned fmt,unsigned bpp,int x,int y,int w,const char *t,uint32_t color) {
    unsigned n=0;while(t[n] && n<8)n++;
    x+=(w-(int)(n*6u-1u))/2;
    for(unsigned k=0;k<n;k++)for(unsigned j=0;j<sizeof(ts_font)/sizeof(ts_font[0]);j++)if(ts_font[j].c==t[k]) {
        for(unsigned r=0;r<7;r++)for(unsigned c=0;c<5;c++)if(ts_font[j].r[r]&(16u>>c))
            pixel(px+((unsigned)(y+(int)r)*320u+(unsigned)(x+6*(int)k+(int)c))*bpp,fmt,color);
        break;
    }
}
static void ts_box(uint8_t *px,unsigned fmt,unsigned bpp,uint8_t *w,
                   const char *a,uint32_t ca,const char *b,uint32_t cb,const char *c,uint32_t cc) {
    int x=*(int *)(w+4),bottom=*(int *)(w+8),width=*(int *)(w+12),height=*(int *)(w+16);
    if(x<0 || width<44 || width>100 || x>320-width || bottom<0 || height<44 || height>100 || bottom>240-height)return;
    int top=240-bottom-height,y=top+(height-44)/2;
    ts_rect(px,fmt,bpp,x+2,top+2,width-4,height-4,theme_knob_palette[2]&0xffffffu);
    ts_text(px,fmt,bpp,x,y+4,width,a,ca);
    ts_text(px,fmt,bpp,x,y+16,width,b,cb);
    if(c)ts_text(px,fmt,bpp,x,y+28,width,c,cc);
}
static void ts_draw(const uint8_t *d) {
    if(!d)return;
    uint8_t *px=*(uint8_t *const *)d;
    unsigned w=*(const uint16_t *)(d+4),h=*(const uint16_t *)(d+6),fmt=d[8],bpp=*(const uint16_t *)(d+10);
    if(w!=320u || h!=240u || !ram((uint32_t)px,w*h*bpp))return;
    if(!((fmt==1u && bpp==4u)||(fmt==2u && bpp==3u)||((fmt==3u||fmt==4u) && bpp==2u)))return;
    uint8_t *p=ts_panel();
    if(!p)return;
    ts_labels_sync(p);
    uint32_t fg=theme_knob_palette[3]&0xffffffu,accent=theme_knob_palette[34]&0xffffffu,dim=0xaaaaaau,on_c=0x22bb22u;
    uint8_t *b=p+0xde48;
    if(ts_page4(p)) {
        static const char *const comps[]={"OFF","GLUE","PUNCH","OPTO","SQUASH","LIMIT"};
        uint8_t *m=p+0xcf08;
        int v=*(uint16_t *)(m+0x94)==TC_MODE?ts_clamp(TC_MODE,*(int *)(m+0x98)):0;
        for(unsigned i=0;i<8;i++)if(p[ts_all[i]+0x2d4] && ts_all[i]!=TS_TITLE)ts_box(px,fmt,bpp,p+ts_all[i],"",fg,"",fg,0,0);
        if(*(uint16_t *)(m+0x94)==TC_MODE)ts_box(px,fmt,bpp,m,"MODE",accent,comps[v],v?on_c:dim,0,0);
        ts_box(px,fmt,bpp,p+TS_TITLE,"COMP",accent,"PAGE 4",dim,0,0);
        return;
    }
    if(!ts_page3(p)) {
        if(*(uint16_t *)(b+0x94)==TS_ON && !b[0x30])
            ts_box(px,fmt,bpp,b,"TRANS",accent,*(int *)(b+0x98)?"ON":"OFF",*(int *)(b+0x98)?on_c:dim,0,0);
        return;
    }
    unsigned ch=*(uint16_t *)(p+0xbc98+4);   /* the bound track, as the native rebind reads it */
    int on=ch<12 && ts_value(ch,TS_ON);
    static const char *const models[]={"DIFFER","PUNCH","SMOOTH"};
    static const char *const names[]={"4 LENGTH","4 MODEL","4 OUTPUT","4 MIX"};
    unsigned e=ts_ui()->enc4;
    uint8_t *m=ts_knob(p,TS_MODEL);
    if(m && *(uint16_t *)(m+0x94)==TS_MODEL) {
        int v=ts_clamp(TS_MODEL,*(int *)(m+0x98));
        ts_box(px,fmt,bpp,m,"MODEL",accent,models[v],e==TS_MODEL?accent:fg,e==TS_MODEL?"ENC 4":0,dim);
    }
    ts_box(px,fmt,bpp,p+TS_TITLE,"TRANS",accent,on?"ON":"OFF",on?on_c:dim,
           names[e==TS_MODEL?1:e==TS_OUTPUT?2:e==TS_MIX?3:0],fg);
}
