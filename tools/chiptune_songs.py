"""The demo songs and the SFX library, written as code.

    python tools/chiptune.py songs      # -> chiptune/music/*.gbm

Each song is a style and a set of chiptune techniques; the docstrings say
which. Three are format 1 -- four Game Boy channels, exactly what a DMG
would play -- and the rest format 2, with more voices, oscillators per
instrument, PWM, sync, ring modulation and a filter.

Mixed for the speaker as well as for headphones: a speaker the size of the
Playdate's plays little below a few hundred Hz, so every part that has to
carry on the device -- the bass above all, and the kick -- has harmonics
there (a saw-like wave, a pulse, a driven sample), and a pure triangle or
sine only ever doubles something (a sub for headphones).

Tempo: a row is a 16th note unless said otherwise, and a groove step is the
frames a row lasts at 59.73 frames/s: [10, 10] is 90 BPM, [7, 7] 128,
[6, 5] 163, [5, 5, 5, 6] 170, [5, 5] 179. Unequal steps swing: [11, 9]
lilts the 16ths without changing the tempo.
"""
import re

from gbm_compose import (Song, noise_snare, noise_hat, noise_crash, pulse_kick, synth, synth_kit, punch_kit,
                         sample_voice, sid_kick, sid_snare, sid_tom, bass_wave, articulation, WAVES,
                         transpose_text, parse_note, note_name)
from gbm_format import env_byte

KIT = {s['name']: s for s in synth_kit()}     # kick, snare, rim, hat, clap: 4-bit, 8192 Hz
PUNCH = {s['name']: s for s in punch_kit()}   # pkick, psnare, rim, hat, clap: for a small speaker


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


def approach(next_root, octave=2):
    """The note a bass walks in on: a semitone under the next root."""
    return note_name(parse_note(f'{next_root}{octave}') - 1)


# ─── 1. Cloud Garden: the main menu ───────────────────────────────────────

def cloud_garden():
    """D major, 90 BPM with a light swing (11-9), format 2 (6 voices).
    Techniques: a PWM pad (the width breathing on its own) holding its chord
    by arpeggio through a low-pass that opens by stages across the song --
    timed cutoff slides, each started and stopped inside a bar -- and closes
    for the loop; a flute on a triangle with an articulated attack (a small
    accent and a scoop up into the note) and delayed vibrato, its echo three
    rows behind on a thin pulse; harp-like broken chords panned left; a warm
    saw-wave bass (a triangle would all but vanish on the speaker); a shaker
    for the second half."""
    s = Song('Cloud Garden', groove=(11, 9), version=2, voices=6,
             filter=dict(cutoff=70, resonance=5, mode=1))
    art = articulation(s, 'flute', peak=13, sustain=11, scoop=6, frames=3)
    s.voice('triangle', 'flute', volume=12, envPace=0, vibSpeed=4, vibDepth=2, vibDelay=18, table=art)
    s.voice('pulse', 'echo', volume=5, width=48, envPace=0, vibSpeed=4, vibDepth=2, vibDelay=18)
    s.voice('pulse', 'harp', volume=9, width=40, envPace=2)
    s.voice('pulse', 'pad', volume=6, width=128, pwm=2, envPace=0, filter=True)
    s.voice('wave', 'bass', volume=13, envPace=6, duty=bass_wave(s))
    s.voice('noise', 'shaker', volume=5, envPace=1)
    s.voice('noise', 'shaker2', volume=7, envPace=1)
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
    pad = {'D': 'D4@pad+047', 'Bm': 'B3@pad+037', 'G': 'G3@pad+04B', 'A': 'A3@pad+057', 'F#m': 'F#3@pad+037',
           'EmA': 'E4@pad+037', 'Em': 'E4@pad+037', 'A7': 'A3@pad+047'}
    # root on one, the fifth (or the seventh) on three
    bass = {'D': ('D3', 'A2'), 'Bm': ('B2', 'F#2'), 'G': ('G2', 'D3'), 'A': ('A2', 'E2'), 'F#m': ('F#2', 'C#3'),
            'EmA': ('E2', 'A2'), 'Em': ('E2', 'B2'), 'A7': ('A2', 'G2')}
    chords = ['D', 'Bm', 'G', 'A', 'D', 'F#m', 'G', 'EmA', 'Bm', 'G', 'D', 'A', 'Bm', 'G', 'Em', 'A7']
    # The filter, by stages: (cutoff to start from or None, {row: slide}) per bar.
    moves = {0: ('+G1046', {0: '+G1201', 8: '+G1200'}),       # 70 -> ~150
             4: ('', {0: '+G1201', 6: '+G1200'}),              # -> ~210
             8: ('', {0: '+G1201', 4: '+G1200'}),              # -> ~250
             14: ('', {0: '+G12FF', 12: '+G1200'}),            # -> ~130
             15: ('', {0: '+G12FF', 8: '+G1200'})}             # -> ~50, and bar 0 resets it
    shaker = '. . #42@shaker . . . #42 . . . #42@shaker2 . . . #42@shaker #44'
    for i, c in enumerate(chords):
        start, slides = moves.get(i, ('', {}))
        first = pad[c] + start + slides.get(0, '')
        tokens = [first] + ['.'] * 15
        for r, cmd in slides.items():
            if r:
                tokens[r] = '.' + cmd
        if c == 'EmA':
            tokens[8] = 'A3+047'
        root, fifth = bass[c]
        b = f'{root}@bass . . . . . . . {fifth} . . . . . . .'
        noi = shaker if i >= 8 else ('. . . . . . . . . . . . . . #44@shaker .' if i % 2 else '.')
        s.bar([lead[i], echo[i], harp[c], ' '.join(tokens), b, noi])
    return s


