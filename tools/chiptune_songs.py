"""The demo songs and the SFX library, written as code.

    python tools/chiptune.py songs      # -> chiptune/music/*.gbm

Each song is a style and a set of chiptune techniques; the docstrings say
which. Three are format 1 -- four Game Boy channels, exactly what a DMG
would play -- and the rest format 2, with more voices, oscillators per
instrument, PWM, sync, ring modulation and a filter.

Tempo: a row is a 16th note unless said otherwise, and a groove step is the
frames a row lasts at 59.73 frames/s: [10, 10] is 90 BPM, [7, 7] 128,
[6, 5] 163, [5, 5, 5, 6] 170, [5, 5] 179.
"""
import re

from gbm_compose import (Song, noise_snare, noise_hat, noise_crash, pulse_kick, synth, synth_kit,
                         sample_voice, sid_kick, sid_snare, sid_tom, WAVES, transpose_text)

KIT = {s['name']: s for s in synth_kit()}     # kick, snare, rim, hat, clap: 4-bit, 8192 Hz


# ─── helpers ──────────────────────────────────────────────────────────────

def drums(pattern, kit):
    """Drum shorthand: letters for the kit's pieces, commands may follow
    (`s+904`), anything else passes through."""
    out = []
    for t in pattern.split():
        head, plus, rest = t.partition('+')
        out.append(kit[head] + plus + rest if head in kit else t)
    return ' '.join(out)


def strip_g(text):
    """A lane without its format-2 extended commands (a copy must not
    repeat the original's filter moves)."""
    return re.sub(r'\+G[0-9A-Fa-f]{4}', '', text)


def retarget(texts, src, dst, semis=0):
    """The same line for another instrument, `semis` away: an echo, a
    unison, a sync slave, a ring-mod master."""
    out = []
    for t in texts:
        t = re.sub('@' + src + r'(?![\w-])', '@' + dst, strip_g(t))
        out.append(transpose_text(t, semis) if semis else t)
    return out


def delayed(texts, rows, src, dst, per_bar=16):
    """The line `rows` later on another instrument: the classic chip echo."""
    tokens = ' '.join(t if len(t.split()) == per_bar else ' '.join((t.split() + ['.'] * per_bar)[:per_bar])
                      for t in retarget(texts, src, dst)).split()
    # sync markers belong to the original only
    tokens = [re.sub(r'\+E[0-9A-Fa-f]{2}', '', t) for t in tokens]
    shifted = ['.'] * rows + tokens[:len(tokens) - rows]
    first = next((i for i, t in enumerate(shifted) if not t.startswith(('.', '-'))), None)
    if first is not None and '@' not in shifted[first]:
        head, plus, rest = shifted[first].partition('+')
        shifted[first] = head + '@' + dst + plus + rest
    return [' '.join(shifted[i:i + per_bar]) for i in range(0, len(shifted), per_bar)]


def kit_of(song, pieces):
    """{letter: 'note@instrument'} from (letter, note, instrument index)."""
    return {k: f'{note}@{song.s["instruments"][i]["name"]}' for k, note, i in pieces}


# ─── 1. Cloud Garden: the main menu ───────────────────────────────────────

def cloud_garden():
    """D major, 90 BPM, format 2 (6 voices).
    Techniques: a PWM pad (the width breathing on its own, `pwm`) holding
    its chord by arpeggio, through a low-pass that opens across the song
    (cutoff slides, `+G12`); a flute on a triangle with delayed vibrato and
    its echo three rows behind on a thin pulse; harp-like broken chords
    panned left; a shaker entering for the second half."""
    s = Song('Cloud Garden', groove=(10, 10), version=2, voices=6,
             filter=dict(cutoff=70, resonance=5, mode=1))
    s.voice('triangle', 'flute', volume=12, envPace=0, vibSpeed=4, vibDepth=2, vibDelay=18)
    s.voice('pulse', 'echo', volume=5, width=48, envPace=0, vibSpeed=4, vibDepth=2, vibDelay=18)
    s.voice('pulse', 'harp', volume=7, width=40, envPace=2)
    s.voice('pulse', 'pad', volume=6, width=128, pwm=2, envPace=0, filter=True)
    s.voice('triangle', 'bass', volume=11, envPace=0)
    s.voice('noise', 'shaker', volume=3, envPace=1)
    s.voice('noise', 'shaker2', volume=5, envPace=1)
    lead = [
        'A5@flute . . . F#5 . . . E5 . . . F#5 . . .',
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
        'G5 . . . . . B5 . D6 . . . E6 . . .',
        'B5 . . . . . A5 . G5 . . . E5 . . .',
        'A5 . . . . . . . . . . . - . . .',
    ]
    echo = delayed(lead, 3, 'flute', 'echo')
    up_down = lambda a, b, c, d: f'{a}@harp+802 . {b} . {c} . {d} . {c} . {b} . {a} . {b} .'
    harp = {
        'D': up_down('D4', 'A4', 'C#5', 'F#5'), 'Bm': up_down('B3', 'F#4', 'A4', 'D5'),
        'G': up_down('G3', 'D4', 'F#4', 'B4'), 'A': 'A3@harp+802 . E4 . A4 . D5 . E5 . C#5 . A4 . E4 .',
        'F#m': up_down('F#3', 'C#4', 'E4', 'A4'), 'EmA': 'E3@harp+802 . B3 . D4 . G4 . A3 . E4 . G4 . C#5 .',
        'Em': up_down('E3', 'B3', 'D4', 'G4'), 'A7': 'A3@harp+802 . E4 . G4 . C#5 . E5 . C#5 . G4 . E4 .',
    }
    # The pad: its chord by arpeggio, held for the bar.
    pad = {'D': 'D4@pad+047', 'Bm': 'B3@pad+037', 'G': 'G3@pad+04B', 'A': 'A3@pad+057', 'F#m': 'F#3@pad+037',
           'EmA': 'E4@pad+037', 'Em': 'E4@pad+037', 'A7': 'A3@pad+047'}
    roots = {'D': 'D3', 'Bm': 'B2', 'G': 'G2', 'A': 'A2', 'F#m': 'F#2', 'EmA': 'E2', 'Em': 'E2', 'A7': 'A2'}
    chords = ['D', 'Bm', 'G', 'A', 'D', 'F#m', 'G', 'EmA', 'Bm', 'G', 'D', 'A', 'Bm', 'G', 'Em', 'A7']
    shaker = '. . #42@shaker . . . #42 . . . #42@shaker2 . . . #42@shaker #44'
    for i, c in enumerate(chords):
        # the filter opens over the first half, further in the second, and
        # closes over the last two bars
        slide = '+G1201' if i == 0 else '+G1202' if i == 8 else '+G12FE' if i == 14 else ''
        p = f'{pad[c]}{slide} . . . . . . . . . . . . . . .'
        bass = f'{roots[c]}@bass . . . . . . . . . . . . . . .'
        if c == 'EmA':
            p = f'E4@pad+037{slide} . . . . . . . A3+047 . . . . . . .'
            bass = 'E2@bass . . . . . . . A2 . . . . . . .'
        noi = shaker if i >= 8 else ('. . . . . . . . . . . . . . #44@shaker .' if i % 2 else '.')
        s.bar([lead[i], echo[i], harp[c], p, bass, noi])
    return s


