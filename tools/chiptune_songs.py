"""The demo songs and the SFX library, written as code.

    python tools/chiptune.py songs      # -> chiptune/music/*.gbm

Each song shows off part of the driver and a style: arpeggio chords, the
wave-channel synth, noise drum recipes, sampled drums, tremolo by retrigger,
slides, portamento, echo on a second channel, grooves, a waltz in 12-row
bars, sync markers for gameplay, songs that end instead of looping.

Tempo: a row is a 16th note unless said otherwise, and a groove step is the
frames a row lasts at 59.73 frames/s. [6, 6] is 149 BPM, [5, 5] 179,
[10, 10] 90, [5, 5, 5, 6] 170.
"""
from gbm_compose import (Song, noise_kick, noise_snare, noise_hat, noise_crash, pulse_kick,
                         synth, synth_kit, sample_inst, WAVES, transpose_text)


def drums(pattern, kit):
    """Drum shorthand: letters for the kit's pieces, commands may follow
    (`s+904`), anything else passes through."""
    out = []
    for t in pattern.split():
        head, plus, rest = t.partition('+')
        out.append(kit[head] + plus + rest if head in kit else t)
    return ' '.join(out)


# ─── 1. Cloud Garden: the main menu, airy and slow ────────────────────────

def cloud_garden():
    """D major, 90 BPM. A bell lead fading on every note, harp-like broken
    chords, a breathing wave pad; a shaker joins for the second half."""
    s = Song('Cloud Garden', groove=(10, 10))
    s.inst('pulse', 'bell', duty=1, volume=10, envPace=5, vibSpeed=4, vibDepth=1, vibDelay=24)
    s.inst('pulse', 'harp', duty=2, volume=6, envPace=2)
    synth(s, 'pad', 'breath', volume=2, speed=5)
    s.inst('noise', 'shaker', volume=3, envPace=1)
    s.inst('noise', 'shaker2', volume=5, envPace=1)
    lead = [
        'A5@bell . . . F#5 . . . E5 . . . F#5 . . .',
        'D5 . . . . . . . C#5 . . . D5 . E5 .',
        'B4 . . . . . D5 . G5 . . . F#5 . . .',
        'E5 . . . . . . . . . . . - . . .',
        'A5 . . . F#5 . . . E5 . . . F#5 . A5 .',
        'C#6 . . . . . B5 . A5 . . . F#5 . . .',
        'G5 . . . F#5 . . . E5 . . . D5 . . .',
        'E5 . . . . . . . A4 . . . C#5 . E5 .',
        'F#5 . . . . . D5 . B4 . . . D5 . F#5 .',
        'G5 . . . . . F#5 . D5 . . . B4 . . .',
        'A5 . . . . . . . F#5 . . . D5 . . .',
        'E5 . . . . . F#5 . E5 . . . C#5 . . .',
        'D5 . . . F#5 . . . B5 . . . A5 . . .',
        'G5 . . . . . B5 . D6 . . . C#6 . . .',
        'B5 . . . . . A5 . G5 . . . E5 . . .',
        'A5 . . . . . . . . . . . - . . .',
    ]
    up_down = lambda a, b, c, d: f'{a}@harp . {b} . {c} . {d} . {c} . {b} . {a} . {b} .'
    harp = {
        'D': up_down('D4', 'A4', 'C#5', 'F#5'), 'Bm': up_down('B3', 'F#4', 'A4', 'D5'),
        'G': up_down('G3', 'D4', 'F#4', 'B4'), 'A': 'A3@harp . E4 . A4 . D5 . E5 . C#5 . A4 . E4 .',
        'F#m': up_down('F#3', 'C#4', 'E4', 'A4'), 'EmA': 'E3@harp . B3 . D4 . G4 . A3 . E4 . G4 . C#5 .',
        'Em': up_down('E3', 'B3', 'D4', 'G4'), 'A7': 'A3@harp . E4 . G4 . C#5 . E5 . C#5 . G4 . E4 .',
    }
    chords = ['D', 'Bm', 'G', 'A', 'D', 'F#m', 'G', 'EmA', 'Bm', 'G', 'D', 'A', 'Bm', 'G', 'Em', 'A7']
    roots = dict(D='D4', Bm='B3', G='G3', A='A3', **{'F#m': 'F#3', 'EmA': 'E3', 'Em': 'E3', 'A7': 'A3'})
    shaker = '. . #42@shaker . . . #42 . . . #42@shaker2 . . . #42@shaker #44'
    for i, (m, c) in enumerate(zip(lead, chords)):
        pad = f'{roots[c]}@pad . . . . . . . . . . . . . . .'
        if c == 'EmA':
            pad = 'E3@pad . . . . . . . A3 . . . . . . .'
        noi = shaker if i >= 8 else ('. . . . . . . . . . . . . . #44@shaker .' if i % 2 else '.')
        s.bar([m, harp[c], pad, noi])
    return s