# ─── 2. Tidal Twang: surf rock, on a real Game Boy ────────────────────────

def tidal_twang():
    """E, 179 BPM, format 1: four DMG channels, exactly.
    Techniques: tremolo picking by retrigger (9x2: restart every 2 frames);
    a glissando by a long slide; a twang with an articulated attack (an
    accent and a scoop, by table, then its own decay); the rhythm guitar
    and the kick drum sharing PU2 -- a pulse kick (a note near C6 dropped
    hard and cut) between chord stabs, the Game Boy's way to a kick with
    body; a pluck bass on the wave synth; noise snare with ghost notes,
    accented hats, a crash on each section."""
    s = Song('Tidal Twang', groove=(5, 5), loop=2)
    s.inst('pulse', 'trem', duty=1, volume=11, envPace=1)
    twang_art = articulation(s, 'twang', peak=13, sustain=11, scoop=8, frames=3, hold_pace=3)
    s.inst('pulse', 'twang', duty=2, volume=12, envPace=3, vibSpeed=6, vibDepth=2, vibDelay=10, table=twang_art)
    s.inst('pulse', 'chug', duty=2, volume=7, envPace=1, length=4)
    pulse_kick(s, drop=0xE0, frames=6)
    synth(s, 'bass', 'pluckBass', volume=3)
    kit = dict(s=f'#33@{s.s["instruments"][noise_snare(s)]["name"]}',
               g=f'#33@{s.s["instruments"][noise_snare(s, name="ghost", volume=6)]["name"]}',
               h=f'#43@{s.s["instruments"][noise_hat(s, volume=5)]["name"]}',
               H=f'#43@{s.s["instruments"][noise_hat(s, name="hatA", volume=9)]["name"]}',
               o=f'#41@{s.s["instruments"][noise_hat(s, open_=True)]["name"]}',
               c=f'#38@{s.s["instruments"][noise_crash(s)]["name"]}')
    beat = drums('H . h . s . h g H . h . s . h o', kit)
    beat2 = drums('H . h . s . h g H . h g s . s o', kit)
    fill = drums('H . s . s . s g H s g s s+902 . s s', kit)
    top = lambda d: drums('c', kit) + ' ' + d.split(' ', 1)[1]      # the crash on a section's first beat

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
        d = fill if i == 7 else (beat2 if i % 4 == 3 else beat)
        s.bar([m, pu2(c + '4'), bassA[c], top(d) if i == 0 else d])
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
        d = fill if i == 7 else (beat2 if i % 2 else beat)
        s.bar([m, pu2(c + '4'), walk[c], top(d) if i == 0 else d])
    return s


# ─── 3. Jungle Pulse: drum & bass ─────────────────────────────────────────

