"""FX1 Phrase Looper on the real patched firmware, under Unicorn.

    LOOPER=1 python3 tests/test_looper.py /path/to/stock/BLUEBOX.BIN

Runs build/BLUEBOX-looper.BIN (checked against build/looper_manifest.json).
Actual firmware code: the stock desktop delay constructor and graph hook, the
native parameter queue and delay body, the compiled looper (M7), the M4 tempo
publisher (cue_ui_tick) and the native UI message queue. Stubbed: the SDRAM
bump allocator (a bounded model of it), the downstream graph node, the M4
settings getter for BPM, and gate_ui_tick (unrelated M4 work chained after
the publisher). Not covered: real STM32 timing, caches shared between the
two cores, SD/recording, the physical UI and sound.
"""
import os
if os.environ.get('LOOPER')!='1':
 print('SKIP Phrase Looper checks: run with LOOPER=1 after LOOPER=1 ./build.sh');raise SystemExit(0)
from delay_fixture import *
import firmware_harness as H

GS=0x38800000;PL=0x38800ea0;TEMPO=0x38800ee0;UIQ=CTX+0x1529c
MODE,WET,CLEAR,BARS,DUB,SYNC,PLAY=0x1a0,0x1a1,0x1a2,0x1a3,0x1a4,0x1a5,0x1a6
EMPTY,ARMED,REC,PLAYING,STOP=range(5)
PL_CAP_MAX=384000;G_CAP=96000;PL_BYTES=PL_CAP_MAX*8;G_BYTES=G_CAP*8;RESERVE=4<<20
S4=M['symbols']['4'];C4=M['symbols']['cue4']
LOOPER_ON=INITIAL+[(MODE,1),(WET,1000),(CLEAR,0),(BARS,1),(DUB,0),(SYNC,0),(PLAY,0)]

def lsetup(limit=0xc2000000,nan=True):
 """delay_fixture.dsetup with a chosen arena limit and an allocation log."""
 u=machine(patched);heap=[0xc0010000];nodes=[];allocs=[]
 def allocate(u):
  size=u.reg_read(UC_ARM_REG_R0);a=heap[0]
  # The native allocator asserts past its limit: the firmware must never ask.
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
 def nextnode(u):nodes.append(1);u.reg_write(UC_ARM_REG_R0,7)
 stub(u,NEXT_FN,nextnode)
 ptr=u32(u,GS+8)
 # Unrecorded loop memory reads as NaN: any read of it poisons the output.
 if nan and ptr:u.mem_write(ptr,struct.pack('<f',float('nan'))*(pl(u)['cap']*2))
 return u,nodes,allocs

def pl(u):
 v=struct.unpack('<IIIIIIiiIfffII',u.mem_read(PL,56))
 return dict(zip(['magic','owner','cap','state','len','pos','play_seen','clear_seen','transport','gain','wet','overdub','bpm_x10','seq'],v))
def tempo(u,raw_bpm,playing):
 u.mem_write(TEMPO,struct.pack('<IiIIIIII',0x504c5431,raw_bpm,playing,0,0,0,0,0))
def inp(k):return signal(.5,k,431),signal(.3,k,733)
def step(u,k,evs=()):
 l,r=inp(k);out,_=dblock(u,l,r,evs);return struct.unpack('<64f',out)
def ui_messages(u):
 n=u32(u,UIQ+0x600)
 return [struct.unpack('<B7xIHHiI',u.mem_read(UIQ+i*24,24)) for i in range(n)]
def finite(o):return all(math.isfinite(x) for x in o)
def f32r(x):return struct.unpack('<f',struct.pack('<f',x))[0]

# ---------------------------------------------------------------- allocation
u,nodes,allocs=lsetup()
p=pl(u);ptr=u32(u,GS+8)
sizes=[s for a,s in allocs]
check(PL_BYTES in sizes and ptr==[a for a,s in allocs if s==PL_BYTES][0],'roomy arena: looper buffer of %d bytes (2 bars at 60 BPM) allocated at FX1 construction'%PL_BYTES)
check(p['magic']==0x504c4f31 and p['cap']==PL_CAP_MAX and p['state']==EMPTY and p['play_seen']==-1,'looper state reset at construction with full capacity, empty, nothing latched')
i=sizes.index(PL_BYTES)
check(len(sizes)>i+1,'FX2 Shoegaze still allocates after the looper buffer (%d bytes)'%sizes[i+1] if len(sizes)>i+1 else 'FX2 allocation present')
cursor=[a for a,s in allocs if s==PL_BYTES][0]
print('INFO cursor before FX1 looper allocation',hex(cursor),'allocations',sizes)