# ─── 2. Tidal Twang: surf rock ────────────────────────────────────────────

def tidal_twang():
    """E, 179 BPM. Tremolo picking is the retrigger command (9x2: restart
    every 2 frames), over E phrygian dominant; then a twangy major chorus
    with a walking bass. Loops back past the intro."""
    s = Song('Tidal Twang', groove=(5, 5), loop=2)
    s.inst('pulse', 'trem', duty=1, volume=13, envPace=1)
    s.inst('pulse', 'twang', duty=2, volume=12, envPace=3, vibSpeed=6, vibDepth=2, vibDelay=10)
    s.inst('pulse', 'chug', duty=2, volume=9, envPace=1, length=4)
    synth(s, 'bass', 'pluckBass', volume=3)
    kit = dict(k=f'#28@{s.s["instruments"][noise_kick(s)]["name"]}',
               s=f'#33@{s.s["instruments"][noise_snare(s)]["name"]}',
               h=f'#43@{s.s["instruments"][noise_hat(s)]["name"]}',
               o=f'#41@{s.s["instruments"][noise_hat(s, open_=True)]["name"]}',
               c=f'#38@{s.s["instruments"][noise_crash(s)]["name"]}')
    beat = drums('k . h . s . h . k . k . s . h o', kit)
    beat2 = drums('k . h . s . h k . k k . s . s o', kit)
    fill = drums('k . s . s . s s k s s s s+902 . s s', kit)
    # Intro: the low-E glissando (a slide down over two bars) and a fill.
    s.bar(['E6@trem+902+210 . . . . . . . . . . . . . . .',
           '. . . . . . . . . . . . . . . .',
           'E3@bass . . . . . . . . . . . . . . .',
           drums('c . . . . . . . . . . . . . . .', kit)])
    s.bar(['. . . . . . . . . . . . - . . .',
           '. . . . . . . . E4@chug+047 . E4 . E4 . E4 .',
           'E3 . E3 . . . E3 . E3 . B3 . . . B3 .',
           fill])
    # A: tremolo melody, E / F.
    trem = [
        'E5@trem+902 . . . F5 . . . G#5 . . . B5 . . .',
        'C6 . . . . . A5 . F5 . . . A5 . . .',
        'G#5 . . . B5 . . . E6 . . . D6 . . .',
        'C6 . . . B5 . A5 . . . G#5 . F5 . . .',
        'E6 . . . D6 . . . C6 . . . B5 . . .',
        'A5 . . . C6 . . . A5 . G#5 . F5 . . .',
        'F5 . . . E5 . . . D5 . . . C5 . . .',
        'B4 . . . . . . . E5 . . . - . . .',
    ]
    rhythm = {'E': 'E4@chug+047 . E4 . E4 . E4 . E4 . E4 . E4 . E4 .',
              'F': 'F4@chug+047 . F4 . F4 . F4 . F4 . F4 . F4 . F4 .'}
    bassA = {'E': 'E3@bass . E3 . B3 . E3 . E4 . B3 . G#3 . B3 .',
             'F': 'F3@bass . F3 . C4 . F3 . F4 . C4 . A3 . C4 .'}
    for i, m in enumerate(trem):
        c = 'EF'[i % 2] if i < 6 else ('F' if i == 6 else 'E')
        s.bar([m, rhythm[c], bassA[c], fill if i == 7 else (beat2 if i % 4 == 3 else beat)])
    # B: twang chorus, E A B A / E A B B.
    twang = [
        'B4@twang+900 . . . E5 . . . G#5 . . . B5 . G#5 .',
        'A5 . . . . . G#5 . E5 . . . C#5 . . .',
        'D#5 . . . F#5 . . . B5 . . . A5 . F#5 .',
        'E5 . . . . . . . C#5 . . . E5 . . .',
        'B5 . . . G#5 . . . E6 . . . C#6 . B5 .',
        'C#6 . . . B5 . . . A5 . . . E5 . . .',
        'F#5 . . . A5 . . . B5 . . . D#6 . . .',
        'E6 . . . . . . . B5+220 . . . . . - .',
    ]
    walk = {'E': 'E3@bass . G#3 . B3 . C#4 . E4 . C#4 . B3 . G#3 .',
            'A': 'A3@bass . C#4 . E4 . F#4 . A4 . F#4 . E4 . C#4 .',
            'B': 'B3@bass . D#4 . F#4 . G#4 . B4 . G#4 . F#4 . D#4 .'}
    stab = lambda r: f'. . {r}@chug+047 . . . {r} . . . {r} . . . {r} {r}'
    for i, (m, c) in enumerate(zip(twang, 'EABAEABB')):
        s.bar([m, stab(c + '4'), walk[c], fill if i == 7 else (beat2 if i % 2 else beat)])
    return s