# ─── 2. Tidal Twang: surf rock, on a real Game Boy ────────────────────────

def tidal_twang():
    """E, 179 BPM, format 1: four DMG channels, exactly.
    Techniques: tremolo picking by retrigger (9x2: restart every 2 frames);
    a glissando by a long slide; the rhythm guitar and the kick drum sharing
    PU2 -- a pulse kick (a note near C6 dropped hard and cut) between chord
    stabs, the Game Boy's way to a kick with body; a pluck bass on the wave
    synth; noise snare, hats and crash."""
    s = Song('Tidal Twang', groove=(5, 5), loop=2)
    s.inst('pulse', 'trem', duty=1, volume=11, envPace=1)
    s.inst('pulse', 'twang', duty=2, volume=12, envPace=3, vibSpeed=6, vibDepth=2, vibDelay=10)
    s.inst('pulse', 'chug', duty=2, volume=7, envPace=1, length=4)
    pulse_kick(s, drop=0xE0, frames=6)
    synth(s, 'bass', 'pluckBass', volume=3)
    kit = dict(s=f'#33@{s.s["instruments"][noise_snare(s)]["name"]}',
               h=f'#43@{s.s["instruments"][noise_hat(s)]["name"]}',
               o=f'#41@{s.s["instruments"][noise_hat(s, open_=True)]["name"]}',
               c=f'#38@{s.s["instruments"][noise_crash(s)]["name"]}')
    beat = drums('h . h . s . h . h . h . s . h o', kit)
    beat2 = drums('h . h . s . h h . h h . s . s o', kit)
    fill = drums('h . s . s . s s h s s s s+902 . s s', kit)

    def pu2(chord):
        # the kick on 1, the "and" of 2 and on 3; the chord chugs between
        c = f'{chord}@chug+047'
        return f'C6@pkick . {c} . {chord} . C6@pkick . C6@pkick . {chord} . {chord} . {chord} .'
    s.bar(['E6@trem+902+210 . . . . . . . . . . . . . . .', '.',
           'E3@bass . . . . . . . . . . . . . . .', drums('c . . . . . . . . . . . . . . .', kit)])
    s.bar(['. . . . . . . . . . . . - . . .', 'C6@pkick . . . C6 . . . E4@chug+047 . E4 . E4 . E4 .',
           'E3 . E3 . . . E3 . E3 . B3 . . . B3 .', fill])
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
    bassA = {'E': 'E3@bass . E3 . B3 . E3 . E4 . B3 . G#3 . B3 .',
             'F': 'F3@bass . F3 . C4 . F3 . F4 . C4 . A3 . C4 .'}
    for i, m in enumerate(trem):
        c = 'EF'[i % 2] if i < 6 else ('F' if i == 6 else 'E')
        s.bar([m, pu2(c + '4'), bassA[c], fill if i == 7 else (beat2 if i % 4 == 3 else beat)])
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
    for i, (m, c) in enumerate(zip(twang, 'EABAEABB')):
        s.bar([m, pu2(c + '4'), walk[c], fill if i == 7 else (beat2 if i % 2 else beat)])
    return s


# ─── 3. Jungle Pulse: drum & bass ─────────────────────────────────────────

