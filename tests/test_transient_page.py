"""TRACK page 3 (transient shaper) on the real native TRACK panel, and the
per-track shaper on the real native channel EQ node. Looper build:
LOOPER=1 python3 test_transient_page.py /path/to/stock/BLUEBOX.BIN"""
from gate_ui_fixture import *
import gate_fixture as GF
C4=M['symbols']['cue4'];G7=M['symbols']['gate7'];D7=M['symbols']['delay7']
MODEL,ATTACK,SUSTAIN,SPEED,LENGTH,OUTPUT,MIX,ON,CMODE,CTHR=range(0x1be,0x1c8)
DEFAULTS={MODEL:0,ATTACK:0,SUSTAIN:0,SPEED:500,LENGTH:500,OUTPUT:0,MIX:1000,ON:0,CMODE:0,CTHR:0}
SLOTS={0xcf08:ATTACK,0xda78:SUSTAIN,0xd2d8:SPEED,0xde48:LENGTH,0xc398:MODEL,0xc768:OUTPUT,0xcb38:MIX}
NATIVE={0xc398:0x4,0xc768:0x63,0xcb38:0x3,0xcf08:0xda,0xd2d8:0xdb,0xd6a8:0x15d,0xda78:0x15e,0xde48:ON}
TSU=0x388001d0;APPOBJ=0x24070000
def s32(x):return struct.unpack('<i',struct.pack('<I',x&0xffffffff))[0]
def cstr(a):return bytes(u.mem_read(a,40)).split(b'\0')[0].decode() if a else ''
def get(ch,pid):return s32(call(u,0x8120234,APP+0xc08+ch*0x30,pid))
def kid(off):return struct.unpack('<H',u.mem_read(T+off+0x94,2))[0]
def lit(off):return u.mem_read(T+off+0x250,1)[0]
def flag():return u32(u,T+0xebbc)
def enc4():return struct.unpack('<H',u.mem_read(TSU+4,2))[0]

# Definitions: labels, types, ranges and saved keys.
tab=u32(u,0x3001eb30)
want={MODEL:(1,'Model:',0,2,'tsmodel'),ATTACK:(8,'Attack:',-1000,1000,'tsattack'),SUSTAIN:(8,'Sustain:',-1000,1000,'tssustain'),
      SPEED:(8,'Speed:',0,1000,'tsspeed'),LENGTH:(8,'Length:',0,1000,'tslength'),OUTPUT:(7,'Output:',-12000,12000,'tsoutput'),MIX:(8,'Mix:',0,1000,'tsmix'),ON:(4,'Transient:',0,1,'tson'),CMODE:(1,'Comp:',0,5,'tcmode'),CTHR:(7,'Thresh:',-24000,12000,'tcthresh')}
for pid,(typ,label,lo,hi,key) in want.items():
 e=tab+pid*28;mn,mx,k=struct.unpack('<iiI',u.mem_read(e+16,12))
 got=(u.mem_read(e+2,1)[0],cstr(u32(u,e+4)),mn,mx,cstr(k))
 check(struct.unpack('<H',u.mem_read(e,2))[0]==pid and got==(typ,label,lo,hi,key),'definition '+label+' '+str(got))
check(cstr(u32(u,tab+0x1ae*28+4))=='Gate:' and cstr(u32(u,tab+0x1bd*28+24))=='lpetype','Gate and looper definitions intact')
# Per-track defaults: every track holds the 7 settings, 59 of 68 entries.
for ch in range(12):
 count,cap=struct.unpack('<HH',u.mem_read(APP+0xc08+ch*0x30+10,4))
 check(all(get(ch,p)==v for p,v in DEFAULTS.items()) and get(ch,0x1ae)==-96000 and (count,cap)==(62,68),'track %d defaults, %d of %d entries'%(ch+1,count,cap))

# The native panel as the current page; the UI root is not at a fixed offset from it.
ROOTUI=0x24068000;w32(u,0x3000d9fc,ROOTUI);w32(u,ROOTUI+0x2b4,T)
ch=2;setup(1,ch,-60000)
for pid,v in [(ATTACK,-250),(SUSTAIN,400),(SPEED,300),(LENGTH,700),(OUTPUT,-3000),(MIX,800),(MODEL,2)]:
 call(u,0x8120264,APP+0xc08+ch*0x30,pid,v&0xffffffff)