# ─── 3. Jungle Pulse: drum and bass ───────────────────────────────────────

def jungle_pulse():
    """F minor, 170 BPM (a 5-5-5-6 groove). Chopped noise breaks with
    ghost snares and retrigger rolls, a reese bass on the wave synth, minor
    pads by arpeggio. The drop carries sync marker E01 for gameplay."""
    s = Song('Jungle Pulse', groove=(5, 5, 5, 6), loop=4)
    s.inst('pulse', 'stab', duty=1, volume=11, envPace=2, vibSpeed=5, vibDepth=2, vibDelay=6)
    s.inst('pulse', 'pad', duty=0, volume=6, envPace=0, vibSpeed=2, vibDepth=1)
    synth(s, 'reese', 'reese', volume=3, speed=2)
    kit = dict(k=f'#29@{s.s["instruments"][noise_kick(s)]["name"]}',
               s=f'#34@{s.s["instruments"][noise_snare(s)]["name"]}',
               g=f'#36@{s.s["instruments"][noise_snare(s, name="ghost", volume=7)]["name"]}',
               h=f'#44@{s.s["instruments"][noise_hat(s, metallic=True, volume=5)]["name"]}',
               o=f'#42@{s.s["instruments"][noise_hat(s, open_=True, volume=7)]["name"]}',
               c=f'#38@{s.s["instruments"][noise_crash(s)]["name"]}')
    amen = drums('k . k h s . h g h g k k s . h g', kit)
    amen2 = drums('k . k h s . h g h g k . s . s+912 g', kit)
    roll = drums('s g s g k . s s+902 k s g s s+913 s s', kit)
    hats = drums('h . h . h . h . h . h . h . o .', kit)
    pads = {'Fm': 'F4@pad+037 . . . . . . . . . . . . . . .', 'Db': 'Db4@pad+047 . . . . . . . . . . . . . . .',
            'Eb': 'Eb4@pad+057 . . . . . . . . . . . . . . .', 'Cm': 'C4@pad+037 . . . . . . . . . . . . . . .'}
    bass = {'Fm': 'F3@reese . . . . . . . . . F3 . . . Ab3 .', 'Db': 'Db3@reese . . . . . . . . . . . Db3 . C3 .',
            'Eb': 'Eb3@reese . . . . . . . Eb3 . . . . . G3 .', 'Cm': 'C3@reese . . . . . . . C4 . . . Bb3 . G3 .'}
    prog = ['Fm', 'Db', 'Eb', 'Cm']
    # Intro: pads and hats, then the bass alone.
    for i, c in enumerate(prog):
        s.bar(['.', pads[c], bass[c] if i >= 2 else '.', hats if i < 3 else roll])
    # A: the drop. E01 on its first row.
    for i in range(8):
        c = prog[i % 4]
        first = '.+E01' if i == 0 else '.'
        s.bar([first, pads[c], bass[c], roll if i == 7 else (amen2 if i % 4 == 3 else amen)])
    # B: the hook over the break.
    hook = [
        'C5@stab . . Ab4 . . Bb4 . C5 . . . Eb5 . C5 .',
        'Db5 . . C5 . . Bb4 . Ab4 . . . F4 . . .',
        'G4 . . Bb4 . . Eb5 . . . G5 . F5 . Eb5 .',
        'C5 . . . . . . . . . . . - . . .',
    ]
    for i in range(8):
        c = prog[i % 4]
        m = hook[i % 4] if i < 4 else transpose_text(hook[i % 4], 12).replace('@stab', '@stab')
        s.bar([m, pads[c], bass[c], roll if i == 7 else (amen2 if i % 2 else amen)])
    # Breakdown: bass and pads, the break thinned out.
    thin = drums('k . . . s . . . . . k . s . . .', kit)
    for i, c in enumerate(prog):
        s.bar(['.+E02' if i == 0 else '.', pads[c], bass[c], roll if i == 3 else thin])
    return s