def jungle_pulse():
    """F minor, 170 BPM (a 5-5-5-6 groove), format 2 (8 voices).
    Techniques: a sampled break -- kick, snare, rim, clap and hat from a
    synthesised 808-style kit, spread over two voices so nothing else is
    stolen -- with retrigger rolls (9xy on a sample restarts it); a reese
    bass of two saws detuned against each other (a constant pitch offset in
    one's table) through a resonant low-pass whose cutoff swings open and
    shut; a triangle sub an octave below; minor pads by arpeggio; a stab
    lead with its echo. The drop carries sync marker E01."""
    s = Song('Jungle Pulse', groove=(5, 5, 5, 6), loop=4, version=2, voices=8,
             filter=dict(cutoff=110, resonance=11, mode=1))
    s.voice('pulse', 'stab', volume=11, width=96, envPace=2, vibSpeed=5, vibDepth=2, vibDelay=6)
    s.voice('pulse', 'echo', volume=4, width=96, envPace=2)
    s.voice('pulse', 'pad', volume=5, width=32, pwm=1, envPace=0, vibSpeed=2, vibDepth=1)
    s.voice('saw', 'reese', volume=10, envPace=0, filter=True)
    detune = s.table('detune', [dict(pitch=-3)], loop=0)
    s.voice('saw', 'reese2', volume=10, envPace=0, filter=True, table=detune)
    s.voice('triangle', 'sub', volume=12, envPace=0)
    kick = sample_voice(s, KIT['kick'], 'k808', volume=15)
    snare = sample_voice(s, KIT['snare'], 's808', volume=14)
    rim = sample_voice(s, KIT['rim'], 'r808', volume=10)
    clap = sample_voice(s, KIT['clap'], 'c808', volume=10)
    hat = sample_voice(s, KIT['hat'], 'h808', volume=8)
    ohat = s.voice('noise', 'ohat', volume=6, envPace=3, duty=1)
    kit = kit_of(s, [('k', 'C5', kick), ('s', 'C5', snare), ('g', 'C5', rim), ('p', 'D5', clap),
                     ('h', 'C5', hat), ('o', '#43', ohat)])
    # The break over two voices: kicks and snares on one; hats, ghosts and
    # claps on the other.
    brk = (drums('k . k . s . . s . . k k s . . s', kit), drums('h . h g h g h . h g h . h g o g', kit))
    brk2 = (drums('k . k . s . . s . . k . s . s+912 .', kit), drums('h . h g h g h . h g h . p g o .', kit))
    roll = (drums('s . s . k . s s+902 k s . s s+913 s s', kit), drums('h h h h h h h h o . o . o o o o', kit))
    thin = (drums('k . . . s . . . . . k . s . . .', kit), drums('h . . . h . . . h . . . h . o .', kit))
    hats = ('.', drums('h . h . h . h . h . h . h . o .', kit))
    pads = {'Fm': 'F4@pad+037', 'Db': 'Db4@pad+047', 'Eb': 'Eb4@pad+057', 'Cm': 'C4@pad+037'}
    bass = {'Fm': 'F3@reese . . . . . . . . . F3 . . . Ab3 .', 'Db': 'Db3@reese . . . . . . . . . . . Db3 . C3 .',
            'Eb': 'Eb3@reese . . . . . . . Eb3 . . . . . G3 .', 'Cm': 'C3@reese . . . . . . . C4 . . . Bb3 . G3 .'}
    prog = ['Fm', 'Db', 'Eb', 'Cm']

    def bar(c, lead, drum, wobble='', bass_on=True):
        b = bass[c].replace('@reese', '@reese' + wobble, 1) if bass_on else '.'
        s.bar([lead, delayed([lead], 3, 'stab', 'echo')[0] if lead != '.' else '.',
               pads[c] + ' . . . . . . . . . . . . . . .', b,
               retarget([b], 'reese', 'reese2')[0] if bass_on else '.',
               retarget([b], 'reese', 'sub', -12)[0] if bass_on else '.', drum[0], drum[1]])
    for i, c in enumerate(prog):
        bar(c, '.', hats if i < 3 else roll, bass_on=i >= 2)
    for i in range(8):
        c = prog[i % 4]
        bar(c, '.+E01' if i == 0 else '.', roll if i == 7 else (brk2 if i % 4 == 3 else brk),
            '+G1203' if i % 2 == 0 else '+G12FD')
    hook = [
        'C5@stab . . Ab4 . . Bb4 . C5 . . . Eb5 . C5 .',
        'Db5 . . C5 . . Bb4 . Ab4 . . . F4 . . .',
        'G4 . . Bb4 . . Eb5 . . . G5 . F5 . Eb5 .',
        'C5 . . . . . . . . . . . - . . .',
    ]
    for i in range(8):
        m = hook[i % 4] if i < 4 else transpose_text(hook[i % 4], 12)
        bar(prog[i % 4], m, roll if i == 7 else (brk2 if i % 2 else brk), '+G1204' if i % 2 == 0 else '+G12FC')
    for i, c in enumerate(prog):
        bar(c, '.+E02' if i == 0 else '.', roll if i == 3 else thin, '+G12FF' if i == 0 else '')
    return s


# ─── 4. Crimson Clash: a JRPG battle ──────────────────────────────────────

