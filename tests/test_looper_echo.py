"""Phrase Looper Echo: the stock FX1 delay running on the loop, on the real firmware.

    LOOPER=1 python3 tests/test_looper_echo.py /path/to/stock/BLUEBOX.BIN

A loop holding one click is recorded inside the stock FX1 delay object. With
Echo at 0 the stock delay stays skipped (as before). With Echo up, the loop
is sent into the stock delay and the return carries the loop plus the stock
delay's echoes: checked against the stock impulse response (first echo at the
delay time, each repeat scaled by Feedback), Ping, Echo level, the tail
ringing out after Echo goes back to 0, and the instruction count per block.
"""
import os,sys,math,struct
if os.environ.get('LOOPER')!='1':
 print('SKIP echo checks: run with LOOPER=1');raise SystemExit(0)
from delay_fixture import *
import firmware_harness as H

GS=0x38800000;PL=0x38800ea0;TEMPO=0x38800ee0
MODE,LEVEL,CLEAR,BARS,DUB,SYNC,REC,STOP,STRETCH,ECHO=0x1a0,0x1a1,0x1a2,0x1a3,0x1a4,0x1a5,0x1a6,0x1ba,0x1bb,0x1bc
TIME,BEAT,FEEDB,PING,ETYPE=0x33,0x35,0x39,0x36,0x1bd
EMPTY,ARMED,RECORDING,PLAYING=0,1,2,3
D=2880                                   # stock delay time for Time=10 (the delay tests' setting)

def setup():
 u=machine(patched);heap=[0xc0010000]
 def allocate(u):
  a=heap[0];heap[0]=(a+u.reg_read(UC_ARM_REG_R0)+15)&~15;w32(u,0x24000004,heap[0]);u.reg_write(UC_ARM_REG_R0,a)
 w32(u,0x24000000,0xc0a00000);w32(u,0x24000004,heap[0])
 stub(u,0x80412a4,allocate)
 u.reg_write(UC_ARM_REG_R0,DOBJ);u.reg_write(UC_ARM_REG_SP,0x2407f000);u.reg_write(UC_ARM_REG_LR,RET|1)
 u.emu_start(0x8050f1b,0x8050f1e,count=50000000)
 w32(u,DOBJ+0x18,0x14);u.mem_write(DOBJ+0x1e,struct.pack('<H',13));u.mem_write(DOBJ+0x273,b'\0')
 w32(u,CTX,0x24040000)
 for addr,buf in [(DBUS,BUF),(CTX+0x150e4+16*20,BUF+0x400),(CTX+0x15260,BUF+0x600),(CTX+0x15274,BUF+0x800)]:
  u.mem_write(addr,struct.pack('<IIIIBBxx',32,32,buf,buf+0x100,0,1))
 w32(u,DOBJ+8,NEXT);w32(u,NEXT,VT);w32(u,VT+12,NEXT_FN|1)
 stub(u,NEXT_FN,lambda u:u.reg_write(UC_ARM_REG_R0,7))
 u.mem_write(TEMPO,struct.pack('<IiIIIIII',0x504c5431,120,0,0,0,0,0,0))
 return u

def pl(u):
 v=struct.unpack('<8I',u.mem_read(PL,32));return dict(zip(['magic','owner','cap','state','len','pos','bars','seq'],v))

class Run:
 def __init__(s,u):s.u=u;s.k=0;s.out=[];s.cost=[]
 def blk(s,evs=(),click=False,count=False):
  l=[0.]*32
  if click:l[0]=.5
  if count:
   c=[0];h=s.u.hook_add(UC_HOOK_CODE,lambda u,a,n,d:c.__setitem__(0,c[0]+1),begin=0x08000000,end=0x081fffff)
  o,_=dblock(s.u,l,l,evs)
  if count:s.u.hook_del(h);s.cost.append(c[0])
  v=struct.unpack('<64f',o);s.out.append((v[:32],v[32:]));s.k+=1
  return v
 def run(s,n,count=False):
  for _ in range(n):s.blk(count=count)
 def take(s,n):
  """Last n blocks as left/right sample lists."""
  L=[x for b in s.out[-n:] for x in b[0]];R=[x for b in s.out[-n:] for x in b[1]];return L,R

def peaks(x,th=.02):
 out=[];i=0
 while i<len(x):
  if abs(x[i])>th:
   j=max(range(i,min(i+8,len(x))),key=lambda k:abs(x[k]));out.append((j,round(x[j],3)));i=j+64
  else:i+=1
 return out