# Tight arena: 1 byte short of buffer + reserve -> hardware-tested Granular size.
u2,_,a2=lsetup(limit=cursor+PL_BYTES+RESERVE-1)
check(G_BYTES in [s for a,s in a2] and PL_BYTES not in [s for a,s in a2] and pl(u2)['cap']==G_CAP,'without 4 MB spare the looper falls back to the tested %d-byte buffer'%G_BYTES)
tempo(u2,120,0);k=0
for ev in [LOOPER_ON+[(BARS,2)],[],[(PLAY,1)]]:step(u2,k,ev);k+=1
check(pl(u2)['len']==96000,'fallback buffer: 2 bars at 120 BPM drops to 1 bar (96000 frames)')
# Exact boundary: enough for buffer + reserve.
u3,_,a3=lsetup(limit=cursor+PL_BYTES+RESERVE)
check(PL_BYTES in [s for a,s in a3],'exactly buffer + 4 MB free still takes the full looper buffer')
# No room even for the Granular size: mode 1 falls back to Delay via the UI queue.
u4,_,a4=lsetup(limit=cursor+G_BYTES-1)
check(u32(u4,GS+8)==0 and G_BYTES not in [s for a,s in a4],'no SDRAM: no FX1 buffer is requested past the limit')
w32(u4,UIQ+0x600,0);o=step(u4,0,LOOPER_ON)
msgs=ui_messages(u4)
check(finite(o) and any(m[2]==MODE and m[4]==0 for m in msgs) and u32(u4,0x38800200+8)==0,'no SDRAM: choosing the looper acknowledges plain Delay through the native UI queue')

# ------------------------------------------------- record, then exact playback
watch={'lo':None,'hi':0}
def on_write(u,access,address,size,value,_):
 off=address-ptr
 watch['hi']=max(watch['hi'],off+size)
 if watch['lo'] is None or off<watch['lo']:watch['lo']=off
u.hook_add(UC_HOOK_MEM_WRITE,on_write,begin=ptr,end=ptr+PL_BYTES+0x40000-1)
tempo(u,240,0)            # 1 bar at 240 BPM = 48000 frames = 1500 blocks
k=0;outs={}
step(u,k,LOOPER_ON);k+=1
check(pl(u)['play_seen']==0 and pl(u)['state']==EMPTY,'switching to the looper latches Play without recording')
for _ in range(10):step(u,k);k+=1
check(abs(f32(u,GS+0x48)-1.)<1e-6,'looper output fully faded in')
start=k;o=step(u,k,[(PLAY,1)]);k+=1
p=pl(u)
check(p['state']==REC and p['len']==48000 and p['pos']==32 and p['bpm_x10']==2400,'Play starts recording at once: 1 bar at 240 BPM = 48000 frames')
check(all(x==0. for x in o),'100% wet while recording outputs silence (no input monitoring on the FX1 return)')
for _ in range(1499):o=step(u,k);k+=1
check(pl(u)['state']==PLAYING and pl(u)['pos']==0,'capture becomes playback exactly after 1500 blocks')
mism=0;worst=0.
for j in range(1500):
 o=step(u,k);k+=1;outs[j]=o
 l,r=inp(start+j)
 for i in range(32):
  t=j*32+i
  if t<240 or t>=48000-240:continue
  if o[i]!=f32r(l[i]) or o[32+i]!=f32r(r[i]):mism+=1;worst=max(worst,abs(o[i]-l[i]))
check(mism==0,'playback reproduces the recording sample for sample away from the 5 ms edge ramps (%d mismatches)'%mism)
edge=[abs(outs[0][i]) for i in range(8)]
check(edge[0]==0. and all(abs(outs[0][i])<=abs(f32r(inp(start)[0][i]))+1e-7 for i in range(32)),'loop start is ramped in from silence (declick)')
check(watch['lo']==0 and watch['hi']==48000*8,'recording wrote exactly the loop region of the buffer, nothing past it')
for _ in range(1600):o=step(u,k);k+=1   # one more pass, then 100 blocks in
l,_=inp(start+100);o=step(u,k);k+=1
check(o[:32]==tuple(f32r(x) for x in l),'second pass repeats the same phrase (continuous playback)')