def crimson_clash():
    """A minor, 163 BPM (6-5 groove), format 2 (7 voices).
    Techniques: a hard-sync lead -- a silent master (volume 0, still
    running) plays the melody while a saw an octave and more above restarts
    on each of its cycles, its own pitch sweeping up through a table, so
    every note tears open at the master's pitch; SID drums (a frame of
    noise, then a falling triangle; a tone, then noise; a pulse tom);
    16th-note broken chords; a sawtooth octave bass; PWM brass stabs."""
    s = Song('Crimson Clash', groove=(6, 5), loop=2, version=2, voices=7)
    s.voice('pulse', 'master', volume=0, envDir=1, envPace=0, width=128)
    sweep = s.table('sync sweep', [dict(transpose=t) for t in (12, 14, 16, 18, 20, 22, 24, 26, 28)] +
                    [dict(transpose=t) for t in (27, 26, 25, 24)], loop=9)
    s.voice('saw', 'sync', volume=12, envPace=0, sync=True, table=sweep, vibSpeed=5, vibDepth=2, vibDelay=12)
    s.voice('pulse', 'arp', volume=6, width=48, envPace=1)
    s.voice('saw', 'bass', volume=10, envPace=1)
    sid_kick(s)
    sid_snare(s)
    sid_tom(s)
    s.voice('noise', 'hat', volume=6, envPace=1, duty=1)
    s.voice('noise', 'crash', volume=9, envPace=6)
    s.voice('pulse', 'brass', volume=10, width=100, pwm=6, envPace=2)
    kit = dict(k='D4@skick', s='A3@ssnare', t='E4@stom', u='B3@stom', h='#43@hat', c='#38@crash')
    beat = (drums('k . . k s . . k . k . . s . . .', kit), drums('h . h . h . h . h . h . h . h h', kit))
    beat2 = (drums('k . . k s . . k . k . k s . s s', kit), drums('h . h . h . h . h . h . h h h h', kit))
    fill = (drums('s . s s t . t t u . u u s s s s', kit), drums('c . . . . . . . . . . . . . . .', kit))
    intro = (drums('k . . . k . . . k . . . s s s s', kit), drums('c . . . . . . . . . . . . . . .', kit))
    riff = 'A4@master A4 A5 A4 G5 A4 F5 A4 E5 A4 D5 A4 E5 . G#5 .'
    arp = lambda a, b, c: ' '.join([f'{a}@arp', b, c, b] + [a, b, c, b] * 3)
    arps = dict(Am=arp('A4', 'C5', 'E5'), F=arp('F4', 'A4', 'C5'), G=arp('G4', 'B4', 'D5'),
                E=arp('E4', 'G#4', 'B4'), Dm=arp('D4', 'F4', 'A4'), Bdim=arp('B3', 'D4', 'F4'))
    octs = lambda r: ' '.join([f'{r}2@bass', '.', f'{r}3', '.'] * 4)
    bass = dict(Am=octs('A'), F=octs('F'), G=octs('G'), E=octs('E'), Dm=octs('D'), Bdim=octs('B'))
    brass = {'Am': ('A4', '037'), 'F': ('F4', '047'), 'G': ('G4', '047'), 'E': ('E4', '047'),
             'Dm': ('D4', '037'), 'Bdim': ('B3', '036')}

    def bar(melody, chord, drum, stabs=True):
        slave = retarget([melody], 'master', 'sync')[0]
        root, fx = brass[chord]
        st = f'{root}@brass+{fx} . . . . . . . . . . . {root} . . .' if stabs else '.'
        s.bar([melody, slave, arps[chord], bass[chord], drum[0], drum[1], st])
    bar(riff, 'Am', intro, False)
    bar(riff, 'Am', fill, False)
    leadA = [
        'E5@master . . . . . A5 . . . B5 . C6 . B5 .',
        'A5 . . . . . . . F5 . . . G5 . A5 .',
        'B5 . . . . . G5 . . . D5 . G5 . B5 .',
        'G#5 . . . . . . . . . . . E5 . . .',
        'E5 . . . . . A5 . . . B5 . C6 . D6 .',
        'E6 . . . . . D6 . C6 . . . A5 . . .',
        'D6 . . . C6 . B5 . . . G5 . A5 . B5 .',
        'B5 . . . . . . . G#5 . . . . . . .',
    ]
    for i, (m, c) in enumerate(zip(leadA, ['Am', 'F', 'G', 'E'] * 2)):
        bar(m, c, fill if i == 7 else (beat2 if i % 4 == 3 else beat))
    leadB = [
        'F5@master . . . E5 . D5 . . . A4 . D5 . F5 .',
        'E5 . . . . . C5 . . . A4 . C5 . E5 .',
        'F5 . . . G5 . A5 . . . C6 . A5 . F5 .',
        'G#5 . . . . . . . B5 . . . E6 . . .',
        'F6 . . . E6 . D6 . . . A5 . D6 . F6 .',
        'E6 . . . . . C6 . . . A5 . C6 . E6 .',
        'D6 . . . F5 . B5 . . . D6 . G#5 . A5 .',
        'B5+E01 . . . . . . . . . . . - . . .',
    ]
    for i, (m, c) in enumerate(zip(leadB, ['Dm', 'Am', 'F', 'E', 'Dm', 'Am', 'Bdim', 'E'])):
        bar(m, c, fill if i == 7 else (beat2 if i % 2 else beat))
    return s