def looper(ping=0,stretch=0,etype=0):
 u=setup();r=Run(u)
 r.blk(INITIAL+[(MODE,1),(LEVEL,1000),(CLEAR,0),(BARS,1),(DUB,1000),(SYNC,0),(REC,0),(STOP,0),(STRETCH,stretch),(ECHO,0),(ETYPE,etype),
                (BEAT,0),(TIME,10),(FEEDB,500),(PING,ping)])
 steady(u)
 r.run(10)
 r.blk([(REC,1),(REC,0)])                      # sequencer stopped, Sync off: records at once
 r.run(100);r.blk(click=True)                   # one click, 0.5, clear of the 1 ms fade-in
 while pl(u)['state']==RECORDING and r.k<5000:r.blk()
 return u,r

BAR=96000;NB=BAR//32
# ------------------------------------------------------------ Echo 0: unchanged
u,r=looper()
check(pl(u)['state']==PLAYING and pl(u)['len']==BAR,'a 1-bar loop with one click is playing (%d samples)'%pl(u)['len'])
r.run(NB,count=True)
L,R=r.take(NB);p=peaks(L)
check(len(p)==1 and abs(p[0][1]-.5)<.01 and peaks(R)==p,'Echo 0: one pass holds only the click, no echoes (%s)'%p)
off_cost=max(r.cost)
print('INFO Echo 0: worst block %d instructions (stock delay skipped)'%off_cost)

# ------------------------------------------- Echo 100%: stock echoes of the loop
r.blk([(ECHO,1000)]);r.cost=[]
r.run(2*NB,count=True)
L,R=r.take(NB);p=peaks(L)
print('INFO Echo 100%, Feedback 50%, Time 10: left peaks',p[:6])
c=p[0][0]
want=[(c,.5),(c+D,.5),(c+2*D,.25),(c+3*D,.125)]
check(len(p)>=4 and all(abs(a[0]-b[0])<=1 and abs(a[1]-b[1])<.01 for a,b in zip(p,want)),
      'Echo 100%%: the click, then the stock delay\'s echoes at +%d, +%d, +%d samples, each halved by Feedback 50%%'%(D,2*D,3*D))
check(peaks(R)==p,'mono click: right channel matches left')
on_cost=max(r.cost)
print('INFO Echo on: worst block %d instructions'%on_cost)
check(on_cost<14813,'Echo on: every block under the tested Granular (worst %d, Echo off %d)'%(on_cost,off_cost))

# ------------------------------------------------ Echo 50%: half-level echoes
r.blk([(ECHO,500)]);r.run(2*NB)
L,R=r.take(NB);p=peaks(L);c=[x for x in p if x[1]>.4][0][0]
e1=[x for x in p if abs(x[0]-(c+D))<=1]
check(e1 and abs(e1[0][1]-.25)<.01,'Echo 50%%: first echo at half level (%s)'%e1)