def jungle_pulse():
    """F minor, 170 BPM (a 5-5-5-6 groove), format 2 (8 voices).
    Techniques: a sampled break with dynamics -- kick, snare and ghost
    snare, accented and soft hats, rim and clap, from a kit driven for a
    small speaker, over two voices of their own -- and crescendo rolls (a
    ghost snare retriggered louder each time: 9A2); a reese bass of two
    saws detuned against each other (a constant pitch offset in one's
    table) through a resonant low-pass swinging between set bounds -- each
    bar sets its start and slides, so it never slams shut; a triangle sub
    an octave under for headphones; minor pads by arpeggio; a stab lead
    with its echo; the filter opening over the intro. The drop carries
    sync marker E01."""
    s = Song('Jungle Pulse', groove=(5, 5, 5, 6), loop=4, version=2, voices=8,
             filter=dict(cutoff=40, resonance=11, mode=1))
    s.voice('pulse', 'stab', volume=11, width=96, envPace=2, vibSpeed=5, vibDepth=2, vibDelay=6)
    s.voice('pulse', 'echo', volume=4, width=96, envPace=2)
    s.voice('pulse', 'pad', volume=5, width=32, pwm=1, envPace=0, vibSpeed=2, vibDepth=1)
    s.voice('saw', 'reese', volume=10, envPace=0, filter=True)
    detune = s.table('detune', [dict(pitch=-3)], loop=0)
    s.voice('saw', 'reese2', volume=10, envPace=0, filter=True, table=detune)
    s.voice('triangle', 'sub', volume=10, envPace=0)
    k = sample_voice(s, PUNCH['pkick'], 'kick', volume=15)
    sn = sample_voice(s, PUNCH['psnare'], 'snare', volume=14)
    gs = sample_voice(s, PUNCH['psnare'], 'ghost', volume=6)
    rim = sample_voice(s, PUNCH['rim'], 'rim', volume=9)
    clap = sample_voice(s, PUNCH['clap'], 'clap', volume=11)
    h = sample_voice(s, PUNCH['hat'], 'hat', volume=6)
    hA = sample_voice(s, PUNCH['hat'], 'hatA', volume=10)
    oh = s.voice('noise', 'ohat', volume=6, envPace=3, duty=1)
    kit = kit_of(s, [('k', 'C5', k), ('s', 'C5', sn), ('g', 'C5', gs), ('r', 'C5', rim), ('p', 'D5', clap),
                     ('h', 'C5', h), ('H', 'C5', hA), ('o', '#43', oh)])
    # kicks and snares on one voice; hats, rims and claps on the other
    brk = (drums('k . k . s . . g . g k . s . . g', kit), drums('H . h h H . h r H . h h H . o .', kit))
    brk2 = (drums('k . k . s . . g . g k . s . g+9A2 .', kit), drums('H . h h H . h r H . p . H . o .', kit))
    roll = (drums('s . g . k . g g+9A2 k s . g g+9A2 s s', kit), drums('h h h h h h h h o . o . o o o o', kit))
    thin = (drums('k . . . s . . . . . k . s . . .', kit), drums('H . . . h . . . H . . . h . o .', kit))
    hats = ('.', drums('H . h . H . h . H . h . H . o .', kit))
    pads = {'Fm': 'F4@pad+037', 'Db': 'Db4@pad+047', 'Eb': 'Eb4@pad+057', 'Cm': 'C4@pad+037'}
    bass = {'Fm': 'F3@reese . . . . . . . . . F3 . . . Ab3 .', 'Db': 'Db3@reese . . . . . . . . . . . Db3 . C3 .',
            'Eb': 'Eb3@reese . . . . . . . Eb3 . . . . . G3 .', 'Cm': 'C3@reese . . . . . . . C4 . . . Bb3 . G3 .'}
    prog = ['Fm', 'Db', 'Eb', 'Cm']
    OPEN = '+G1050+G1202'       # from 80, sliding up to ~240 over the bar
    SHUT = '+G10F0+G12FE'       # from 240 back down to ~80

    def bar(c, lead, drum, filt='', bass_on=True):
        b = bass[c].replace('@reese', '@reese' + filt, 1) if bass_on else '.'
        s.bar([lead, delayed([lead], 3, 'stab', 'echo')[0] if lead != '.' else '.',
               pads[c] + ' . . . . . . . . . . . . . . .', b,
               retarget([b], 'reese', 'reese2')[0] if bass_on else '.',
               retarget([b], 'reese', 'sub', -12)[0] if bass_on else '.', drum[0], drum[1]])
    # Intro: pads and hats; the bass arrives with the filter closed and it opens.
    bar('Fm', '.', hats, bass_on=False)
    bar('Db', '.', hats, bass_on=False)
    bar('Eb', '.', hats, '+G1028+G1201')
    bar('Cm', '.', roll)
    for i in range(8):
        bar(prog[i % 4], '.+E01' if i == 0 else '.', roll if i == 7 else (brk2 if i % 4 == 3 else brk),
            OPEN if i % 2 == 0 else SHUT)
    hook = [
        'C5@stab . . Ab4 . . Bb4 . C5 . . . Eb5 . C5 .',
        'Db5 . . C5 . . Bb4 . Ab4 . . . F4 . . .',
        'G4 . . Bb4 . . Eb5 . . . G5 . F5 . Eb5 .',
        'C5 . . . . . . . . . . . - . . .',
    ]
    for i in range(8):
        m = hook[i % 4] if i < 4 else transpose_text(hook[i % 4], 12)
        bar(prog[i % 4], m, roll if i == 7 else (brk2 if i % 2 else brk), OPEN if i % 2 == 0 else SHUT)
    for i, c in enumerate(prog):
        bar(c, '.+E02' if i == 0 else '.', roll if i == 3 else thin, '+G10A0+G12FF' if i == 0 else '')
    return s


