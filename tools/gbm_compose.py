"""Writing GBM songs as code.

The notation and the instrument recipes are gameboy-lab's (shared/gbm/ts:
text.ts, drums.ts, synth.ts, kit.ts), ported so songs can be written here
without that toolchain. A Song builds a .gbm.json project -- the format the
GBM tracker opens -- and gbm_format.encode_song turns it into a blob.

Pattern text: one token per row, separated by spaces.
    .            empty row
    -            note off
    C4 C#4 Db4   a note (C1 is note 0)
    #26          a raw note number (noise shapes: 0 dark .. 45 bright)
    @lead @3     instrument, by name or index
    +047 +4 32   a command: hex digit, then two hex digits
Suffixes combine: `A3@bass+037`. A command alone: `.+F01`.

Commands (the hex digit): 0 arpeggio, 1/2 slide up/down, 3 portamento,
4 vibrato, 5 envelope/volume, 6 duty/wave, 7 delay, 8 pan, 9 retrigger,
A cut, B jump, C sweep, D break, E sync marker, F groove.
"""
import math
import re

from gbm_format import WAVES, new_instrument, NOTE_OFF, FX

PC = dict(C=0, D=2, E=4, F=5, G=7, A=9, B=11)
NOTE_NAMES = ['C-', 'C#', 'D-', 'D#', 'E-', 'F-', 'F#', 'G-', 'G#', 'A-', 'A#', 'B-']


def parse_note(s):
    if s.startswith('#'):
        return int(s[1:])
    m = re.fullmatch(r'([A-G])([#b]?)(-?\d)', s)
    if not m:
        raise ValueError(f'Not a note: {s}')
    return (int(m[3]) - 1) * 12 + PC[m[1]] + (1 if m[2] == '#' else -1 if m[2] == 'b' else 0)


def parse_cell(token, song=None):
    m = re.fullmatch(r'([^@+]*)(?:@([\w-]+))?((?:\+[0-9A-Fa-f]{3})*)', token)
    if not m:
        raise ValueError(f'Bad cell: {token}')
    note, inst, fx = m[1], m[2], m[3]
    cell = {}
    if note in ('-', '='):
        cell['note'] = NOTE_OFF
    elif note and note != '.':
        cell['note'] = parse_note(note)
    if inst is not None:
        if inst.isdigit():
            i = int(inst)
        else:
            names = [x['name'] for x in song['instruments']] if song else []
            if inst not in names:
                raise ValueError(f'No instrument {inst}')
            i = names.index(inst)
        cell['inst'] = i
    if fx:
        cell['fx'] = [dict(cmd=int(f[0], 16), val=int(f[1:], 16)) for f in fx[1:].split('+')]
    return cell


def parse_pattern(text, rows, song=None):
    tokens = text.split()
    if len(tokens) > rows:
        raise ValueError(f'{len(tokens)} rows, the pattern has {rows}: {text}')
    cells = [parse_cell(t, song) for t in tokens]
    cells += [{} for _ in range(rows - len(cells))]
    return cells


# ─── a song under construction ────────────────────────────────────────────