# ─── 5. Willow Lane: a village waltz, on a real Game Boy ──────────────────

def willow_lane():
    """G major in 3/4 (12-row bars), 112 BPM, format 1.
    Techniques: pulse-width movement the Game Boy way -- a table stepping
    the lead's duty 25% -> 50% -> 25% as each note plays; delayed vibrato;
    oom-pa-pa chords by arpeggio with an auto-cut; a triangle bass walking
    between chord tones; a borrowed C minor; a countermelody on PU2 that
    answers the lead's long notes in the second half."""
    s = Song('Willow Lane', groove=(8, 8), rows=12)
    breathe = s.table('breathe', [dict(duty=1), dict(duty=1), dict(duty=2), dict(duty=2), dict(duty=2),
                                  dict(duty=1)], loop=2)
    s.inst('pulse', 'flute', duty=1, volume=11, envPace=0, vibSpeed=3, vibDepth=2, vibDelay=14,
           table=breathe, tableSpeed=3)
    s.inst('pulse', 'pa', duty=1, volume=6, envPace=1, length=8)
    s.inst('pulse', 'answer', duty=2, volume=7, envPace=3)
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
    arp = dict(G=('G4', '047', 'G3', 'B3'), D=('D4', '047', 'F#3', 'A3'), Em=('E4', '037', 'E3', 'G3'),
               C=('C4', '047', 'C3', 'E3'), Am=('A4', '037', 'A3', 'C4'), D7=('D4', '04A', 'D3', 'C4'),
               G7=('G4', '04A', 'G3', 'F3'), Cm=('C4', '037', 'C3', 'Eb3'))
    answers = {9: '. . . . . . . . G5@answer . F5 .', 11: '. . . . . . . . G4@answer . C5 .',
               13: '. . . . . . . . D5@answer . E5 .', 14: '. . . . . . . . C5@answer . . .'}
    for i, (m, c) in enumerate(zip(lead, chords)):
        root, fx, low, walk = arp[c]
        pu2 = answers.get(i, f'. . . . {root}@pa+{fx} . . . {root} . . .')
        s.bar([m, pu2, f'{low}@bass . . . . . . . {walk} . . .', '. . . . #41@brush . . . #41 . . .'])
    return s


# ─── 6. Hollow Deep: a dungeon ────────────────────────────────────────────

def hollow_deep():
    """D phrygian, 100 BPM, format 2 (7 voices).
    Techniques: a ring-modulated bell -- a triangle multiplied by a silent
    square an octave and a tritone above it, so its partials are the sum
    and difference of two unrelated pitches: metal, not a music box; a
    growling wave drone through a resonant band-pass whose centre drifts up
    and down (cutoff slides); a ghostly thin pulse sliding by portamento,
    its echo three rows behind; the 808 kick sample played two octaves down
    as a distant boom (a sample follows the note); dripping water."""
    s = Song('Hollow Deep', groove=(9, 9), version=2, voices=7, filter=dict(cutoff=60, resonance=12, mode=2))
    s.voice('pulse', 'mod', volume=0, envDir=1, envPace=0, width=128)
    s.voice('triangle', 'bell', volume=13, envPace=5, ring=True)
    drone = synth(s, 'drone', 'growl', mode='pingpong', speed=6, volume=10)
    s.s['instruments'][drone]['filter'] = True
    s.voice('pulse', 'ghost', volume=9, width=24, envPace=0, vibSpeed=2, vibDepth=3, vibDelay=20)
    s.voice('pulse', 'echo', volume=3, width=24, envPace=0, vibSpeed=2, vibDepth=3, vibDelay=20)
    s.voice('noise', 'drip', volume=6, envPace=1)
    sample_voice(s, KIT['kick'], 'boom', volume=15)
    bells = ['D5@bell . . . . . . . . . . . . . . .', '.', 'A4@bell . . . . . . . . . . . . . . .', '.',
             'D5@bell . . . . . . . Eb5 . . . . . . .', '.', 'A4@bell . . . . . . . G#4 . . . . . . .', '.']
    mods = retarget(bells, 'bell', 'mod', 18)
    lead = [
        '.',
        'D5@ghost . . . . . . . . . . . A5 . . .',
        'Bb5 . . . . . . . A5 . . . . . . .',
        'F5 . . . . . . . E5+308 . . . . . . .',
        'Eb5+304 . . . . . . . D5 . . . . . - .',
        'A4 . . . . . . . D5 . . . F5 . . .',
        'E5 . . . . . . . Eb5+306 . . . . . . .',
        'D5 . . . C#5 . . . D5 . . . - . . .',
    ]
    echo = delayed(lead, 3, 'ghost', 'echo')
    drones = ['D3@drone+G1201 . . . . . . . . . . . . . . .', 'D3 . . . . . . . . . . . . . . .',
              'D3+G12FF . . . . . . . . . . . . . . .', 'Eb3 . . . . . . . . . . . . . . .',
              'D3+G1202 . . . . . . . . . . . . . . .', 'D3 . . . . . . . . . . . . . . .',
              'Eb3+G12FE . . . . . . . . . . . . . . .', 'C#3 . . . . . . . D3 . . . . . . .']
    drips = ['. . . . . #45@drip . . . . . . . . . .', '. . . . . . . . . . #43@drip . . . . .',
             '. . . . . . . . . . . . . #44@drip . .', '. . . #45@drip . . . . . . . . . . . .',
             '. . . . . . . . . #42@drip . . . . . .', '. . . . . . #45@drip . . . . . . . . .',
             '. . . . . . . . . . . . . #43@drip . .', '. . . . . #44@drip . . . . . . . . . .']
    for i in range(8):
        boom = 'C3@boom . . . . . . . . . . . . . . .' if i in (2, 5, 7) else '.'
        s.bar([mods[i], bells[i], drones[i], lead[i], echo[i], drips[i], boom])
    return s


