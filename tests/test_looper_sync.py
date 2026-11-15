"""Phrase Looper sync to the bluebox song position, on the real firmware.

    LOOPER=1 python3 tests/test_looper_sync.py /path/to/stock/BLUEBOX.BIN

The compiled looper runs inside the stock FX1 delay object. A simulated
sequencer writes the song position (960 ticks per beat) where the firmware
reads it: *(0x3000a894)+0x78b0, with the app flag +0x7408 set. Checks that
bar-line takes start and end on bar lines, that playback stays locked with no
drift when the sequencer runs 0.5% off the tempo the looper is given (with the
position updated every block, or only every 3rd block with jitter), that each
Stretch mode follows a tempo change while locked, and the CPU cost.
"""
import os,sys,math,struct,random
if os.environ.get('LOOPER')!='1':
 print('SKIP sync checks: run with LOOPER=1');raise SystemExit(0)
from delay_fixture import *
import firmware_harness as H

GS=0x38800000;PL=0x38800ea0;TEMPO=0x38800ee0;ENGINE=0x24010000;APP=0x300173d0
MODE,LEVEL,CLEAR,BARS,DUB,SYNC,REC,STOP,STRETCH=0x1a0,0x1a1,0x1a2,0x1a3,0x1a4,0x1a5,0x1a6,0x1ba,0x1bb
EMPTY,ARMED,RECORDING,PLAYING=0,1,2,3
BAR=3840
ON=INITIAL+[(MODE,1),(LEVEL,1000),(CLEAR,0),(BARS,1),(DUB,1000),(SYNC,0),(REC,0),(STOP,0)]

def setup():
 u=machine(patched);heap=[0xc0010000]
 def allocate(u):
  a=heap[0];heap[0]=(a+u.reg_read(UC_ARM_REG_R0)+15)&~15;w32(u,0x24000004,heap[0]);u.reg_write(UC_ARM_REG_R0,a)
 w32(u,0x24000000,0xc0a00000);w32(u,0x24000004,heap[0])   # the tested 768 KB buffer, as on the bluebox
 stub(u,0x80412a4,allocate)
 u.reg_write(UC_ARM_REG_R0,DOBJ);u.reg_write(UC_ARM_REG_SP,0x2407f000);u.reg_write(UC_ARM_REG_LR,RET|1)
 u.emu_start(0x8050f1b,0x8050f1e,count=50000000)
 w32(u,DOBJ+0x18,0x14);u.mem_write(DOBJ+0x1e,struct.pack('<H',13));u.mem_write(DOBJ+0x273,b'\0')
 w32(u,CTX,0x24040000)
 for addr,buf in [(DBUS,BUF),(CTX+0x150e4+16*20,BUF+0x400),(CTX+0x15260,BUF+0x600),(CTX+0x15274,BUF+0x800)]:
  u.mem_write(addr,struct.pack('<IIIIBBxx',32,32,buf,buf+0x100,0,1))
 w32(u,DOBJ+8,NEXT);w32(u,NEXT,VT);w32(u,VT+12,NEXT_FN|1)
 stub(u,NEXT_FN,lambda u:u.reg_write(UC_ARM_REG_R0,7))
 w32(u,0x3000a894,ENGINE);u.mem_write(APP+0x7408,b'\x01')
 return u

class Seq:
 """Song position at bpm, written every `every` blocks with +/-`jitter` ticks of read noise."""
 def __init__(s,u,bpm=120.0,every=1,jitter=0,seed=1):
  s.u=u;s.t=0.0;s.on=False;s.bpm=bpm;s.every=every;s.jitter=jitter;s.k=0;s.rnd=random.Random(seed)
 def write(s):
  if s.k%s.every==0:
   v=int(s.t)+(s.rnd.randint(-s.jitter,s.jitter) if s.jitter and s.on else 0)
   w32(s.u,ENGINE+0x78b0,v&0xffffffff);w32(s.u,ENGINE+0x78b4,0)
 def advance(s):
  s.k+=1
  if s.on:s.t+=32*s.bpm*960/(60*48000)

def pl(u):
 v=struct.unpack('<8I',u.mem_read(PL,32));return dict(zip(['magic','owner','cap','state','len','pos','bars','seq'],v))
