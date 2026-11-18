"""Turn the generated Cobalt patcher page into the Phrase Looper patcher.

Only wording changes and a short guide are added; the patching code, theme
editor, verification and restore are the template's, driven by the looper
manifest. Every replacement must match exactly once, so a template change
cannot silently drop one.
"""

GUIDE = '''<section id="looper"><h2>Using the Phrase Looper</h2>
<p class="muted">Turn up the FX1 send on the track(s) you want to loop, open FX1 and choose <b>Phrase Looper</b> (where Granular was). The FX1 title shows the state: Looper, ARMED, REC 1/2, PLAY, DUB or STOP. Empty, it shows the tempo the looper measured, e.g. Lp128.0.</p>
<p class="muted">With the sequencer playing, REC waits for the next bar line and records exactly the set bars; the loop stays locked to the song position. The tempo is measured from the song position, so an external master clock (such as a Blackbox) is followed without setting the bluebox BPM.</p>
<table class="looper-table">
<tr><th>REC / OVDUB</th><td>Empty: record (on the next bar line while the sequencer plays). At the end of the bars the loop plays by itself. Recording: end on the next bar line. Once a loop exists the button reads OVDUB: overdub on / off.</td></tr>
<tr><th>Transport</th><td>The bluebox (or master clock) Stop stops the loop; Play plays it again in step with the song. There is no on-screen STOP.</td></tr>
<tr><th>CLEAR</th><td>Empty the loop.</td></tr>
<tr><th>Sync</th><td>On: with the sequencer stopped, REC waits and recording starts when you press start. Locked while a loop exists.</td></tr>
<tr><th>Bars</th><td>1 or 2 bars at the tempo measured from the song position (before the sequencer has run: MIDI clock or project BPM).</td></tr>
<tr><th>Level</th><td>Loop volume. The FX1 return carries only the loop.</td></tr>
<tr><th>Stretch</th><td>What the loop does when the tempo changes after recording. <b>Off</b>: keeps its recorded speed and restarts on every loop cycle. <b>Vari</b>: plays faster or slower to stay in time, and the pitch moves with it, like tape (&plusmn;8 BPM at 120 is about &plusmn;1 semitone). <b>Keep</b>: stays in time at the same pitch, with slight graininess on sustained notes.</td></tr>
<tr><th>Time / Feedb</th><td>The stock delay, played on the loop: Time (a note division with Beat Sync on) and feedback. Other delay settings come from the Delay page.</td></tr>
<tr><th>Echo</th><td>How much of the loop goes into the delay; 0 = off. The FX1 return carries the loop plus its echoes.</td></tr>
<tr><th>Type</th><td>The echoes' delay type: Warp, Tape, Duck (Ducked) or Delay. Only the chosen type runs, on the echoes only; its settings come from that type's page.</td></tr>
<tr><th>Ping</th><td>Button, top right: echoes alternate left and right.</td></tr>
</table>
<p class="muted">REC and CLEAR act once per press and never stay lit. While the loop plays, the tracks feeding FX1 are muted automatically, so you hear only the loop. They are unmuted while you record or overdub, and when you stop, clear or leave the looper. Tracks you muted yourself are never touched.</p>
<p class="muted">Loops are stored as 16-bit audio. The TOOLS page shows the longest loop, for example <code>Cblt L4.0s</code>: 4 seconds is 2 bars at 120 BPM or faster. When 2 bars don’t fit, the loop is 1 bar and the title shows REC 1/1. Switching FX1 to another mode empties the loop.</p>
</section>
'''

STYLE = ('<style>.looper-table{border-collapse:collapse;width:100%;margin:8px 0 12px;font-size:14px}'
         '.looper-table th{text-align:left;white-space:nowrap;padding:6px 12px 6px 0;vertical-align:top}'
         '.looper-table td{padding:6px 0;vertical-align:top}'
         '.looper-table tr+tr th,.looper-table tr+tr td{border-top:1px solid rgba(127,127,127,.25)}</style>\n')


def adapt(page, manifest):
    v = manifest['version']
    swaps = [
        ('<title>Bluebox Cobalt mod</title>', '<title>Bluebox Cobalt Phrase Looper</title>'),
        ('content="Patch the Bluebox desktop 1.5.2 firmware with the Cobalt mod and a custom colour theme, locally in your browser."',
         'content="Patch the Bluebox desktop 1.5.2 firmware with Cobalt and the FX1 Phrase Looper, locally in your browser."'),
        ('<h1>Bluebox Cobalt mod</h1>', '<h1>Bluebox Cobalt + Phrase Looper</h1>'),
        ('Unofficial effects &amp; theme mod for bluebox desktop firmware 1.5.2 · v' + v,
         'Cobalt v' + v + ' with an FX1 Phrase Looper, for bluebox desktop firmware 1.5.2 · experimental'),
        ('<a class="chip jump" href="#guide">New in v1.1: scenes and MIDI ›</a>',
         '<a class="chip jump" href="#looper">Using the Phrase Looper ›</a><a class="chip jump" href="#guide">Scenes and MIDI ›</a>'),
        ('Restore the original from a Cobalt ' + v + ' firmware file',
         'Restore the original from a Cobalt ' + v + ' + Phrase Looper firmware file'),
        ('Generate a new BLUEBOX.BIN and install it with your usual SD-card procedure.',
         'Generate a new BLUEBOX.BIN. Copy it to the root of the microSD card, hold <b>A</b> while powering the bluebox on, and let go when “Bluebox Installer” appears. TOOLS then shows <code>Cblt L…</code>.'),
        ('Unofficial firmware · Cobalt v' + v + '.', 'Unofficial, experimental firmware · Cobalt v' + v + ' + FX1 Phrase Looper.'),
        ('<section id="guide">', GUIDE + '<section id="guide">'),
        ('<p class="notice">Use the original official desktop 1.5.2 firmware. Keep your working firmware and a project backup.</p>',
         '<p class="notice">Use the original official desktop 1.5.2 firmware. Keep your working firmware and a project backup. '
         '<b>The Phrase Looper build has been tested on one bluebox desktop only.</b> '
         '<a href="https://github.com/matewmusic-stack/Cobalt-Phrase-Looper#hardware-testing-one-device">What was tested</a></p>'),
        # Theme preview: the FX1 mode list (B on the FX page).
        ("listRows(P,['Delay','Warp delay','Granular','Tape','Ducked','Reverse']",
         "listRows(P,['Delay','Warp delay','Phrase Looper','Tape','Ducked','Reverse']"),
        ('</head>', STYLE + '</head>') if '</head>' in page else ('<header>', STYLE + '<header>'),
    ]
    for old, new in swaps:
        n = page.count(old)
        if n != 1:
            raise ValueError('looper page: expected one %r, found %d' % (old[:60], n))
        page = page.replace(old, new)
    return page