# ─── 7. Neon Acid: acid house ─────────────────────────────────────────────

def neon_acid():
    """A minor, 128 BPM, format 2 (6 voices).
    Techniques: the 303 line -- a saw through a screaming resonant low-pass
    whose cutoff each note sweeps down through its instrument's table (a
    cutoff command on every row), accents that start it higher and louder,
    slides by portamento between notes; a four-on-the-floor 808 kick
    sample, clap and rim samples, an open noise hat on the off-beats; PWM
    stabs arriving with the second section, the two in opposite PWM
    directions."""
    s = Song('Neon Acid', groove=(7, 7), loop=1, version=2, voices=6,
             filter=dict(cutoff=80, resonance=13, mode=1))
    env = s.table('squelch', [dict(fx=(0x10, c)) for c in (150, 130, 112, 98, 88, 80, 74, 70)])
    acc = s.table('accent', [dict(fx=(0x10, c)) for c in (210, 185, 160, 138, 120, 104, 92, 84)])
    s.voice('saw', 'acid', volume=11, envPace=0, filter=True, table=env)
    s.voice('saw', 'accent', volume=14, envPace=0, filter=True, table=acc)
    sample_voice(s, KIT['kick'], 'k808', volume=15)
    sample_voice(s, KIT['clap'], 'c808', volume=11)
    sample_voice(s, KIT['rim'], 'r808', volume=9)
    s.voice('noise', 'ohat', volume=7, envPace=2, duty=1)
    s.voice('pulse', 'stab', volume=9, width=64, pwm=5, envPace=2)
    s.voice('pulse', 'stab2', volume=5, width=160, pwm=-4, envPace=2)
    four = 'C5@k808 . . . C5 . . . C5 . . . C5 . . .'
    four_fill = 'C5@k808 . . . C5 . . . C5 . . . C5 . C5 C5'
    claps = '. . . . C5@c808 . . . . . . C5@r808 C5@c808 . . .'
    claps2 = '. . . . C5@c808 . . C5@r808 . . C5@r808 . C5@c808 . C5@r808 .'
    hats = '. . #42@ohat . . . #42 . . . #42 . . . #42 .'
    acid = [
        'A2@accent . A2@acid A3 . A2 C3+303 . A2@accent . E3@acid . G3 . A3@accent+303 .',
        'A2@acid . A2 G3@accent+303 . A2@acid . C3 A2@accent . A3@acid+302 . E3 . D3 .',
        'F2@accent . F2@acid F3 . F2 A2+303 . F2@accent . C3@acid . Eb3 . F3@accent+303 .',
        'G2@acid . G2 G3@accent+303 . G2@acid . B2 G2@accent . D3@acid+302 . E3 . G3 .',
    ]
    stabs = ['. . A4@stab+037 . . . . . . . A4 . . . . .', '. . A4@stab+037 . . . . . . . G4+047 . . . . .',
             '. . F4@stab+047 . . . . . . . F4 . . . . .', '. . G4@stab+047 . . . . . . . E4+047 . . . . .']
    stabs2 = [transpose_text(retarget([t], 'stab', 'stab2')[0], 12) for t in stabs]
    s.bar([acid[0], four, '.', '.', '.', '.'])
    for i in range(8):
        s.bar([acid[i % 4], four_fill if i % 4 == 3 else four, claps2 if i % 4 == 3 else claps, hats, '.', '.'])
    for i in range(8):
        s.bar([acid[i % 4], four_fill if i % 4 == 3 else four, claps2 if i % 2 else claps, hats,
               stabs[i % 4], stabs2[i % 4]])
    return s


# ─── 8. Victory: a fanfare that ends ──────────────────────────────────────

def victory():
    """C major, format 2 (5 voices), no loop: the song stops and
    Chiptune.onEnd fires. PWM brass in two parts moving opposite ways, a
    triangle bass, a SID snare roll into a crash."""
    s = Song('Victory', groove=(5, 5), loop=None, version=2, voices=5)
    s.voice('pulse', 'brass', volume=13, width=110, pwm=4, envPace=0, vibSpeed=5, vibDepth=2, vibDelay=16)
    s.voice('pulse', 'brass2', volume=9, width=70, pwm=-3, envPace=0, vibSpeed=5, vibDepth=2, vibDelay=16)
    s.voice('triangle', 'bass', volume=12, envPace=0)
    sid_snare(s)
    sid_kick(s)
    s.voice('noise', 'crash', volume=11, envPace=6)
    kit = dict(s='A3@ssnare', k='D4@skick', c='#38@crash')
    s.bar(['G4@brass . G4 . G4 . C5 . . . . . . . . .', 'E4@brass2 . E4 . E4 . G4 . . . . . . . . .',
           'C3@bass . C3 . C3 . C3 . . . . . . . . .', drums('s . s . s . k . . . . . k . s s', kit),
           drums('. . . . . . c . . . . . . . . .', kit)])
    s.bar(['E5 . . . D5 . . . E5 . . . G5 . . .', 'C5 . . . B4 . . . C5 . . . D5 . . .',
           'A2 . . . G2 . . . C3 . . . G2 . . .', drums('k . . . s . . . k . . . s s s s', kit), '.'])
    s.bar(['C6 . . . . . . . . . . . . . . .', 'E5+047 . . . . . . . . . . . . . . .',
           'C2 . . . . . . . . . . . . . . .', drums('k . . . . . . . . . . . . . . .', kit),
           drums('c . . . . . . . . . . . . . . .', kit)])
    s.bar(['. . . . . . . . - . . . . . . .', '. . . . . . . . - . . . . . . .',
           '. . . . . . . . - . . . . . . .', '.', '.'])
    return s