def sync(u):
 cap=pl(u)['cap'];ptr=u32(u,GS+8)
 v=struct.unpack('<IIiiffiiIIii',u.mem_read(ptr+cap*4+96,48))
 return dict(zip(['magic','still','last','qi','qf','r','start','end','lt','flags','bar','cycle'],v))
def tempo(u,bpm):u.mem_write(TEMPO,struct.pack('<IiIIIIII',0x504c5431,bpm,0,0,0,0,0,0))

def blk(u,seq,evs=(),count=None):
 seq.write()
 l=[.3*math.sin(2*math.pi*440*(seq.k*32+i)/48000) for i in range(32)]
 if count is not None:
  c=[0];h=u.hook_add(UC_HOOK_CODE,lambda u,a,n,d:c.__setitem__(0,c[0]+1),begin=0x08000000,end=0x081fffff)
 out,_=dblock(u,l,l,evs)
 if count is not None:u.hook_del(h);count.append(c[0])
 seq.advance()
 return struct.unpack('<64f',out)

def take(u,seq,bars=1,mode=0):
 """Running sequencer: arm REC, wait for the bar line, record to the bar line."""
 blk(u,seq,ON+[(BARS,bars),(STRETCH,mode)])
 for _ in range(10):blk(u,seq)
 seq.on=True;seq.t+=1000.0                  # running, mid-bar
 for _ in range(3):blk(u,seq)
 blk(u,seq,[(REC,1),(REC,0)])
 assert pl(u)['state']==ARMED,pl(u)
 k=0
 while pl(u)['state']==ARMED and k<8000:blk(u,seq);k+=1
 start_seen=seq.t
 while pl(u)['state']==RECORDING and k<40000:blk(u,seq);k+=1
 return start_seen

def restarts(u,seq,bars,nbars):
 """Off mode: the play position falls back at each loop cycle. Distance in
 ticks from the nearest loop-cycle boundary of the song at each restart."""
 lt=bars*BAR;s=sync(u);out=[];last=pl(u)['pos'];end=seq.t+nbars*BAR
 while seq.t<end:
  t0=seq.t;blk(u,seq)
  pos=pl(u)['pos']
  if pos<last:
   ph=(t0-s['start'])%lt;out.append(min(ph,lt-ph))
  last=pos
 return out

# ------------------------------------------------ bar-line take, 0.5% tempo error
u=setup();tempo(u,120);seq=Seq(u,bpm=120.6)
take(u,seq,bars=1)
p=pl(u);s=sync(u);want=BAR/(120.6*960/(60*48000))
check(p['state']==PLAYING and s['flags']&2 and s['start']%BAR==0 and s['lt']==BAR,'sequencer at 120.6 BPM, looper told 120: take on a bar line (tick %d), locked'%s['start'])
check(abs(p['len']-want)<=32,'take is one bar at the sequencer\'s real tempo: %d samples (want %.0f)'%(p['len'],want))
r=restarts(u,seq,1,20)
print('INFO Off, position every block: %d restarts in 20 bars, worst %.2f ticks from the bar line'%(len(r),max(r)))
check(len(r)>=19 and max(r)<=2.5,'Off: restarts once per bar for 20 bars, each within 2.5 ticks (0.06 ms) of the bar line, no drift')
cost=[]
for _ in range(200):blk(u,seq,count=cost)
check(max(cost)<14813,'locked playback: every block under the tested Granular\'s instruction count (worst %d)'%max(cost))

# ------------------------- 2 bars on the tested 4 s buffer (192000 frames)
for bpm,label in [(120.0,'exactly 120 BPM: 2 bars fill the buffer exactly'),(119.5,'119.5 BPM: 0.4% too long, ends at the buffer')]:
 u=setup();tempo(u,120);seq=Seq(u,bpm=bpm)
 take(u,seq,bars=2)
 p=pl(u);s=sync(u)
 check(p['state']==PLAYING and p['bars']==2 and s['lt']==2*BAR and s['flags']&2 and abs(p['len']-192000)<=64,'%s: a locked 2-bar take, %d samples'%(label,p['len']))

