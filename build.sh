#!/bin/sh
set -eu
cd "$(dirname "$0")"
mkdir -p build
CC=${ARM_CC:-arm-none-eabi-gcc}
OBJCOPY=${ARM_OBJCOPY:-arm-none-eabi-objcopy}
NM=${ARM_NM:-arm-none-eabi-nm}
# LOOPER=1 builds the FX1 Phrase Looper variant (replaces Granular). The
# default build is unchanged, byte for byte.
DEFS=
if [ "${LOOPER:-0}" = "1" ]; then DEFS=-DPHRASE_LOOPER; fi
cc_() { "$CC" $DEFS "$@"; }
# Hot DSP loops (tape_fast_m7.c, dsp_fast_m7.c) build at -O2; all other M7
# code stays at -Os. No fast-math: float semantics are unchanged.
M7_FLAGS="-mcpu=cortex-m7 -mfpu=fpv5-d16 -mthumb -mfloat-abi=hard -ffreestanding -nostdlib -fno-builtin -fno-unwind-tables -fno-asynchronous-unwind-tables -Wall -Wextra -Werror"
for core in 7 4; do
  if [ "$core" = 7 ]; then FPU=fpv5-d16; else FPU=fpv4-sp-d16; fi
  cc_ -mcpu="cortex-m$core" -mfpu="$FPU" -mthumb -mfloat-abi=hard -Os \
    -ffreestanding -nostdlib -fno-builtin -fno-unwind-tables -fno-asynchronous-unwind-tables \
    -Wall -Wextra -Werror -Wl,--build-id=none,-e,0 \
    -T "src/cm$core.ld" -o "build/cm$core.elf" "src/cm${core}_cpu.c"
  "$OBJCOPY" -O binary -j .cave "build/cm$core.elf" "build/cm$core.bin"
  "$NM" "build/cm$core.elf" > "build/cm$core.symbols"
done
# PC map experiment: separate M4 payload so Cobalt's cm4 layout is unchanged.
cc_ -mcpu=cortex-m4 -mfpu=fpv4-sp-d16 -mthumb -mfloat-abi=hard -Os \
  -ffreestanding -nostdlib -fno-builtin -fno-unwind-tables -fno-asynchronous-unwind-tables \
  -Wall -Wextra -Werror -Wl,--build-id=none,-e,0 \
  -Wl,--defsym=sat_defs=0x$(awk '$3=="sat_defs"{print $1}' build/cm4.symbols) \
  -Wl,--defsym=cpu_present=0x$(awk '$3=="cpu_present"{print $1}' build/cm4.symbols) \
  -T src/pcm4.ld -o build/pcm4.elf src/pc_m4.c
"$OBJCOPY" -O binary -j .cave build/pcm4.elf build/pcm4.bin
"$NM" build/pcm4.elf > build/pcm4.symbols
# alpha.6 overdub fix: in-place PCM24 loops for the stock 0x081-page bodies.
"$OBJCOPY" -O binary -j .pcmhot build/cm4.elf build/pcmhot.bin
"$OBJCOPY" -O binary -j .pcmdm build/cm4.elf build/pcmdm.bin
"$OBJCOPY" -O binary -j .pcmds build/cm4.elf build/pcmds.bin
cc_ $M7_FLAGS -Os -c -o build/gr7_main.o src/gr_m7.c
cc_ $M7_FLAGS -O2 -fno-tree-loop-distribute-patterns -c -o build/gr7_fast.o src/tape_fast_m7.c
cc_ $M7_FLAGS -Wl,--build-id=none,-e,0 -T src/gr7.ld \
  -o build/gr7.elf build/gr7_main.o build/gr7_fast.o
"$OBJCOPY" -O binary -j .cave build/gr7.elf build/gr7.bin
"$NM" build/gr7.elf > build/gr7.symbols
cc_ $M7_FLAGS -Os -c -o build/delay7_main.o src/delay_m7.c
cc_ $M7_FLAGS -O2 -fno-tree-loop-distribute-patterns -c -o build/delay7_fast.o src/dsp_fast_m7.c
cc_ $M7_FLAGS -Wl,--build-id=none,-e,0 -T src/delay7.ld \
  -o build/delay7.elf build/delay7_main.o build/delay7_fast.o
"$OBJCOPY" -O binary -j .cave build/delay7.elf build/delay7.bin
"$NM" build/delay7.elf > build/delay7.symbols
cc_ -mcpu=cortex-m7 -mfpu=fpv5-d16 -mthumb -mfloat-abi=hard -Os \
  -ffreestanding -nostdlib -fno-builtin -fno-unwind-tables -fno-asynchronous-unwind-tables \
  -Wall -Wextra -Werror -Wl,--build-id=none,-e,0 -T src/gate7.ld \
  -o build/gate7.elf src/gate_m7.c
"$OBJCOPY" -O binary -j .cave build/gate7.elf build/gate7.bin
"$NM" build/gate7.elf > build/gate7.symbols
cc_ -mcpu=cortex-m7 -mfpu=fpv5-d16 -mthumb -mfloat-abi=hard -Os \
  -ffreestanding -nostdlib -fno-builtin -fno-unwind-tables -fno-asynchronous-unwind-tables \
  -Wall -Wextra -Werror -Wl,--build-id=none,-e,0 -T src/cue7.ld \
  -o build/cue7.elf src/cue_m7.c
"$OBJCOPY" -O binary -j .cave build/cue7.elf build/cue7.bin
"$NM" build/cue7.elf > build/cue7.symbols
cc_ -mcpu=cortex-m4 -mfpu=fpv4-sp-d16 -mthumb -mfloat-abi=hard -Os   -ffreestanding -nostdlib -fno-builtin -fno-unwind-tables -fno-asynchronous-unwind-tables   -Wall -Wextra -Werror -Wl,--build-id=none,-e,0   -Wl,--defsym=pc_present=0x$(awk '$3=="pc_present"{print $1}' build/pcm4.symbols)   -Wl,--defsym=gate_ui_tick=0x$(awk '$3=="gate_ui_tick"{print $1}' build/cm4.symbols) \
  -Wl,--defsym=pc_defs_hook=0x$(awk '$3=="pc_defs_hook"{print $1}' build/pcm4.symbols) \
  $(for s in gate_default gate_turn gate_track_local gate_track_bind gate_mix_setup gate_mix_construct gate_mix_local gate_column gate_mix_event theme_knob_palette; do printf -- '-Wl,--defsym=%s=0x%s ' $s $(awk -v s=$s '$3==s{print $1}' build/cm4.symbols); done)   -T src/cue4.ld -o build/cue4.elf src/cue_m4.c
"$OBJCOPY" -O binary -j .cave build/cue4.elf build/cue4.bin
"$NM" build/cue4.elf > build/cue4.symbols
rm -f build/gr7_main.o build/gr7_fast.o build/delay7_main.o build/delay7_fast.o
python3 tools/make_release.py "$@"