def global_event(t):
 u.mem_write(TMP,struct.pack('<6I',t,0x8148664,ch,0,0,0));call(u,0x8133194,T,TMP)
call(u,0x81327cc,T,1);global_event(0x67)
check(flag()==1 and all(kid(o)==i for o,i in NATIVE.items()),'page 2 keeps native knobs; the Gate spot is TRANSIENT')
check([bytes(u.mem_read(T+o+0xf8,16)).split(b'\0')[0] for o in (0xc398,0xc768,0xcb38)]==[b'VOL',b'PAN',b'GAIN'],'stock knob names as built: VOL, PAN, GAIN')
# TRANSIENT on/off on page 2: encoder 4 and tap, committed per track.
def turn(index,delta):
 clock[0]+=1000;w32(u,0x3001eb3c,clock[0])
 u.mem_write(TMP,struct.pack('<6I',0x32,0x8148664,0,index&0xffffffff,delta&0xffffffff,0));call(u,0x8133194,T,TMP)
def touch(pid):
 parents.clear();u.mem_write(TMP,struct.pack('<HHIIHH12x',0x16a,0,0x8148664,ch,pid,0))
 return call(u,C4['ts_track_local'],T,TMP)
commands.clear();turn(3,1)
check(get(ch,ON)==1 and val(T+0xde48)==1 and commands[-1]==(ch,ON,1),'encoder 4 right turns TRANSIENT on for this track')
turn(3,-1);check(get(ch,ON)==0 and val(T+0xde48)==0,'encoder 4 left turns it off')
touch(ON);check(get(ch,ON)==1 and flag()==1,'tap toggles TRANSIENT on, page stays')
check(get(ch-1,ON)==0 and get(ch+1,ON)==0,'other tracks stay off')
check(get(ch,0x1ae)==-60000,'TRANSIENT leaves the saved Gate threshold alone')
# The TRACK button (stock: app pages 5/6 TRACK view <-> 22 Side Chain):
# TRACK view -> Side Chain -> page 3 -> TRACK view. Page 3 lands through the
# native 0x8c view change, whose flag set (0x081345fe) is ts_subpage.
pages=[];stub(u,0x8122508,lambda q:pages.append((q.reg_read(UC_ARM_REG_R0),q.reg_read(UC_ARM_REG_R1))))
def key(app_page,view=6):
 pages.clear();u.mem_write(APPOBJ+0x739a,bytes([app_page]));u.mem_write(APPOBJ+0x739d,bytes([view]))
 call(u,C4['ts_track_key'],APPOBJ)
def view_change(sub):  # what the native 0x8c handler does: set the flag, then rebind
 call(u,C4['ts_subpage'],T,sub);global_event(0x67)
for page,sub in ((5,0),(6,1)):
 view_change(sub);key(page)
 check(pages==[(APPOBJ,22)] and flag()==sub,'TRACK view (app page %d): TRACK goes to Side Chain'%page)
w32(u,ROOTUI+0x2b4,P)   # Side Chain is another screen
key(22,6);check(pages==[(APPOBJ,6)] and u.mem_read(0x388001f0,1)[0]==1,'Side Chain: TRACK asks for the TRACK view with page 3 pending')
w32(u,ROOTUI+0x2b4,T);view_change(1)
check(flag()==2 and u.mem_read(0x388001f0,1)[0]==0,'the native view change lands on page 3 and clears pending')
check(all(kid(o)==i and val(T+o)==get(ch,i) and struct.unpack('<H',u.mem_read(T+o+0x32,2))[0]==ch for o,i in SLOTS.items()),'all 7 knobs rebound to this track\'s saved transient values')
check([lit(o) for o in (0xcf08,0xda78,0xd2d8,0xde48,0xc398,0xc768,0xcb38,0xd6a8)]==[1,1,1,1,0,0,0,0],'encoders light Attack, Sustain, Speed, Length')
def lbl(o):return bytes(u.mem_read(T+o+0xf8,16)).split(b'\0')[0]
check([lbl(o) for o in (0xc398,0xc768,0xcb38)]==[b'MODEL',b'OUTPUT',b'MIX'],'page 3 renames the VOL/PAN/GAIN knobs Model/Output/Mix')
check(u.mem_read(T+0xd6a8+0x2d4,1)[0]==1,'spare knob is the inert title')
# A native rebind (another edit, track refresh) keeps page 3.
global_event(0x67);check(flag()==2 and kid(0xcf08)==ATTACK and kid(0xde48)==LENGTH,'native rebind re-applies page 3')