# ---------------------------------- position only every 3rd block, +/-2 ticks noise
u=setup();tempo(u,120);seq=Seq(u,bpm=120.6,every=3,jitter=2,seed=4)
take(u,seq,bars=2)
p=pl(u);s=sync(u)
check(p['state']==PLAYING and s['flags']&2 and s['lt']==2*BAR,'coarse, noisy position: 2-bar take locked')
r=restarts(u,seq,2,40)
print('INFO Off, position every 3rd block +/-2 ticks: %d restarts in 40 bars, worst %.2f ticks'%(len(r),max(r)))
check(len(r)>=19 and max(r)<=6,'Off: still locked after 20 cycles with a coarse, noisy position (worst %.1f ticks, 0.15 ms)'%max(r))

# --------------------------------------- tempo change 120 -> 128 while locked
for mode,name in [(0,'Off'),(1,'Vari'),(2,'Keep')]:
 u=setup();tempo(u,120);seq=Seq(u,bpm=120.0)
 take(u,seq,bars=1,mode=mode)
 seq.bpm=128.0;tempo(u,128)
 for _ in range(200):blk(u,seq)
 s=sync(u);lt=BAR;worst=0;cyc_seen=set();n=0;costs=[]
 end=seq.t+6*BAR
 while seq.t<end:
  t0=seq.t;blk(u,seq,count=costs if n%7==0 else None);n+=1
  p=pl(u);s=sync(u)
  ph=(t0-s['start'])%lt
  if mode:
   want=ph*p['len']/lt;e=abs(want-p['pos']);e=min(e,p['len']-e);worst=max(worst,e)
  cyc_seen.add(s['cycle'])
 if mode:
  print('INFO %s at 128 BPM: play position within %.0f samples of the song phase over 6 bars; worst block %d instructions'%(name,worst,max(costs)))
  check(worst<=3000 if mode==2 else worst<=64,'%s at 128 BPM (recorded at 120): the loop follows the song phase (worst %.0f samples)'%(name,worst))
 else:
  r=restarts(u,seq,1,6)
  print('INFO Off at 128 BPM: restarts worst %.2f ticks from the bar line'%max(r))
  check(len(r)>=5 and max(r)<=2.5,'Off at 128 BPM: loop restarts on every bar line (the end of each pass is cut)')
 check(max(costs)<14813,'%s locked at 128 BPM: every block under the tested Granular (worst %d)'%(name,max(costs)))

# ------------------------------- sequencer stops and restarts: relocks to the song
u=setup();tempo(u,120);seq=Seq(u,bpm=120.0)
take(u,seq,bars=1)
seq.on=False
for _ in range(400):blk(u,seq)
check(pl(u)['state']==4,'transport stopped: the loop stops with it (STOP)')
o=blk(u,seq);check(all(x==0. for x in o),'... and is silent')
seq.t=7*BAR+500.0;seq.on=True                    # restart from a located position
for _ in range(80):blk(u,seq)
p=pl(u);s=sync(u)
ph=(seq.t-s['start'])%BAR;want=ph*p['len']/BAR;e=abs(want-p['pos']);e=min(e,p['len']-e)
check(p['state']==PLAYING and e<=64,'transport starts again from bar 8: the loop plays, in step with the song (%.0f samples off)'%e)
# ------------- external clock changes tempo, the bluebox BPM stays at 126
u=setup();tempo(u,126);seq=Seq(u,bpm=126.0)
take(u,seq,bars=2,mode=1)
seq.bpm=128.0
for _ in range(int(8*60/128*48000/32)):blk(u,seq)          # 8 beats at 128
m=u32(u,PL+36)
check(abs(m-12800)<=3,'master goes to 128 (bluebox still 126): the looper measures %.2f BPM from the song position'%(m/100))
blk(u,seq,[(CLEAR,1),(CLEAR,0)]);blk(u,seq,[(REC,1),(REC,0)])
k=0
while pl(u)['state']!=PLAYING and k<40000:blk(u,seq);k+=1
p=pl(u);s=sync(u);want=2*BAR/(128*960/(60*48000))
check(p['state']==PLAYING and p['bars']==2 and s['flags']&2 and abs(p['len']-want)<=64,'next take, bluebox BPM untouched: 2 bars at 128, %d samples (want %.0f), locked'%(p['len'],want))
r=restarts(u,seq,2,20)
check(len(r)>=9 and max(r)<=2.5,'it plays on the bar lines at 128 for 20 bars (worst %.2f ticks)'%max(r))
print('PASSED',H.checks,'Phrase Looper sync checks; real STM32 timing and the bluebox\'s own position update rate remain hardware tests.')
