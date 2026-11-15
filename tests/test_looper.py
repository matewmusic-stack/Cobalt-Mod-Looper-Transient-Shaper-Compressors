"""FX1 Phrase Looper on the real patched firmware, under Unicorn.

    LOOPER=1 python3 tests/test_looper.py /path/to/stock/BLUEBOX.BIN

Runs build/BLUEBOX-looper.BIN (checked against build/looper_manifest.json).
Actual firmware code: the stock desktop delay constructor and graph hook, the
native FX1 event queue and delay body, the compiled looper (M7); and on the
M4 side the real parameter definitions and tag tables, the auto-mute and
button reset (lp_main), the tempo publisher (cue_ui_tick) and the FX1 title
call site. Stubbed: the SDRAM bump allocator (bounded model), the downstream
graph node, the native knob call SC_KNOB (recorded and applied to the table,
as test_scenes.py does) and gate_ui_tick. Not covered: STM32 timing, the
caches shared between the two cores, the M4->M7 event delivery, the screen,
the SD card and sound.
"""
import os
if os.environ.get('LOOPER')!='1':
 print('SKIP Phrase Looper checks: run with LOOPER=1 after LOOPER=1 ./build.sh');raise SystemExit(0)
from delay_fixture import *
import firmware_harness as H

GS=0x38800000;PL=0x38800ea0;TEMPO=0x38800ee0;SESSION=0x300173d0
MODE,LEVEL,CLEAR,BARS,DUB,SYNC,REC,STOP=0x1a0,0x1a1,0x1a2,0x1a3,0x1a4,0x1a5,0x1a6,0x1ba
MUTE,FX1SEND=0x160,0xda
EMPTY,ARMED,RECORDING,PLAYING,STOPPED,DUBBING=range(6)
PL_MAGIC=0x504c4f32;PL_CAP_MAX=384000;PL_BYTES=PL_CAP_MAX*4;G_BYTES=768000;G_FRAMES=G_BYTES//4;RESERVE=4<<20
XB=224  # stretch + sync state kept after the loop audio (PLT_BYTES)
# Loop audio is 16-bit stereo, +/-2.0 full scale: frame k is 4 bytes at ptr+4k.
def q16(u,a,n):return struct.unpack('<%dh'%(2*n),u.mem_read(a,4*n))
S4=M['symbols']['4'];C4=M['symbols']['cue4'];PC=M['symbols']['pcm4']
LOOPER_ON=INITIAL+[(MODE,1),(LEVEL,1000),(CLEAR,0),(BARS,1),(DUB,1000),(SYNC,0),(REC,0),(STOP,0)]
def press(pid):return [(pid,1),(pid,0)]   # UI press, then the M4 reset, in one block

def lsetup(limit=0xc2000000,nan=True):
 """delay_fixture.dsetup with a chosen arena limit and an allocation log."""
 u=machine(patched);heap=[0xc0010000];allocs=[]
 def allocate(u):
  size=u.reg_read(UC_ARM_REG_R0);a=heap[0]
  assert a+size<=limit,'allocation past the arena limit: %d bytes at %s'%(size,hex(a))
  heap[0]=(a+size+15)&~15;w32(u,0x24000004,heap[0]);allocs.append((a,size));u.reg_write(UC_ARM_REG_R0,a)
 w32(u,0x24000000,limit);w32(u,0x24000004,heap[0])
 stub(u,0x80412a4,allocate)
 u.reg_write(UC_ARM_REG_R0,DOBJ);u.reg_write(UC_ARM_REG_SP,0x2407f000);u.reg_write(UC_ARM_REG_LR,RET|1)
 u.emu_start(0x8050f1b,0x8050f1e,count=50000000)
 assert u.reg_read(UC_ARM_REG_PC)==0x8050f1e,'native constructor did not return'
 w32(u,DOBJ+0x18,0x14);u.mem_write(DOBJ+0x1e,struct.pack('<H',13));u.mem_write(DOBJ+0x273,b'\0')
 w32(u,CTX,0x24040000)
 for addr,buf in [(DBUS,BUF),(CTX+0x150e4+16*20,BUF+0x400),(CTX+0x15260,BUF+0x600),(CTX+0x15274,BUF+0x800)]:
  u.mem_write(addr,struct.pack('<IIIIBBxx',32,32,buf,buf+0x100,0,1))
 w32(u,DOBJ+8,NEXT);w32(u,NEXT,VT);w32(u,VT+12,NEXT_FN|1)
 stub(u,NEXT_FN,lambda u:u.reg_write(UC_ARM_REG_R0,7))
 ptr=u32(u,GS+8)
 if nan and ptr:u.mem_write(ptr,b'\x5a\x5a'*(pl(u)['cap']*2))   # sentinel: never a recorded value here
 return u,allocs