# Encoders: native dispatch -> page 3 knobs -> shared model commit.
for index,pid in enumerate((ATTACK,SUSTAIN,SPEED,LENGTH)):
 before={p:get(ch,p) for p in DEFAULTS};commands.clear()
 for i in range(30):turn(index,4)
 after={p:get(ch,p) for p in DEFAULTS}
 changed=[p for p in DEFAULTS if after[p]!=before[p]]
 check(changed==[pid] and after[pid]>before[pid] and val(T+[o for o,i in SLOTS.items() if i==pid][0])==after[pid],'encoder %d turns only %s (%d -> %d)'%(index+1,want[pid][1],before[pid],after[pid]))
 check(commands and all(c==(ch,pid,c[2]) for c in commands) and s32(commands[-1][2])==after[pid],'encoder %d sends its value to the audio core'%(index+1))
check(get(ch,0x1ae)==-60000,'page 3 turns leave the Gate threshold')
# Touch: Model/Output/Mix take encoder 4; Length takes it back.
for pid,offs in [(MIX,0xcb38),(OUTPUT,0xc768),(MODEL,0xc398)]:
 touch(pid)
 check(enc4()==pid and lit(offs)==1 and lit(0xde48)==0 and flag()==2 and not parents,'touch %s: on encoder 4, lit, still page 3'%want[pid][1])
touch(MIX);m0=get(ch,MIX);l0=get(ch,LENGTH)
for i in range(30):turn(3,-4)
check(get(ch,MIX)<m0 and get(ch,LENGTH)==l0,'encoder 4 turns Mix after touching Mix')
touch(MODEL);commands.clear()
for i in range(20):turn(3,-16)
check(get(ch,MODEL)==1 and val(T+0xc398)==1,'Model steps one notch per 256 units (Smooth -> Punch)')
for i in range(40):turn(3,-16)
check(get(ch,MODEL)==0 and commands and commands[-1][1]==MODEL,'Model stops at Differ and commits')
touch(0x4);check(flag()==2 and enc4()==MODEL,'touching a native id cannot switch halves on page 3')
touch(LENGTH);check(enc4()==LENGTH and lit(0xde48)==1,'touch Length returns it to encoder 4')

# Overlay text actually passed to the compiled renderer.
FB=0xc0100000;DESC=0x24078000
u.mem_write(DESC,struct.pack('<IHHBxH',FB,320,240,1,4))
stub(u,0x810139a,lambda q:q.reg_write(UC_ARM_REG_R0,DESC));stub(u,M['symbols']['pcm4']['pc_present'],lambda q:None)
texts=[]
def text_hook(q,a,n,d):texts.append(cstr(u32(q,q.reg_read(UC_ARM_REG_SP)+8)))
h=u.hook_add(UC_HOOK_CODE,text_hook,begin=C4['ts_text'],end=C4['ts_text'])
call(u,C4['cue_present'],0,0,0,0)
check(texts[:5]==['MODEL','DIFFER','TRANS','ON','4 LENGTH'],'page 3 overlay: Model name; title with ON and encoder 4 '+str(texts))
touch(MODEL);texts.clear();call(u,C4['cue_present'],0,0,0,0)
check(texts==['MODEL','DIFFER','ENC 4','TRANS','ON','4 MODEL'],'Model on encoder 4 is marked '+str(texts))
u.hook_del(h)

