"""Turn the generated Cobalt patcher page into the Phrase Looper patcher.

Only wording changes and a short guide are added; the patching code, theme
editor, verification and restore are the template's, driven by the looper
manifest. Every replacement must match exactly once, so a template change
cannot silently drop one.
"""

GUIDE = '''<section id="looper"><h2>Using the Phrase Looper</h2>
<p class="muted">Turn up the FX1 send on the track(s) you want to loop, open FX1 and choose <b>Phrase Looper</b> (where Granular was). The FX1 title shows the state: Looper, ARMED, REC 1/2, PLAY, DUB or STOP. Empty, it shows the tempo the looper measured, e.g. Lp128.0. The header also shows the detected tempo right of the bar count, in every FX1 mode.</p>
<p class="muted">With the sequencer playing, REC waits for the next bar line and records exactly the set bars; the loop stays locked to the song position. The tempo is measured from the song position, so an external master clock (such as a Blackbox) is followed without setting the bluebox BPM.</p>
<table class="looper-table">
<tr><th>REC / OVDUB</th><td>Empty: record (on the next bar line while the sequencer plays). At the end of the bars the loop plays by itself. Recording: end on the next bar line. Once a loop exists the button reads OVDUB: overdub on / off.</td></tr>
<tr><th>Transport</th><td>The bluebox (or master clock) Stop stops the loop; Play plays it again in step with the song. There is no on-screen STOP.</td></tr>
<tr><th>CLEAR</th><td>Empty the loop.</td></tr>
<tr><th>Sync</th><td>The looper's sync, bottom row of the first knob group. On: with the sequencer stopped, REC waits and recording starts when you press start. Locked while a loop exists.</td></tr>
<tr><th>Bars</th><td>1 or 2 bars at the tempo measured from the song position (before the sequencer has run: MIDI clock or project BPM).</td></tr>
<tr><th>Level</th><td>Loop volume. The FX1 return carries only the loop.</td></tr>
<tr><th>Stretch</th><td>What the loop does when the tempo changes after recording. <b>Off</b>: keeps its recorded speed and restarts on every loop cycle. <b>Vari</b>: plays faster or slower to stay in time, and the pitch moves with it, like tape (&plusmn;8 BPM at 120 is about &plusmn;1 semitone). <b>Keep</b>: stays in time at the same pitch, with slight graininess on sustained notes.</td></tr>
<tr><th>Time / Feedb</th><td>The stock delay, played on the loop: Time (a note division with Beat on) and feedback. Other delay settings come from the Delay page.</td></tr>
<tr><th>Echo</th><td>How much of the loop and the live FX1 sends goes into the delay; 0 = off. The FX1 return carries the loop plus the echoes (live tracks are heard dry on the mixer). Works with no loop too.</td></tr>
<tr><th>Type</th><td>The echoes' delay type: Warp, Tape, Duck (Ducked) or Delay. Only the chosen type runs, on the echoes only; its settings come from that type's page.</td></tr>
<tr><th>Ping</th><td>Button, top right: echoes alternate left and right.</td></tr>
<tr><th>Beat</th><td>Button, bottom right: the delay's tempo sync, separate from the looper's Sync. On: Time is a note division; off: milliseconds.</td></tr>
</table>
<p class="muted">REC and CLEAR act once per press and never stay lit. While the loop plays, the tracks feeding FX1 are muted automatically, so you hear only the loop. They are unmuted while you record or overdub, and when you stop, clear or leave the looper. Tracks you muted yourself are never touched.</p>
<p class="muted">Loops are stored as 16-bit audio. The TOOLS page shows the longest loop, for example <code>4s 1.5M</code>: a 4-second loop is 2 bars at 120 BPM or faster. When 2 bars don’t fit, the loop is 1 bar and the title shows REC 1/1. Switching FX1 to another mode empties the loop.</p>
</section>
<section id="transient"><h2>Transient shaper and compressor</h2>
<p class="muted">This build replaces Cobalt's per-track noise gate with a <b>transient shaper</b> and adds a per-track <b>compressor</b>, both ported from Joebox. The <b>TRACK</b> button now cycles: TRACK view → Side Chain → page 3 (transient) → page 4 (compressor) → TRACK view.</p>
<table class="looper-table">
<tr><th>TRANSIENT</th><td>On/off per track: the bottom-right knob of the TRACK view (beside OUT2, where GATE was; tap it or turn encoder 4), or the MIXER <b>Trans</b> column.</td></tr>
<tr><th>Page 3</th><td>Encoders: Attack (&minus;100…+100&nbsp;%), Sustain (&minus;100…+100&nbsp;%), Speed, Length. Tap Model (Differ / Punch / Smooth), Output (&plusmn;12&nbsp;dB) or Mix to put it on encoder 4; tap Length to give it back. Attack and Sustain at 0 with Output 0&nbsp;dB leave the sound unchanged.</td></tr>
<tr><th>Page 4</th><td>Encoder 1: Comp mode, Off / Glue / Punch / Opto / Squash / Limit (Limit without lookahead). Encoder 2: Thresh, &minus;24…+12&nbsp;dB (for Limit: the drive into a &minus;0.3&nbsp;dBFS ceiling). The compressor runs after the shaper, whether TRANSIENT is on or off.</td></tr>
</table>
<p class="muted">Settings are saved per track in the project. Saved Gate thresholds from older projects are ignored.</p>
</section>
'''