# ─── 4. Crimson Clash: a JRPG battle ──────────────────────────────────────

def crimson_clash():
    """A minor, 163 BPM (6-5 groove). A pedal-tone riff, 16th-note broken
    chords on the second pulse, driving octave bass, a heroic lead with
    vibrato. i-VI-VII-V, then a iv-i-VI-V bridge."""
    s = Song('Crimson Clash', groove=(6, 5), loop=2)
    s.inst('pulse', 'hero', duty=2, volume=13, envPace=0, vibSpeed=5, vibDepth=2, vibDelay=12)
    s.inst('pulse', 'riff', duty=1, volume=11, envPace=1)
    s.inst('pulse', 'arp', duty=0, volume=7, envPace=1)
    synth(s, 'bass', 'pluckBass', volume=3, speed=1)
    kit = dict(k=f'#28@{s.s["instruments"][noise_kick(s)]["name"]}',
               s=f'#33@{s.s["instruments"][noise_snare(s)]["name"]}',
               h=f'#43@{s.s["instruments"][noise_hat(s)]["name"]}',
               c=f'#38@{s.s["instruments"][noise_crash(s)]["name"]}')
    beat = drums('k . h . s . h k . k h . s . h .', kit)
    beat2 = drums('k . h k s . h . k . h k s . s s', kit)
    fill = drums('s . s s s . s s k s s s s s s s', kit)
    riff = 'A4@riff A4 A5 A4 G5 A4 F5 A4 E5 A4 D5 A4 E5 . G#5 .'
    s.bar([riff, transpose_text(riff, -12).replace('@riff', '@riff'), 'A3@bass . A3 . A3 . A3 . A3 . A3 . A3 . G#3 .',
           drums('c . . . k . . . k . . . s s s s', kit)])
    s.bar([riff, transpose_text(riff, -12), 'A3 . A3 . A3 . A3 . A3 . A3 . E3 . G#3 .', fill])
    arp = lambda a, b, c: ' '.join([f'{a}@arp', b, c, b] + [a, b, c, b] * 3)
    arps = dict(Am=arp('A4', 'C5', 'E5'), F=arp('F4', 'A4', 'C5'), G=arp('G4', 'B4', 'D5'),
                E=arp('E4', 'G#4', 'B4'), Dm=arp('D4', 'F4', 'A4'), Bdim=arp('B3', 'D4', 'F4'))
    octs = lambda r: ' '.join([f'{r}3@bass', '.', f'{r}4', '.'] * 4)
    bass = dict(Am=octs('A'), F=octs('F'), G=octs('G'), E=octs('E'), Dm=octs('D'), Bdim=octs('B'))
    leadA = [
        'E5@hero . . . . . A5 . . . B5 . C6 . B5 .',
        'A5 . . . . . . . F5 . . . G5 . A5 .',
        'B5 . . . . . G5 . . . D5 . G5 . B5 .',
        'G#5 . . . . . . . . . . . E5 . . .',
        'E5 . . . . . A5 . . . B5 . C6 . D6 .',
        'E6 . . . . . D6 . C6 . . . A5 . . .',
        'D6 . . . C6 . B5 . . . G5 . A5 . B5 .',
        'B5 . . . . . . . G#5 . . . . . . .',
    ]
    for i, (m, c) in enumerate(zip(leadA, ['Am', 'F', 'G', 'E'] * 2)):
        s.bar([m, arps[c], bass[c], fill if i == 7 else (beat2 if i % 4 == 3 else beat)])
    leadB = [
        'F5 . . . E5 . D5 . . . A4 . D5 . F5 .',
        'E5 . . . . . C5 . . . A4 . C5 . E5 .',
        'F5 . . . G5 . A5 . . . C6 . A5 . F5 .',
        'G#5 . . . . . . . B5 . . . E6 . . .',
        'F6 . . . E6 . D6 . . . A5 . D6 . F6 .',
        'E6 . . . . . C6 . . . A5 . C6 . E6 .',
        'D6 . . . F5 . B5 . . . D6 . G#5 . A5 .',
        'B5+E01 . . . . . . . . . . . - . . .',
    ]
    for i, (m, c) in enumerate(zip(leadB, ['Dm', 'Am', 'F', 'E', 'Dm', 'Am', 'Bdim', 'E'])):
        s.bar([m, arps[c], bass[c], fill if i == 7 else (beat2 if i % 2 else beat)])
    return s