class Song:
    def __init__(self, name, groove=(6, 6), rows=16, loop=0):
        self.s = dict(format='gbm-song', version=1, name=name, rows=rows, loop=loop,
                      grooves=[list(groove)], instruments=[], tables=[], waves=[],
                      patterns=[], orders=[], sfx=[])

    # -- parts
    def inst(self, kind, name, **o):
        """An instrument; options as in the tracker: volume, envDir (+1/-1),
        envPace (0 hold .. 7 slowest), duty (pulse 0-3 / wave index / noise
        1 = metallic), length (auto-cut, frames), table, tableSpeed,
        vibSpeed, vibDepth, vibDelay, sweep (raw NR10), sample."""
        i = dict(new_instrument(kind, name))
        i.update(o)
        self.s['instruments'].append(i)
        return len(self.s['instruments']) - 1

    def table(self, name, rows, loop=None):
        """Rows are dicts of transpose, env, duty, pitch, fx=(cmd, val)."""
        out = []
        for r in rows:
            row = dict(transpose=0, env=None, duty=None, pitch=0, fx=None)
            row.update(r)
            if isinstance(row['fx'], tuple):
                row['fx'] = dict(cmd=row['fx'][0], val=row['fx'][1])
            out.append(row)
        self.s['tables'].append(dict(name=name, loop=loop, rows=out))
        return len(self.s['tables']) - 1

    def wave(self, samples):
        self.s['waves'].append(list(samples))
        return len(self.s['waves']) - 1

    def groove(self, steps):
        self.s['grooves'].append(list(steps))
        return len(self.s['grooves']) - 1

    # -- music
    def pattern(self, text, rows=None):
        cells = parse_pattern(text, rows or self.s['rows'], self.s)
        key = repr(cells)
        for i, p in enumerate(self.s['patterns']):
            if repr(p['cells']) == key and not any(x['pattern'] == i for x in self.s['sfx']):
                return i
        self.s['patterns'].append(dict(cells=cells))
        return len(self.s['patterns']) - 1

    def bar(self, lanes, tr=(0, 0, 0, 0)):
        """An order row from four pattern texts (PU1, PU2, WAV, NOI);
        identical patterns are shared."""
        pat = [self.pattern(t) for t in lanes]
        self.s['orders'].append(dict(pat=pat, tr=list(tr)))
        return len(self.s['orders']) - 1

    def sfx(self, name, text, channel, priority=2, speed=2):
        """An effect: a pattern of its own length that plays on `channel`
        (0 PU1, 1 PU2, 2 WAV, 3 NOI), `speed` frames a row. The stream
        ends where the text does."""
        tokens = text.split()
        cells = parse_pattern(text, len(tokens), self.s)
        self.s['patterns'].append(dict(cells=cells))
        self.s['sfx'].append(dict(name=name, pattern=len(self.s['patterns']) - 1,
                                  channel=channel, priority=priority, speed=speed))
        return len(self.s['sfx']) - 1

    def project(self):
        return self.s