def pl(u):
 a=struct.unpack('<8I',u.mem_read(PL,32));b=struct.unpack('<3bBIfffII',u.mem_read(PL+32,28))
 d=dict(zip(['magic','owner','cap','state','len','pos','bars','seq'],a))
 d.update(last=b[:3],presses=b[3],transport=b[4],gain=b[5],level=b[6],dub=b[7],bpm_x100=b[8],free_kb=b[9]);return d
def tempo(u,raw_bpm,playing,muted=None):
 m=u32(u,TEMPO+24) if muted is None else muted
 u.mem_write(TEMPO,struct.pack('<IiIIIIII',0x504c5431,raw_bpm,playing,0,0,0,m,0))
def inp(k):return signal(.5,k,431),signal(.3,k,733)
K=[0]
# Simulated sequencer: the song position (960 ticks per beat) in the engine
# object the firmware reads (*(0x3000a894)+0x78b0 with the app flag +0x7408
# set), written before each audio block and advanced at SEQ['bpm'].
SEQ={'on':False,'t':0.0,'bpm':120.0,'engine':0}
def seq_write(u):
 if SEQ['engine']:w32(u,SEQ['engine']+0x78b0,int(SEQ['t'])&0xffffffff);w32(u,SEQ['engine']+0x78b4,0)
def step(u,evs=()):
 seq_write(u)
 l,r=inp(K[0]);out,_=dblock(u,l,r,evs);K[0]+=1
 if SEQ['on']:SEQ['t']+=32*SEQ['bpm']*960/(60*48000)
 return struct.unpack('<64f',out)
def run(u,n):
 for _ in range(n):o=step(u)
 return o
def finite(o):return all(math.isfinite(x) for x in o)
def f32r(x):return struct.unpack('<f',struct.pack('<f',x))[0]

# ----- M4 side in the same machine: real definitions and tag tables
def taddr(cell):return SESSION+(0xc08+cell*0x30 if cell<12 else 0xe48+(cell-0x14)*0x10)
knobs=[]
def m4(u):
 heap=[0xc1800000]
 def alloc(u):a=heap[0];heap[0]=(a+u.reg_read(UC_ARM_REG_R0)+15)&~15;u.reg_write(UC_ARM_REG_R0,a)
 stub(u,0x8103128,alloc);call(u,0x8134cb8,0)     # definitions; also runs sc_boot/lp_boot
 def table_init(addr,kind):
  u.mem_write(0x24010000,bytes([kind]));call(u,0x81202b8,addr,0x24010000);w32(u,addr,0x814ae3c)
 for c in range(12):table_init(taddr(c),1)
 table_init(taddr(0x14),4);table_init(SESSION+0xe58,5);table_init(SESSION+0xe68,8)
 def knobpath(u):
  cell=struct.unpack('<H',u.mem_read(u.reg_read(UC_ARM_REG_R1),2))[0];pid=u.reg_read(UC_ARM_REG_R2);v=u.reg_read(UC_ARM_REG_R3)
  knobs.append((cell,pid,v))
  base=u32(u,taddr(cell)+4);n=struct.unpack('<H',u.mem_read(taddr(cell)+10,2))[0]
  for i in range(n):
   if struct.unpack('<H',u.mem_read(base+8*i,2))[0]==pid:w32(u,base+8*i+4,v)
 stub(u,0x8124b44,knobpath)
 stub(u,S4['gate_ui_tick'],lambda u:None)
