# Cobalt Mod: Looper, Transient Shaper, Compressors for 1010music bluebox desktop

**Cobalt 1.2.0 + an FX1 Phrase Looper with Echo + a per-track transient shaper and compressor - for bluebox desktop firmware 1.5.2**

This repository is the [Cobalt](https://github.com/sbsmnt/bluebox-cobalt-mod) firmware mod with two additions: a **Phrase Looper** in FX1, in place of the Granular mode, with **Echo** (the stock FX1 delay played on the loop), and a per-track **TRANSIENT** shaper and **compressor** (ported from Joebox) in place of Cobalt's noise gate.

- **Part 1** (below) is what this repository adds: the Phrase Looper, Echo, and the transient shaper and compressor.
- **Part 2** is the original Cobalt 1.2.0 documentation, unchanged. Everything in it still applies.

**Open the looper web patcher: [matewmusic-stack.github.io/Cobalt-Mod-Looper-Transient-Shaper-Compressors/looper](https://matewmusic-stack.github.io/Cobalt-Mod-Looper-Transient-Shaper-Compressors/looper/)** - it runs locally in your browser on your own copy of the official 1.5.2 firmware. No firmware is distributed here.

> Not made, endorsed or supported by 1010music or by the Cobalt author. Keep a copy of your working firmware and back up your projects before installing.

## What is added

- **Phrase Looper (FX1, where Granular was):** 1 or 2 bar loops, recorded on the bar line and locked to the bluebox song position, so they stay on the beat.
- **External tempo:** the tempo is measured from the song position, so a master clock such as a 1010music Blackbox is followed without setting the bluebox BPM.
- **Transport:** the loop stops with the bluebox Stop and plays in step with Play.
- **REC / OVDUB** and **CLEAR** buttons, **Sync** (locked while a loop exists), **Bars**, **Level** and **Stretch** (Off / Vari / Keep).
- **Echo:** Time, Feedb, Echo and **Type** knobs plus a **Ping** button run the stock FX1 delay on the loop, in time with the song, as one delay type at a time: Warp, Tape, Duck(ed) or Delay.
- **Auto-mute** of the tracks feeding FX1 while the loop plays.
- **Detected tempo in the header,** right of the bar count, in every FX1 mode (measured from the song position, so it shows an external master's tempo).
- **TRANSIENT per track** (replaces Cobalt's Gate): on/off on the TRACK page (bottom-right knob, beside OUT2) and in a MIXER **Trans** column. Its settings are on **TRACK page 3**: Model (Differ / Punch / Smooth), Attack, Sustain, Speed, Length, Output and Mix.
- **Compressor per track on TRACK page 4:** Glue, Punch, Opto, Squash or Limit (the Joebox master compressor modes, Limit without lookahead) and Thresh.

# Part 1 - Added in this repository: Phrase Looper + Echo, transient shaper + compressor

> **Tested on one device only.** The Phrase Looper build has been installed and tried on a single bluebox desktop running firmware 1.5.2. It has not been tested on any other unit. See [Hardware testing](#hardware-testing-one-device) for what was checked. Keep the official firmware so you can go back.

## Install

**Looper web patcher: [matewmusic-stack.github.io/Cobalt-Mod-Looper-Transient-Shaper-Compressors/looper](https://matewmusic-stack.github.io/Cobalt-Mod-Looper-Transient-Shaper-Compressors/looper/)** publishes the current build (default theme SHA-256 `c699a6d0…`): the per-track TRANSIENT shaper and compressor (TRACK pages 3 and 4) in place of the Gate, and the Phrase Looper, locked to the song position, bar-quantized REC, Stretch, tempo measured from the song position (so it follows an external master clock), the loop following the transport, and Echo, the stock FX1 delay played on the loop and the live FX1 sends with a choice of delay type and its own Beat sync. This build has been tried on hardware. Drop in the original desktop 1.5.2 `BLUEBOX.BIN`; everything runs locally: the page checks the file, applies the looper patch with your theme, and offers the new `BLUEBOX.BIN`. **Restore** gives back the exact original. `patch_looper.py` does the same from the command line. Neither the stock firmware nor any patched image is included. `LOOPER=1 ./build.sh` does not touch the live page; `LOOPER=1 PUBLISH=1 ./build.sh` replaces `docs/looper/index.html` when a build is ready. GitHub Pages serves `docs/` from `main` directly (Settings → Pages → Deploy from a branch, `main` `/docs`), so a push to `main` publishes it.

Install the new `BLUEBOX.BIN` as any bluebox firmware: copy it to the root of the microSD card, hold **A** while powering on, and let go when "Bluebox Installer" appears. TOOLS then shows the looper readout, e.g. `4s 1.5M`, in the middle field.

## Using the looper

Turn up the FX1 send on the tracks to loop and select **Phrase Looper** in the FX1 mode list (where Granular was). The header shows the detected tempo right of the bar count, for example `12:2 126`, whatever FX1 is set to. The FX1 title shows the state: `Looper` (empty), `ARMED`, `REC 1/2`, `PLAY`, `DUB` or `STOP`. Once the looper has measured a tempo, the empty title shows it instead, for example `Lp128.0`.

Page layout. The physical knobs turn the knobs of one highlighted group of four list entries; buttons are never on them.

| Left | Knob group 1 | Knob group 2 | Right |
|---|---|---|---|
| REC / OVDUB (top) | Bars, Stretch | Time, Echo | Ping |
| CLEAR (below) | Level, Sync | Feedb, Type | Beat |

The loop follows the bluebox transport: Stop (the button, or the external master stopping) stops the loop, and Play plays it again in step with the song. There is no on-screen STOP and no Dub knob: they were too easy to hit during a set, and overdubs are layered at full level.

| Control | Kind | What it does |
|---|---|---|
| REC | button | Empty: record (on the next bar line while the sequencer plays); at the end of the bars the loop plays by itself. Recording: end on the next bar line. Once a loop exists the button reads **OVDUB**: overdub on/off (a stopped loop overdubs from the start). |
| CLEAR | button | Empty the loop. |
| Sync | on/off (default off), in knob group 1 | The looper's own sync. On: with the sequencer stopped, REC arms and recording starts when it starts. REC again cancels. Locked while a loop exists: a change is put back at once. |
| Bars | 1 or 2 (default 2) | Loop length in 4/4 bars at the current tempo, measured from the song position, so an external master (e.g. a Blackbox) is followed without setting the bluebox BPM. Before the sequencer has run: the MIDI clock or the project BPM. |
| Level | 0–100 % (default 100 %) | Loop volume on the FX1 return. The return carries only the loop. |
| Stretch | Off / Vari / Keep (default Off) | What the loop does when the tempo changes after recording. Off: keeps its recorded speed. Vari: varispeed, stays in time and the pitch follows the tempo. Keep: stays in time at the same pitch (WSOLA time-stretch). |
| Time | delay time | The stock delay's Time: a note division while Beat is on (default), so the echoes follow the tempo; ms when off. Filter, Drift etc. come from the Delay page. |
| Feedb | 0–100 % | Stock delay feedback: how many repeats. |
| Echo | 0–100 % (default 0 = off) | How much of the loop and the live FX1 sends goes into the stock delay. The FX1 return carries loop + echoes; the live tracks are heard dry on the mixer, so only their echoes come back. Works with no loop too (a plain send delay). Back to 0, the echoes ring out, then the delay is skipped again. |
| Type | Warp / Tape / Duck / Delay (default Warp) | The echoes' delay type; exactly one runs at a time, on the echoes only. Warp: Drift and Pitch (if set). Tape: tape saturation, Hi C, Lo C and its Drift. Duck (Ducked): the echoes duck under the loop and swell into its gaps. Delay: the stock delay only (no Drift, Pitch or reverb send). Each type's settings come from its own FX1 page and are saved with the project. Slow notched travel. Reverse is not offered: it needs the buffer the loop lives in. |
| Ping | button (top right) | Stock ping-pong: repeats alternate left and right. |
| Beat | button (bottom right) | The delay's tempo sync (stock Beat), separate from the looper's Sync. On (default): Time is a note division. Off: Time in ms. |

Auto-mute: while the loop plays, the M4 mutes the tracks whose FX1 send is above 0 and that were not already muted. It uses the same native knob call as Scenes recall, so the Mute buttons, the saved project and the audio engine all follow. Those tracks are unmuted while recording or overdubbing, and on stop, CLEAR or leaving the mode. A track the user unmutes during playback stays unmuted, and tracks the user muted are never touched. The record of muted tracks is cleared at boot and on project or bank loads, without unmuting anything.

## Echo: the stock delay after the looper

Time, Feedb, Echo and Type (knob group 2) and the Ping button run the stock FX1 delay on the loop. Echo 0 is off. With Beat on (the default; the Beat button on the looper page) Time is a note division, so the echoes follow the tempo, including an external master.

**Echo.** With Echo above 0 and the looper fully faded in, the stock FX1 delay is no longer skipped: the loop is rendered first, written into the delay's bus at the Echo level, the stock delay body runs on it, and the loop is added back to the echoes. No memory is added (the stock delay's rings already exist; the ring-clear state machine keeps stale audio out when it resumes). Echo is a new parameter, `0x1bc` (`lpecho`), in an empty stock slot. Measured on the firmware in the emulator (`tests/test_looper_echo.py`): a click returns exactly as the stock impulse response; worst block 8.3k instructions with Echo (tested Granular: 14.8k–16.8k).

**Echo type.** Type is a new list parameter, `0x1bd` (`lpetype`). The FX1 delay types are flags on the same stock delay engine, so Type only chooses which type's extras run: `x_kind()` in `delay_types.h` maps FX1 mode 1 (the looper) to the chosen type for the Tape stage, ducking, Drift and Pitch; the Cobalt-only build compiles identically. Duck uses the loop plus the live FX1 sends as its key. An emulator check turns every type's controls up at once and confirms only the selected type's processing runs. Worst block with Ping on (instructions; Granular peaked at 16.8k on hardware):

| Stretch | Warp | Tape | Duck |
|---|---|---|---|
| Off | 9.1k | 13.3k | 11.9k |
| Vari | 13.3k | 17.4k | 16.1k |
| Keep | 13.3k | 17.5k | 16.2k |

On the bluebox the CPU bar stays green with Keep + Tape + Ping.

## Transient shaper and compressor (TRACK pages 3 and 4)

The looper build replaces Cobalt's per-track noise gate with a **transient shaper** and adds a per-track **compressor**. Both are C ports of the Joebox 3.5 algorithms, checked sample for sample against the original code in the emulator (`tests/test_transient.py`, `tests/test_comp.py`). The Gate is retired: its TRACK knob and MIXER column now control TRANSIENT, and saved Gate thresholds are ignored.

**The TRACK button** now cycles through four pages: the TRACK view → Side Chain → page 3 (transient) → page 4 (compressor) → back to the TRACK view.

**TRANSIENT on/off.** In the TRACK view the bottom-right knob (beside OUT2, where GATE was) reads `TRANS ON` / `OFF`: tap it or turn encoder 4. In MIXER the Gate column is now **Trans** (`TS` when OUT3 is present), one on/off per track; Main shows N/A. The shaper runs only while TRANSIENT is on.

**Page 3: shaper settings** (per track, saved in the project):

| Control | Range | What it does |
|---|---|---|
| Model | Differ / Punch / Smooth | The Joebox detector model |
| Attack | −100 … +100 % | Boost or soften the hit |
| Sustain | −100 … +100 % | Boost or tame the tail |
| Speed | 0 … 100 % | Detector speed |
| Length | 0 … 100 % | How long the attack stage lasts |
| Output | −12 … +12 dB | Output gain |
| Mix | 0 … 100 % | Dry/wet |

Encoders 1–4 turn Attack, Sustain, Speed and Length. Tap Model, Output or Mix to put it on encoder 4; tap Length to give encoder 4 back. Attack and Sustain at 0 with Output at 0 dB pass the audio unchanged.

**Page 4: compressor.** Encoder 1 picks the mode: Off, Glue, Punch, Opto, Squash or Limit (the Joebox master compressor table, bit for bit). Encoder 2 is Thresh, −24 … +12 dB: an offset to the mode's threshold, or for Limit the drive into a fixed −0.3 dBFS ceiling. Joebox's Limit delays the audio 1.5 ms (lookahead); here every mode runs with no delay, so Limit lets slightly more peaks reach the hard clip (2.9 % against 2.4 % of samples on a loud drum test). The compressor runs after the shaper, and it runs whether TRANSIENT is on or off. Its CPU cost is estimated at about 110–120 instructions per stereo sample per track, so many tracks at once can add noticeably to the CPU meter; this has not been measured on hardware.

**How it works.** Ten new per-track settings, `0x1be`–`0x1c7`, in empty stock definition slots (track settings lists: 62 of 68 entries used). The M7 runs the shaper and compressor after the old gate point in each track's chain, with state in one SDRAM block allocated at boot (`ts_allocate`). The M4 code (`src/transient_m4.h`) lives in the cue-icon payload, because the Cobalt M4 code space is full. It rebinds the TRACK panel's eight knobs from a new page flag (2 = page 3, 3 = page 4), relabels them, and draws the boxes. `tests/test_transient_page.py` drives the TRACK button cycle, the knobs, the labels and the MIXER column through the real UI code in the emulator. The old Gate tests are kept in `tests/retired_gate/`.

**Hardware:** build `ddb1f45d…` on the same bluebox: the TRACK cycle to pages 3 and 4, the TRANSIENT button, the page-3 labels and the compressor page were confirmed. In one case the TRACK view came back with the page-3 names (MODEL, OUTPUT, MIX) on the VOL, PAN and GAIN knobs (photo 1 below). The knobs still turned VOL, PAN and GAIN; only the names were wrong. The current build `c699a6d0…` checks those three names on every frame and puts the right ones back; confirmed on the device. The sound of each model and mode, and the CPU load with many tracks, have not been checked in detail.

| | | |
|---|---|---|
| ![TRACK view with TRANS ON](images/hardware/v16-1-track-view-trans-on.jpg) | ![TRACK page 3: transient shaper](images/hardware/v16-2-track-page3-transient.jpg) | ![TRACK page 4: compressor, Limit](images/hardware/v16-3-track-page4-comp-limit.jpg) |
| **TRACK view** (`ddb1f45d…`): `TRANS ON` beside OUT2, where GATE was. The left knobs show the stale page-3 names, fixed in `c699a6d0…` | **Page 3:** Model `SMOOTH`, Output, Mix and the title box (`TRANS ON`, `4 LENGTH`: Length on encoder 4); encoders on Attack, Sustain, Speed, Length | **Page 4:** Mode `LIMIT` on encoder 1, Thresh on encoder 2; the other knobs blanked, title `COMP PAGE 4` |

## Hardware testing (one device)

All hardware testing so far was done on **one bluebox desktop** (official firmware 1.5.2), with the current looper image `c699a6d0…` (the knob-name fix), `ddb1f45d…` (transient shaper and compressor), `162a50a3…`, `c2c58e04…` (header tempo rounded), `e7dd3237…` (header tempo with the decimal), `f4fab10b…` (version 12), `3f14345a…` (version 10), `1438c1ad…` (external tempo), `73d9066f…` (song-position lock), `dc79805d…` (before Stretch) and earlier development builds, clocked by a 1010music Blackbox as master. Results on other units may differ, for example in how much SDRAM is free when FX1 is built.

Build `162a50a3…`, clocked by the Blackbox at 126 BPM:

| | |
|---|---|
| ![Looper page: Sync in knob group 1, Beat bottom right; header 104:2 126](images/hardware/v15-1-layout-sync-beat-header-104.jpg) | ![TOOLS 4s 1.5M](images/hardware/v15-2-tools-4s-1.5m.jpg) |
| **Layout:** Sync in the open spot of knob group 1, BEAT (the delay's sync) bottom right below Ping. Header `104:2 126`: the tempo shows in full past bar 100 | **TOOLS:** `4s 1.5M`, the longest loop and the free SDRAM, now inside its field |

Build `c2c58e04…`, clocked by the Blackbox at 128 and then 126 BPM:

| | |
|---|---|
| ![Empty, tempo in title and header](images/hardware/v14-1-empty-tempo.jpg) | ![ARMED](images/hardware/v14-2-armed.jpg) |
| **Empty:** title `Lp128.1`, header `3:4 128` (rounded). Time `1 bar` | **ARMED:** REC pressed with the song playing, waiting for the bar line |
| ![REC 1/2](images/hardware/v14-3-rec-1-of-2.jpg) | ![REC 2/2](images/hardware/v14-4-rec-2-of-2.jpg) |
| **REC 1/2** from the bar line (`8:2`) | **REC 2/2** |
| ![PLAY, OVDUB, Warp](images/hardware/v14-5-play-ovdub-warp.jpg) | ![Echo type Duck](images/hardware/v14-6-echo-duck.jpg) |
| **PLAY:** button reads `OVDUB`; knob group 2 selected: Time `1/8D`, Type `Warp` | Echo Type `Duck` |
| ![Echo type Delay](images/hardware/v14-7-echo-delay.jpg) | ![126 BPM, Keep](images/hardware/v14-8-126bpm-keep.jpg) |
| Echo Type `Delay` | **Tempo change:** the Blackbox at 126, header `52:2 126`; Stretch `Keep`, Ping on |
| ![126 BPM, Vari](images/hardware/v14-9-126bpm-vari.jpg) | |
| Stretch `Vari` at 126 | |

Build `e7dd3237…` (header tempo with the clipped decimal), clocked by the Blackbox:

| | |
|---|---|
| ![Empty, tempo in title and header](images/hardware/v13-1-empty-tempo.jpg) | ![REC 1/2](images/hardware/v13-2-rec-1-of-2.jpg) |
| **Empty:** title `Lp126.0`, header `3:2 126.` (detected tempo right of the bar count). Knob group 1: Bars, Stretch (`Off`), Level; group 2: Time (`1/64`), Echo, Feedb, Type (`Warp`); Ping and Sync on the right | **REC 1/2** on the bar line, header `10:2 126` |
| ![REC 2/2](images/hardware/v13-3-rec-2-of-2.jpg) | ![PLAY, OVDUB](images/hardware/v13-4-play-ovdub.jpg) |
| **REC 2/2** | **PLAY:** the button now reads `OVDUB` |
| ![Echo type Delay](images/hardware/v13-5-echo-type-delay.jpg) | ![Echo Warp, 1/8D](images/hardware/v13-6-echo-warp-dotted.jpg) |
| **Knob group 2 selected** (the physical knobs turn Time, Echo, Feedb, Type): Time `1/8`, Type `Delay` | Time `1/8D`, Type `Warp` |
| ![Ping on](images/hardware/v13-7-ping-on.jpg) | ![Ping on, later](images/hardware/v13-8-ping-on-later.jpg) |
| **Ping on** (top right) | Ping on, bar 52 |
| ![Keep at 128 BPM](images/hardware/v13-9-keep-128bpm.jpg) | |
| **Tempo change:** the Blackbox at 128, header `64:4 128`; Stretch `Keep` | |

Version 10 (`3f14345a…`), clocked by the Blackbox at 128 BPM, taking a 2-bar loop:

| | |
|---|---|
| ![Looper empty, measured tempo](images/hardware/v10-looper-empty-tempo.jpg) | ![ARMED](images/hardware/v10-armed.jpg) |
| **Empty:** the title shows the tempo measured from the song position, `Lp128.0`. Left: REC, CLEAR. Knob group 1: Bars, Stretch (`Keep`), Level. Group 2: Time (`1/8`), Echo, Feedb. Right: Ping, Sync | **ARMED:** REC pressed while the song plays; the take waits for the next bar line |
| ![REC 1/2](images/hardware/v10-rec-1-of-2.jpg) | ![REC 2/2](images/hardware/v10-rec-2-of-2.jpg) |
| **REC 1/2:** recording the first of 2 bars | **REC 2/2:** the second bar; the take closes on the bar line |
| ![PLAY, OVDUB](images/hardware/v10-play-ovdub.jpg) | ![TOOLS capacity readout](images/hardware/v10-tools-capacity.jpg) |
| **PLAY:** the loop plays in step; the REC button now reads `OVDUB` | **TOOLS:** `L4.0s` longest loop, `F1…` free SDRAM when FX1 was built (readout cut off; fixed in `162a50a3…`) |

Earlier builds:

| | |
|---|---|
| ![FX1 mode menu](images/hardware/fx1-mode-menu.jpg) | ![Empty looper](images/hardware/looper-page-empty.jpg) |
| **FX1 menu (B):** Phrase Looper in place of Granular | **Looper page, empty (earlier build):** title `Looper`; Bars, Level and Dub knobs; REC, STOP, CLEAR and Sync |
| ![Looper page, 1 bar](images/hardware/looper-page-1-bar.jpg) | ![Looper page, 2 bars](images/hardware/looper-page-2-bars.jpg) |
| **Bars = 1 bar,** title `STOP` | **Bars = 2 bars,** title `STOP`, Sync on |
| ![TOOLS capacity readout](images/hardware/tools-capacity-readout.jpg) | |
| **TOOLS:** `L4.0s` = 4 s longest loop, `F1…` = arena free when FX1 was built. The readout was too wide for its field (fixed in `162a50a3…`: `4s 1.5M`). | |

Confirmed on that unit:

- the looper build installs (hold **A** at power-on) and boots, and the other Cobalt features keep working in normal use;
- FX1 lists Phrase Looper, and the looper page shows its controls and live title;
- tempo: a 1-bar loop at 120 BPM lasts 2 s (earlier build);
- with the sequencer running, REC waits for the bar line, and the loop stays on the beat over many passes (`73d9066f…`);
- with the Blackbox as master clock, the loop follows project changes with slightly different tempos (e.g. 126 → 128), and the looper detects the external tempo and records the next loop in sync without touching the bluebox BPM (`1438c1ad…`);
- 2-bar takes at 128 BPM on the bar lines: ARMED, REC 1/2, REC 2/2, PLAY (photos above);
- version 10 (`3f14345a…`) installed and tested: Echo on the loop, the new page layout and knob groups, transport stop, OVDUB and the Sync lock;
- current build `c699a6d0…`: the TRACK view always comes back with VOL, PAN and GAIN;
- build `ddb1f45d…`: the TRACK button cycle (view → Side Chain → page 3 → page 4), the TRANSIENT button in the TRACK view and MIXER, the page-3 shaper labels and the page-4 compressor page;
- build `162a50a3…`: the new layout (Sync in knob group 1, BEAT bottom right), the header tempo in full past bar 100 (`104:2 126`, bar-count label widened from 100 to 124 px), TOOLS `4s 1.5M` inside its field (photos above);
- build `c2c58e04…`: the header tempo rounded to whole BPM (`128`, `126`), ARMED, REC 1/2 and 2/2 on the bar lines, OVDUB, echo types Warp, Duck and Delay, Ping, and the loop following the Blackbox from 128 to 126 with Stretch Keep and Vari (photos above);
- build `e7dd3237…`: the detected tempo in the header (decimal clipped by the label), 2-bar takes on the bar lines, OVDUB, the knob groups on the physical knobs, echo types Warp and Delay, Ping, and the loop following a tempo change to 128 with Stretch Keep (photos above);
- the echo Type knob and the CPU: the CPU bar stays green with Stretch Keep, Tape echo and Ping (version 11), and the current build `f4fab10b…` with the smooth Vari/Keep lock;
- known: REC or CLEAR pressed within a few seconds of a project/bank change (e.g. the Blackbox switching projects) can stay lit, because Cobalt pauses its button and mixer upkeep during loads; the next press only turns it off;
- the free arena when FX1 is built is only about 1.5 MB (TOOLS `1.5M`), so the looper uses the tested 768,000-byte buffer: 4 s, which is 2 bars at 120 BPM or faster. An earlier 32-bit build fell back to 1 bar for this reason (title `REC 1/1`).

Not yet confirmed on hardware:

- 2 bars at exactly 120 BPM, the length of the 4 s buffer (2-bar takes at 128 BPM are confirmed, see the photos);
- REC, STOP and CLEAR switching themselves off, and auto-mute of the tracks feeding FX1;
- Stretch Vari and Keep by ear;
- a take started by pressing start with Sync on (it begins when the position first moves, up to 0.7 ms after the downbeat);
- CPU load and sound over long sessions;
- the live FX1 sends in the Echo (emulator-tested), and BEAT off switching Time to milliseconds.

Keep the stock `BLUEBOX.BIN` at hand before trying it.

## How it works

REC, STOP and CLEAR are pedal-style: the M7 counts a press when a button goes from 0 to 1 in the FX1 event queue, and the M4 sets it back to 0 at once, so the buttons never stay lit. A value seen before the first one, such as a project load, only latches. STOP uses a new FX1 parameter, `0x1ba` (`lpstop`), in an empty stock definition slot; it is no longer on the page (the transport stops the loop).

How it works: the looper uses the Granular SDRAM buffer, allocated once when FX1 is built and before FX2. Loop audio is stored as 16-bit stereo, scaled so ±2.0 (overdub headroom) fills the range, at 4 bytes per frame. The hardware-tested Granular size (768,000 bytes) therefore holds 4 s: 2 bars at 120 BPM. When more SDRAM is free than that plus a 4 MB reserve, the buffer grows to whatever fits, up to 2 bars at 60 BPM (1,536,000 bytes). Longer loops drop to 1 bar, then to the buffer length. The TOOLS middle field shows the longest loop and the arena space that was free for it at boot, for example `4s 1.5M` (whole seconds, then MB). On the first hardware test the old 32-bit buffer could not get its 7 MB and fell back to 2 s, so 2 bars became 1. The M4 publishes the project BPM (setting `0x85`, plain BPM 40–250), the sequencer state, its mute record and the measured MIDI clock tempo to backup SRAM `0x38800EE0`. The M7 looper state lives at `0x38800EA0`, and its first cache line is cleaned after every block for the M4 (title and auto-mute). FX2 and the bootloader are not patched. Leaving the looper mode empties the loop.

**Sync to the sequencer.** The looper follows the bluebox's song position, the 960-ticks-per-beat count behind the `bar:beat` display. On the M7, each block reads `*(0x3000a894)+0x78b0` (or `+0x78b8`, by the app flag `+0x7408`, as the display does). It keeps its own sample-accurate position from the tempo, pulled 1/8 of the way toward each new value; a jump of more than one beat (start, locate) is taken at once.

- **REC with the sequencer running** waits for the next bar line (ARMED). The take ends on the bar line Bars bars later, so it is exactly that many bars of song time. When the sequencer is stopped, Sync on waits for the start, and Sync off records at once (free). A bar-line wait whose sequencer stops falls back to recording at once. A take started by the sequencer starting begins when the position first moves, up to one block (0.7 ms) after the downbeat.
- **Playback while the sequencer runs** is locked to the song: Off plays 1:1 and restarts on every loop cycle, and Vari and Keep map the whole loop onto the cycle. A free loop locks where it is when the sequencer starts. When the transport stops, the loop stops; when it starts, the loop plays in step with the song.
- **2 bars on the tested 4 s buffer** fit exactly at 120 BPM. A sequencer up to 1% slower ends the take at the buffer, still locked.
- Measured on the firmware in the emulator (`tests/test_looper_sync.py`): with the sequencer 0.5% off the stated tempo, 20 restarts in 20 bars, the worst 0.68 ticks (17 µs) from the bar line. With the position updated only every 3rd block with ±2 ticks of noise, the worst is 0.84 ticks. After a 120 → 128 BPM change, Off restarts within 0.45 ticks of each bar line, and Vari and Keep stay within 23 samples of the song phase. The worst block is 11.9k instructions (the tested Granular: 14.8k+).

**Tempo from the song position.** The tempo the looper uses is measured from the song position itself: at each beat crossing it stores the position and the sample count, and the tempo is ticks ÷ samples over up to the last 7 beats. It therefore follows whatever drives the sequencer, the bluebox's own BPM or an external master, with no need for the project BPM to match. This fixed the first hardware report with a Blackbox as master: after switching from a 126 to a 128 BPM project the loop followed, but the next take needed the bluebox BPM set to 128 by hand. A tempo change settles within about 7 beats. The measured tempo sets the take length, drives the position lock between updates, and is the recorded tempo for Stretch. After the sequencer stops it is kept (an external clock stopping leaves the bluebox BPM where it was) until the stated tempo is changed while stopped; before the sequencer has run, the looper uses the MIDI clock or project BPM below. The M7 publishes it in the looper state's second cache line, also cleaned every block, for the title. Measured on the firmware in the emulator with the bluebox at 126 and the song at 128: 128.02 BPM, the next 2-bar take is 180,000 samples (exactly 2 bars at 128), locked, and lands on the bar lines for 20 bars.

**External MIDI clock.** When the bluebox receives MIDI clock, the looper measures its tempo directly instead of trusting the project BPM. Cobalt's MIDI pump (`mo_next`, in the MIDI timer interrupt) already chooses which input owns clock (Clock Src). Every accepted clock tick (0xF8, 24 per beat) is counted, and every 24th is timestamped with the 1 ms UI clock. The tempo is beats ÷ time over up to the last 8 beats (about 4 s at 120 BPM), in hundredths of a BPM. If a single beat differs by more than 2%, the window restarts, so tempo changes are followed within two beats. The looper uses this tempo for loop length and Stretch whenever it is between 20 and 300 BPM, and falls back to the project BPM 300 ms after the last tick. Measured through the real `mo_next` in the emulator: 100.00 BPM exactly, 128.00 after a change from 100, 98.75 for 98.73, and 120.00 with ±1 ms jitter on every tick. This clock tempo is the fallback before the song position has been measured; while the sequencer runs, the loop is locked to the song position.

**Tempo follow (Stretch).** The loop remembers the BPM it was recorded at, and with Stretch on it follows the current tempo (rate = now ÷ recorded, limited to 0.5–2×). *Vari* reads the loop at that rate with 4-point cubic Hermite interpolation. *Keep* plays 2048-frame (43 ms) Hann grains at normal speed, one every 1024 frames, and starts each grain at the offset (±5 ms) whose start best matches the previous grain's continuation (WSOLA). The search is spread over the blocks between grains, so no block is heavy. Its state (96 bytes, then 128 bytes of sync and tempo state) sits after the loop audio, so the buffer request is 768,224 bytes. The read position is kept as whole samples plus a fraction: a single float position loses up to 0.4% of the rate above 65,536 samples. Measured in the emulator (`tests/test_stretch.py`, 1 bar recorded at 120 BPM, played at 112 and 128 BPM):

| | Off | Vari | Keep |
|---|---|---|---|
| Beat timing | 120 BPM (drifts) | new tempo, within 0.03 % | new tempo; single beats ±5 ms |
| 440 Hz tone at 112 / 128 BPM | 440 / 440 Hz | 410.67 / 469.33 Hz | 440.1 / 439.9 Hz |
| Tone residual | −79 dB | −79 dB | −35 to −39 dB |
| Instructions per block, worst | 3.3k | 6.9k | 9.2k (tested Granular: 14.8k–16.8k) |

At the recorded tempo both modes play the loop unchanged. While stretched, overdubbing layers input at the current read position.

**Header tempo.** The header builds its bar count with `snprintf("%d:%d")` at `0x08139810`; in the looper build that call goes to `lp_header_bar`, which appends the tempo. With the Phrase Looper in FX1 it uses the looper's sample-accurate measurement; otherwise `lp_song_tempo` (M4, every pass of the UI loop) reads the same song position, stores it with the UI millisecond clock at each beat, and measures over the last 2 to 7 beats; else the MIDI clock tempo. The next header label is placed after the text's measured width, as before. The header label clips text past about 8 characters, so the tempo is shown rounded to whole BPM (`126`): a clipped `125.9` would have read as `125` (the build `e7dd3237…` in the photos showed the clipped decimal, e.g. `3:2 126.`). Tested through the real UI loop with FX1 on another mode: 126, 128 and 122 for 122.37 BPM, kept while stopped.

**Smooth lock (no crunch).** Locked to the song, Vari and Keep used to set their read position from the song phase on every sample, so it jumped with each song-position update: audible grit. The read position now runs at the song's speed and is steered once per block (a 0.1 s pull plus a learned speed correction over 0.5 s, at most ±10%; more than 50 ms off jumps). Keep also plays the loop straight while the speed is within 0.2% of the recording (hysteresis to 0.4%), and splices grains only when the tempo really differs. Emulator, chord loop, song running at the recorded tempo: Vari high-frequency grit +45.9 → +17.3 dB over the clean chord (Off, the 16-bit floor: +19.6), Keep worst-window smearing −42 → −53 dB; after a sudden 120 → 128 BPM jump the loop stays within 5 ms of the song while catching up, then within 0.5 ms. Input louder than ±2.0 (+6 dB over full scale) clips in the 16-bit loop.

## Building and testing the looper

The looper is built as a separate firmware variant. The default build is unchanged: it still reproduces the released Cobalt 1.2.0 image (SHA-256 `c28981e5…`), and `patch_bluebox.html` and `docs/index.html` stay Cobalt-only.

```sh
# Arm GNU Toolchain 13.2.Rel1 on PATH, as for the normal build
LOOPER=1 ./build.sh /path/to/stock/BLUEBOX.BIN   # writes build/BLUEBOX-looper.BIN
```

Host checks for the looper logic (any C compiler):

```sh
cc -std=c11 -O1 -Wall -Wextra -Werror -DPHRASE_LOOPER -Isrc tests/looper_host.c -o build/looper_host -lm && build/looper_host
```

### Testing in the emulator

The upstream Unicorn suite runs against either build. With `LOOPER=1` it loads `build/BLUEBOX-looper.BIN` (checked against `build/looper_manifest.json`) instead of the Cobalt-only image:

```sh
python3 -m venv .venv && .venv/bin/pip install unicorn==2.1.4 capstone==5.0.9
LOOPER=1 .venv/bin/python tests/test_looper.py /path/to/stock/BLUEBOX.BIN
LOOPER=1 .venv/bin/python tests/test_wild_094.py /path/to/stock/BLUEBOX.BIN
```

`tests/test_looper.py` runs the compiled looper inside the stock native FX1 delay object, with the M4 side on the real parameter tables: construction and SDRAM allocation (roomy, tight and full arenas), pedal presses through the FX1 event queue, record and playback of the 16-bit loop, a read watch (no unrecorded frame is ever read), Level, overdub, STOP and CLEAR, auto-mute and unmute through the native knob call, the button reset, the FX1 title states, Sync driven by the real M4 tempo publisher, BPM, early-closed takes, overdub bounds, a buffer-overrun watch, leaving the mode, the TOOLS capacity readout, and instruction counts relative to the hardware-tested Granular mode. Every other `tests/test_*.py` also runs with `LOOPER=1`. The six Granular-renderer suites report SKIP there, and `test_wild_094.py` checks that Tape, Warp, Ducked, Reverse and Delay match Cobalt v0.9.4. The emulator does not model STM32 timing, the caches shared between the two cores, or sound.

---

# Part 2 - Cobalt 1.2.0 (upstream, unchanged)

Everything below is the original Cobalt 1.2.0 documentation by sbsmnt ([bluebox-cobalt-mod](https://github.com/sbsmnt/bluebox-cobalt-mod)). It all still applies to the looper build, except that FX1 Granular is replaced by the Phrase Looper. The patcher linked here is the upstream, Cobalt-only one.

**v1.2.0 - for bluebox desktop firmware 1.5.2**

Cobalt is an unofficial firmware mod for the bluebox desktop. It adds delay
modes, a new reverb, a per-track noise gate, master saturation, compressor
meters, an overdub recording fix, mixer scenes with MIDI recall, MIDI
controller sync and custom colour themes. The patcher runs locally: it takes your copy of the official
1.5.2 firmware and writes a new `BLUEBOX.BIN`. No firmware is distributed
here.

**Open the patcher: [sbsmnt.github.io/bluebox-cobalt-mod](https://sbsmnt.github.io/bluebox-cobalt-mod/)**

> Cobalt is not made, endorsed or supported by 1010music. Keep a copy of your
> working firmware and back up your projects before installing.

## New in v1.2

- **Phones Src AUTO:** MAIN → B → Phones Src has a third choice, AUTO. The
  phones play the cue mix while any track is cued and the main mix
  otherwise, like PFL on a DJ mixer.
- **Cue icons:** a small headphone marks every cued track on the track
  headers.
- **Unconfigured tracks:** tracks with no input selected are greyed out on
  the track headers.

Thanks to [Milan Wulf](https://github.com/milanwulf) for this feature ([pull request #1](https://github.com/sbsmnt/bluebox-cobalt-mod/pull/1)). Details in [Phones AUTO cue](#phones-auto-cue).

## New in v1.1

- **Scenes:** up to 16 snapshots per project of the mixer, master and aux
  buses, FX1/FX2 (including the effect type) and BPM. Recall is instant,
  with no project load, so playback and recording carry on.
- **Scene page:** select a project in PROJ and press A to load or save a
  scene and set the project's Bank #.
- **Quick save:** hold A for 2 s on MAIN to save the next empty scene.
- **MIDI recall:** Program Change recalls a scene; Bank Select loads the
  project with that Bank #. Channel and Bank CC in TOOLS > MIDI Settings.
- **Map CC Sync:** the bluebox sends the values of its mapped CCs to your
  controller on plug-in, project load and scene recall, so LED rings and
  motor faders show the bluebox values.
- **MIDI Out thru:** notes and CC from USB (or USB and MIDI in) are passed to
  the MIDI out.
- **Clock Src:** with clock on more than one input, one of them is followed
  (MIDI In first, or USB first).
- **PROJ list:** the loaded project is marked with `* `, and long names
  scroll.
- **MIXER sends with OUT3:** buttons read `O 2`, `O 3` and `NG` (gate) so
  all seven fit.

Details in [Scenes](#scenes), [MIDI](#midi) and the [CHANGELOG](CHANGELOG.md).

## Install

1. Open the patcher at
   [sbsmnt.github.io/bluebox-cobalt-mod](https://sbsmnt.github.io/bluebox-cobalt-mod/),
   or open `patch_bluebox.html` from this repository in any modern browser.
   Nothing is uploaded; patching happens in the page.
2. Drop the **original official desktop 1.5.2 `BLUEBOX.BIN`** on the drop
   zone (or click to browse). Other versions and already-patched files are
   refused.
3. Pick a theme preset or build your own, then **Verify and prepare
   download**.
4. Install the new `BLUEBOX.BIN` with the usual SD-card procedure.
5. Check that the middle TOOLS field shows **Cblt 1.2**. The official version
   field still shows 1.5.2.

To go back, tick **Restore the original** and choose your Cobalt
`BLUEBOX.BIN`: the page rebuilds the exact official 1.5.2 file.

The same patcher runs from the command line:

```sh
python3 patch_bluebox.py /path/to/BLUEBOX.BIN --check
python3 patch_bluebox.py /path/to/BLUEBOX.BIN --output /path/to/new/BLUEBOX.BIN
python3 patch_bluebox.py /path/to/BLUEBOX.BIN --theme themes/synthwave.json --output /path/to/new/BLUEBOX.BIN
python3 patch_bluebox.py /path/to/cobalt/BLUEBOX.BIN --restore --output /path/to/original/BLUEBOX.BIN
```

## Features

### FX1 delay modes

Open FX1 and press **B** to choose the mode. Each mode shows its own
controls on the FX1 panel; switching modes keeps every mode's settings.

#### Delay

The stock 1.5.2 delay, unchanged and bit-identical. New projects start here.

| Control | What it does |
|---|---|
| Time | Delay time in ms, or a note division (such as 1/4T) when BEAT is on |
| FEEDB | How much of each repeat is fed back (more repeats) |
| FILT | Turns the delay's filter on |
| CUTOF / WIDTH | Filter frequency and width |
| BEAT | Syncs Time to the project tempo |
| PING | Ping-pong repeats between left and right |
| QUAD | The stock quad delay layout |

#### Warp delay (panel title: Warp)

The stock delay with three extra controls:

| Control | What it does |
|---|---|
| Pitch | Shifts every repeat by −12 to +12 semitones (the toggle turns it on), so repeats climb or fall in pitch as they feed back |
| Drift | Tape-style wow: a slow 0.6 Hz wobble plus a random wander, up to about ±2.5 % pitch at full |
| To Rev | Sends the repeats into FX2, so the echoes are reverberated |

#### Granulr (Granular)

Records the last 2 seconds into a buffer and replays it as up to four
overlapping grains. When fully wet, the stock delay engine is paused to save
CPU.

| Control | What it does |
|---|---|
| Position | How far back in the 2-second buffer grains start: 0 % is the most recent audio, 100 % the oldest |
| Size ms | Grain length, 20–250 ms |
| Density | How many grains overlap, 1–4 (more is smoother and denser) |
| Pitch | Grain pitch, −12 to +12 semitones |
| Jitter | Randomises each grain's start position around Position |
| Feedback | Feeds grains back into the buffer (up to 95 %) for evolving clouds |
| To Rev | Send to the FX2 reverb |
| Freeze | Stops recording: grains keep playing from what is already in the buffer |
| Reverse | Grains play backwards |

With jitter or pitch the grains are mixed by power, so jittered settings stay
as loud as plain ones.

#### Tape

A tape echo: every repeat passes through saturation and filters inside the
feedback loop, so repeats get darker, thinner and more driven as they decay.

| Control | What it does |
|---|---|
| Time / FEEDB | Delay time and feedback, as on Delay |
| Drift | Wow and flutter, as on Warp |
| Drive | Saturation of each repeat (takes WIDTH's place). Quiet tails are not boosted, so drive adds grit without runaway feedback |
| Lo C | Low cut inside the loop: each repeat loses a little more low end. 20 Hz is Off |
| Hi C | High cut inside the loop, 500 Hz–16 kHz: each repeat gets a little darker |
| To Rev | Send to the FX2 reverb |
| BEAT / PING / QUAD | As on Delay |
| WILD | Adds pre-drive damping and extra regeneration in the loop, for a less polite, more unstable echo |

Tape bypasses the stock filter (no FILT), and your FILT setting is kept for
the other modes.

#### Ducked

A delay whose repeats duck while you play and swell back in the gaps.

| Control | What it does |
|---|---|
| Duck | How much the repeats are turned down while the FX1 input is loud (takes WIDTH's place) |
| Release ms | How quickly the repeats come back after the input stops, 20–2000 ms (takes Drift's place) |
| Pitch / To Rev | As on Warp |
| Time / FEEDB / FILT / CUTOF / BEAT / PING / QUAD | As on Delay |

Only what you hear is ducked: the feedback loop keeps running underneath, so
the echoes are all there when they swell back.

#### Reverse

Plays the input backwards in overlapping segments.

| Control | What it does |
|---|---|
| Segment ms | Length of each reversed slice, 40–600 ms (a note division when BEAT is on) |
| Feedback | Feeds reversed audio back for repeated reverse echoes |
| Tone | Low-pass on the reversed sound, from dark (200 Hz) to open (10 kHz) |
| Pitch | −12 to +12 semitones |
| To Rev | Send to the FX2 reverb |
| BEAT | Syncs Segment to the project tempo |

### FX2 Gazer reverb

FX2 → B → **Gazer**: a large, modulated shoegaze reverb with a fuzz stage in
front.

| Control | What it does |
|---|---|
| Saturate | Fuzz before the reverb: clean at 0, about 7 dB of drive at 35 %, pedal-style fuzz at the top. Output level stays constant |
| Size | Room size and decay, from about 3 s to about 40 s |
| Diffusion | How much the sound is smeared before it enters the reverb; higher is smoother |
| Mod Depth | Pitch modulation of the reverb tail (chorus-like shimmer) |
| Rate mHz | Modulation speed, 10–2000 mHz (0.01–2 Hz) |
| Hi C / Lo C | High and low cut on the sound going into the reverb |

### Noise gate

A gate on every track. Set it on TRACK (GATE knob) or in MIXER → Gate (`NG`
when OUT3 is present). The
threshold runs from −96 dB to −12 dB; the lowest setting is Off. It takes fine
steps when turned slowly and speeds up when spun. MIXER → Gate meters show
the level the gate listens to on the Gate fader's scale, so the meter crosses
the fader exactly when the gate opens.

### Phones AUTO cue

MAIN → B → **Phones Src** has a third choice, **AUTO**, next to CUE and MAIN.
It works like PFL on a DJ mixer: the phones play the cue mix while any track
has its cue on (CUE Style Toggle) or turned up (CUE Style Fader), and the
main mix otherwise. Only the cue setting counts, not whether the track is
playing or has an input, so a cued track that is stopped still gives you its
(silent) cue. After the last cue goes off, the phones return to Main within
0.1 s. CUE Send (Pre/Post Fader) works as before. CUE and MAIN are unchanged.

**Track headers** on every page with the track strip:

- A small headphone icon in the top-right corner marks each track with its
  cue on, in any Phones Src mode. It uses the theme's active button fill
  with a background-colour outline. On narrow headers it can cover the last
  letter of the name.
- Tracks with no input selected are greyed out with a stipple, so
  unconfigured tracks stand out. Tracks with a recorded clip are not greyed.

Both follow the track count, Single/Double Row and renamed tracks.

Thanks to [Milan Wulf](https://github.com/milanwulf) for this feature ([pull request #1](https://github.com/sbsmnt/bluebox-cobalt-mod/pull/1)).

### Master saturation

MAIN → B adds four rows after the compressor:

| Control | What it does |
|---|---|
| Saturate | Amount of saturation on the master. 0 is a true bypass |
| Sat Mode | **Soft** or **Tape** |
| Tape Tone | Tape mode only: the treble roll-off, from darker (about 5 kHz) to brighter (about 18 kHz). Default 50 % is about 11.5 kHz |
| Sat Out | Output level after saturation, −12 to +6 dB, to match levels when comparing. Has no effect while Saturate is 0 |

- **Soft** is a smooth, symmetric saturation (adapted from BlueLex). Drive is
  level-compensated, so turning it up adds harmonics rather than volume.
- **Tape** is a tape-style voicing, not a model of a specific machine. Like
  tape it boosts treble going in and cuts it coming out, so highs saturate
  first. Loud passages also lose a little more treble (the treble roll-off is
  linked across both channels). More Saturate adds a gentle low-end bump. Very
  low frequencies and DC are removed. **Tape Tone** sets where the treble
  starts to roll off. Turn it down for warm, darker tape; turn it up to keep
  the top end open.

### Meters

**CPU load bar.** The thin bar right of the clock shows how busy the audio
engine is. It is green up to 70 %, amber to 90 % and red above. A white mark
shows the recent peak.

**Compressor gain reduction.** When the master compressor is on, Cobalt
shows how much it is turning the level down:

- **Header bar:** the bar just left of the CPU bar. Half height is 10 dB of
  reduction; full height is 40 dB.
- **Thresh row (MAIN → B):** a strip along the bottom of the Thresh row. It
  fills from the left as gain reduction rises. Full width is 40 dB. The three
  scale markers are at **5 dB, 10 dB and 20 dB**.

Both use a square-root scale, so small amounts of compression are easy to
see. They show the larger of the two channels, held over about 20 ms. The
fill colour is set in the theme editor (Compressor GR meter).

### Overdub recording fix

Stock 1.5.2 can stop with an error while overdubbing long takes because the
storage task falls behind. Cobalt converts recorded and played-back audio in
word-sized bursts instead of byte by byte. The audio is bit-identical.

### Scenes

A scene is a snapshot of the mixer (track level, pregain, pan, sends, mute,
solo, compressor, EQ and gate), the master and aux buses, every FX1/FX2
parameter including the effect type, and the BPM. Each project holds up to
16, saved in the project file. Recalling a scene changes only the values
that differ, without loading anything, so playback and recording carry on.

- **Scene page:** select a project in PROJ and press A. Turn to pick a row
  and a number, then press Select:
  - **Load Scene:** recall that scene.
  - **Save Scene:** save the current state to that scene.
  - **Bank #:** give the project a number (None or 1–128) for MIDI Bank
    Select. A number another project has is refused ("BANK n IN USE").
  Press A to leave. PROJ Save also applies the Bank # chosen there.
- **Quick save:** hold A for 2 s on MAIN. A band at the top shows progress,
  then saves the next empty scene. A new project starts at scene 1.
- **MIDI:** Program Change recalls a scene: program 0 (PC 1 on gear that
  counts from 1) is scene 1. Bank Select loads the project with that Bank #
  (value 0 = Bank 1); a Program Change after it waits for the load. TOOLS > **MIDI Settings** (tap it, or press B with it selected;
  B goes back) sets **Bank CC** (MSB - CC 0 or LSB - CC 32) and **PC Ch** (All, None or
  1–16).
- **PROJ list:** the loaded project is marked with `* `, and a long selected
  name scrolls.

### MIDI

Also in TOOLS > **MIDI Settings**:

- **MIDI Out:** what the MIDI out passes on, besides the bluebox's own MIDI
  output. `Default` passes nothing else (stock). `USB Thru` passes the
  messages (notes, CC, …) coming from USB (computer on USB-B, controller on
  USB-A). `All Thru` also passes MIDI in. Channels are kept. Clock and transport are never
  passed on, so a clocked setup never sees a second clock.
- **Map CC Sync:** where the values of the mapped CCs are sent, so a
  controller with LED rings or motor faders (OXI E16, MIDI Fighter Twister,
  Launch Control XL 3, Roto-Control, Faderfox EC4, …) shows them:
  - `Off`: never.
  - `USB` (default): to the controller on USB-A when it is plugged in, after
    a project load and after a scene recall.
  - `USB+MIDI Out`: as USB, plus the MIDI out after a project load or scene
    recall.
  - `MIDI Out`: the MIDI out only, after a project load or scene recall.
  The controller must listen on the channel and CC it sends (the usual
  default). If the values can't get out, a band says `MAP CC SYNC: USB OUT
  STUCK` or `MAP CC SYNC: MIDI OUT STUCK`.
- **Clock Src:** which input is followed when more than one sends clock.
  `MIDI In` (default): MIDI in, then the computer (USB-B), then the USB-A
  controller. `USB`: USB-B, USB-A, then MIDI in. The preferred input takes
  over at once; a lower one only after 300 ms without clock from the current
  one. Start, stop, continue and song position follow the same input. The
  band shows the order when the setting is changed.

### Themes

The patcher page has a theme editor with 18 presets and 22 colours, a live
preview of 27 device screens, hold-to-compare with stock and an RGB565
preview. Themes export and import as JSON (`themes/` holds the presets).

## Building from source

Requirements: Arm GNU Toolchain **13.2.Rel1** (other GCC versions produce
different payloads), Python 3 and the original firmware.

```sh
ARM_CC=/path/to/arm-none-eabi-gcc ARM_OBJCOPY=/path/to/arm-none-eabi-objcopy \
ARM_NM=/path/to/arm-none-eabi-nm sh build.sh /path/to/BLUEBOX.BIN
```

`build.sh` compiles the payloads into `build/` and regenerates
`patch_bluebox.html`, `patch_bluebox.py`, `patch_manifest.json`, `themes/`
and `docs/index.html`.

### Tests

The tests run the real patched firmware routines in the Unicorn emulator,
compile host-side DSP checks with sanitizers, and drive both patchers.

```sh
python3 -m pip install -r tests/requirements.txt
python3 tests/run_checks.py /path/to/BLUEBOX.BIN
```

They need Node.js and a host C compiler; add `--browser` to also run the
Playwright end-to-end test. Regression tests compare against earlier
development builds kept in `tests/references/` (patch data only, no
firmware). The tests cover correctness, not sound or CPU load on the device.

### Continuous integration and GitHub Pages

`.github/workflows/pages.yml` runs on every push and pull request. It checks
that no firmware image is committed, that the Python sources compile, that
the theme presets load, and that `docs/index.html` matches
`patch_bluebox.html`. It also runs the patcher page tests and the sanitized
DSP host tests. The emulator suite needs the original firmware, so run
`tests/run_checks.py` locally before pushing.

Pull requests go to the `dev` branch; `main` only receives tested releases
(see [CONTRIBUTING](CONTRIBUTING.md)). On `main`, the workflow then publishes `docs/` (the self-contained patcher
page) to GitHub Pages at [https://sbsmnt.github.io/bluebox-cobalt-mod/](https://sbsmnt.github.io/bluebox-cobalt-mod/).
Enable it once under **Settings → Pages → Build and
deployment → Source: GitHub Actions**.

## Layout

| Path | Contents |
|---|---|
| `src/` | Payload sources (M7 audio core, M4 UI core) and linker scripts |
| `tools/` | Release builder and patcher templates |
| `tests/` | Emulator, host and patcher tests |
| `themes/` | Theme presets as JSON |
| `docs/` | GitHub Pages copy of the patcher |
| `.github/workflows/` | Checks and Pages deployment |
| `patch_bluebox.html`, `patch_bluebox.py` | Ready-to-use patchers |

## Credits

Cobalt builds on **BlueLex**, the modded firmware for the 1010music Bluebox
Euro by lexnels: https://github.com/lexnels/bluelex-bluebox-euro. The CPU
load indicator, the MAIN → B compressor level and meter approach, the Soft
master saturation, and the delay pitch and send to reverb were adapted from
BlueLex, with every desktop address and hook traced independently.
[NOTICE.md](NOTICE.md) has the full attribution and disclaimer.

See [CHANGELOG.md](CHANGELOG.md) for release notes.