# ------------------------------------------------------------ dry/wet blend
for _ in range(5):step(u,k,[(WET,0)] if _==0 else []);k+=1
l,r=inp(k);o=step(u,k);k+=1
check(max(abs(o[i]-l[i]) for i in range(32))<1e-6,'Dry/Wet 0% passes the FX1 input unchanged')
for _ in range(5):step(u,k,[(WET,500)] if _==0 else []);k+=1
pos=pl(u)['pos'];l,r=inp(k);o=step(u,k);k+=1
rec=struct.unpack('<64f',u.mem_read(ptr+pos*8,256))[0::2]
check(max(abs(o[i]-(.5*l[i]+.5*rec[i])) for i in range(32))<1e-5,'Dry/Wet 50% is half input plus half loop')
step(u,k,[(WET,1000)]);k+=1

# ---------------------------------------------------------------- stop, play
step(u,k,[(PLAY,0)]);k+=1
check(pl(u)['state']==STOP,'Play off stops')
for _ in range(10):o=step(u,k);k+=1
check(all(x==0. for x in o) and pl(u)['pos']==0 and pl(u)['len']==48000,'stopped loop is silent and kept, rewound to the start')
step(u,k,[(PLAY,1)]);k+=1
for _ in range(20):o=step(u,k);k+=1
l,_=inp(start+20)   # resume block plays loop block 0; 20 more blocks follow
check(pl(u)['state']==PLAYING and o[:32]==tuple(f32r(x) for x in l),'Play resumes the kept loop from its start')

# --------------------------------------------------------------------- clear
w32(u,UIQ+0x600,0)
step(u,k,[(CLEAR,1)]);k+=1
msgs=ui_messages(u);p=pl(u)
check(p['state']==EMPTY and p['len']==0,'Clear empties the loop')
check(sorted((m[2],m[4]) for m in msgs if m[0]==0x39)==[(CLEAR,0),(PLAY,0)] and all(m[1]==0x14 for m in msgs if m[0]==0x39),'Clear posts Clear=0 and Play=0 to FX1 through the native UI queue')
step(u,k);k+=1
check(pl(u)['state']==EMPTY,'Play still on after Clear does not start a new take by itself')
for _ in range(10):o=step(u,k,[(CLEAR,0),(PLAY,0)] if _==0 else []);k+=1
check(all(x==0. for x in o) and pl(u)['state']==EMPTY,'cleared looper stays silent')

# ---------------------------- sync: real M4 tempo publisher feeds the M7 looper
ENGINE=0x24010000;NOW=0x3001eb3c;TABLE=0x300173d0+0xe68
bpm_value=[1200];gets=[]
stub(u,S4['gate_ui_tick'],lambda u:None)
def getter(u):
 gets.append((u.reg_read(UC_ARM_REG_R0),u.reg_read(UC_ARM_REG_R1)))
 u.reg_write(UC_ARM_REG_R0,bpm_value[0] if u.reg_read(UC_ARM_REG_R1)==0x85 else 0)
stub(u,0x8120234,getter)
w32(u,0x3000a894,ENGINE);w32(u,TABLE+4,0x24070000)
def m4_tick(now,pos):
 w32(u,NOW,now);w32(u,ENGINE+0x78b0,pos);w32(u,ENGINE+0x78b8,0)
 call(u,C4['cue_ui_tick'],0x24060000,0x24060100)
u.mem_write(TEMPO,bytes(32))
m4_tick(5000,0)
t=struct.unpack('<IiIIII',u.mem_read(TEMPO,24))
check(t[0]==0x504c5431 and t[1]==1200 and (TABLE,0x85) in gets,'M4 publishes the project BPM setting 0x85 from the session settings table')
check(t[2]==0,'M4: transport position not moving = sequencer stopped')
step(u,k,[(BARS,2),(SYNC,1)]);k+=1
step(u,k,[(PLAY,1)]);k+=1
check(pl(u)['state']==ARMED,'Sync on with the sequencer stopped: Play arms instead of recording')
for n in range(30):m4_tick(5010+n,0);o=step(u,k);k+=1
check(pl(u)['state']==ARMED and all(x==0. for x in o),'armed looper waits silently')
m4_tick(5100,32)
check(struct.unpack('<I',u.mem_read(TEMPO+8,4))[0]==1,'M4: transport position moved = sequencer playing')
o=step(u,k);k+=1;p=pl(u)
check(p['state']==REC and p['pos']==32 and p['len']==192000 and p['bpm_x10']==1200,'sequencer start begins a 2-bar take at the published 120 BPM (stored as 1200)')
m4_tick(5300,32)
check(struct.unpack('<I',u.mem_read(TEMPO+8,4))[0]==0,'M4: position unchanged for 100 ms = stopped again')