# ─── 4. Crimson Clash: a JRPG battle ──────────────────────────────────────

def crimson_clash():
    """A minor, 163 BPM (6-5 groove), format 2 (7 voices).
    Techniques: a hard-sync lead -- a silent master (volume 0, still
    running) plays the melody while a saw an octave and more above restarts
    on each of its cycles; the saw's own pitch sweeps up through a table
    and settles back, with an accent on the attack, so every note tears
    open at the master's pitch and then calms; SID drums (a frame of noise,
    then a falling triangle; a tone, then noise; a pulse tom); broken
    chords in 16ths, then in 8ths an octave up for the bridge; a sawtooth
    octave bass that walks into each chord a semitone under; PWM brass
    stabs on a 3+3+2 accent; soft and accented hats."""
    s = Song('Crimson Clash', groove=(6, 5), loop=2, version=2, voices=7)
    s.voice('pulse', 'master', volume=0, envDir=1, envPace=0, width=128)
    ups = [12, 14, 16, 18, 20, 22, 24, 26, 28, 27, 25, 23, 22, 21, 20, 19]
    rows = [dict(transpose=t) for t in ups]
    rows[0]['env'] = env_byte(14, -1, 1)          # the accent
    rows[4]['env'] = env_byte(12, -1, 0)          # the sustain
    sweep = s.table('sync sweep', rows)
    s.voice('saw', 'sync', volume=12, envPace=0, sync=True, table=sweep, vibSpeed=5, vibDepth=2, vibDelay=16)
    s.voice('pulse', 'arp', volume=6, width=48, envPace=1)
    s.voice('pulse', 'arp8', volume=7, width=80, envPace=2)
    s.voice('saw', 'bass', volume=10, envPace=1)
    sid_kick(s)
    sid_snare(s)
    sid_tom(s)
    s.voice('noise', 'hat', volume=4, envPace=1, duty=1)
    s.voice('noise', 'hatA', volume=8, envPace=1, duty=1)
    s.voice('noise', 'crash', volume=9, envPace=6)
    s.voice('pulse', 'brass', volume=10, width=100, pwm=6, envPace=2)
    kit = dict(k='D4@skick', s='A3@ssnare', t='E4@stom', u='B3@stom', h='#43@hat', H='#43@hatA', c='#38@crash')
    beat = (drums('k . . k s . . k . k . . s . . .', kit), drums('H . h . H . h . H . h . H . h h', kit))
    beat2 = (drums('k . . k s . . k . k . k s . s s', kit), drums('H . h . H . h . H . h . H h H h', kit))
    fill = (drums('s . s s t . t t u . u u s s s s', kit), drums('c . . . . . . . . . . . . . . .', kit))
    intro = (drums('k . . . k . . . k . . . s s s s', kit), drums('c . . . . . . . . . . . . . . .', kit))
    riff = 'A4@master A4 A5 A4 G5 A4 F5 A4 E5 A4 D5 A4 E5 . G#5 .'
    arp16 = lambda a, b, c: ' '.join([f'{a}@arp', b, c, b] + [a, b, c, b] * 3)
    arp8 = lambda a, b, c: ' '.join(f'{x} .' for x in [f'{a}@arp8', b, c, b, a, c, b, c])
    tones = dict(Am=('A4', 'C5', 'E5'), F=('F4', 'A4', 'C5'), G=('G4', 'B4', 'D5'), E=('E4', 'G#4', 'B4'),
                 Dm=('D4', 'F4', 'A4'), Bdim=('B3', 'D4', 'F4'))
    roots = dict(Am='A', F='F', G='G', E='E', Dm='D', Bdim='B')
    brass = {'Am': ('A4', '037'), 'F': ('F4', '047'), 'G': ('G4', '047'), 'E': ('E4', '047'),
             'Dm': ('D4', '037'), 'Bdim': ('B3', '036')}

    def bass_line(chord, next_chord):
        r = roots[chord]
        return ' '.join([f'{r}2@bass', '.', f'{r}3', '.'] * 3 + [f'{r}2', '.', approach(roots[next_chord]), '.'])

    def bar(melody, chord, next_chord, drum, stabs=True, bridge=False):
        slave = retarget([melody], 'master', 'sync')[0]
        root, fx = brass[chord]
        st = f'{root}@brass+{fx} . . . . . {root} . . . {root} . . . . .' if stabs else '.'
        a = arp8(*[transpose_text(n, 12) for n in tones[chord]]) if bridge else arp16(*tones[chord])
        s.bar([melody, slave, a, bass_line(chord, next_chord), drum[0], drum[1], st])
    bar(riff, 'Am', 'Am', intro, False)
    bar(riff, 'Am', 'Am', fill, False)
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
    chA = ['Am', 'F', 'G', 'E'] * 2
    for i, m in enumerate(leadA):
        bar(m, chA[i], chA[i + 1] if i < 7 else 'Dm', fill if i == 7 else (beat2 if i % 4 == 3 else beat))
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
    chB = ['Dm', 'Am', 'F', 'E', 'Dm', 'Am', 'Bdim', 'E']
    for i, m in enumerate(leadB):
        bar(m, chB[i], chB[i + 1] if i < 7 else 'Am', fill if i == 7 else (beat2 if i % 2 else beat), bridge=True)
    return s


