"""Desktop compressor telemetry and UI integration under Unicorn.
Real stock compressor, constructor, queues and buffers are executed. An
unsupported Unicorn float32->float64 comparison is modeled in the harness.
This model changes no firmware bytes and is also used for the stock baseline.
"""
import importlib.util,pathlib,sys,struct,math,hashlib
from unicorn import *
from unicorn.arm_const import *
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('patcher',ROOT/'patch_bluebox.py');p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
stock=pathlib.Path(sys.argv[1]).read_bytes();patched=p.transform(stock);M=p.MANIFEST
# LOOPER=1: run against the Phrase Looper image built by `LOOPER=1 ./build.sh`
# (build/BLUEBOX-looper.BIN, checked against its manifest) instead.
import os,json
if os.environ.get('LOOPER')=='1':
 M=json.loads((ROOT/'build'/'looper_manifest.json').read_text())
 patched=(ROOT/'build'/'BLUEBOX-looper.BIN').read_bytes()
 if hashlib.sha256(stock).hexdigest()!=M['stock_sha256'] or hashlib.sha256(patched).hexdigest()!=M['patched_sha256']:
  raise SystemExit('looper image does not match build/looper_manifest.json; rebuild with LOOPER=1 ./build.sh')
LOOPER_BUILD=os.environ.get('LOOPER')=='1'
def theme_image(theme):
 """Firmware under test with a theme applied, as the patcher would apply it.
 Cobalt-only: the patcher itself. Looper: the patcher's theme field edits,
 with offsets inside the mod's code caves moved by the looper symbol table."""
 if not LOOPER_BUILD:return p.transform(stock,theme=theme)
 CM=p.MANIFEST
 syms=sorted((v,k,mod) for mod,t in CM['symbols'].items() for k,v in t.items() if isinstance(v,int))
 def relocate(off):
  a=off+0x08040000
  if not 0x080a0000<=a<0x080e0000:return off   # stock region: same in both images
  v,k,mod=max(x for x in syms if x[0]<=a)
  return M['symbols'][mod][k]+(a-v)-0x08040000
 selected=p.theme_values(theme,None);out=bytearray(patched)
 for field in CM['theme']['fields']:
  for off in field['offsets']:
   o=relocate(off);old=p.accent_bytes(field['default'],field.get('alpha',255))
   if out[o:o+4]!=old:raise ValueError('looper theme offset mismatch for '+field['key'])
   out[o:o+4]=p.accent_bytes(selected[field['key']],field.get('alpha',255))
 return bytes(out)
# FX1 mode 1 defaults for ids 0x1a1..0x1a3, its list name, and its control list.
GDEF=[(0x1a1,1000),(0x1a2,0),(0x1a3,2)] if LOOPER_BUILD else [(0x1a1,250),(0x1a2,80),(0x1a3,4)]
JDEF=1000 if LOOPER_BUILD else 0          # 0x1a4 default: Looper Dub 100%, Granular Jitter 0
XDEF=[(0x1ba,0),(0x1bb,0),(0x1bc,0)] if LOOPER_BUILD else []   # Looper STOP button, Stretch (Off), Echo (off), appended last
XIDS={0x1ba,0x1bb,0x1bc} if LOOPER_BUILD else set()     # ids the looper build adds
MODE1_NAME=b'Phrase Looper' if LOOPER_BUILD else b'Granular'
MODE1_TITLE=b'Looper' if LOOPER_BUILD else b'Granulr'
DENSITY_MAX=2 if LOOPER_BUILD else 4  # Looper Bars reuses the Density id
MODE1_IDS=[0x1a3,0x1a1,0x1a4,0x1bb,0x33,0x39,0x1bc,0x36,0x1a6,0x1a2,0x1ba,0x1a5] if LOOPER_BUILD else [0x1a1,0x1a2,0x1a3,0x4a,0x1a4,0x39,0x3d,0x1a5,0x1a6]
RET=0x080dfff0;NEXT_FN=0x080dff00;checks=0

def check(cond,msg):
 global checks
 if not cond:raise AssertionError(msg)
 checks+=1;print('PASS',msg)