# ─── 5. Willow Lane: a village waltz ──────────────────────────────────────

def willow_lane():
    """G major in 3/4: 12-row bars, 112 BPM. A flute-like lead with delayed
    vibrato, oom-pa-pa chords, a triangle bass, a borrowed C minor."""
    s = Song('Willow Lane', groove=(8, 8), rows=12)
    s.inst('pulse', 'flute', duty=2, volume=11, envPace=0, vibSpeed=3, vibDepth=2, vibDelay=14)
    s.inst('pulse', 'pa', duty=1, volume=6, envPace=1, length=8)
    tri = s.wave(WAVES['triangle']())
    s.inst('wave', 'bass', duty=tri, volume=3)
    s.inst('noise', 'brush', volume=4, envPace=1)
    lead = [
        'D5@flute . . . . . . . G5 . A5 .', 'B5 . . . . . . . A5 . . .',
        'G5 . . . . . F#5 . E5 . . .', 'E5 . . . . . . . . . . .',
        'D5 . . . . . . . B5 . A5 .', 'G5 . . . . . . . E5 . . .',
        'F#5 . . . G5 . . . A5 . . .', 'A5 . . . . . . . . . . .',
        'B5 . . . . . C6 . D6 . . .', 'D6 . . . . . C6 . B5 . . .',
        'C6 . . . . . B5 . A5 . . .', 'G5 . . . . . Eb5 . . . . .',
        'D5 . . . . . G5 . B5 . . .', 'B5 . . . A5 . . . G5 . . .',
        'A5 . . . . . . . F#5 . . .', 'G5 . . . . . . . . . - .',
    ]
    chords = ['G', 'D', 'Em', 'C', 'G', 'Am', 'D', 'D7', 'G', 'G7', 'C', 'Cm', 'G', 'Em', 'D', 'G']
    arp = dict(G=('G4', '047', 'G3'), D=('D4', '047', 'F#3'), Em=('E4', '037', 'E3'), C=('C4', '047', 'C3'),
               Am=('A4', '037', 'A3'), D7=('D4', '4A', 'D3'), G7=('G4', '4A', 'G3'), Cm=('C4', '037', 'C3'))
    for m, c in zip(lead, chords):
        root, fx, low = arp[c]
        fx = fx if len(fx) == 3 else '0' + fx
        s.bar([m, f'. . . . {root}@pa+{fx} . . . {root} . . .',
               f'{low}@bass . . . . . . . . . . .',
               '. . . . #41@brush . . . #41 . . .'])
    return s


# ─── 6. Hollow Deep: a dungeon ────────────────────────────────────────────