# TRACK on page 3: page 4, the compressor (same panel, flag 3).
ALL=(0xc398,0xc768,0xcb38,0xd6a8,0xcf08,0xd2d8,0xda78,0xde48)
dis=lambda o:u.mem_read(T+o+0x2d4,1)[0]
key(6);check(flag()==3 and pages==[],'TRACK on page 3 opens page 4')
check(kid(0xcf08)==CMODE and kid(0xda78)==CTHR and val(T+0xcf08)==get(ch,CMODE) and val(T+0xda78)==get(ch,CTHR),'page 4 binds Comp (encoder 1) and Thresh (encoder 2)')
check([dis(o) for o in ALL]==[1,1,1,1,0,1,0,1] and lit(0xcf08)==1 and lit(0xda78)==1,'the other six knobs are blanked; encoders 1-2 lit')
global_event(0x67);check(flag()==3 and kid(0xcf08)==CMODE,'native rebind keeps page 4')
commands.clear()
for i in range(20):turn(0,16)
check(get(ch,CMODE)==1 and commands and commands[-1][1]==CMODE,'encoder 1 steps Comp Off -> Glue (one notch per 256 units)')
for i in range(80):turn(0,16)
check(get(ch,CMODE)==5,'Comp stops at Limit')
t0=get(ch,CTHR)
for i in range(30):turn(1,-40)
check(get(ch,CTHR)<t0,'encoder 2 lowers Thresh (%d -> %d mdB)'%(t0,get(ch,CTHR)))
before={p:get(ch,p) for p in DEFAULTS};turn(2,40);turn(3,40)
check({p:get(ch,p) for p in DEFAULTS}==before,'encoders 3-4 do nothing on page 4')
touch(0x4);check(flag()==3,'touches cannot switch halves on page 4')
texts.clear();h=u.hook_add(UC_HOOK_CODE,text_hook,begin=C4['ts_text'],end=C4['ts_text']);call(u,C4['cue_present'],0,0,0,0);u.hook_del(h)
check([t for t in texts if t]==['MODE','LIMIT','COMP','PAGE 4'] and texts.count('')==10,'page 4 draws Mode, title and five blank boxes '+str([t for t in texts if t]))
# TRACK on page 4: back to the TRACK view (the same app page, flag reset).
key(6);check(pages==[(APPOBJ,6)],'TRACK on page 4 asks for the TRACK view')
view_change(0)
check(flag()==0 and all(kid(o)==i for o,i in NATIVE.items()) and all(dis(o)==0 for o in ALL),'page 1 restores all native knobs, none left disabled')
check([lbl(o) for o in (0xc398,0xc768,0xcb38)]==[b'VOL',b'PAN',b'GAIN'],'page 1 has the stock VOL/PAN/GAIN names back')
check(val(T+0xde48)==1,'TRANSIENT knob back with this track\'s ON')
texts.clear();h=u.hook_add(UC_HOOK_CODE,text_hook,begin=C4['ts_text'],end=C4['ts_text']);call(u,C4['cue_present'],0,0,0,0);u.hook_del(h)
check(texts==['TRANS','ON'],'page 1 draws the TRANSIENT button '+str(texts))
# Hardware: MODEL/OUTPUT/MIX were seen on the TRACK view (the flag changed
# without a rebind). A frame draw puts the right names back.
for o,n in ((0xc398,b'MODEL'),(0xc768,b'OUTPUT'),(0xcb38,b'MIX')):u.mem_write(T+o+0xf8,n+b'\0')
call(u,C4['cue_present'],0,0,0,0)
check([lbl(o) for o in (0xc398,0xc768,0xcb38)]==[b'VOL',b'PAN',b'GAIN'],'a frame on page 1 corrects stale page-3 names to VOL/PAN/GAIN')
for o in (0xc398,0xc768,0xcb38):u.mem_write(T+o+0x9c,b'\0')
call(u,C4['cue_present'],0,0,0,0)
check(all(u.mem_read(T+o+0x9c,1)[0]==0 for o in (0xc398,0xc768,0xcb38)),'correct names are left alone (no redraw flag)')
# From any other page TRACK returns to the remembered TRACK view, as native.
w32(u,ROOTUI+0x2b4,P)
key(8,5);check(pages==[(APPOBJ,5)] and u.mem_read(0x388001f0,1)[0]==0,'from another page TRACK opens the remembered TRACK view')
key(2,6);check(pages==[(APPOBJ,6)],'from MIXER TRACK opens the TRACK view')
w32(u,ROOTUI+0x2b4,T)
# The patches: TRACK is hardware button 1 (handler 0x08123ad8); MIXER's stays stock.
img=patched if not LOOPER_BUILD else (ROOT/'build'/'BLUEBOX-looper.BIN').read_bytes()
off=0x8123ad8-0x08040000
check(img[off+4:off+6]==bytes.fromhex('18e0'),'TRACK handler: bl ts_track_key; b 0x08123b10')
check(img[0x8123a9e-0x08040000:][:0x3a]==stock[0x8123a9e-0x08040000:][:0x3a],'MIXER button handler is stock')
# Through the native hardware-button dispatch (event 0xf9, button 1 = TRACK).
view_change(1);pages.clear()
u.mem_write(APPOBJ+0x739a,bytes([6]));u.mem_write(APPOBJ+0x739d,bytes([6]));u.mem_write(APPOBJ+0x73b0,b'\0');u.mem_write(APPOBJ+0x73b2,b'\0')
u.mem_write(TMP,struct.pack('<HHIII8x',0xf9,0,0x8148664,0,1))  # button index at +12
call(u,0x8123854,APPOBJ,TMP)
check(pages==[(APPOBJ,22)],'hardware TRACK press on the TRACK view goes to Side Chain')
u.mem_write(APPOBJ+0x739a,bytes([22]));w32(u,ROOTUI+0x2b4,P);pages.clear();u.mem_write(APPOBJ+0x73b0,b'\0')
call(u,0x8123854,APPOBJ,TMP);w32(u,ROOTUI+0x2b4,T);view_change(1)
check(pages==[(APPOBJ,6)] and flag()==2,'hardware TRACK press on Side Chain opens page 3')
u.mem_write(APPOBJ+0x739a,bytes([6]));pages.clear();u.mem_write(APPOBJ+0x73b0,b'\0')  # native busy flag, cleared by the app between presses
u.mem_write(TMP,struct.pack('<HHIII8x',0xf9,0,0x8148664,0,1))
call(u,0x8123854,APPOBJ,TMP)
check(pages==[] and flag()==3,'hardware TRACK press on page 3 opens page 4')
u.mem_write(APPOBJ+0x73b0,b'\0');u.mem_write(TMP,struct.pack('<HHIII8x',0xf9,0,0x8148664,0,1))
call(u,0x8123854,APPOBJ,TMP)
check(pages==[(APPOBJ,6)],'hardware TRACK press on page 4 returns to the TRACK view')
view_change(1)