def note_name(n):
    return NOTE_NAMES[n % 12].replace('-', '') + str(n // 12 + 1)


def transpose_text(text, semis):
    """Shifts every named note in a pattern text by `semis` semitones."""
    def shift(m):
        return note_name(parse_note(m[0]) + semis)
    return re.sub(r'(?<![#\w])[A-G][#b]?-?\d(?![\w])', shift, text)


# ─── drums (drums.ts) ─────────────────────────────────────────────────────

def noise_kick(song, name='kick', volume=15):
    """The shape falls fast (LSDj SF0 SF0 SE0), the envelope snaps. Play at #26-30."""
    t = song.table(f'{name} drop', [dict(transpose=x) for x in (0, -5, -10, -14, -18, -22, -26)])
    return song.inst('noise', name, volume=volume, envPace=1, table=t)


def noise_snare(song, name='snare', volume=13):
    """A bright crack settling on a body shape. Play at #30-36."""
    t = song.table(f'{name} crack', [dict(transpose=9), dict(transpose=4), dict(transpose=1), dict(transpose=0)])
    return song.inst('noise', name, volume=volume, envPace=2, table=t)


def noise_hat(song, open_=False, metallic=False, name=None, volume=None):
    """Closed (short) or open; 7-bit mode for a metallic edge. Play at #40-45."""
    return song.inst('noise', name or ('ohat' if open_ else 'hat'), volume=volume or (9 if open_ else 8),
                     envPace=3 if open_ else 1, duty=1 if metallic else 0)


def noise_crash(song, name='crash'):
    return song.inst('noise', name, volume=12, envPace=6)


def pulse_kick(song, drop=0xE0, frames=6, name='pkick'):
    """nitro2k01's P-command kick: start near C6, drop the period hard every
    frame, cut before it wraps into a low buzz. Play at C6."""
    rows = [dict(fx=(FX['SLIDE_DOWN'], drop))] + [{} for _ in range(1, frames)] + [dict(fx=(FX['CUT'], 1))]
    t = song.table(f'{name} drop', rows)
    return song.inst('pulse', name, duty=2, volume=15, envPace=1, table=t)


def sweep_kick(song, shift=3, name='skick'):
    """PU1 only: the hardware sweep does the drop. Play around C6."""
    return song.inst('pulse', name, duty=2, volume=15, envPace=1, sweep=0x18 | (shift & 7), length=8)


def wave_kick(song, drop=0xC0, frames=5, name='wkick'):
    """A triangle sliding down fast, cut short (the LSDj manual's best kick).
    Takes CH3. Play at C5-C6."""
    w = song.wave(WAVES['triangle']())
    rows = [dict(fx=(FX['SLIDE_DOWN'], drop))] + [{} for _ in range(1, frames)] + [dict(fx=(FX['CUT'], 1))]
    t = song.table(f'{name} drop', rows)
    return song.inst('wave', name, duty=w, volume=3, table=t)


# ─── the wave synth (synth.ts) ────────────────────────────────────────────

def _at(r, t, d):
    if r is None:
        return d
    if isinstance(r, (int, float)):
        return r
    return r[0] + (r[1] - r[0]) * t


def _osc(shape, x, width):
    if shape == 'saw':
        return 1 - 2 * x
    if shape == 'square':
        return 1 if x < width else -1
    if shape == 'triangle':
        return 4 * x - 1 if x < 0.5 else 3 - 4 * x
    return math.sin(2 * math.pi * x)


def synth_waves(shape='saw', width=None, filter='none', cutoff=None, resonance=None, volume=None,
                phase=None, drive=None, distortion='clip', frames=16):
    """A run of 32-sample waves, every parameter moving from its first value
    to its second across the run (LSDj's synth)."""
    n, raw = 256, []
    for k in range(frames):
        t = k / (frames - 1) if frames > 1 else 0
        w = _at(width, t, 0.5)
        cut = max(0.01, min(1, _at(cutoff, t, 1)))
        res = min(0.97, _at(resonance, t, 0))
        ph = min(0.95, _at(phase, t, 0))
        vol = _at(volume, t, 1)
        drv = _at(drive, t, 1)
        period = []
        for i in range(n):
            x = i / n
            y = min(1, x / (1 - ph)) if ph > 0 else x
            period.append(_osc(shape, y % 1, w))
        out = period
        if filter != 'none':
            f = 2 * math.sin(math.pi * min(0.45, cut * 16 / n))
            q = 2 * (1 - res)
            low = band = 0.0
            last = []
            for rep in range(8):
                for i in range(n):
                    high = period[i] - low - q * band
                    band += f * high
                    low += f * band
                    if rep == 7:
                        last.append(low if filter == 'lowpass' else high if filter == 'highpass' else band)
            out = last
        wv = []
        for j in range(32):
            v = sum(out[j * n // 32 + i] for i in range(n // 32)) / (n // 32) * drv
            v = ((v + 1) % 2 + 2) % 2 - 1 if distortion == 'wrap' else max(-1, min(1, v))
            wv.append(v * vol)
        raw.append(wv)
    peak = max(1e-9, max(abs(v) for w in raw for v in w))
    return [[max(0, min(15, int(math.floor(7.5 + v / peak * 7.5 + 0.5)))) for v in w] for w in raw]


SYNTHS = dict(
    pluckBass=(dict(shape='saw', filter='lowpass', cutoff=(0.9, 0.18), resonance=(0.55, 0.3)), 'once', 2),
    pwmBass=(dict(shape='square', width=(0.5, 0.1), filter='lowpass', cutoff=0.6), 'pingpong', 3),
    wah=(dict(shape='saw', filter='bandpass', cutoff=(0.15, 0.8), resonance=0.8), 'pingpong', 2),
    growl=(dict(shape='sine', phase=(0, 0.85), drive=(1, 2.5)), 'once', 2),
    # Added here: a soft, breathing pad (a sine opening into a triangle-ish
    # shape and back) and a reese-like detuned growl for jungle basses.
    breath=(dict(shape='triangle', filter='lowpass', cutoff=(0.25, 0.7), resonance=0.2), 'pingpong', 4),
    reese=(dict(shape='saw', filter='lowpass', cutoff=(0.35, 0.6), resonance=(0.2, 0.6), phase=(0, 0.3)), 'pingpong', 2),
)


def synth(song, name, preset=None, mode=None, speed=None, volume=3, **params):
    """Adds a synth: its waves, a table stepping through them, and a wave
    instrument playing it. A preset from SYNTHS, or params of synth_waves."""
    if preset:
        p, m, s = SYNTHS[preset]
        params = {**p, **params}
        mode = mode or m
        speed = speed or s
    waves = synth_waves(**params)
    first = len(song.s['waves'])
    song.s['waves'] += waves
    order = list(range(len(waves)))
    if mode == 'pingpong':
        order = order + order[1:-1][::-1]
    t = song.table(f'{name} sweep', [dict(duty=first + i) for i in order], loop=None if (mode or 'once') == 'once' else 0)
    return song.inst('wave', name, duty=first, volume=volume, table=t, tableSpeed=max(0, (speed or 1) - 1))


# ─── drum samples (kit.ts) ────────────────────────────────────────────────

SAMPLE_RATE = 8192


def to4bit(x, gain=1.0, dither=True, seed=1):
    peak = max(1e-9, max(abs(v) for v in x))
    s = seed

    def rnd():
        # In doubles, as the original's JavaScript does: the product passes
        # 2^53 and rounds, and that rounding is part of the sequence.
        nonlocal s
        s = int(float(s) * 1103515245.0 + 12345.0) & 0x7fffffff
        return s / 0x7fffffff
    out = []
    for v in x:
        d = (rnd() - rnd()) * 0.5 if dither else 0
        out.append(max(0, min(15, int(math.floor(7.5 + v / peak * gain * 7.5 + d + 0.5)))))
    return out


def _render(seconds, f):
    n = round(seconds * SAMPLE_RATE)
    return [f(i / SAMPLE_RATE, i) for i in range(n)]


def _noise(seed):
    s = seed

    def nxt():
        nonlocal s
        s = (s * 1664525 + 1013904223) & 0xFFFFFFFF
        return s / 2 ** 31 - 1
    return nxt


def synth_kit():
    """An 808-flavoured kit, synthesised: kick, snare, rim, hat, clap."""
    ph = [0.0]

    def kick(t, i):
        f = 48 + 112 * math.exp(-t * 38)
        ph[0] += 2 * math.pi * f / SAMPLE_RATE
        return math.sin(ph[0]) * math.exp(-t * 16) + (0.6 * (1 - t / 0.004) if t < 0.004 else 0)
    n1, n2, n3 = _noise(7), _noise(3), _noise(11)
    snare = lambda t, i: ((math.sin(2 * math.pi * 185 * t) + 0.6 * math.sin(2 * math.pi * 330 * t)) * math.exp(-t * 30) * 0.5
                          + n1() * math.exp(-t * 22) * 0.8)
    rim = lambda t, i: (math.sin(2 * math.pi * 1700 * t) + 0.5 * math.sin(2 * math.pi * 820 * t)) * math.exp(-t * 110)
    prev = [0.0]

    def hat(t, i):
        v = n2()
        y = v - prev[0]
        prev[0] = v
        return y * math.exp(-t * 80)
    clap = lambda t, i: n3() * (math.exp(-((t % 0.01) * 400)) if t < 0.03 else math.exp(-(t - 0.03) * 30) * 0.7)
    return [dict(name='kick', data=to4bit(_render(0.15, kick))),
            dict(name='snare', data=to4bit(_render(0.14, snare), gain=0.95)),
            dict(name='rim', data=to4bit(_render(0.04, rim))),
            dict(name='hat', data=to4bit(_render(0.05, hat), gain=0.8)),
            dict(name='clap', data=to4bit(_render(0.12, clap)))]


def sample_inst(song, sample, name, volume=0, noise_volume=None, **o):
    """A noise instrument whose hit plays a drum sample on CH3. volume 0
    leaves the sample alone; otherwise a noise layer sounds with it."""
    samples = song.s.setdefault('samples', [])
    names = [x['name'] for x in samples]
    if sample['name'] not in names:
        samples.append(sample)
        names.append(sample['name'])
    return song.inst('noise', name, volume=volume if noise_volume is None else noise_volume,
                     envPace=o.pop('envPace', 1), sample=names.index(sample['name']), **o)