def hollow_deep():
    """D minor with a phrygian E-flat, 100 BPM. A growling wave drone that
    sinks a half step, a slow lead that slides by portamento, its echo three
    rows behind on the second pulse, and water dripping on the noise."""
    s = Song('Hollow Deep', groove=(9, 9))
    s.inst('pulse', 'ghost', duty=0, volume=9, envPace=0, vibSpeed=2, vibDepth=3, vibDelay=20)
    s.inst('pulse', 'echo', duty=0, volume=3, envPace=0, vibSpeed=2, vibDepth=3, vibDelay=20)
    synth(s, 'drone', 'growl', mode='pingpong', speed=6, volume=2)
    s.inst('noise', 'drip', volume=6, envPace=1)
    s.inst('noise', 'rumble', volume=7, envPace=7)
    lead = [
        'D5@ghost . . . . . . . . . . . A5 . . .',
        'Bb5 . . . . . . . A5 . . . . . . .',
        'F5 . . . . . . . E5+308 . . . . . . .',
        'Eb5+304 . . . . . . . D5 . . . . . - .',
        'A4 . . . . . . . D5 . . . F5 . . .',
        'E5 . . . . . . . Eb5+306 . . . . . . .',
        'D5 . . . C#5 . . . D5 . . . F5 . A5 .',
        'G#5+302 . . . . . . . A5 . . . - . . .',
    ]
    tokens = ' '.join(lead).split()
    # The echo: the same line three rows late, on the quiet instrument.
    delayed = ['.'] * 3 + [t.replace('@ghost', '@echo') for t in tokens[:-3]]
    delayed[3] = delayed[3] if '@' in delayed[3] else delayed[3] + '@echo'
    echo = [' '.join(delayed[i * 16:(i + 1) * 16]) for i in range(8)]
    drone = ['D3@drone . . . . . . . . . . . . . . .'] * 3 + ['Eb3 . . . . . . . . . . . . . . .'] + \
            ['D3 . . . . . . . . . . . . . . .'] * 2 + ['Eb3 . . . . . . . . . . . . . . .', 'C#3 . . . . . . . D3 . . . . . . .']
    drips = ['. . . . . #45@drip . . . . . . . . . .', '. . . . . . . . . . #43@drip . . . . .',
             '#8@rumble . . . . . . . . . . . . . #44@drip .', '. . . #45@drip . . . . . . . . . . . .',
             '. . . . . . . . . #42@drip . . . . . .', '#8@rumble . . . . . . #45@drip . . . . . . . .',
             '. . . . . . . . . . . . . #43@drip . .', '. . . . . #44@drip . . . . . . . . . .']
    for i in range(8):
        s.bar([lead[i], echo[i], drone[i], drips[i]])
    return s


# ─── 7. Victory: a fanfare that ends ──────────────────────────────────────

def victory():
    """C major, no loop: the song stops, Chiptune.onEnd fires."""
    s = Song('Victory', groove=(5, 5), loop=None)
    s.inst('pulse', 'brass', duty=2, volume=13, envPace=0, vibSpeed=5, vibDepth=2, vibDelay=16)
    s.inst('pulse', 'brass2', duty=1, volume=10, envPace=0, vibSpeed=5, vibDepth=2, vibDelay=16)
    tri = s.wave(WAVES['triangle']())
    s.inst('wave', 'bass', duty=tri, volume=3)
    kit = dict(s=f'#33@{s.s["instruments"][noise_snare(s)]["name"]}',
               c=f'#38@{s.s["instruments"][noise_crash(s)]["name"]}',
               k=f'#28@{s.s["instruments"][noise_kick(s)]["name"]}')
    s.bar(['G4@brass . G4 . G4 . C5 . . . . . . . . .', 'E4@brass2 . E4 . E4 . G4 . . . . . . . . .',
           'C4@bass . C4 . C4 . C4 . . . . . . . . .', drums('s . s . s . c . . . . . k . s s', kit)])
    s.bar(['E5 . . . D5 . . . E5 . . . G5 . . .', 'C5 . . . B4 . . . C5 . . . D5 . . .',
           'A3 . . . G3 . . . C4 . . . G3 . . .', drums('k . . . s . . . k . . . s . s s', kit)])
    s.bar(['C6 . . . . . . . . . . . . . . .', 'E5+047 . . . . . . . . . . . . . . .',
           'C3 . . . . . . . . . . . . . . .', drums('c . . . . . . . . . . . . . . .', kit)])
    s.bar(['. . . . . . . . - . . . . . . .', '. . . . . . . . - . . . . . . .',
           '. . . . . . . . - . . . . . . .', '.'])
    return s


# ─── 8. Fade Out: game over ───────────────────────────────────────────────