# ─── 5. Willow Lane: a village waltz, on a real Game Boy ──────────────────

def willow_lane():
    """G major in 3/4 (12-row bars), 112 BPM, format 1.
    Techniques: pulse-width movement the Game Boy way -- a table stepping
    the lead's duty 25% -> 50% -> 25% as each note plays, with a scoop up
    into the note on its first rows; delayed vibrato; oom-pa-pa chords by
    arpeggio with an auto-cut; a bass on a warm saw wave (the DMG's
    triangle is mostly fundamental, too little for a small speaker) walking
    between chord tones; a borrowed C minor; a countermelody on PU2 that
    answers the lead's long notes in the second half."""
    s = Song('Willow Lane', groove=(8, 8), rows=12)
    breathe = s.table('breathe', [dict(duty=1, pitch=-6), dict(duty=1, pitch=-3), dict(duty=2), dict(duty=2),
                                  dict(duty=2), dict(duty=1)], loop=2)
    s.inst('pulse', 'flute', duty=1, volume=11, envPace=0, vibSpeed=3, vibDepth=2, vibDelay=14,
           table=breathe, tableSpeed=3)
    s.inst('pulse', 'pa', duty=1, volume=7, envPace=1, length=8)
    s.inst('pulse', 'answer', duty=2, volume=7, envPace=3)
    s.inst('wave', 'bass', duty=bass_wave(s), volume=3)
    s.inst('noise', 'brush', volume=5, envPace=1)
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
    """D phrygian, 100 BPM, format 2 (7 voices), sixteen bars.
    Techniques: a ring-modulated bell -- a triangle multiplied by a silent
    square an octave and a tritone above it, so its partials are the sum
    and difference of two unrelated pitches: metal, not a music box; a
    growling wave drone through a resonant band-pass whose centre drifts up
    and back, each drift timed inside a bar; a ghostly thin pulse sliding by
    portamento, its echo three rows behind; the snare sample played two
    octaves down as a distant rumble (a sample follows the note); dripping
    water; a phrygian cadence, Bb falling to A, for the second half."""
    s = Song('Hollow Deep', groove=(9, 9), version=2, voices=7, filter=dict(cutoff=60, resonance=12, mode=2))
    s.voice('pulse', 'mod', volume=0, envDir=1, envPace=0, width=128)
    s.voice('triangle', 'bell', volume=13, envPace=5, ring=True)
    drone = synth(s, 'drone', 'growl', mode='pingpong', speed=6, volume=10)
    s.s['instruments'][drone]['filter'] = True
    art = articulation(s, 'ghost', peak=11, sustain=9, scoop=3, frames=4)
    s.voice('pulse', 'ghost', volume=9, width=24, envPace=0, vibSpeed=2, vibDepth=3, vibDelay=20, table=art)
    s.voice('pulse', 'echo', volume=3, width=24, envPace=0, vibSpeed=2, vibDepth=3, vibDelay=20)
    s.voice('noise', 'drip', volume=6, envPace=1)
    sample_voice(s, PUNCH['psnare'], 'rumble', volume=15, envPace=4)
    bells = ['D5@bell . . . . . . . . . . . . . . .', '.', 'A4@bell . . . . . . . . . . . . . . .', '.',
             'Bb4@bell . . . . . . . A4 . . . . . . .', '.', 'A4@bell . . . . . . . G#4 . . . . . . .', '.',
             'F5@bell . . . . . . . . . . . . . . .', '.', 'Bb4@bell . . . . . . . A4 . . . . . . .', '.',
             'D5@bell . . . . . . . . . . . . . . .', 'Eb5@bell . . . . . . . . . . . . . . .',
             'A4@bell . . . . . . . Bb4 . . . A4 . . .', '.']
    mods = retarget(bells, 'bell', 'mod', 18)
    lead = [
        '.',
        'D5@ghost . . . . . . . . . . . A5 . . .',
        'Bb5 . . . . . . . A5 . . . . . . .',
        'F5 . . . . . . . Eb5+308 . . . . . . .',
        'D5+304 . . . . . . . . . . . . . - .',
        'A4 . . . . . . . D5 . . . F5 . . .',
        'F5 . . . . . . . Eb5+306 . . . . . . .',
        'D5 . . . C#5 . . . D5 . . . - . . .',
        'F5 . . . . . . . D5+306 . . . . . . .',
        'D5 . . . . . . . C5 . . . Bb4 . . .',
        'Bb4 . . . . . . . A4+304 . . . . . . .',
        'D5 . . . . . . . - . . . . . . .',
        'F5 . . . E5 . . . F5 . . . G5 . . .',
        'F5 . . . . . . . Bb5+305 . . . . . . .',
        'A5 . . . G5 . . . F5 . . . E5 . . .',
        'D5 . . . . . . . . . . . - . . .',
    ]
    echo = delayed(lead, 3, 'ghost', 'echo')
    roots = ['D3', 'D3', 'D3', 'Eb3', 'D3', 'D3', 'Eb3', 'C#3',
             'Bb2', 'Bb2', 'A2', 'A2', 'D3', 'Bb2', 'A2', 'D3']
    # the band-pass drifts up in some bars and back in others, each move
    # started from a set point and stopped inside its bar
    moves = {0: '+G103C+G1201', 2: '+G10B4+G12FF', 4: '+G103C+G1201', 6: '+G10B4+G12FF',
             8: '+G1050+G1201', 10: '+G10C8+G12FF', 12: '+G103C+G1201', 14: '+G10B4+G12FF'}
    drips = ['. . . . . #45@drip . . . . . . . . . .', '. . . . . . . . . . #43@drip . . . . .',
             '. . . . . . . . . . . . . #44@drip . .', '. . . #45@drip . . . . . . . . . . . .',
             '. . . . . . . . . #42@drip . . . . . .', '. . . . . . #45@drip . . . . . . . . .',
             '. . . . . . . . . . . . . #43@drip . .', '. . . . . #44@drip . . . . . . . . . .']
    for i in range(16):
        tokens = [f'{roots[i]}@drone' + moves.get(i, '')] + ['.'] * 15
        if i in moves:
            tokens[12] = '.+G1200'
        if i == 7:
            tokens[8] = 'D3'
        rumble = 'C3@rumble . . . . . . . . . . . . . . .' if i in (2, 5, 7, 10, 13, 15) else '.'
        s.bar([mods[i], bells[i], ' '.join(tokens), lead[i], echo[i], drips[i % 8], rumble])
    return s