# ─── 9. Fade Out: game over, on a real Game Boy ───────────────────────────

def fade_out():
    """A minor, format 1, no loop: a slow line falling over a chromatic
    bass, and its sigh on PU2 -- the same line, quieter, two rows late."""
    s = Song('Fade Out', groove=(9, 9), loop=None)
    s.inst('pulse', 'sad', duty=1, volume=11, envPace=0, vibSpeed=3, vibDepth=3, vibDelay=10)
    s.inst('pulse', 'sigh', duty=1, volume=4, envPace=0, vibSpeed=3, vibDepth=3, vibDelay=10)
    tri = s.wave(WAVES['triangle']())
    s.inst('wave', 'bass', duty=tri, volume=3)
    line = ['E5@sad . . . D5 . . . C5 . . . B4 . . .', 'C5 . . . B4 . . . A4 . . . G#4 . . .',
            'A4 . . . . . . . . . . . . . . .', '. . . . . . . . - . . . . . . .']
    echo = delayed(line, 2, 'sad', 'sigh')
    bass = ['A3@bass . . . . . . . G#3 . . . . . . .', 'G3 . . . . . . . F3 . . . . . . .',
            'E3 . . . . . . . A2 . . . . . . .', '. . . . . . . . - . . . . . . .']
    for i in range(4):
        s.bar([line[i], echo[i], bass[i], '.'])
    return s


SONGS = {
    'cloud_garden': cloud_garden,
    'tidal_twang': tidal_twang,
    'jungle_pulse': jungle_pulse,
    'crimson_clash': crimson_clash,
    'willow_lane': willow_lane,
    'hollow_deep': hollow_deep,
    'neon_acid': neon_acid,
    'victory': victory,
    'fade_out': fade_out,
}


# ─── the SFX library ──────────────────────────────────────────────────────