def fade_out():
    """A minor, no loop: a slow line falling over a chromatic bass."""
    s = Song('Fade Out', groove=(9, 9), loop=None)
    s.inst('pulse', 'sad', duty=1, volume=11, envPace=0, vibSpeed=3, vibDepth=3, vibDelay=10)
    s.inst('pulse', 'low', duty=2, volume=6, envPace=3)
    tri = s.wave(WAVES['triangle']())
    s.inst('wave', 'bass', duty=tri, volume=3)
    s.bar(['E5@sad . . . D5 . . . C5 . . . B4 . . .', 'C5@low . . . . . . . A4 . . . . . . .',
           'A3@bass . . . . . . . G#3 . . . . . . .', '.'])
    s.bar(['C5 . . . B4 . . . A4 . . . G#4 . . .', 'A4 . . . . . . . F4 . . . . . . .',
           'G3 . . . . . . . F3 . . . . . . .', '.'])
    s.bar(['A4 . . . . . . . . . . . . . . .', 'E4+037 . . . . . . . . . . . . . . .',
           'E3 . . . . . . . A2 . . . . . . .', '.'])
    s.bar(['. . . . . . . . - . . . . . . .', '. . . . . . . . - . . . . . . .',
           '. . . . . . . . - . . . . . . .', '.'])
    return s


SONGS = {
    'cloud_garden': cloud_garden,
    'tidal_twang': tidal_twang,
    'jungle_pulse': jungle_pulse,
    'crimson_clash': crimson_clash,
    'willow_lane': willow_lane,
    'hollow_deep': hollow_deep,
    'victory': victory,
    'fade_out': fade_out,
}


# ─── the SFX library ──────────────────────────────────────────────────────