# ─── 7. Neon Acid: acid house ─────────────────────────────────────────────

def neon_acid():
    """A minor, 128 BPM with a house swing (8-6), format 2 (6 voices).
    Techniques: the 303 line -- a saw through a screaming resonant
    low-pass whose cutoff each note sweeps down through its instrument's
    table (a cutoff command on every row), accents that start it higher
    and louder, and slides by portamento fast enough to be 303 slides (a
    slide does not restart the note, so the filter keeps falling through
    it); the build -- closed tables for the first section, open ones and
    more resonance for the second, with a two-bar break where the kick
    drops out and a clap roll brings it back; a four-on-the-floor kick
    sample driven for a small speaker, clap and rim samples, open hats on
    the off-beats over soft closed 16ths; PWM stabs moving in opposite
    directions."""
    s = Song('Neon Acid', groove=(8, 6), loop=1, version=2, voices=6,
             filter=dict(cutoff=80, resonance=12, mode=1))
    tables = {
        'acid': (150, 130, 112, 98, 88, 80, 74, 70), 'accent': (210, 185, 160, 138, 120, 104, 92, 84),
        'acid_o': (200, 178, 158, 142, 128, 118, 110, 104), 'accent_o': (250, 232, 210, 188, 168, 150, 136, 124),
    }
    for name, cuts in tables.items():
        t = s.table(f'{name} env', [dict(fx=(0x10, c)) for c in cuts])
        s.voice('saw', name, volume=13 if 'accent' in name else 11, envPace=0, filter=True, table=t)
    sample_voice(s, PUNCH['pkick'], 'kick', volume=15)
    sample_voice(s, PUNCH['clap'], 'clap', volume=14)
    sample_voice(s, PUNCH['rim'], 'rim', volume=11)
    s.voice('noise', 'ohat', volume=5, envPace=2, duty=1)
    s.voice('noise', 'chat', volume=3, envPace=1, duty=1)
    s.voice('pulse', 'stab', volume=9, width=64, pwm=5, envPace=2)
    s.voice('pulse', 'stab2', volume=5, width=160, pwm=-4, envPace=2)
    four = 'C5@kick . . . C5 . . . C5 . . . C5 . . .'
    four_fill = 'C5@kick . . . C5 . . . C5 . . . C5 . C5 C5'
    claps = '. . . . C5@clap . . . . . . C5@rim C5@clap . . .'
    claps2 = '. . . . C5@clap . . C5@rim . . C5@rim . C5@clap . C5@rim .'
    clap_roll = '. . . . C5@clap . . . C5 . C5 . C5 C5 C5 C5'
    hats = '#44@chat . #42@ohat #44@chat #44 . #42@ohat #44@chat #44 . #42@ohat #44@chat #44 . #42@ohat #44@chat'
    # 3xx speeds sized to each jump (period units a frame): 303 slides take
    # ~3-6 frames whatever the interval.
    lineA = [
        'A2@accent . A2@acid A3 . A2 C3+330 . A2@accent . E3@acid . G3 . A3@accent+330 .',
        'A2@acid . A2 G3@accent+360 . A2@acid . C3 A2@accent . A3@acid+360 . E3 . D3 .',
        'F2@accent . F2@acid F3 . F2 A2+360 . F2@accent . C3@acid . Eb3 . F3@accent+320 .',
        'G2@acid . G2 G3@accent+380 . G2@acid . B2 G2@accent . D3@acid+360 . E3 . G3 .',
    ]
    lineB = [
        'A3@accent_o . A2@acid_o A3 . C4+330 A3 . E3@accent_o . A2@acid_o A2 G3+360 . A3@accent_o+330 .',
        'A2@accent_o . A3@acid_o . A2 . C3@accent_o . A2@acid_o D3 . E3+330 . G3@accent_o . A3@acid_o+330',
        'F2@accent_o . F3@acid_o . F2 . A2@accent_o+360 . C3@acid_o . F3+360 . Eb3 . C3@accent_o .',
        'G2@accent_o . G3@acid_o . G2 . B2 . D3@accent_o+360 . G2@acid_o . E3@accent_o+360 . D3+330 .',
    ]
    stabs = ['. . A4@stab+037 . . . . . . . A4 . . . . .', '. . A4@stab+037 . . . . . . . G4+047 . . . . .',
             '. . F4@stab+047 . . . . . . . F4 . . . . .', '. . G4@stab+047 . . . . . . . E4+047 . . . . .']
    stabs2 = [transpose_text(retarget([t], 'stab', 'stab2')[0], 12) for t in stabs]
    s.bar([lineA[0], four, '.', '.', '.', '.'])
    for i in range(8):
        line = lineA[i % 4]
        if i == 0:      # the section's resonance: set where the loop comes back
            line = line.replace('A2@accent', 'A2@accent+G11C1', 1)
        s.bar([line, four_fill if i % 4 == 3 else four, claps2 if i % 4 == 3 else claps, hats, '.', '.'])
    # the break: no kick, the open line arriving, a clap roll
    s.bar([lineB[0].replace('A3@accent_o', 'A3@accent_o+G11E1', 1), '.', '.', hats, '.', '.'])
    s.bar([lineB[1], '.', clap_roll, hats, stabs[1], stabs2[1]])
    for i in range(8):
        s.bar([lineB[i % 4], four_fill if i % 4 == 3 else four, claps2 if i % 2 else claps, hats,
               stabs[i % 4], stabs2[i % 4]])
    return s