# Audio core: link, defaults, events and processing on the native EQ node.
a,_,_=GF.gsetup(ch=3)
w32(a,0x24000004,0xc0200000);w32(a,0x24000000,0xc0400000)
call(a,D7['ts_allocate'])
TL=u32(a,0x38800654)
check(u32(a,0x38800650)==0x54534c31 and TL>=0xc0010000,'boot allocation publishes the 12-track block')
TRK=TL+3*96  # struct ts_track: state 36, params 28, owner, on, comp state 16, mode, thresh
def f(x):return struct.unpack('<f',struct.pack('<f',x))[0]
def params(q):return struct.unpack('<I6f',q.mem_read(TRK+36,28))
sig=[.6*math.sin(i*.2)*math.exp(-(i%32)/9.) for i in range(32)]
def ref(q,state,p,l,r):
 S0=0x24070000;q.mem_write(S0,state);q.mem_write(S0+0x40,p);q.mem_write(S0+0x100,struct.pack('<32f',*l));q.mem_write(S0+0x200,struct.pack('<32f',*r))
 q.reg_write(UC_ARM_REG_SP,0x2407f000-8);q.mem_write(0x2407f000-8,struct.pack('<ii',32,0))
 for reg,v in [(UC_ARM_REG_R0,S0),(UC_ARM_REG_R1,S0+0x40),(UC_ARM_REG_R2,S0+0x100),(UC_ARM_REG_R3,S0+0x200),(UC_ARM_REG_LR,RET|1)]:q.reg_write(reg,v)
 q.emu_start(G7['ts_process']|1,RET,count=3000000)
 return bytes(q.mem_read(S0+0x100,128))+bytes(q.mem_read(S0+0x200,128))