def sfx_library():
    """Effects in one bank. Priorities: 1 interface, 2 gameplay, 3 events,
    4 the big ones; a stronger effect takes a slot from a weaker one.
    Channels: PU1 for gameplay tones, PU2 for the interface (so a menu blip
    never cuts a gameplay sound), NOI for impacts, WAV for bells and magic
    (it borrows the bass for as long as it rings)."""
    s = Song('SFX', rows=16)
    s.inst('pulse', 'blip', duty=1, volume=9, envPace=1, length=4)
    s.inst('pulse', 'ping', duty=1, volume=11, envPace=1)
    s.inst('pulse', 'ding', duty=2, volume=12, envPace=2)
    s.inst('pulse', 'sq', duty=2, volume=11, envPace=0)
    s.inst('pulse', 'buzz', duty=0, volume=12, envPace=0)
    s.inst('pulse', 'jump', duty=2, volume=11, envPace=1)
    s.inst('pulse', 'hurt', duty=1, volume=13, envPace=1)
    zap_t = s.table('zap', [dict(fx=(0x2, 0x30))] + [{} for _ in range(8)] + [dict(fx=(0xA, 1))])
    s.inst('pulse', 'zap', duty=2, volume=12, envPace=1, table=zap_t)
    s.inst('pulse', 'charge', duty=1, volume=10, envPace=0, vibSpeed=8, vibDepth=2)
    s.inst('pulse', 'warp', duty=0, volume=11, envPace=0, vibSpeed=10, vibDepth=4)
    s.inst('pulse', 'alarm', duty=1, volume=12, envPace=0)
    s.inst('pulse', 'boing', duty=2, volume=12, envPace=2)
    s.inst('pulse', 'sweep', duty=2, volume=13, envPace=2, sweep=0x2E)
    s.inst('noise', 'thud', volume=10, envPace=1)
    s.inst('noise', 'tick', volume=6, envPace=1)
    s.inst('noise', 'crack', volume=13, envPace=1)
    s.inst('noise', 'boom', volume=15, envPace=5)
    s.inst('noise', 'boom2', volume=13, envPace=3)
    s.inst('noise', 'pew', volume=12, envPace=1, duty=1)
    s.inst('noise', 'creak', volume=9, envPace=2, duty=1)
    s.inst('noise', 'whoosh', volume=9, envPace=2)
    s.inst('noise', 'splash', volume=11, envPace=3)
    s.inst('noise', 'fuse', volume=7, envPace=1, duty=1)
    sine = s.wave(WAVES['sine']())
    bell_t = s.table('bell fade', [dict(env=3), {}, {}, dict(env=2), {}, {}, {}, dict(env=1), {}, {}, {}, {}, dict(env=0)])
    s.inst('wave', 'bell', duty=sine, volume=3, table=bell_t, tableSpeed=1)
    shimmer = synth(s, 'shimmer', 'wah', volume=3, speed=1)
    s.s['instruments'][shimmer]['name'] = 'shimmer'
    fx = [
        # interface (PU2, priority 1)
        ('cursor', 'E6@blip . . -', 1, 1, 1),
        ('select', 'E5@ping A5 E6 . . -', 1, 1, 3),
        ('back', 'A5@ping E5 . . -', 1, 1, 3),
        ('error', 'C3@buzz . - C3 . . -', 1, 2, 4),
        ('pause', 'E6@ping C6 E6 C6 . . -', 1, 1, 3),
        ('text', 'G5@blip . -', 1, 1, 1),
        ('toggle', 'C6@blip G6 -', 1, 1, 2),
        ('score', 'C7@blip -', 1, 1, 1),
        # movement
        ('jump', 'C4@jump+110 . . . . . . . . . . -', 1, 2, 1),
        ('double_jump', 'G4@jump+120 . . . . . . -', 1, 2, 1),
        ('land', '#20@thud #16 #12 -', 3, 2, 1),
        ('step', '#30@tick . -', 3, 1, 1),
        ('dash', '#44@whoosh #42 #40 #38 #36 #34 #32 -', 3, 2, 1),
        ('bounce', 'C5@boing+118 . . . . . G5+218 . . . . . -', 1, 2, 1),
        ('splash', '#38@splash #36 #40 #34 #30 . . -', 3, 2, 2),
        # combat
        ('hit', '#34@crack #28 #24 #20 . . -', 3, 3, 1),
        ('hurt', 'A5@hurt+220 . F5 . . . -', 0, 3, 2),
        ('laser', 'C7@zap . . . . . . . . . -', 0, 2, 1),
        ('shoot', '#40@pew #36 #32 #28 -', 3, 2, 1),
        ('explosion', '#12@boom #10 #8 #6 #5 #4 #3 . . . . . -', 3, 4, 3),
        ('small_boom', '#18@boom2 #14 #10 #8 . . -', 3, 3, 2),
        ('fuse', '#40@fuse+902 . . . . . . . . . . . . . . . . . . -', 3, 2, 1),
        ('sweep_shot', 'C6@sweep . . . . . . . -', 0, 2, 2),
        ('death', 'B4@hurt+204 . . F4 . . D4 . . B3 . . . . -', 0, 4, 3),
        # rewards
        ('coin', 'B5@ding E6 . . . . . -', 0, 2, 4),
        ('pickup', 'G5@ping B5 D6 G6 . -', 1, 2, 3),
        ('powerup', 'C5@sq+047 E5 G5 C6 E6 G6 C7 . . -', 1, 3, 2),
        ('oneup', 'E6@ping G6 E7 C7 D7 G7 . -', 1, 3, 4),
        ('chest', 'C5@sq G5 C6 E6 G6 C7+047 . . . . -', 1, 3, 2),
        ('heal', 'C5@bell E5 G5 C6 . . . . . . -', 2, 2, 3),
        ('key', 'E6@bell B6 . . . . . . -', 2, 2, 4),
        ('magic', 'C6@shimmer+047 . . . . . . . . . . . -', 2, 2, 2),
        ('win', 'C5@ping E5 G5 C6 . G5 C6 . . -', 1, 3, 4),
        ('lose', 'G4@hurt F#4 F4 E4 . . -', 1, 3, 5),
        # world
        ('door', '#6@creak #7 #8 #6 #5 . #20@thud . -', 3, 2, 3),
        ('charge', 'C4@charge+104 . . . . . . . . . . . . . . . . . . . . . . . -', 0, 2, 2),
        ('warp', 'C4@warp+0C7 E4 G4 C5 E5 G5 C6 E6 G6 C7 . -', 0, 3, 2),
        ('alarm', 'A5@alarm E5 A5 E5 A5 E5 -', 0, 3, 6),
    ]
    for name, text, ch, prio, speed in fx:
        s.sfx(name, text, ch, prio, speed)
    s.s['orders'] = []
    return s