STYLE = ('<style>.looper-table{border-collapse:collapse;width:100%;margin:8px 0 12px;font-size:14px}'
         '.looper-table th{text-align:left;white-space:nowrap;padding:6px 12px 6px 0;vertical-align:top}'
         '.looper-table td{padding:6px 0;vertical-align:top}'
         '.looper-table tr+tr th,.looper-table tr+tr td{border-top:1px solid rgba(127,127,127,.25)}</style>\n')


# TRACK pages 3 and 4, drawn from hardware photos of build ddb1f45d.
TS_HELPERS = (
    "const TS_ON='#22bb22',TS_DIM='#aaaaaa';"
    "function tsBox(P,cx,cy,a,b,bc,c){P.rect(cx-23,cy-17,46,44,WELL);if(a)P.text(cx,cy-3,a,'knob',8);"
    "if(b)P.text(cx,cy+9,b,bc,8);if(c)P.text(cx,cy+21,c,'text',8);}\n"
    "function tsPage(P,body){base(P,'1');strip(P,20,126,{master:.12,tracks:[{state:'sel'},{},{level:.06}]});"
    "P.rect(0,127,320,18,'button_idle');P.text(160,141,'1','text',14);P.rect(0,146,30,94,WELL);"
    "P.poly('2,152 2,160 7,156','text');P.text(8,160,'0dB','text',8,'start');body();P.rect(130,147,90,92,'none','accent',1.6);"
    "button(P,220,147,50,46,'','button_idle',9,['SIDE','CHAIN']);button(P,270,147,50,46,'MUTE','button_idle',9,null,15);"
    "button(P,220,193,50,47,'REC','button_idle',9,null,15);button(P,270,193,50,47,'SOLO','button_idle',9,null,15);}\n")
TS_DRAW = (
    " trans(P){tsPage(P,()=>{tsBox(P,57,165,'MODEL','SMOOTH','text');knob(P,105,165,'OUTPUT',.5);knob(P,57,209,'MIX',.95);"
    "tsBox(P,105,209,'TRANS','ON',TS_ON,'4 LENGTH');knob(P,152,165,'ATTAC',.5);knob(P,197,165,'SPEED',.5);"
    "knob(P,152,209,'SUSTA',.5);knob(P,197,209,'LENGT',.5);});},\n"
    " comp(P){tsPage(P,()=>{[[57,165],[105,165],[57,209],[197,165],[197,209]].forEach(([x,y])=>tsBox(P,x,y));"
    "tsBox(P,105,209,'COMP','PAGE 4',TS_DIM);tsBox(P,152,165,'MODE','LIMIT',TS_ON);knob(P,152,209,'THRES',.67);});},\n")