# ─── 8. Victory: a fanfare that ends ──────────────────────────────────────

def victory():
    """C major, format 2 (5 voices), no loop: the song stops and
    Chiptune.onEnd fires. PWM brass in two parts moving opposite ways, the
    lead with an accented attack; a pulse bass walking up to the tonic; a
    SID snare roll into a crash."""
    s = Song('Victory', groove=(5, 5), loop=None, version=2, voices=5)
    art = articulation(s, 'brass', peak=15, sustain=13, scoop=8, frames=3)
    s.voice('pulse', 'brass', volume=13, width=110, pwm=4, envPace=0, vibSpeed=5, vibDepth=2, vibDelay=16, table=art)
    s.voice('pulse', 'brass2', volume=9, width=70, pwm=-3, envPace=0, vibSpeed=5, vibDepth=2, vibDelay=16)
    s.voice('pulse', 'bass', volume=10, width=80, envPace=2)
    sid_snare(s)
    sid_kick(s)
    s.voice('noise', 'crash', volume=11, envPace=6)
    kit = dict(s='A3@ssnare', k='D4@skick', c='#38@crash')
    s.bar(['G4@brass . G4 . G4 . C5 . . . . . . . . .', 'E4@brass2 . E4 . E4 . G4 . . . . . . . . .',
           'C3@bass . C3 . C3 . C3 . . . . . . . . .', drums('s . s . s . k . . . . . k . s s', kit),
           drums('. . . . . . c . . . . . . . . .', kit)])
    s.bar(['E5 . . . D5 . . . E5 . . . G5 . . .', 'C5 . . . B4 . . . C5 . . . D5 . . .',
           'A2 . . . G2 . . . C3 . . . G2 . A2 B2', drums('k . . . s . . . k . . . s s s s', kit), '.'])
    s.bar(['C6 . . . . . . . . . . . . . . .', 'E5+047 . . . . . . . . . . . . . . .',
           'C3 . . . . . . . . . . . . . . .', drums('k . . . . . . . . . . . . . . .', kit),
           drums('c . . . . . . . . . . . . . . .', kit)])
    s.bar(['. . . . . . . . - . . . . . . .', '. . . . . . . . - . . . . . . .',
           '. . . . . . . . - . . . . . . .', '.', '.'])
    return s


