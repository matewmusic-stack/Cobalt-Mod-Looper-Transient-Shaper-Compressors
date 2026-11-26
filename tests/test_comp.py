"""Per-track compressor: production C (src/joebox_comp.h) against the original
Joebox 3.5.zi master compressor (BBEXTRA.BIN 0x0810F3C8), both in Unicorn on a
Cortex-M7. Limit runs without lookahead: the original is run with Limit's
72-sample delay set to 0 in its mode table (the path the other modes use).
Every output sample and the detector/envelope state must match bit for bit.
Usage: JOEBOX_BBEXTRA=/path/to/joebox-3.5.zi/BBEXTRA.BIN python3 test_comp.py [stock]"""
import os,sys,struct,math,random,subprocess,pathlib,tempfile
from unicorn import *
from unicorn.arm_const import *
HERE=pathlib.Path(__file__).resolve().parent
JOE=pathlib.Path(os.environ.get('JOEBOX_BBEXTRA',''))
CC=os.environ.get('ARM_CC','arm-none-eabi-gcc');OBJCOPY=os.environ.get('ARM_OBJCOPY','arm-none-eabi-objcopy')
FLAGS='-mcpu=cortex-m7 -mfpu=fpv5-d16 -mthumb -mfloat-abi=hard -Os -ffreestanding -nostdlib -fno-builtin -fno-unwind-tables -fno-asynchronous-unwind-tables -Wall -Wextra -Werror'.split()
ORIG=0x0810f3c8;MINE=0x08200000|1;RAM=0x20000000;HALT=0x08300000;JSTATE=0x38800400
LIMIT_LOOK=0x0810f7ec+48*4+44
fails=0
def check(ok,msg):
    global fails
    print(('PASS ' if ok else 'FAIL ')+msg)
    if not ok:fails+=1
def build():
    t=pathlib.Path(tempfile.mkdtemp())
    subprocess.check_call([CC,*FLAGS,'-Wl,--build-id=none,-e,0','-T',str(HERE/'transient_arm.ld'),'-o',str(t/'c.elf'),str(HERE/'comp_arm.c')])
    subprocess.check_call([OBJCOPY,'-O','binary','-j','.cave',str(t/'c.elf'),str(t/'c.bin')])
    return (t/'c.bin').read_bytes()
def machine(joe,mine):
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
    for a,n in [(0x08100000,0x100000),(0x08200000,0x100000),(0x08300000,0x1000),(RAM,0x40000),(0x38800000,0x1000)]:u.mem_map(a,n)
    u.mem_write(0x08100000,joe);u.mem_write(0x08200000,mine);u.mem_write(HALT,b'\xfe\xe7')
    return u
L=RAM+0x1000;R=RAM+0x9000;ST=RAM+0x100;SP=RAM+0x3f000
def run(u,orig,mode,thresh,l,r,n):
    u.mem_write(L,struct.pack('<%df'%n,*l));u.mem_write(R,struct.pack('<%df'%n,*r))
    u.reg_write(UC_ARM_REG_S0,struct.unpack('<I',struct.pack('<f',thresh))[0])
    if orig:regs=[(UC_ARM_REG_R0,mode),(UC_ARM_REG_R1,L),(UC_ARM_REG_R2,R),(UC_ARM_REG_R3,n)];u.reg_write(UC_ARM_REG_SP,SP)
    else:
        regs=[(UC_ARM_REG_R0,ST),(UC_ARM_REG_R1,mode),(UC_ARM_REG_R2,L),(UC_ARM_REG_R3,R)]
        u.reg_write(UC_ARM_REG_SP,SP-8);u.mem_write(SP-8,struct.pack('<ii',n,0))
    for reg,v in regs+[(UC_ARM_REG_LR,HALT|1)]:u.reg_write(reg,v)
    u.emu_start((ORIG|1) if orig else MINE,HALT,count=20000000)
    st=bytes(u.mem_read(JSTATE+8,8) if orig else u.mem_read(ST+8,8))
    return bytes(u.mem_read(L,4*n))+bytes(u.mem_read(R,4*n)),st
def sig(kind,n0,n,rng):
    out=[]
    for i in range(n0,n0+n):
        if kind=='drums':ph=i%2400;x=math.exp(-ph/500.)*math.sin(i*.07)*1.2+rng.uniform(-.01,.01)
        elif kind=='sine':x=.7*math.sin(i*.013)*(1+.8*math.sin(i*.0005))
        elif kind=='noise':x=rng.uniform(-1,1)*(.05 if (i//3000)%2 else .9)
        elif kind=='hot':x=2.5*math.sin(i*.11)
        else:x=0.
        out.append(struct.unpack('<f',struct.pack('<f',x))[0])
    return out
def main():
    if not JOE.is_file():print('SKIP: set JOEBOX_BBEXTRA to the Joebox 3.5.zi BBEXTRA.BIN');sys.exit(0)
    joe=bytearray(JOE.read_bytes());mine=build()
    o=LIMIT_LOOK-0x08100000
    check(struct.unpack('<i',joe[o:o+4])[0]==72,'original Limit has a 72-sample lookahead; set to 0 for comparison')
    joe[o:o+4]=bytes(4);joe=bytes(joe)
    check(len(mine)<4096,'compressor code is %d bytes'%len(mine))
    rng=random.Random(11);same=0;total=0
    for mode in (2,3,4,5,6):
        for thresh in (-24.,-12.,-6.,0.,6.,12.):
            for kind in ('drums','sine','noise','hot','zero'):
                ua=machine(joe,mine);ub=machine(joe,mine);pos=0;ok=True
                for n in [32,32,7,1,32,16,32]*6:
                    l=sig(kind,pos,n,rng);r=[x*.6 for x in sig(kind,pos+17,n,rng)];pos+=n
                    if run(ua,True,mode,thresh,l,r,n)!=run(ub,False,mode,thresh,l,r,n):
                        ok=False
                        if total-same<3:print('  mismatch mode',mode,'thresh',thresh,kind,'at sample',pos)
                        break
                same+=ok;total+=1
    check(same==total,'bit-exact on %d/%d (5 modes x 6 thresholds x 5 signals, odd block sizes)'%(same,total))
    # Mode change resets the detector and envelope exactly as the original does.
    ua=machine(joe,mine);ub=machine(joe,mine);ok=True;pos=0
    for mode in (2,6,2,5,3,4):
        l=sig('drums',pos,32,rng);pos+=32
        ok&=run(ua,True,mode,-10.,l,l,32)==run(ub,False,mode,-10.,l,l,32)
    check(ok,'mode switches between blocks match (state reset)')
    sys.exit(1 if fails else 0)
main()