out,_=GF.gblock(a,sig,[x*.5 for x in sig],ch=3)
check(out==struct.pack('<32f',*sig)+struct.pack('<32f',*[x*.5 for x in sig]),'defaults are an exact bypass')
check(params(a)==struct.unpack('<I6f',struct.pack('<I6f',0,0,0,.5,.5,.5,1)),'defaults convert as Joebox '+str(params(a)))
GF.gblock(a,sig,sig,evs=[(ATTACK,1000),(SUSTAIN,-500),(MODEL,1),(OUTPUT,6000),(MIX,750)],ch=3)
out,_=GF.gblock(a,sig,sig,ch=3)
check(out==struct.pack('<32f',*sig)*2,'settings alone do nothing while TRANSIENT is off')
GF.gblock(a,sig,sig,evs=[(ON,1)],ch=3)
p=params(a)
check(p[0]==1 and p[1]==1.0 and p[2]==struct.unpack('<f',struct.pack('<f',-.5))[0] and abs(p[5]-(.5+6000/24082.4))<1e-6 and p[6]==f(750*f(.001)),'track events reach this track\'s shaper '+str(p))
same=True
for b in range(20):
 l=[x*(1+b%3) for x in sig];r=[x*.3 for x in l]
 state=bytes(a.mem_read(TRK,36));praw=bytes(a.mem_read(TRK+36,28))
 out,_=GF.gblock(a,l,r,ch=3)
 same&=out==ref(a,state,praw,l,r)
check(same,'native EQ node output equals the tested shaper, 20 blocks')
check(out!=struct.pack('<32f',*l)+struct.pack('<32f',*r),'shaper changes the audio when set')
GF.gblock(a,sig,sig,evs=[(ON,0)],ch=3)
out,_=GF.gblock(a,sig,sig,ch=3)
check(out==struct.pack('<32f',*sig)*2,'TRANSIENT off is an exact bypass again')
GF.gblock(a,sig,sig,evs=[(ATTACK,800)],foreign=4,ch=3)
check(params(a)[1]==1.0,'another track\'s event cannot change this track')
# Page 4 compressor on the native node: Off is an exact bypass; set, it equals
# the tested Joebox compressor (no lookahead), stereo and mono.
GF.gblock(a,sig,sig,evs=[(CTHR,-6000)],ch=3)
out,_=GF.gblock(a,sig,sig,ch=3)
check(out==struct.pack('<32f',*sig)*2,'Comp Off is an exact bypass, whatever the threshold')
check(struct.unpack('<f',a.mem_read(TRK+92,4))[0]==f(-6000*f(.001)),'Thresh converts as Joebox (-6 dB)')
def cref(q,state,mode,thr,l,r):
 S0=0x24070000;q.mem_write(S0,state);q.mem_write(S0+0x100,struct.pack('<32f',*l));q.mem_write(S0+0x200,struct.pack('<32f',*r))
 q.reg_write(UC_ARM_REG_SP,0x2407f000-8);q.mem_write(0x2407f000-8,struct.pack('<ii',32,0))
 q.reg_write(UC_ARM_REG_S0,struct.unpack('<I',struct.pack('<f',thr))[0])
 for reg,v in [(UC_ARM_REG_R0,S0),(UC_ARM_REG_R1,mode),(UC_ARM_REG_R2,S0+0x100),(UC_ARM_REG_R3,S0+0x200),(UC_ARM_REG_LR,RET|1)]:q.reg_write(reg,v)
 q.emu_start(G7['jc_process']|1,RET,count=3000000)
 return bytes(q.mem_read(S0+0x100,128)),bytes(q.mem_read(S0+0x200,128))
for cm,name in ((1,'Glue'),(5,'Limit')):
 GF.gblock(a,sig,sig,evs=[(CMODE,cm)],ch=3)
 same=True
 for b in range(20):
  l=[x*(1+b%4) for x in sig];r=[x*.4 for x in l]
  st=bytes(a.mem_read(TRK+72,16));out,_=GF.gblock(a,l,r,ch=3)
  cl,cr=cref(a,st,cm+1,f(-6000*f(.001)),l,r)
  same&=out==cl+cr
 check(same and max(abs(x) for x in struct.unpack('<64f',out))<=.9661,name+': node output equals the tested compressor, 20 stereo blocks, within -0.3 dBFS')
