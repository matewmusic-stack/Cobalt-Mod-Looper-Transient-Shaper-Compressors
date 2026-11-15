"""Experiment: tempo-follow modes of the Phrase Looper on the real firmware.

    LOOPER=1 python3 tests/test_stretch.py /path/to/stock/BLUEBOX.BIN [wav_dir]

Records one bar at 120 BPM through the compiled looper inside the stock FX1
delay object, then plays it back with the project tempo at 112, 120 and 128
BPM in each mode (0 off, 1 varispeed, 2 keep pitch), selected with the
experimental FX1 parameter 0x1ba+1 (LP_STRETCH). Measures beat spacing, the
pitch of a 440 Hz tone, tone-level ripple and emulated instructions per
block, and writes WAV files (16-bit stereo, 48 kHz) when wav_dir is given.
"""
import os,sys,math,struct,wave
if os.environ.get('LOOPER')!='1':
 print('SKIP stretch experiment: run with LOOPER=1');raise SystemExit(0)
WAVDIR=sys.argv[2] if len(sys.argv)>2 else None
sys.argv=sys.argv[:2]
from delay_fixture import *
import firmware_harness as H

GS=0x38800000;PL=0x38800ea0;TEMPO=0x38800ee0
MODE,LEVEL,CLEAR,BARS,DUB,SYNC,REC,STOP,STRETCH=0x1a0,0x1a1,0x1a2,0x1a3,0x1a4,0x1a5,0x1a6,0x1ba,0x1bb
FS=48000;BEAT=24000;BAR=96000      # 120 BPM, 1 bar
ON=INITIAL+[(MODE,1),(LEVEL,1000),(CLEAR,0),(BARS,1),(DUB,1000),(SYNC,0),(REC,0),(STOP,0)]

# ---------------------------------------------------------------- signals
def tone_clicks(n):
 x=[];y=[]
 for t in range(n):
  v=.3*math.sin(2*math.pi*440*t/FS)
  if t%BEAT<48:v+=.8
  x.append(v);y.append(v)
 return x,y