def sfx_library():
    """38 effects in one format-2 bank, on voices 6 and 7: a song of up to 6
    voices -- and every Game Boy song -- keeps all of its own. Priorities: 1
    interface, 2 gameplay, 3 events, 4 the big ones; a stronger effect takes
    a slot from a weaker one. Voice 7 carries the interface, voice 6 the
    game, so a menu blip never cuts a gameplay sound.

    Techniques: the SID trick for impacts (noise, then a falling tone, in
    one table); a triangle sub-drop woven into the explosions' noise frame
    by frame; PWM on the sustained tones; a saw laser; a wave-synth
    shimmer; the hardware-style sweep; retrigger for the fuse."""
    s = Song('SFX', rows=16, version=2, voices=8)
    UI, GAME = 7, 6
    s.voice('pulse', 'blip', volume=9, width=64, envPace=1, length=4)
    s.voice('pulse', 'ping', volume=11, width=64, envPace=1)
    s.voice('pulse', 'ding', volume=12, width=128, envPace=2)
    s.voice('pulse', 'sq', volume=11, width=128, pwm=8, envPace=0)
    s.voice('pulse', 'buzz', volume=12, width=24, envPace=0)
    s.voice('pulse', 'jump', volume=11, width=100, envPace=1)
    s.voice('pulse', 'hurt', volume=13, width=64, envPace=1)
    zap = s.table('zap', [dict(fx=(0x2, 0x30))] + [{} for _ in range(8)] + [dict(fx=(0xA, 1))])
    s.voice('saw', 'zap', volume=12, envPace=1, table=zap)
    s.voice('pulse', 'charge', volume=10, width=40, pwm=6, envPace=0, vibSpeed=8, vibDepth=2)
    s.voice('pulse', 'warp', volume=11, width=32, pwm=10, envPace=0, vibSpeed=10, vibDepth=4)
    s.voice('pulse', 'alarm', volume=12, width=64, envPace=0)
    s.voice('triangle', 'boing', volume=14, envPace=2)
    s.voice('pulse', 'sweep', volume=13, width=128, envPace=2, sweep=0x2E)
    # A low noise starts silent (its LFSR needs 15 steps): the low sounds
    # trigger high and fall by table, without a restart.
    fall_short = s.table('fall short', [dict(transpose=-i) for i in range(0, 13, 2)])
    s.voice('noise', 'thud', volume=11, envPace=1, table=fall_short)
    s.voice('noise', 'tick', volume=6, envPace=1)
    crack = s.table('crack', [dict(osc='noise', transpose=12), dict(osc='pulse', fx=(0x2, 0x50)), {}, {},
                              dict(osc='noise', transpose=4), {}, dict(fx=(0xA, 1))])
    s.voice('pulse', 'crack', volume=14, width=128, envPace=1, table=crack)
    boom = s.table('boom', [dict(osc='noise', transpose=-i) if i % 2 == 0 else dict(osc='triangle', transpose=-24 - i)
                            for i in range(24)])
    s.voice('noise', 'boom', volume=15, envPace=5, table=boom, tableSpeed=1)
    boom2 = s.table('boom2', [dict(osc='noise', transpose=-i) if i % 2 == 0 else dict(osc='triangle', transpose=-24 - i)
                              for i in range(14)])
    s.voice('noise', 'boom2', volume=14, envPace=3, table=boom2)
    s.voice('noise', 'pew', volume=12, envPace=1, duty=1)
    s.voice('noise', 'creak', volume=9, envPace=2, duty=1)
    s.voice('noise', 'whoosh', volume=9, envPace=2)
    s.voice('noise', 'splash', volume=11, envPace=3)
    s.voice('noise', 'fuse', volume=7, envPace=1, duty=1)
    sine = s.wave(WAVES['sine']())
    s.voice('wave', 'bell', volume=13, envPace=3, duty=sine)
    shimmer = synth(s, 'shimmer', 'wah', volume=12, speed=1)
    s.s['instruments'][shimmer]['envPace'] = 3
    fx = [
        # interface (voice 7, priority 1)
        ('cursor', 'E6@blip . . -', UI, 1, 1),
        ('select', 'E5@ping A5 E6 . . -', UI, 1, 3),
        ('back', 'A5@ping E5 . . -', UI, 1, 3),
        ('error', 'C3@buzz . - C3 . . -', UI, 2, 4),
        ('pause', 'E6@ping C6 E6 C6 . . -', UI, 1, 3),
        ('text', 'G5@blip . -', UI, 1, 1),
        ('toggle', 'C6@blip G6 -', UI, 1, 2),
        ('score', 'C7@blip -', UI, 1, 1),
        # movement
        ('jump', 'C4@jump+110 . . . . . . . . . . -', GAME, 2, 1),
        ('double_jump', 'G4@jump+120 . . . . . . -', GAME, 2, 1),
        ('land', '#24@thud . . . . . . -', GAME, 2, 1),
        ('step', '#30@tick . -', GAME, 1, 1),
        ('dash', '#44@whoosh #42 #40 #38 #36 #34 #32 -', GAME, 2, 1),
        ('bounce', 'C4@boing+118 . . . . . G4+218 . . . . . -', GAME, 2, 1),
        ('splash', '#38@splash #36 #40 #34 #30 . . -', GAME, 2, 2),
        # combat
        ('hit', 'A3@crack . . . . . . -', GAME, 3, 1),
        ('hurt', 'A5@hurt+220 . F5 . . . -', GAME, 3, 2),
        ('laser', 'C7@zap . . . . . . . . . -', GAME, 2, 1),
        ('shoot', '#40@pew #36 #32 #28 -', GAME, 2, 1),
        ('explosion', '#28@boom . . . . . . . . . . . . . . . . . . . . -', GAME, 4, 2),
        ('small_boom', '#30@boom2 . . . . . . . . . . -', GAME, 3, 1),
        ('fuse', '#40@fuse+902 . . . . . . . . . . . . . . . . . . -', GAME, 2, 1),
        ('sweep_shot', 'C6@sweep . . . . . . . -', GAME, 2, 2),
        ('death', 'B4@hurt+204 . . F4 . . D4 . . B3 . . . . -', GAME, 4, 3),
        # rewards
        ('coin', 'B5@ding E6 . . . . . -', GAME, 2, 4),
        ('pickup', 'G5@ping B5 D6 G6 . -', GAME, 2, 3),
        ('powerup', 'C5@sq+047 E5 G5 C6 E6 G6 C7 . . -', GAME, 3, 2),
        ('oneup', 'E6@ping G6 E7 C7 D7 G7 . -', GAME, 3, 4),
        ('chest', 'C5@sq G5 C6 E6 G6 C7+047 . . . . -', GAME, 3, 2),
        ('heal', 'C5@bell E5 G5 C6 . . . . . . -', GAME, 2, 3),
        ('key', 'E6@bell B6 . . . . . . -', GAME, 2, 4),
        ('magic', 'C6@shimmer+047 . . . . . . . . . . . -', GAME, 2, 2),
        ('win', 'C5@ping E5 G5 C6 . G5 C6 . . -', UI, 3, 4),
        ('lose', 'G4@hurt F#4 F4 E4 . . -', UI, 3, 5),
        # world
        ('door', '#24@creak #25 #26 #24 #23 . #24@thud . -', GAME, 2, 3),
        ('charge', 'C4@charge+104 . . . . . . . . . . . . . . . . . . . . . . . -', GAME, 2, 2),
        ('warp', 'C4@warp+0C7 E4 G4 C5 E5 G5 C6 E6 G6 C7 . -', GAME, 3, 2),
        ('alarm', 'A5@alarm E5 A5 E5 A5 E5 -', GAME, 3, 6),
    ]
    for name, text, ch, prio, speed in fx:
        s.sfx(name, text, ch, prio, speed)
    s.s['orders'] = []
    return s