# ------------------------------------------ BPM scaling and loop length, real M7
lengths={}
for raw,bars in [(120,2),(1200,2),(12000,2),(60,2),(40,2),(40,1),(300,1),(0,1),(99999,1)]:
 step(u,k,[(CLEAR,1)]);k+=1;step(u,k,[(CLEAR,0),(PLAY,0),(SYNC,0),(BARS,bars)]);k+=1
 tempo(u,raw,0);step(u,k,[(PLAY,1)]);k+=1
 lengths[(raw,bars)]=pl(u)['len']
print('INFO loop lengths',lengths)
check(lengths[(120,2)]==lengths[(1200,2)]==lengths[(12000,2)]==192000,'BPM read as 120, 120.0 (x10) or 120.00 (x100) all give 2 bars = 4 s')
check(lengths[(60,2)]==384000,'2 bars at 60 BPM fill the buffer exactly')
check(lengths[(40,2)]==288000 and lengths[(40,1)]==288000,'too long for 2 bars at 40 BPM: drops to 1 bar')
check(lengths[(300,1)]==38400 and lengths[(0,1)]==96000 and lengths[(99999,1)]==96000,'300 BPM 1 bar = 0.8 s; invalid tempo falls back to 120 BPM')

# ------------------------------------------- partial take, overdub, bounds
step(u,k,[(CLEAR,1)]);k+=1;step(u,k,[(CLEAR,0),(PLAY,0)]);k+=1
tempo(u,240,1);step(u,k,[(PLAY,1),(BARS,2)]);k+=1
for _ in range(400):step(u,k);k+=1
step(u,k,[(PLAY,0)]);k+=1;p=pl(u)
check(p['state']==STOP and p['len']==401*32,'Play off during a take keeps the %d frames recorded so far'%(401*32))
before=bytes(u.mem_read(ptr,p['len']*8))
step(u,k,[(PLAY,1),(DUB,1000)]);k+=1
worst=0.;ok=True
for _ in range(401*6):
 o=step(u,k);k+=1;ok=ok and finite(o);worst=max([worst]+[abs(x) for x in o])
after=struct.unpack('<%df'%(p['len']*2),u.mem_read(ptr,p['len']*8))
check(ok and bytes(u.mem_read(ptr,p['len']*8))!=before,'Overdub 100% layers input into the loop over six passes, output finite')
check(max(abs(x) for x in after)<=2. and worst<=2.,'overdubbed loop and output stay within +/-2.0 (peak %.3f)'%max(abs(x) for x in after))
check(watch['hi']<=PL_BYTES,'no write ever went past the looper buffer (FX2 memory untouched)')

# --------------------------------------------------- CPU (emulated instructions)
count=[0]
def tick(u,a,n,d):count[0]+=1
h=u.hook_add(UC_HOOK_CODE,tick,begin=0x08000000,end=0x081fffff)
def cost(evs=()):
 global k
 count[0]=0;step(u,k,evs);k+=1;return count[0]
play_dub=cost()
step(u,k,[(DUB,0)]);k+=1;play=cost()
step(u,k,[(CLEAR,1)]);k+=1;step(u,k,[(CLEAR,0),(PLAY,0)]);k+=1;step(u,k,[(PLAY,1)]);k+=1;rec=cost()
step(u,k,[(MODE,5)]);k+=1
for _ in range(10):step(u,k);k+=1
delay=cost()
u.hook_del(h)
print('INFO emulated instructions per 32-frame block: looper record %d, play %d, play+overdub %d; plain Delay %d'%(rec,play,play_dub,delay))
check(max(rec,play,play_dub)<delay,'looper blocks execute fewer instructions than the stock Delay they replace (relative, not hardware cycles)')

# --------------------------------------------- leaving the mode hands back the ring
check(pl(u)['state']==EMPTY,'plain Delay drops the loop at once')
step(u,k,[(MODE,1)]);k+=1
for _ in range(10):o=step(u,k);k+=1
check(pl(u)['state']==EMPTY and all(x==0. for x in o),'back in the looper with Play still on: empty and silent, no stale loop and no surprise take')
step(u,k,[(PLAY,0)]);k+=1;step(u,k,[(PLAY,1)]);k+=1
for _ in range(50):step(u,k);k+=1
step(u,k,[(MODE,4),(0x1aa,100)]);k+=1
energy=0.;ok=True
for _ in range(400):
 o=step(u,k);k+=1;ok=ok and finite(o);energy+=sum(x*x for x in o)
p=pl(u)
check(p['state']==EMPTY and u32(u,GS+0x34)!=0 and ok and energy>1.,'switching to Reverse fades the looper out, resets the ring, and Reverse plays from fresh history')
print('PASSED',H.checks,'Phrase Looper firmware checks; device timing, shared-cache behaviour, sound and the physical UI remain hardware tests.')