def groove(n):
 import random
 rnd=random.Random(7);L=[0.]*n;R=[0.]*n
 bass=[55,55,65.41,49]                     # A1 A1 C2 G1, one per beat
 for t in range(n):
  b=t%BEAT;beat=(t//BEAT)%4
  v=0.
  if beat in (0,2) and b<9000:            # kick: falling sine
   f=50+120*math.exp(-b/600);v+=.7*math.exp(-b/2500)*math.sin(2*math.pi*f*b/FS)
  if beat in (1,3) and b<6000:v+=.35*math.exp(-b/1200)*(rnd.random()*2-1)   # snare
  if (t%(BEAT//2))<1500:v+=.12*math.exp(-(t%(BEAT//2))/250)*(rnd.random()*2-1)  # hats
  f=bass[beat];ph=2*math.pi*f*b/FS
  v+=.25*math.exp(-b/16000)*(math.sin(ph)+.3*math.sin(3*ph))
  L.append(0) if False else None
  L[t]=v;R[t]=.9*v
 return L,R

# ---------------------------------------------------------------- machine
def setup():
 u=machine(patched);heap=[0xc0010000]
 def allocate(u):
  a=heap[0];heap[0]=(a+u.reg_read(UC_ARM_REG_R0)+15)&~15;w32(u,0x24000004,heap[0]);u.reg_write(UC_ARM_REG_R0,a)
 w32(u,0x24000000,0xc0a00000);w32(u,0x24000004,heap[0])   # ~3.9 MB free at FX1: the tested 768 KB buffer
 stub(u,0x80412a4,allocate)
 u.reg_write(UC_ARM_REG_R0,DOBJ);u.reg_write(UC_ARM_REG_SP,0x2407f000);u.reg_write(UC_ARM_REG_LR,RET|1)
 u.emu_start(0x8050f1b,0x8050f1e,count=50000000)
 w32(u,DOBJ+0x18,0x14);u.mem_write(DOBJ+0x1e,struct.pack('<H',13));u.mem_write(DOBJ+0x273,b'\0')
 w32(u,CTX,0x24040000)
 for addr,buf in [(DBUS,BUF),(CTX+0x150e4+16*20,BUF+0x400),(CTX+0x15260,BUF+0x600),(CTX+0x15274,BUF+0x800)]:
  u.mem_write(addr,struct.pack('<IIIIBBxx',32,32,buf,buf+0x100,0,1))
 w32(u,DOBJ+8,NEXT);w32(u,NEXT,VT);w32(u,VT+12,NEXT_FN|1)
 stub(u,NEXT_FN,lambda u:u.reg_write(UC_ARM_REG_R0,7))
 return u
def tempo(u,bpm):u.mem_write(TEMPO,struct.pack('<IiIIIIII',0x504c5431,bpm,0,0,0,0,0,0))
def state(u):return struct.unpack('<8I',u.mem_read(PL,32))

def run_case(sig,mode,bpm,loops=3,count=False):
 u=setup();tempo(u,120)
 L,R=sig
 out_l=[];out_r=[];costs=[]
 def blk(l,r,evs=()):
  o,_=dblock(u,l,r,evs);v=struct.unpack('<64f',o);return v[:32],v[32:]
 blk([0.]*32,[0.]*32,ON+[(STRETCH,mode)])
 for _ in range(10):blk([0.]*32,[0.]*32)
 # record exactly one bar
 for k in range(BAR//32):
  ev=[(REC,1),(REC,0)] if k==0 else []
  blk(L[k*32:k*32+32],R[k*32:k*32+32],ev)
 s=state(u);assert s[3]==3 and s[4]==BAR,('not playing a 1-bar loop',s)
 tempo(u,bpm)                                  # tempo change at the loop start
 n=int(BAR*120/bpm*loops)//32
 cnt=[0]
 h=u.hook_add(UC_HOOK_CODE,lambda u,a,s_,d:cnt.__setitem__(0,cnt[0]+1),begin=0x08000000,end=0x081fffff) if count else None
 for k in range(n):
  cnt[0]=0
  l,r=blk([0.]*32,[0.]*32)
  if count:costs.append(cnt[0])
  out_l+=l;out_r+=r
 if h:u.hook_del(h)
 return out_l,out_r,costs

# ---------------------------------------------------------------- measures
def beats(x):
 """Click positions: first sample above 0.5 after at least 9000 quiet samples."""
 p=[];last=-10**9
 for i,v in enumerate(x):
  if abs(v)>.5 and i-last>9000:p.append(i);last=i
  elif abs(v)>.5:last=i
 return p
def pitch(x,a,b):
 z=[i+x[i]/(x[i]-x[i+1]) for i in range(a,b-1) if x[i]<=0<x[i+1]]
 return (len(z)-1)/((z[-1]-z[0])/FS) if len(z)>2 else 0.
def purity(x,a,b,f):
 """Fit a sine at f over x[a:b]; residual energy relative to it, in dB."""
 s=c=ss=cc=sc=xs=xc=0.
 for i in range(a,b):
  w=2*math.pi*f*i/FS;si=math.sin(w);co=math.cos(w)
  ss+=si*si;cc+=co*co;sc+=si*co;xs+=x[i]*si;xc+=x[i]*co
 det=ss*cc-sc*sc;A=(xs*cc-xc*sc)/det;B=(xc*ss-xs*sc)/det
 res=sum((x[i]-A*math.sin(2*math.pi*f*i/FS)-B*math.cos(2*math.pi*f*i/FS))**2 for i in range(a,b))
 sig=sum((A*math.sin(2*math.pi*f*i/FS)+B*math.cos(2*math.pi*f*i/FS))**2 for i in range(a,b))
 return 10*math.log10(max(res,1e-30)/sig)
def tone_windows(clk,spacing):
 # click-free stretch of tone in each beat: from 15% to 85% of the beat
 return [(int(c+.15*spacing),int(c+.85*spacing)) for c in clk[:-1]]

def write_wav(path,l,r):
 with wave.open(path,'wb') as w:
  w.setnchannels(2);w.setsampwidth(2);w.setframerate(FS)
  w.writeframes(b''.join(struct.pack('<hh',*(max(-32767,min(32767,int(v*32767))) for v in (a,b))) for a,b in zip(l,r)))

# ================================================================ run
NAMES={0:'off',1:'varispeed',2:'keep pitch'}
sig=tone_clicks(BAR)
results={}
for mode in (0,1,2):
 for bpm in (112,120,128):
  l,r,c=run_case(sig,mode,bpm,count=(bpm==128))
  spacing=BEAT*120/bpm
  clk=beats(l)
  # skip the first 240 samples' fade-in
  # The 5 ms declick at the loop start hides each loop's first click, so
  # beat spacing is taken from consecutive detected clicks within a loop.
  exp=spacing if mode else BEAT
  gaps=[b-a for a,b in zip(clk,clk[1:]) if b-a<1.5*exp]
  # Tone windows only between two consecutive clicks of the same loop pass
  # (never across the loop wrap), 15%..85% of the way.
  win=[(int(a+.15*(b-a)),int(a+.85*(b-a))) for a,b in zip(clk,clk[1:]) if b-a<1.5*exp]
  z=[];per=[]
  for a,b in win:
   zz=[i+l[i]/(l[i]-l[i+1]) for i in range(a,b-1) if l[i]<=0<l[i+1]]
   per+=[y-x_ for x_,y in zip(zz,zz[1:])]
  med=sorted(per)[len(per)//2];per=[q for q in per if abs(q-med)<.02*med]
  f=FS/(sum(per)/len(per))
  # residual after the best-fitting sine (frequency refined to 0.01 Hz)
  def best(a,b):
   lo,hi=f-.3,f+.3
   for _ in range(12):
    m1,m2=lo+(hi-lo)/3,hi-(hi-lo)/3
    if purity(l,a,b,m1)<purity(l,a,b,m2):hi=m2
    else:lo=m1
   return purity(l,a,b,(lo+hi)/2)
  pur=max(best(a,min(b,a+2400)) for a,b in win[:4])
  results[(mode,bpm)]=dict(gap=sum(gaps)/len(gaps),gap_min=min(gaps),gap_max=max(gaps),pitch=f,purity=pur,cost=(sum(c)/len(c),max(c)) if c else None)
  if WAVDIR:write_wav(os.path.join(WAVDIR,'tone-clicks_%s_%dbpm.wav'%(NAMES[mode].replace(' ','-'),bpm)),l,r)
  print('INFO %-10s %3d BPM: beat spacing %.1f (min %d, max %d; want %.0f), tone %.2f Hz, worst tone residual %.1f dB%s'%(NAMES[mode],bpm,results[(mode,bpm)]['gap'],min(gaps),max(gaps),exp,f,pur,
       ', instructions/block avg %.0f max %d'%results[(mode,bpm)]['cost'] if c else ''))

for bpm in (112,128):
 want=BEAT*120/bpm
 r0,r1,r2=results[(0,bpm)],results[(1,bpm)],results[(2,bpm)]
 check(abs(r0['gap']-BEAT)<2 and abs(r0['pitch']-440)<1,'off at %d BPM: loop keeps 120 BPM timing and pitch (drifts against the new tempo)'%bpm)
 check(abs(r1['gap']-want)<.001*want and abs(r1['pitch']-440*bpm/120)<.5,'varispeed at %d BPM: beats every %.0f samples, pitch %.1f Hz (expected %.1f)'%(bpm,r1['gap'],r1['pitch'],440*bpm/120))
 check(abs(r2['gap']-want)<.005*want and abs(r2['pitch']-440)<.5,'keep pitch at %d BPM: average beat spacing %.0f (want %.0f), pitch %.1f Hz'%(bpm,r2['gap'],want,r2['pitch']))
for mode in (1,2):
 r=results[(mode,120)]
 check(abs(r['gap']-BEAT)<2 and abs(r['pitch']-440)<1,'%s at the recorded tempo plays the loop unchanged in timing and pitch'%NAMES[mode])
check(results[(1,128)]['cost'][1]<14813,'varispeed: every block runs fewer instructions than the tested Granular (14813+)')
check(results[(2,128)]['cost'][1]<14813,'keep pitch: every block, including grain starts, runs fewer instructions than the tested Granular (worst %d)'%results[(2,128)]['cost'][1])

if WAVDIR:
 g=groove(BAR)
 write_wav(os.path.join(WAVDIR,'groove_recorded-at-120bpm.wav'),g[0]*3,g[1]*3)
 for mode in (0,1,2):
  for bpm in (112,128):
   l,r,_=run_case(g,mode,bpm)
   write_wav(os.path.join(WAVDIR,'groove_%s_%dbpm.wav'%(NAMES[mode].replace(' ','-'),bpm)),l,r)
 write_wav(os.path.join(WAVDIR,'tone-clicks_recorded-at-120bpm.wav'),sig[0]*3,sig[1]*3)
 print('INFO WAV files written to',WAVDIR)
print('PASSED',H.checks,'stretch experiment checks')