# ─── 9. Fade Out: game over, on a real Game Boy ───────────────────────────

def fade_out():
    """A minor, format 1, no loop: a slow line falling over a chromatic
    bass (on a warm saw wave), and sighs on PU2 -- long, quiet chord tones
    under it: A minor, E over G#, C over G, then F minor (the line's G#
    heard as A-flat), and home. (An echo was tried here: on a stepwise
    line it only smears one step into the next.)"""
    s = Song('Fade Out', groove=(9, 9), loop=None)
    s.inst('pulse', 'sad', duty=1, volume=11, envPace=0, vibSpeed=3, vibDepth=3, vibDelay=10)
    s.inst('pulse', 'sigh', duty=2, volume=5, envPace=0, vibSpeed=3, vibDepth=2, vibDelay=20)
    s.inst('wave', 'bass', duty=bass_wave(s), volume=3)
    line = ['E5@sad . . . D5 . . . C5 . . . B4 . . .', 'C5 . . . B4 . . . A4 . . . G#4 . . .',
            'A4 . . . . . . . . . . . . . . .', '. . . . . . . . - . . . . . . .']
    echo = ['C5@sigh . . . . . . . E4 . . . . . . .', 'E4 . . . . . . . C4 . . . . . . .',
            'E4 . . . . . . . C4 . . . . . . .', '. . . . . . . . - . . . . . . .']
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