def get(u,cell,pid):return struct.unpack('<i',struct.pack('<I',call(u,0x8120234,taddr(cell),pid)))[0]
def put(u,cell,pid,v):call(u,0x8120264,taddr(cell),pid,v&0xffffffff)
def lp_main(u,loading=0):knobs.clear();call(u,PC['lp_main'],loading);return list(knobs)
LABEL=0x24050000;STR=0x24050100
def title(u):
 u.mem_write(STR,b'Delay\0');call(u,0x812ac38,LABEL,STR,end=0x812ac3c)
 return bytes(u.mem_read(LABEL+0x31,32)).split(b'\0')[0].decode()

# ================================================================ allocation
u,allocs=lsetup()
p=pl(u);ptr=u32(u,GS+8);sizes=[s for a,s in allocs]
check(PL_BYTES+XB in sizes and ptr==[a for a,s in allocs if s==PL_BYTES+XB][0],'roomy arena: looper buffer of %d bytes (2 bars at 60 BPM) allocated at FX1 construction'%PL_BYTES)
check(p['magic']==PL_MAGIC and p['cap']==PL_CAP_MAX and p['state']==EMPTY and p['last']==(-1,-1,-1),'looper reset at construction: full capacity, empty, no button history')
i=sizes.index(PL_BYTES+XB)
check(len(sizes)>i+1,'FX2 Shoegaze still allocates after the looper buffer')
cursor=[a for a,s in allocs if s==PL_BYTES+XB][0]
u2,a2=lsetup(limit=cursor+PL_BYTES+XB+RESERVE-1)
SZ=(PL_BYTES+XB-1)&~31
check(SZ in [s for a,s in a2] and pl(u2)['cap']==(SZ-XB)//4,'less room: the looper takes what fits while 4 MB stay free (%d bytes)'%SZ)
u2,a2=lsetup(limit=cursor+G_BYTES+XB+RESERVE)
check(G_BYTES+XB in [s for a,s in a2] and pl(u2)['cap']==G_FRAMES and pl(u2)['free_kb']==(G_BYTES+XB+RESERVE)//1024,'no room above the reserve: the tested %d-byte buffer, 4 s of 16-bit stereo'%G_BYTES)
tempo(u2,120,0,0);K[0]=0
step(u2,LOOPER_ON+[(BARS,2)]);run(u2,10);step(u2,press(REC))
check(pl(u2)['len']==192000 and pl(u2)['bars']==2,'tested buffer: 2 bars at 120 BPM now fit (192000 frames)')
step(u2,press(CLEAR));tempo(u2,100,0);step(u2,press(REC))
check(pl(u2)['len']==115200 and pl(u2)['bars']==1,'tested buffer at 100 BPM: drops to 1 bar')
u3,a3=lsetup(limit=cursor+PL_BYTES+XB+RESERVE)
check(PL_BYTES+XB in [s for a,s in a3],'exactly buffer + 4 MB free still takes the full looper buffer')
u4,a4=lsetup(limit=cursor+G_BYTES-1)
w32(u4,CTX+0x1529c+0x600,0);o=step(u4,LOOPER_ON)
msgs=[struct.unpack('<B7xIHHiI',u4.mem_read(CTX+0x1529c+i*24,24)) for i in range(u32(u4,CTX+0x1529c+0x600))]
check(u32(u4,GS+8)==0 and finite(o) and any(m[2]==MODE and m[4]==0 for m in msgs),'no SDRAM: no buffer requested past the limit; choosing the looper falls back to Delay via the UI queue')

# ====================================================== record and playback
m4(u);tempo(u,240,0,0);K[0]=0
put(u,0x14,MODE,1)
watch={'hi':0,'lo':None}
def on_write(u,access,address,size,value,_):
 off=address-ptr
 if PL_BYTES<=off<PL_BYTES+XB:return   # tempo-follow state, not loop audio
 watch['hi']=max(watch['hi'],off+size)
 if watch['lo'] is None or off<watch['lo']:watch['lo']=off
u.hook_add(UC_HOOK_MEM_WRITE,on_write,begin=ptr,end=ptr+PL_BYTES+0x40000-1)
bad_reads=[]
def on_read(u,access,address,size,value,_):
 # Recorded frames: the loop length (set when a take starts or closes) or
 # the record position, whichever is larger; the end-of-take fade reads
 # back the last frames of the take before the state moves on.
 n=max(u32(u,PL+16),u32(u,PL+20))
 if PL_BYTES<=address-ptr<PL_BYTES+XB:return   # tempo-follow state
 if address-ptr>=n*4:bad_reads.append((address-ptr,u32(u,PL+12),u32(u,PL+16),u32(u,PL+20)))
rh=u.hook_add(UC_HOOK_MEM_READ,on_read,begin=ptr,end=ptr+PL_BYTES+XB-1)
step(u,[e if e!=(REC,0) else (REC,1) for e in LOOPER_ON])   # a project saved with REC=1: its only REC value latches
check(pl(u)['state']==EMPTY and pl(u)['last']==(1,0,0),'values at load latch: a saved REC=1 does not start a take')
step(u,[(REC,0)]);run(u,10)
check(abs(f32(u,GS+0x48)-1.)<1e-6 and title(u)=='Looper','looper faded in; FX1 title reads Looper')
start=K[0];o=step(u,press(REC))
p=pl(u)
check(p['state']==RECORDING and p['len']==48000 and p['bars']==1 and p['pos']==32,'one REC press (on, then reset off in the same block) records 1 bar at 240 BPM')
check(all(x==0. for x in o),'FX1 return is silent while recording: the source is heard in its own channel')
check(title(u)=='REC 1/1','title shows REC 1/1')
o=run(u,1499)
check(pl(u)['state']==PLAYING and pl(u)['pos']==0 and title(u)=='PLAY','capture turns into playback after exactly 1500 blocks; title PLAY')
mism=0;far=0
for j in range(1500):
 stored=q16(u,ptr+j*32*4,32);o=step(u);l,r=inp(start+j)
 for i in range(32):
  t=j*32+i
  if t>=240 and (o[i]!=f32r(stored[2*i]/16384) or o[32+i]!=f32r(stored[2*i+1]/16384)):mism+=1   # after the 5 ms play fade-in
  if 240<=t<48000-240 and (abs(o[i]-l[i])>.5/16384+1e-7 or abs(o[32+i]-r[i])>.5/16384+1e-7):far+=1
check(mism==0,'after its 5 ms fade-in, playback outputs the stored loop sample for sample (%d mismatches)'%mism)
check(far==0,'the stored loop is the take within half a 16-bit step, away from the 5 ms edge ramps (%d outside)'%far)
check(watch['lo']==0 and watch['hi']==48000*4,'recording wrote exactly the loop region (16-bit stereo)')
step(u,[(LEVEL,500)]);pos=pl(u)['pos'];o=step(u)
rec=[v/16384 for v in q16(u,ptr+pos*4,32)[0::2]]
check(max(abs(o[i]-.5*rec[i]) for i in range(32))<1e-6,'Level 50% plays the loop at half volume, with no dry input on the FX1 return')
step(u,[(LEVEL,1000)])

# ============================================================= auto-mute (M4)
for cell,send,mute in [(0,500,0),(1,0,0),(2,1000,0),(3,300,1)]:put(u,cell,FX1SEND,send);put(u,cell,MUTE,mute)
calls=lp_main(u)
check(sorted(calls)==[(0,MUTE,1),(2,MUTE,1)],'loop playing: tracks feeding FX1 are muted through the native knob call (not tracks without a send or already muted) %s'%calls)
check(u32(u,TEMPO+24)&~0x60000000==0x80000005 and lp_main(u)==[],'muted tracks are remembered and muting runs once per playback')
# Sync is locked while a loop exists: a change is put back.
s0=get(u,0x14,SYNC);put(u,0x14,SYNC,1-s0)
check(lp_main(u)==[(0x14,SYNC,s0)] and lp_main(u)==[],'a loop exists: a Sync change is put back at once (locked)')
# REC reads OVDUB once a loop exists, while the looper page shows.
LP_PANEL=0xc1c00000;labels=[]
stub(u,0x813820c,lambda u:labels.append(bytes(u.mem_read(u.reg_read(UC_ARM_REG_R1),8)).split(b'\0')[0].decode()))
u.mem_write(LP_PANEL,bytes(0x100b0+13*0x1d4));u.mem_write(LP_PANEL+0xc3a4,struct.pack('<h',0x14))
RECW=LP_PANEL+0x100b0+8*0x1d4;u.mem_write(RECW+0xfa,struct.pack('<H',REC));u.mem_write(RECW+0x65,b'REC\0')
w32(u,0x38800b04,LP_PANEL);w32(u,0x38800b94,u32(u,0x3001eb3c)-1000)
lp_main(u);check(labels==[],'page not showing: the REC button is left alone')
w32(u,0x38800b94,u32(u,0x3001eb3c));lp_main(u)
check(labels==['OVDUB'],'a loop exists, looper page showing: the REC button reads OVDUB (%s)'%labels)
u.mem_write(RECW+0x65,b'OVDUB\0');labels.clear();lp_main(u);check(labels==[],'... set once, not every tick')
put(u,0,MUTE,0);check(lp_main(u)==[],'a track you unmute during playback stays unmuted')
step(u,press(REC))
check(pl(u)['state']==DUBBING and title(u)=='DUB','REC while playing starts overdub; title DUB')
check(lp_main(u)==[(2,MUTE,0)] and u32(u,TEMPO+24)&~0x60000000==0,'overdub unmutes the sources the looper muted, so you hear what you play')
before=bytes(u.mem_read(ptr,48000*4));run(u,1500)
after=q16(u,ptr,48000)
check(bytes(u.mem_read(ptr,48000*4))!=before and max(abs(x) for x in after)<=32767 and min(after)>=-32767,'overdub layers input into the loop, saturating at +/-2.0 (no wrap-around)')
step(u,press(REC))
check(pl(u)['state']==PLAYING and sorted(lp_main(u))==[(0,MUTE,1),(2,MUTE,1)],'REC again ends overdub and the sources are muted again')
put(u,0x14,REC,1)
check((0x14,REC,0) in lp_main(u) and get(u,0x14,REC)==0,'pedal buttons are set back off by the M4 after a press')

# ============================================================== stop, clear
step(u,press(STOP))
check(pl(u)['state']==STOPPED and title(u)=='STOP' and sorted(lp_main(u))==[(0,MUTE,0),(2,MUTE,0)],'STOP stops, title STOP, sources unmuted')
o=run(u,10)
check(all(x==0. for x in o) and pl(u)['pos']==0,'stopped loop is silent and rewound')
step(u,press(STOP));o=run(u,20)
loop20=tuple(f32r(v/16384) for v in q16(u,ptr+20*32*4,32)[0::2])   # the (overdubbed) loop at block 20
check(pl(u)['state']==PLAYING and o[:32]==loop20,'STOP again plays from the start of the loop')
lp_main(u)
check(lp_main(u,loading=1)==[] and u32(u,TEMPO+24)==0,'a project load forgets the mute record without unmuting anything')
step(u,press(STOP));check(lp_main(u)==[],'after a load, stopping does not unmute tracks of the new project')
step(u,press(REC))
check(pl(u)['state']==DUBBING and pl(u)['pos']==32,'REC (OVDUB) on a stopped loop overdubs from the start');step(u,press(REC))
step(u,press(CLEAR))
check(pl(u)['state']==EMPTY and pl(u)['len']==0 and title(u)=='Looper','CLEAR empties the loop; title back to Looper')
labels.clear();w32(u,0x38800b94,u32(u,0x3001eb3c));lp_main(u)
check(labels==['REC'],'no loop: the button reads REC again (%s)'%labels)
s0=get(u,0x14,SYNC);put(u,0x14,SYNC,1-s0)
check(lp_main(u)==[] and get(u,0x14,SYNC)==1-s0,'no loop: Sync can be changed');put(u,0x14,SYNC,s0);lp_main(u)
w32(u,0x38800b04,0)
o=run(u,10);check(all(x==0. for x in o),'cleared looper is silent')
t=[]
for v in (12802,9950,0):w32(u,PL+36,v);t.append(title(u))
check(t==['Lp128.0','Lp99.5','Looper'],'empty with a measured song tempo: title shows it (%s)'%t)

# =================================================== takes closed early
step(u,press(REC));run(u,400);step(u,press(REC))
check(pl(u)['state']==PLAYING and pl(u)['len']==401*32,'REC during a take closes the loop at once (%d frames)'%(401*32))
step(u,press(CLEAR));step(u,press(REC));run(u,400);step(u,press(STOP))
check(pl(u)['state']==STOPPED and pl(u)['len']==401*32,'STOP during a take keeps it, stopped')
step(u,press(CLEAR));step(u,press(REC));step(u,press(REC))
check(pl(u)['state']==EMPTY,'a take shorter than 20 ms is dropped')
step(u,press(REC));run(u,100);step(u,press(REC)+press(STOP))
check(pl(u)['state']==STOPPED,'REC and STOP in the same block: STOP wins')
step(u,press(CLEAR))

# ======================== sync: real M4 tempo publisher feeds the M7 looper
ENGINE=0x24010000;NOW=0x3001eb3c
w32(u,0x3000a894,ENGINE);u.mem_write(0x300173d0+0x7408,b'\x01')   # app flag: header reads +0x78b0
SEQ.update(engine=ENGINE,on=False,t=0.0)
call(u,0x8120264,SESSION+0xe68,0x85,120)
def m4_tick(now,pos=None):
 w32(u,NOW,now)
 if pos is not None:w32(u,ENGINE+0x78b0,pos);w32(u,ENGINE+0x78b8,0)
 call(u,C4['cue_ui_tick'],0x24060000,0x24060100)
def sync_state():
 v=struct.unpack('<IIiiffiiIIii',u.mem_read(ptr+pl(u)['cap']*4+96,48))
 return dict(zip(['magic','still','last','qi','qf','r','start','end','lt','flags','bar','cycle'],v))
u.mem_write(TEMPO,bytes(32));m4_tick(5000,0)
t=struct.unpack('<IiII',u.mem_read(TEMPO,16))
check(t[0]==0x504c5431 and t[1]==120 and t[2]==0,'M4 publishes the real project BPM setting (120, stored as plain BPM) and a stopped sequencer')
run(u,70)                                         # stopped long enough to register
step(u,[(BARS,2),(SYNC,1)]);step(u,press(REC))
check(pl(u)['state']==ARMED and title(u)=='ARMED','Sync on, sequencer stopped: REC arms; title ARMED')
step(u,press(REC));check(pl(u)['state']==EMPTY,'REC again cancels the armed take')
step(u,press(REC))
for n in range(30):m4_tick(5010+n);o=step(u)
check(pl(u)['state']==ARMED and all(x==0. for x in o),'armed looper waits silently')
SEQ.update(on=True,t=0.0)                          # sequencer starts at bar 1
k=0
while pl(u)['state']==ARMED and k<8:step(u);k+=1
p=pl(u);sy=sync_state()
check(p['state']==RECORDING and p['bars']==2 and sy['start']==0 and k<=2,'sequencer start begins a 2-bar take on bar 1, within %d blocks'%k)
m4_tick(5100,int(SEQ['t']))
check(struct.unpack('<I',u.mem_read(TEMPO+8,4))[0]==1,'M4 sees the sequencer playing')
run(u,2000);check(title(u)=='REC 1/2','title counts bars while recording (REC 1/2)')
run(u,2000);check(title(u)=='REC 2/2','... and REC 2/2')
while pl(u)['state']==RECORDING and k<20000:step(u);k+=1
p=pl(u);sy=sync_state()
# A start is seen when the position first moves, one block after the downbeat:
# such a take begins up to ~1 ms late (a bar-line take armed while running is exact).
check(p['state']==PLAYING and sy['flags']&2 and sy['lt']==7680 and 192000-64<=p['len']<=192000,'the take closes on bar 3: 2 bars of song time less the start-detection delay, %d samples (2 bars = 192000), locked'%p['len'])
# REC while running mid-bar waits for the next bar line
step(u,press(CLEAR));step(u,[(SYNC,0)])
SEQ['t']+=1000.0
for _ in range(3):step(u)
step(u,press(REC))
check(pl(u)['state']==ARMED,'sequencer running mid-bar, Sync off: REC still waits for the bar line')
k=0
while pl(u)['state']==ARMED and k<4000:step(u);k+=1
sy=sync_state()
check(pl(u)['state']==RECORDING and sy['start']%3840==0 and sy['start']>SEQ['t']-32*0.04*3,'... and starts on it (tick %d)'%sy['start'])
step(u,press(CLEAR))
SEQ['on']=False;run(u,70)                          # stop; let the stop register

# ================================================== Stretch switch (M7 side)
for v,name in [(1,'Vari'),(2,'Keep'),(9,'Keep (clamped)'),(0,'Off')]:
 step(u,[(0x1bb,v)])
 check(u32(u,PL+60)==min(v,2),'Stretch event %d sets the looper to %s'%(v,name))
# ================================================== BPM and loop lengths
m=u32(u,PL+36)
check(abs(m-12000)<=3,'after the sequencer stops, the looper keeps the tempo it measured from the song position (%.2f)'%(m/100))
tempo(u,100,0);step(u)
check(u32(u,PL+36)==0,'changing the project BPM while stopped hands the tempo back to it')
lengths={}
for raw,bars in [(120,2),(1200,2),(60,2),(40,2),(250,1),(0,1)]:
 step(u,press(CLEAR)+[(BARS,bars)]);tempo(u,raw,0);step(u,press(REC));lengths[(raw,bars)]=(pl(u)['len'],pl(u)['bars'])
print('INFO loop lengths',lengths)
check(lengths[(120,2)]==lengths[(1200,2)]==(192000,2) and lengths[(60,2)]==(384000,2),'2 bars at 120 BPM = 4 s (plain or tenths); 2 bars at 60 BPM fill the buffer')
check(lengths[(40,2)]==(288000,1) and lengths[(250,1)]==(46080,1) and lengths[(0,1)]==(96000,1),'40 BPM drops to 1 bar; 250 BPM 1 bar = 0.96 s; no tempo = 120 BPM')
check(watch['hi']<=PL_BYTES,'no write ever went past the looper buffer (FX2 memory untouched)')
check(not bad_reads,'the looper never read loop memory outside the recorded frames %s'%bad_reads[:4])
u.hook_del(rh)
# TOOLS middle field: longest loop and free SDRAM at boot
texts=[];h=stub(u,0x813820c,lambda u:texts.append(bytes(u.mem_read(u.reg_read(UC_ARM_REG_R1),24)).split(b'\0')[0].decode()))
call(u,S4['dly_tools_version'],0x24050000,0x24050200);u.hook_del(h)
fr=pl(u)['free_kb']*10//1024
want='Cblt L8.0s F%d.%dM'%(fr//10,fr%10)
check(texts[-1]==want,'TOOLS shows the longest loop and the free SDRAM: %s'%texts[-1])

# ============================================ MIDI clock tempo (M4 -> M7)
def clock_line(raw,clock_x100,clock_at=0):
 u.mem_write(TEMPO,struct.pack('<IiIIIIII',0x504c5431,raw,0,clock_at,0,0,0,clock_x100))
for clk,want in [(10000,115200),(9873,1152000000//9873),(25000,46080)]:
 step(u,press(CLEAR)+[(BARS,1)]);clock_line(120,clk);step(u,press(REC))
 check(pl(u)['len']==want and pl(u)['bpm_x100']==clk,'project at 120 BPM, MIDI clock at %.2f BPM: the take follows the clock (%d frames)'%(clk/100,want))
step(u,press(CLEAR));clock_line(120,1500);step(u,press(REC))
check(pl(u)['len']==96000,'an out-of-range clock tempo (15 BPM) is ignored: project BPM is used')
# The real UI tick drops the clock tempo 300 ms after the last tick.
call(u,0x8120264,SESSION+0xe68,0x85,120)
clock_line(120,10000,clock_at=7000);m4_tick(7300,0)
check(struct.unpack('<I',u.mem_read(TEMPO+28,4))[0]==10000,'clock tempo kept 300 ms after the last tick')
m4_tick(7301,0)
check(struct.unpack('<I',u.mem_read(TEMPO+28,4))[0]==0,'clock tempo dropped once ticks stop for more than 300 ms')
step(u,press(CLEAR));step(u,press(REC))
check(pl(u)['len']==96000,'without clock the next take uses the project BPM again')
step(u,press(CLEAR));tempo(u,120,0)

# ======================================================== CPU (relative)
step(u,press(CLEAR));tempo(u,240,1)
count=[0]
def tick(u,a,n,d):count[0]+=1
h=u.hook_add(UC_HOOK_CODE,tick,begin=0x08000000,end=0x081fffff)
def cost(evs=()):count[0]=0;step(u,evs);return count[0]
step(u,press(REC));rec=cost()
run(u,1500);play=cost()
step(u,press(REC));dub=cost()
step(u,[(MODE,5)]);run(u,10);delay=cost()
u.hook_del(h)
# Reference: the hardware-tested Granular this mode replaces, on the Cobalt-only image.
g,_,_=dsetup(H.p.transform(stock));gc=[0]
for n in range(400):dblock(g,signal(.5,n,431),evs=INITIAL+[(MODE,1),(0x1a3,4),(0x1a4,500),(0x4a,7)] if n==0 else [])
hg=g.hook_add(UC_HOOK_CODE,lambda u,a,n,d:gc.__setitem__(0,gc[0]+1),begin=0x08000000,end=0x081fffff)
gran=[]
for n in range(400,410):gc[0]=0;dblock(g,signal(.5,n,431));gran.append(gc[0])
g.hook_del(hg)
print('INFO emulated instructions per 32-frame block: record %d, play %d, overdub %d; plain Delay %d; Granular (tested) %d-%d'%(rec,play,dub,delay,min(gran),max(gran)))
check(max(rec,play,dub)<min(gran),'every looper block executes fewer instructions than the hardware-tested Granular it replaces (relative, not hardware cycles)')

# ==================================================== leaving the mode
check(pl(u)['state']==EMPTY and pl(u)['last']==(-1,-1,-1),'plain Delay drops the loop and the button history at once')
step(u,[(MODE,1),(REC,1)]);o=run(u,10)
check(pl(u)['state']==EMPTY and all(x==0. for x in o),'back in the looper with a button left on: empty and silent, no surprise take')
step(u,[(REC,0)]);step(u,press(REC));run(u,50)
step(u,[(MODE,4),(0x1aa,100)])
energy=0.;ok=True
for _ in range(400):o=step(u);ok=ok and finite(o);energy+=sum(x*x for x in o)
check(pl(u)['state']==EMPTY and u32(u,GS+0x34)!=0 and ok and energy>1.,'switching to Reverse fades the looper out, resets the ring, and Reverse plays from fresh history')
put(u,0x14,MODE,4)
check(lp_main(u)==[],'outside the looper the M4 leaves buttons and mutes alone')
print('PASSED',H.checks,'Phrase Looper firmware checks; device timing, shared-cache behaviour, the screen and sound remain hardware tests.')