# Mono track: the detector sees L on both sides; only L is written.
m,_,_=GF.gsetup(ch=5,stereo=False);w32(m,0x24000004,0xc0200000);w32(m,0x24000000,0xc0400000);call(m,D7['ts_allocate'])
TM=u32(m,0x38800654)+5*96
GF.gblock(m,sig,None,evs=[(CMODE,5),(CTHR,-6000)],ch=5)
same=True
for b in range(10):
 l=[x*(1+b%4) for x in sig];st=bytes(m.mem_read(TM+72,16));out,_=GF.gblock(m,l,None,ch=5)
 cl,_=cref(m,st,6,f(-6000*f(.001)),l,l)
 same&=out[:128]==cl
check(same,'mono track: Limit equals the tested compressor with L on both sides')
GF.gblock(a,sig,sig,evs=[(CMODE,0)],ch=3);out,_=GF.gblock(a,sig,sig,ch=3)
check(out==struct.pack('<32f',*sig)*2,'Comp back to Off is an exact bypass')

# MIXER: the Gate button is Trans; its column is per-track TRANSIENT on/off.
def mtxt(b):return bytes(u.mem_read(b+0x65,12)).split(b'\0')[0]
for t in range(12):call(u,0x8120264,APP+0xc08+t*0x30,ON,0)
call(u,0x8120264,APP+0xe78,0x18c,0)
call(u,C4['ts_mix_setup'],P,1);call(u,S['gate_mix_select'],P,6)
check(struct.unpack('<H',u.mem_read(P+0xbca0,2))[0]==ON and mtxt(P+0xc3a4)==b'Trans','MIXER sends button reads Trans and selects TRANSIENT')
for sl in range(13):
 u.mem_write(TMP,struct.pack('<h',sl));call(u,C4['ts_column'],P,TMP)
kk=lambda c:P+0xbe0+c*0xd98+0x8f0
check(all(struct.unpack('<H',u.mem_read(kk(c)+0x94,2))[0]==ON for c in range(12)) and u.mem_read(kk(12)+0x2d4,1)[0]==1,'track columns bind TRANSIENT; Main is disabled')
for i,off in enumerate((0x40,0x328,0x610,0x8f8)):
 call(u,0x8120264,APP+0xc08+i*0x30,4,(-10000)&0xffffffff);call(u,0x813bbc4,4,(-10000)&0xffffffff,P+off)
def mturn(index,delta):
 clock[0]+=1000;w32(u,0x3001eb3c,clock[0])
 u.mem_write(TMP,struct.pack('<6I',0x32,0x8148664,0,index&0xffffffff,delta&0xffffffff,0));call(u,C4['ts_mix_event'],P,TMP)
commands.clear();mturn(0,40);mturn(1,40)
check([get(t,ON) for t in range(4)]==[1,1,0,0] and all(c[1]==ON for c in commands),'MIXER encoders 1-2 turn tracks 1-2 on, nothing else sent')
mturn(1,-40);check([get(t,ON) for t in range(3)]==[1,0,0],'left turn switches a track off')
check(all(get(i,4)==-10000 for i in range(4)),'Trans turns never change Vol (native base bindings)')
u.mem_write(TMP,struct.pack('<6I',0x6e,0x8148664,12,ON,1,0));call(u,C4['ts_mix_local'],P,TMP)
check(not any(c[0]==12 for c in commands),'Main edits are dropped')
u.mem_write(TMP,struct.pack('<6I',0x6e,0x8148664,5,ON,1,0));commands.clear();call(u,C4['ts_mix_local'],P,TMP)
check(get(5,ON)==1 and commands==[(5,ON,1)],'a touched MIXER switch commits once for its track')
print(str(H.checks)+' TRANSIENT button (TRACK and MIXER), page 3 shaper and page 4 compressor checks passed (emulator); hardware test required.')