def adapt(page, manifest):
    v = manifest['version']
    swaps = [
        ('<title>Bluebox Cobalt mod</title>', '<title>Bluebox Cobalt: Looper, Transient Shaper, Compressors</title>'),
        ('content="Patch the Bluebox desktop 1.5.2 firmware with the Cobalt mod and a custom colour theme, locally in your browser."',
         'content="Patch the Bluebox desktop 1.5.2 firmware with Cobalt, the FX1 Phrase Looper and a per-track transient shaper and compressor, locally in your browser."'),
        ('<h1>Bluebox Cobalt mod</h1>', '<h1>Bluebox Cobalt: Looper, Transient Shaper, Compressors</h1>'),
        ('Unofficial effects &amp; theme mod for bluebox desktop firmware 1.5.2 · v' + v,
         'Cobalt v' + v + ' with an FX1 Phrase Looper and per-track transient shaper + compressor, for bluebox desktop firmware 1.5.2 · experimental'),
        ('<a class="chip jump" href="#guide">New in v1.1: scenes and MIDI ›</a>',
         '<a class="chip jump" href="#looper">Using the Phrase Looper ›</a><a class="chip jump" href="#transient">Transient + compressor ›</a><a class="chip jump" href="#guide">Scenes and MIDI ›</a>'),
        ('Restore the original from a Cobalt ' + v + ' firmware file',
         'Restore the original from a Cobalt ' + v + ' + Phrase Looper firmware file'),
        ('Generate a new BLUEBOX.BIN and install it with your usual SD-card procedure.',
         'Generate a new BLUEBOX.BIN. Copy it to the root of the microSD card, hold <b>A</b> while powering the bluebox on, and let go when “Bluebox Installer” appears. TOOLS then shows the looper readout, e.g. <code>4s 1.5M</code>.'),
        ('Unofficial firmware · Cobalt v' + v + '.', 'Unofficial, experimental firmware · Cobalt v' + v + ' + FX1 Phrase Looper.'),
        ('<section id="guide">', GUIDE + '<section id="guide">'),
        ('<p class="notice">Use the original official desktop 1.5.2 firmware. Keep your working firmware and a project backup.</p>',
         '<p class="notice">Use the original official desktop 1.5.2 firmware. Keep your working firmware and a project backup. '
         '<b>This build has been tested on one bluebox desktop only.</b> '
         '<a href="https://github.com/matewmusic-stack/Cobalt-Mod-Looper-Transient-Shaper-Compressors#hardware-testing-one-device">What was tested</a></p>'),
        # Theme preview: the FX1 mode list (B on the FX page).
        ("listRows(P,['Delay','Warp delay','Granular','Tape','Ducked','Reverse']",
         "listRows(P,['Delay','Warp delay','Phrase Looper','Tape','Ducked','Reverse']"),
        # Theme preview: the Gate is now the TRANSIENT button, and TRACK has pages 3 and 4.
        ("P.text(197,201,'GATE','knob',8);P.text(197,211,'OFF','text',8);P.text(197,221,'OFF','text',8);",
         "P.text(197,203,'TRANS','knob',8);P.text(197,215,'ON',TS_ON,8);"),
        ("['sidechain','TRACK','Side chain'],",
         "['sidechain','TRACK','Side chain'],['trans','TRACK','Page 3 · Transient'],['comp','TRACK','Page 4 · Comp'],"),
        (' main(P){base(P);', TS_DRAW + ' main(P){base(P);'),
        ('function trackPage(', TS_HELPERS + 'function trackPage('),
        ('Knob arcs and pointers, GATE label, XY pad markers', 'Knob arcs and pointers, TRANS label, XY pad markers'),
        ('and Gate state colours are drawn', 'and TRANS on/off colours are drawn'),
        ("'compressor','EQ','gate','the master", "'compressor','EQ','the master"),
        ('</head>', STYLE + '</head>') if '</head>' in page else ('<header>', STYLE + '<header>'),
    ]
    for old, new in swaps:
        n = page.count(old)
        if n != 1:
            raise ValueError('looper page: expected one %r, found %d' % (old[:60], n))
        page = page.replace(old, new)
    return page