def u32(u,a):return struct.unpack('<I',u.mem_read(a,4))[0]
def w32(u,a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
def f32(u,a):return struct.unpack('<f',u.mem_read(a,4))[0]
def machine(image=patched,double=False,cpu_model=UC_CPU_ARM_CORTEX_M7):
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB if double else UC_MODE_THUMB|UC_MODE_MCLASS);u.ctl_set_cpu_model(UC_CPU_ARM_MAX if double else cpu_model)
 for a,n in [(0x08000000,0x200000),(0x20000000,0x20000),(0x24000000,0x80000),(0x30000000,0x48000),(0x38000000,0x10000),(0x38800000,0x1000),(0x40024000,0x1000),(0x58024000,0x1000),(0xe000e000,0x1000),(0xc0000000,0x2000000)]:u.mem_map(a,n)
 if double:u.reg_write(UC_ARM_REG_FPEXC,0x40000000)
 u.mem_write(0x8040000,image);u.reg_write(UC_ARM_REG_C1_C0_2,0xf00000);return u
def call(u,a,*args,end=RET):
 for r,v in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):u.reg_write(r,v)
 u.reg_write(UC_ARM_REG_SP,0x2407f000);u.reg_write(UC_ARM_REG_LR,RET|1)
 u.emu_start(a|1,end,count=3000000)
 if u.reg_read(UC_ARM_REG_PC)!=end:raise AssertionError('Function timeout: '+hex(a))
 return u.reg_read(UC_ARM_REG_R0)
def stub(u,a,fn):
 def h(u,addr,size,data):fn(u);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
 return u.hook_add(UC_HOOK_CODE,h,begin=a,end=a)
OBJ=0xc0000000;CTX=0x30000000;BUF=0x24020000;QUEUE=CTX+12*0x604+4
NEXT=0x24030000;VT=NEXT+0x100

def setup(image=patched,chain=True):
 u=machine(image);heap=[0xc0010000];nexts=[]
 def alloc(u):
  size=u.reg_read(UC_ARM_REG_R0);a=heap[0];heap[0]=(a+size+15)&~15;u.reg_write(UC_ARM_REG_R0,a)
 stub(u,0x80412a4,alloc)
 def double_compare(u,a,n,_):
  value=struct.unpack('<f',struct.pack('<I',u.reg_read(UC_ARM_REG_S14)))[0]
  threshold=struct.unpack('<d',struct.pack('<Q',u.reg_read(UC_ARM_REG_D5)))[0]
  flags=3 if math.isnan(value) or math.isnan(threshold) else 2 if value>threshold else 6 if value==threshold else 8
  u.reg_write(UC_ARM_REG_FPSCR,(u.reg_read(UC_ARM_REG_FPSCR)&0x0fffffff)|(flags<<28));u.reg_write(UC_ARM_REG_PC,0x8042825)
 u.hook_add(UC_HOOK_CODE,double_compare,begin=0x804281c,end=0x804281c)
 call(u,0x8042364,OBJ,48000,32)
 w32(u,OBJ+0x18,12);u.mem_write(OBJ+0x1e,struct.pack('<H',12))
 if chain:
  w32(u,OBJ+8,NEXT);w32(u,NEXT,VT);w32(u,VT+12,NEXT_FN|1)
  def nextnode(u):
   nexts.append((u.reg_read(UC_ARM_REG_R0),u.reg_read(UC_ARM_REG_R1),u32(u,OBJ+8)));u.reg_write(UC_ARM_REG_R0,7)
  stub(u,NEXT_FN,nextnode)
 return u,nexts

def events(u,evs):
 for i,(pid,val) in enumerate(evs):u.mem_write(QUEUE+i*24,struct.pack('<B7xIHHiI',0x39,12,pid,0,val,0))
 w32(u,QUEUE+0x600,len(evs))
def block(u,l,r,evs=(),process=None):
 events(u,evs);u.mem_write(CTX+0x150e4+12*20,struct.pack('<IIIIBBxx',32,32,BUF,BUF+0x100,0,1))
 u.mem_write(BUF,struct.pack('<32f',*l));u.mem_write(BUF+0x100,struct.pack('<32f',*r))
 fn=process if process is not None else u32(u,u32(u,OBJ)+12)
 ret=call(u,fn,OBJ,CTX)
 return bytes(u.mem_read(BUF,128))+bytes(u.mem_read(BUF+0x100,128)),ret

def signal(amp,b,frequency=1000):return [amp*math.sin(2*math.pi*frequency*(b*32+i)/48000) for i in range(32)]
def report(u):return struct.unpack('<IHBBI',u.mem_read(0x38800f40,12))
