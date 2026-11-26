"""Transient shaper: production C (src/transient_shaper.h) against the original
Joebox 3.5.zi code (BBEXTRA.BIN 0x0810E210), both run in Unicorn on a Cortex-M7.
Every output sample and every state word must match bit for bit.
Usage: JOEBOX_BBEXTRA=/path/to/joebox-3.5.zi/BBEXTRA.BIN python3 test_transient.py [stock]
(run_checks.py passes the stock image as argv[1]; it is not used here.)"""
import os,sys,struct,math,random,subprocess,pathlib,tempfile
from unicorn import *
from unicorn.arm_const import *
HERE=pathlib.Path(__file__).resolve().parent
JOE=pathlib.Path(os.environ.get('JOEBOX_BBEXTRA',''))
CC=os.environ.get('ARM_CC','arm-none-eabi-gcc');OBJCOPY=os.environ.get('ARM_OBJCOPY','arm-none-eabi-objcopy')
FLAGS='-mcpu=cortex-m7 -mfpu=fpv5-d16 -mthumb -mfloat-abi=hard -Os -ffreestanding -nostdlib -fno-builtin -fno-unwind-tables -fno-asynchronous-unwind-tables -Wall -Wextra -Werror'.split()
ORIG=0x0810e210;MINE=0x08200000|1;RAM=0x20000000;HALT=0x08300000
fails=0
def check(ok,msg):
    global fails
    print(('PASS ' if ok else 'FAIL ')+msg)
    if not ok:fails+=1
def build():
    t=pathlib.Path(tempfile.mkdtemp())
    subprocess.check_call([CC,*FLAGS,'-Wl,--build-id=none,-e,0','-T',str(HERE/'transient_arm.ld'),'-o',str(t/'ts.elf'),str(HERE/'transient_arm.c')])
    subprocess.check_call([OBJCOPY,'-O','binary','-j','.cave',str(t/'ts.elf'),str(t/'ts.bin')])
    return (t/'ts.bin').read_bytes()
def machine(joe,mine):
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
    u.mem_map(0x08100000,0x100000);u.mem_map(0x08200000,0x100000);u.mem_map(0x08300000,0x1000);u.mem_map(RAM,0x40000)
    u.mem_write(0x08100000,joe);u.mem_write(0x08200000,mine);u.mem_write(HALT,b'\xfe\xe7')
    return u
ST=RAM+0x100;PR=RAM+0x200;L=RAM+0x1000;R=RAM+0x9000;SP=RAM+0x3f000
def run(u,fn,state,params,l,r,n):
    u.mem_write(ST,state);u.mem_write(PR,params)
    u.mem_write(L,struct.pack('<%dI'%len(l),*l))
    if r is not None:u.mem_write(R,struct.pack('<%dI'%len(r),*r))
    u.reg_write(UC_ARM_REG_SP,SP-8);u.mem_write(SP-8,struct.pack('<ii',n,0))
    for reg,v in [(UC_ARM_REG_R0,ST),(UC_ARM_REG_R1,PR),(UC_ARM_REG_R2,L),(UC_ARM_REG_R3,R if r is not None else 0),(UC_ARM_REG_LR,HALT|1)]:u.reg_write(reg,v)
    u.emu_start(fn,HALT,count=5000000)
    return (bytes(u.mem_read(ST,36)),bytes(u.mem_read(L,4*len(l))),bytes(u.mem_read(R,4*len(r))) if r is not None else b'')
def f2u(x):return struct.unpack('<I',struct.pack('<f',x))[0]
def signal(kind,n0,n,rng):
    out=[]
    for i in range(n0,n0+n):
        if kind=='drums':  # decaying hits every 4800 samples
            ph=i%4800;x=math.exp(-ph/900.)*math.sin(i*.09)*.9+rng.uniform(-.02,.02)
        elif kind=='sine':x=.5*math.sin(i*.031)
        elif kind=='noise':x=rng.uniform(-1,1)
        elif kind=='hot':x=3.5*math.sin(i*.2)*(1 if (i//700)%2 else .01)
        else:x=0.
        out.append(f2u(x))
    return out
def main():
    if not JOE.is_file():print('SKIP: set JOEBOX_BBEXTRA to the Joebox 3.5.zi BBEXTRA.BIN');sys.exit(0)
    joe=JOE.read_bytes();mine=build()
    check(len(mine)<4096,'shaper code is %d bytes'%len(mine))
    rng=random.Random(7)
    cases=[]
    for model in (0,1,2,3):
        for (a,s) in [(1,0),(-1,0),(0,1),(0,-1),(.6,-.4),(-.3,.8),(0,0)]:
            for (spd,ln,out,mix) in [(.5,.5,.5,1),(0,0,.5,1),(1,1,.75,.5),(.2,.9,.25,0),(.8,.1,1,1)]:
                cases.append((model,a,s,spd,ln,out,mix))
    rng.shuffle(cases)
    same=0;total=0
    for ci,(model,a,s,spd,ln,out,mix) in enumerate(cases):
        params=struct.pack('<I6f',model,a,s,spd,ln,out,mix)
        ua=machine(joe,mine);ub=machine(joe,mine)
        sa=sb=bytes(36)
        if ci%5==4:  # start from a previous model's live state (model switch path)
            sa=sb=struct.pack('<6fiII',0.,.2,.1,.3,.5,.9,3,0x54535431,(model+1)%3)
        kind=['drums','sine','noise','hot','zero'][ci%5];pos=0;ok=True
        for blk,n in enumerate([32,32,7,3,1,32,16,5,32,32]*4):
            l=signal(kind,pos,n,rng);r=None if ci%3==0 else signal('noise' if kind=='zero' else kind,pos+11,n,rng)
            pos+=n
            ra=run(ua,ORIG|1,sa,params,l,r,n);rb=run(ub,MINE,sb,params,l,r,n)
            sa,sb=ra[0],rb[0]
            if ra!=rb:
                ok=False
                if total-same<3:print('  first mismatch case',ci,(model,a,s,spd,ln,out,mix),'block',blk,'n',n,'stereo',r is not None)
                break
        same+=ok;total+=1
    check(same==total,'bit-exact on %d/%d parameter sets (models, mono/stereo, odd block sizes)'%(same,total))
    sys.exit(1 if fails else 0)
main()