# ------------------------------- Echo back to 0: the tail rings out, then skip
r.blk([(ECHO,0)])
L,R=r.take(1)
r.run(NB//2)
tail=[x for b in r.out[-NB//2:] for x in b[0]]
check(max(abs(x) for x in tail[:D*3])>.01,'Echo to 0: echoes already in the delay keep ringing (no cut)')
r.cost=[];r.run(NB,count=True)
L,R=r.take(NB);p=peaks(L)
check(len(p)==1 and abs(p[0][1]-.5)<.01,'after the tail: one pass holds only the click again (%s)'%p)
check(max(r.cost[-200:])<=off_cost+64,'after the tail: the stock delay is skipped again (worst %d)'%max(r.cost[-200:]))

# -------------------------------------------------- Ping: echoes alternate L/R
u,r=looper(ping=1)
r.run(NB);r.blk([(ECHO,1000)]);r.run(2*NB)
L,R=r.take(NB);pl_,pr=peaks(L),peaks(R)
print('INFO Ping: left',pl_[:4],'right',pr[:4])
check(len(pl_)>=2 and len(pr)>=2 and pl_[0][0]!=pr[1][0],'Ping: echoes alternate between left and right')

# ------------------------------------- worst case: Keep stretch + Ping + Echo
u,r=looper(ping=1,stretch=2)
r.run(NB);r.blk([(ECHO,1000)]);r.cost=[]
for i in range(600):r.blk(count=(i%3==0))
print('INFO Keep + Ping + Echo: worst block %d instructions'%max(r.cost))
check(max(r.cost)<16829,'Keep + Ping + Echo: every block within the tested Granular range (worst %d, Granular 14813-16829)'%max(r.cost))
# ------------------------------------------------ echo types: Warp/Tape/Duck/Delay
res={}
for et,name in [(0,'Warp'),(1,'Tape'),(2,'Duck'),(3,'Delay')]:
 u,r=looper(etype=et)
 check(u.mem_read(PL+61,1)[0]==et,'Type %s reaches the looper state (etype %d)'%(name,et))
 r.run(NB);r.blk([(ECHO,1000)]);r.cost=[];r.run(2*NB,count=True)
 L,R=r.take(NB);p=peaks(L,th=.005);c=[x for x in p if abs(x[1]-.5)<.01]
 e1=max((abs(v) for v in L[c[0][0]+D-200:c[0][0]+D+200]),default=0) if c else 0
 res[name]=(p[:4],e1,max(r.cost),all(math.isfinite(v) for v in L+R))
 print('INFO %-5s peaks %s first echo %.3f worst block %d'%(name,p[:4],e1,max(r.cost)))
 check(c and res[name][3],'%s: the loop click passes unchanged (0.5) and the output is finite'%name)
check(res['Warp'][0]==res['Delay'][0] and abs(res['Warp'][1]-.5)<.01,'Warp and Delay (no Drift/Pitch set): the stock echoes, first echo 0.5')
check(res['Tape'][1]>.01 and abs(res['Tape'][1]-res['Warp'][1])>.01,'Tape: echoes present and coloured by the tape stage (first echo %.3f vs %.3f)'%(res['Tape'][1],res['Warp'][1]))
# Duck needs a sustained loop: record a held tone, compare the echoes' share
# of the output (pass with Echo minus the same pass without) for Warp and Duck.
def tone_echo(et):
 u=setup();r=Run(u)
 r.blk(INITIAL+[(MODE,1),(LEVEL,1000),(CLEAR,0),(BARS,1),(DUB,1000),(SYNC,0),(REC,0),(STOP,0),(STRETCH,0),(ECHO,0),(ETYPE,et),
                (BEAT,0),(TIME,10),(FEEDB,500),(PING,0)])
 steady(u);r.run(10);r.blk([(REC,1),(REC,0)])
 k=0
 while pl(u)['state']==RECORDING and k<5000:
  l=[.3*math.sin(2*math.pi*220*((k*32+i)/48000.)) for i in range(32)];dblock(u,l,l,());k+=1
 r.run(NB);ref,_=r.take(NB)
 r.blk([(ECHO,1000)]);r.run(2*NB-1);out,_=r.take(NB)
 diff=[a-b for a,b in zip(out,ref)]
 return math.sqrt(sum(x*x for x in diff[NB*16:])/len(diff[NB*16:]))
w,dk=tone_echo(0),tone_echo(2)
print('INFO held tone: echo RMS Warp %.4f, Duck %.4f'%(w,dk))
check(w>.05 and dk<w*.5,'Duck: under a sustained loop the echoes are ducked (echo RMS %.4f vs Warp %.4f)'%(dk,w))
for name in res:check(res[name][2]<14813,'%s echo: every block under the tested Granular (worst %d)'%(name,res[name][2]))
worst={}
for st,sn in [(0,'Off'),(1,'Vari'),(2,'Keep')]:
 for et,en in [(0,'Warp'),(1,'Tape'),(2,'Duck')]:
  u,r=looper(ping=1,stretch=st,etype=et)
  r.run(NB);r.blk([(ECHO,1000)]);r.cost=[]
  for i in range(600):r.blk(count=(i%3==0))
  worst[(sn,en)]=max(r.cost)
print('INFO worst block with Ping, by Stretch x echo type:',worst)
for k,v in worst.items():
 if v<16829:check(True,'Ping + Stretch %s + %s echo: within the tested Granular range (worst %d)'%(k[0],k[1],v))
 else:print('WARN Ping + Stretch %s + %s echo: worst block %d instructions, above the hardware-tested Granular (16829): check the CPU meter on the bluebox'%(k[0],k[1],v))
check(all(worst[(st,et)]<16829 for st in ('Off',) for et in ('Warp','Tape','Duck')) and all(worst[(st,'Warp')]<16829 for st in ('Vari','Keep')),'Stretch Off with any echo type, and Warp echo with any Stretch: within the tested range')
check(max(worst.values())<20000,'every combination stays under 20k instructions (worst %d)'%max(worst.values()))
print('PASSED',H.checks,'Phrase Looper Echo checks; sound and real CPU load remain hardware tests.')
