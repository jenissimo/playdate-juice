#!/usr/bin/env python3
"""The jungle kit: every sample the jungle songs play, synthesised here from
nothing -- no recordings, no third-party audio -- and written to
chiptune/samples/ as 8-bit mono WAVs (loop points and root notes in their
`smpl` chunks). The songs read the WAVs, so building them needs no numpy;
this script does (scipy only makes it faster).

    python tools/jungle_kit.py          writes chiptune/samples/*.wav

The breaks are played, not programmed: a kit (modal drum heads, a beater,
snare wires, metallic hats) recorded into a small room, through a bus
compressor and tape-ish saturation, with a drummer's timing -- ghost notes
late, hats swung -- then cut to the tracker's grid: one bar, a 16th every
2048 frames, so FT2's sample offset (9xx, 256 frames) finds every 16th at
a multiple of 8. At 23211 Hz that grid is 170 BPM; a song sets the rate
that matches its own tempo, which is how a tracker musician pitched a
break to fit.

For the small speaker, everything that has to carry is built of mid-range:
the kick's beater and knock, the snare's body, a reese with its fundamental
turned down (its weight is in the 2nd-6th harmonics), pads high-passed
above 160 Hz. The 60-250 Hz band is left to the game's engine.
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gbm_compose import save_wav  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'chiptune', 'samples')

try:
    from scipy.signal import lfilter as _lfilter
except ImportError:          # the slow way, the same result
    _lfilter = None


def lfilter(b, a, x):
    if _lfilter is not None:
        return _lfilter(b, a, x)
    y = np.zeros_like(x)
    b0, b1, b2 = b
    _, a1, a2 = a
    x1 = x2 = y1 = y2 = 0.0
    for i, v in enumerate(x):
        o = b0 * v + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, v, y1, o
        y[i] = o
    return y


def biquad(x, kind, f0, sr, q=0.707, gain_db=0.0):
    """RBJ's cookbook filters."""
    w = 2 * math.pi * min(f0, sr * 0.49) / sr
    cw, sw = math.cos(w), math.sin(w)
    al = sw / (2 * q)
    A = 10 ** (gain_db / 40)
    if kind == 'lp':
        b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]; a = [1 + al, -2 * cw, 1 - al]
    elif kind == 'hp':
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]; a = [1 + al, -2 * cw, 1 - al]
    elif kind == 'bp':
        b = [al, 0, -al]; a = [1 + al, -2 * cw, 1 - al]
    elif kind == 'peak':
        b = [1 + al * A, -2 * cw, 1 - al * A]; a = [1 + al / A, -2 * cw, 1 - al / A]
    elif kind == 'lowshelf':
        s = 2 * math.sqrt(A) * al
        b = [A * ((A + 1) - (A - 1) * cw + s), 2 * A * ((A - 1) - (A + 1) * cw), A * ((A + 1) - (A - 1) * cw - s)]
        a = [(A + 1) + (A - 1) * cw + s, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - s]
    elif kind == 'highshelf':
        s = 2 * math.sqrt(A) * al
        b = [A * ((A + 1) + (A - 1) * cw + s), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - s)]
        a = [(A + 1) - (A - 1) * cw + s, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - s]
    else:
        raise ValueError(kind)
    b = np.array(b) / a[0]
    a = np.array(a) / a[0]
    return lfilter(b, a, np.asarray(x, dtype=float))


def fft_convolve(x, h):
    n = len(x) + len(h) - 1
    m = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(h, m), m)[:n]


def decimate(x, factor, cutoff=0.45):
    """Down by an integer factor through a windowed-sinc low-pass at
    `cutoff` of the new rate: linear phase, so a transient stays one."""
    taps = 64 * factor + 1
    n = np.arange(taps) - (taps - 1) / 2
    fc = cutoff / factor
    h = 2 * fc * np.sinc(2 * fc * n) * np.blackman(taps)
    h /= h.sum()
    y = np.convolve(x, h)[(taps - 1) // 2:][:len(x)]
    return y[::factor]


def to_int8(x, peak=0.985):
    """Normalised to `peak` and rounded: 8 bits, no dither -- the grit of a
    90s tracker sample is part of the sound."""
    x = np.asarray(x, dtype=float)
    x = x / max(1e-9, np.max(np.abs(x))) * peak * 127.0
    return np.clip(np.round(x), -128, 127).astype(int)


def compress(x, sr, threshold=0.3, ratio=3.0, attack=0.001, release=0.08):
    """A feed-forward peak compressor: what glues a break's hits and room."""
    env = np.abs(x)
    ka, kr = math.exp(-1 / (attack * sr)), math.exp(-1 / (release * sr))
    e, out = 0.0, np.empty_like(env)
    for i, v in enumerate(env):
        e = ka * e + (1 - ka) * v if v > e else kr * e + (1 - kr) * v
        out[i] = e
    gain = np.where(out > threshold, (np.maximum(out, 1e-9) / threshold) ** (1 / ratio - 1), 1.0)
    return x * gain


def room(rng, sr, length=0.5, rt60=0.35, bright=6000.0, early=True):
    """A small room's impulse response: a few early reflections, then a
    diffuse tail darkening as it decays."""
    n = int(length * sr)
    t = np.arange(n) / sr
    tail = rng.standard_normal(n) * np.exp(-6.9 * t / rt60)
    tail = biquad(tail, 'lp', bright, sr, 0.6)
    tail[:int(0.008 * sr)] = 0
    h = tail / math.sqrt(np.sum(tail ** 2))
    if early:
        for d, g in ((0.0047, 0.5), (0.0083, -0.38), (0.0121, 0.3), (0.0169, -0.24), (0.0226, 0.2)):
            h[int(d * sr)] += g
    return h


# ─── the drum kit ──────────────────────────────────────────────────────────

def env_ad(t, attack, decay):
    return (1 - np.exp(-t / max(attack, 1e-6))) * np.exp(-t / decay)


def kick(rng, sr, vel=1.0, tune=1.0, decay=0.075, length=0.4):
    """A kick a small speaker can place: the head's pitch falling from ~280
    Hz to ~52, short; a felt beater's click at 2-4 kHz; the shell's knock
    at ~300 and ~520 Hz; driven into soft clipping, whose odd harmonics of
    the body (150-260 Hz and up) are what a little speaker plays."""
    n = int(length * sr)
    t = np.arange(n) / sr
    f = tune * (52 + 120 * np.exp(-t / 0.022) + 110 * np.exp(-t / 0.004))
    body = np.sin(2 * np.pi * np.cumsum(f) / sr) * (0.6 * np.exp(-t / decay) + 0.4 * np.exp(-t / 0.02))
    body *= 1 - np.exp(-t / 0.0004)
    click = biquad(rng.standard_normal(n), 'bp', 2800 * tune, sr, 0.7) * np.exp(-t / 0.003)
    click += 0.7 * np.sin(2 * np.pi * 1750 * tune * t) * np.exp(-t / 0.005)
    knock = 0.5 * np.sin(2 * np.pi * 300 * tune * t + 0.4) * env_ad(t, 0.0005, 0.04)
    knock += 0.25 * np.sin(2 * np.pi * 520 * tune * t) * env_ad(t, 0.0005, 0.02)
    y = body + (0.45 + 0.3 * vel) * click + knock
    return np.tanh(2.2 * y) / 1.1 * vel


def snare(rng, sr, vel=1.0, pitch=192.0, snappy=1.0, tail=0.11, length=0.45):
    """Modal head (its partials, the first bending down as the head
    settles), wires (band-passed noise, darker for a soft stroke) and the
    stick's crack."""
    n = int(length * sr)
    t = np.arange(n) / sr
    bend = 1 + 0.07 * np.exp(-t / 0.01)
    head = np.zeros(n)
    for r, a, d in ((1.0, 1.0, 0.075), (1.593, 0.55, 0.05), (2.135, 0.42, 0.04), (2.296, 0.3, 0.035),
                    (2.653, 0.24, 0.03), (3.155, 0.16, 0.025)):
        head += a * np.sin(2 * np.pi * np.cumsum(pitch * r * bend) / sr + rng.uniform(0, 6.28)) * np.exp(-t / d)
    head *= 1 - np.exp(-t / 0.0003)
    wires = biquad(rng.standard_normal(n), 'hp', 1400, sr, 0.7)
    wires = biquad(wires, 'lp', 3500 + 6000 * vel, sr, 0.7)
    wires = biquad(wires, 'peak', 5200, sr, 1.0, 3.0)
    wire_env = (1 - np.exp(-t / 0.0007)) * (0.85 * np.exp(-t / 0.04) + 0.15 * np.exp(-t / tail))
    crack = biquad(rng.standard_normal(n), 'hp', 2500, sr) * np.exp(-t / 0.0012)
    y = (0.5 + 0.5 * vel) * 0.65 * head + snappy * (0.45 + 0.7 * vel) * wires * wire_env + 0.7 * vel * crack
    return np.tanh(1.4 * y) / 1.1 * vel


def metal(rng, sr, n, scale=1.9):
    """The 808's six detuned squares, scaled: a metallic bed for hats."""
    t = np.arange(n) / sr
    return sum(np.sign(np.sin(2 * np.pi * f * scale * t + rng.uniform(0, 6.28)))
               for f in (205.3, 304.4, 369.6, 522.7, 540.0, 800.0)) / 6


def hat(rng, sr, vel=1.0, open_=False, length=None):
    length = length or (0.45 if open_ else 0.12)
    n = int(length * sr)
    t = np.arange(n) / sr
    m = biquad(biquad(metal(rng, sr, n), 'bp', 8200, sr, 1.1), 'hp', 6000, sr)
    nz = biquad(biquad(rng.standard_normal(n), 'hp', 7000, sr), 'lp', 11000, sr)
    e = env_ad(t, 0.0004, 0.24 if open_ else 0.019)
    return (0.8 * m + 0.55 * nz) * e * vel * (0.9 if open_ else 1.0)


def tambourine(rng, sr, vel=1.0, length=0.14):
    """Jingles: noise through a few narrow resonances, a shaken envelope."""
    n = int(length * sr)
    t = np.arange(n) / sr
    x = rng.standard_normal(n)
    y = sum(biquad(x, 'bp', f, sr, 9.0) * g for f, g in ((6300, 1.0), (7700, 0.8), (9200, 0.7), (10600, 0.5)))
    y += 0.3 * biquad(x, 'hp', 8000, sr)
    return y * env_ad(t, 0.002, 0.035) * vel


def cymbal(rng, sr, length=1.2, lo=2600.0, hi=7400.0, decay=0.42, partials=70):
    """A crash: a cloud of inharmonic partials, each ringing its own time,
    over hiss; a stick transient on top."""
    n = int(length * sr)
    t = np.arange(n) / sr
    y = np.zeros(n)
    for f in np.exp(rng.uniform(math.log(lo), math.log(hi), partials)):
        d = decay * rng.uniform(0.6, 1.4) * (3000 / f) ** 0.3
        y += rng.uniform(0.3, 1.0) * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) * np.exp(-t / d)
    y /= math.sqrt(partials)
    hiss = biquad(biquad(rng.standard_normal(n), 'hp', 3500, sr), 'lp', hi * 1.05, sr)
    y += 0.9 * hiss * np.exp(-t / (decay * 0.8))
    y += 1.2 * biquad(rng.standard_normal(n), 'hp', 1500, sr) * np.exp(-t / 0.004)
    return y * (1 - np.exp(-t / 0.0008))


# ─── the breaks ────────────────────────────────────────────────────────────

GRID = 2048                    # frames a 16th, in the file
BREAK_RATE = 23211             # 170 BPM: 2048 x 170 x 4 / 60
OS = 4                         # synthesised at 4x, decimated


def play_break(seed, hits, kit, drive=1.25, room_mix=0.16, rt60=0.3, comp=(0.4, 2.5)):
    """One bar. `hits` are (16th, piece, velocity, ms late); a closed or
    pedal hat chokes an open one, as a drummer's foot does."""
    rng = np.random.default_rng(seed)
    sr = BREAK_RATE * OS
    n = 16 * GRID * OS
    dry = np.zeros(n + sr)
    step = GRID * OS
    open_end = None
    for pos, piece, vel, late in sorted(hits, key=lambda h: h[0] * 100 + h[3]):
        at = pos * step + int(late * 1e-3 * sr)
        vel *= rng.uniform(0.94, 1.04)
        if piece in ('h', 'o') and open_end is not None and open_end[0] < at:
            s0, lenw = open_end
            dry[at:at + int(0.012 * sr)] *= np.linspace(1, 0.15, int(0.012 * sr))
            open_end = None
        x = kit[piece](rng, sr, vel)
        dry[at:at + len(x)] += x[:len(dry) - at]
        if piece == 'o':
            open_end = (at, len(x))
    wet = fft_convolve(dry, room(rng, sr, rt60=rt60))[:len(dry)]
    mix = dry + room_mix * wet / max(1e-9, np.max(np.abs(wet))) * np.max(np.abs(dry))
    # the bus: glue, then tape: soft saturation; a lift where the speaker is
    mix = compress(mix / np.max(np.abs(mix)), sr, *comp, release=0.05)
    mix = np.tanh(drive * mix / np.max(np.abs(mix))) / math.tanh(drive)
    mix = biquad(mix, 'lowshelf', 90, sr, 0.7, -3.0)
    mix = biquad(mix, 'peak', 2600, sr, 0.8, 2.5)
    y = decimate(mix, OS)[:16 * GRID]
    # the bar's last frames fade, so a chop that runs into them ends clean
    y[-256:] *= np.linspace(1, 0, 256)
    return to_int8(y)


def break_a():
    """Funky, open: kick on 1 and a soft 1-e-and, snares on 2 and 4 with
    ghosts behind them, the classic kick-kick on 3-and, swung 16th hats,
    an open hat on the 4-and. Slices (16ths): 0 kick, 2 soft kick, 4 snare,
    7 and 9 ghosts, 8 hat alone, 10 and 11 kicks, 12 snare, 14 open hat,
    15 ghost."""
    kit = dict(k=lambda r, s, v: kick(r, s, v), s=lambda r, s, v: snare(r, s, v),
               g=lambda r, s, v: snare(r, s, v, snappy=0.8), h=lambda r, s, v: hat(r, s, v),
               o=lambda r, s, v: hat(r, s, v, open_=True))
    hits = [(0, 'k', 1.0, 0), (2, 'k', 0.55, 2), (10, 'k', 0.95, 0), (11, 'k', 0.62, 3),
            (4, 's', 1.0, 1.5), (12, 's', 0.96, 1.5),
            (7, 'g', 0.30, 7), (9, 'g', 0.26, 9), (15, 'g', 0.33, 6), (13, 'g', 0.18, 8)]
    for i in range(16):
        if i == 14:
            hits.append((14, 'o', 0.62, 1))
        elif i % 2 == 0:
            hits.append((i, 'h', 0.75 if i % 4 == 0 else 0.58, 0.5))
        else:
            hits.append((i, 'h', 0.30 if i != 15 else 0.4, 7.5))      # the swing
    return play_break(1701, hits, kit)


def break_b():
    """Tight and hard, for racing: a higher, cracking snare, a shorter kick
    (1, the 2-and, 3), tambourine in 16ths over closed 8th hats, fewer
    ghosts, more compression and drive. Slices: 0 kick, 4 snare, 6 kick,
    9 ghost, 10 kick, 12 snare, 14 hat and ghost."""
    kit = dict(k=lambda r, s, v: kick(r, s, v, tune=1.12, decay=0.055),
               s=lambda r, s, v: snare(r, s, v, pitch=232, snappy=1.25, tail=0.09),
               g=lambda r, s, v: snare(r, s, v, pitch=232, snappy=0.9, tail=0.07),
               h=lambda r, s, v: hat(r, s, v), t=lambda r, s, v: tambourine(r, s, v))
    hits = [(0, 'k', 1.0, 0), (6, 'k', 0.85, 1), (10, 'k', 0.95, 0), (15, 'k', 0.5, 2),
            (4, 's', 1.0, 1), (12, 's', 1.0, 1), (9, 'g', 0.34, 6), (14, 'g', 0.3, 7), (7, 'g', 0.22, 8)]
    for i in range(16):
        hits.append((i, 't', 0.75 if i % 4 == 2 else 0.45, 0 if i % 2 == 0 else 4))
        if i % 2 == 0:
            hits.append((i, 'h', 0.7 if i % 4 == 0 else 0.5, 0))
    return play_break(2202, hits, kit, drive=1.6, room_mix=0.12, rt60=0.24, comp=(0.3, 3.5))


# ─── tonal samples ─────────────────────────────────────────────────────────

C2 = 65.40639
C3, C4 = 2 * C2, 4 * C2


def reese(rate=11025, cycles=96):
    """Three saws, the outer two a cycle more and a cycle less over the
    loop (about +-18 cents, a slow swirl as they beat), built in the
    frequency domain over exactly one loop: it is periodic by construction,
    distortion included, so the loop has no seam. The fundamental is turned
    down (a 2-pole high-pass at 150 Hz), the top rolled off above ~2 kHz:
    a growl in the mid-range, which the vox filter then sweeps."""
    rng = np.random.default_rng(36)
    L = round(rate * cycles / C2)
    f0 = rate / L                            # Hz a bin
    os_ = 8
    N = L * os_
    X = np.zeros(N // 2 + 1, dtype=complex)
    for c, g in ((cycles - 1, 0.9), (cycles, 1.0), (cycles + 1, 0.9)):
        h = np.arange(1, (N // 2) // c + 1)
        f = h * c * f0
        amp = g / h * (f / 150) ** 2 / (1 + (f / 150) ** 2) / (1 + (f / 2100) ** 2)
        X[h * c] += amp * np.exp(1j * rng.uniform(0, 2 * np.pi, len(h)))
    x = np.fft.irfft(X, N)
    x = np.tanh(2.2 * x / np.max(np.abs(x)))
    Y = np.fft.rfft(x)[:L // 2 + 1]
    Y[int(L // 2 * 0.92):] = 0              # band-limited to the file's rate
    y = np.fft.irfft(Y, L)
    return to_int8(y, 0.97), rate, (0, L)


def detuned_saws(sr, n, freqs, cents=(-9, -3, 4, 10), rng=None, amps=None):
    t = np.arange(n) / sr
    y = np.zeros(n)
    for i, f in enumerate(freqs):
        a = 1.0 if amps is None else amps[i]
        for c in cents:
            ff = f * 2 ** (c / 1200)
            ph = rng.uniform(0, 1)
            y += a * (2 * ((ff * t + ph) % 1.0) - 1)
    return y


def crossfade_loop(x, start, length, fade):
    """A loop [start, start+length) whose last `fade` frames blend into the
    audio before its start: the frame after the loop's end is then the one
    after start - 1, and the seam is gone."""
    y = x[:start + length].copy()
    w = np.linspace(0, 1, fade) ** 0.5
    a = start + length - fade
    y[a:] = (1 - w) * x[a:start + length] + w * x[start - fade:start]
    return y


def even_out(x, sr, start, window=0.15, most=2.5):
    """A sustain held level: after `start`, divided by its own slow RMS, so
    detuned saws drifting in and out of phase do not swell once a loop."""
    w = max(1, int(window * sr))
    e = np.sqrt(np.convolve(x ** 2, np.ones(w) / w, 'same'))
    a = int(start * sr)
    ref = np.mean(e[a:]) if a < len(x) else 1.0
    g = np.clip(ref / np.maximum(e, 1e-9), 1 / most, most)
    fade = np.clip((np.arange(len(x)) - a) / (0.1 * sr), 0, 1)
    return x * (1 + (g - 1) * fade)


def chorus(x, sr, taps=((0.012, 0.0025, 0.31), (0.018, 0.003, 0.23))):
    n = np.arange(len(x))
    y = x.copy()
    for base, depth, hz in taps:
        d = (base + depth * np.sin(2 * np.pi * hz * n / sr)) * sr
        y += 0.7 * np.interp(n - d, n, x, left=0.0)
    return y


def pad(rate=8820):
    """An airy chord to play in parallel: root, fifth, ninth, twelfth and
    octave (no third, so it sits under minor and major alike), four
    detuned saws a note, through a low-pass breathing slowly, chorus and a
    long room; high-passed above 160 Hz. Root C3; loops after its swell."""
    rng = np.random.default_rng(48)
    os_ = 4
    sr = rate * os_
    total = 2.9
    n = int(total * sr)
    t = np.arange(n) / sr
    notes = [C3, C3 * 2 ** (7 / 12), C4 * 2 ** (2 / 12), C4 * 2 ** (7 / 12), 2 * C4]
    x = detuned_saws(sr, n, notes, rng=rng, amps=[0.9, 0.8, 0.7, 0.55, 0.45])
    # a slow low-pass: a state-variable filter, its cutoff breathing
    fc = 1500 * (1 + 0.25 * np.sin(2 * np.pi * 0.35 * t))
    f = 2 * np.sin(np.pi * fc / sr)
    low = band = 0.0
    y = np.empty(n)
    for i in range(n):
        low += f[i] * band
        high = x[i] - low - 0.9 * band
        band += f[i] * high
        y[i] = low
    y = biquad(biquad(y, 'hp', 160, sr, 0.7), 'hp', 160, sr, 0.7)
    y = chorus(y, sr)
    wet = fft_convolve(y, room(rng, sr, length=2.0, rt60=1.6, bright=4000, early=False))[:n]
    y = y + 0.5 * wet / np.max(np.abs(wet)) * np.max(np.abs(y))
    y = even_out(y, sr, 0.3)
    y *= np.minimum(1, t / 0.22) ** 2          # the swell
    y = decimate(y, os_)
    start, length = int(0.62 * rate), int(1.5 * rate)
    y = crossfade_loop(y, start, length, int(0.45 * rate))
    return to_int8(y, 0.95), rate, (start, length)


def stab(rate=16000):
    """The rave stab: a minor seventh (C4 E-flat G B-flat, and C3 under)
    of detuned saws and a square, a resonant low-pass snapping shut, a
    short room. Root C4."""
    rng = np.random.default_rng(60)
    os_ = 4
    sr = rate * os_
    n = int(0.42 * sr)
    t = np.arange(n) / sr
    notes = [C3, C4, C4 * 2 ** (3 / 12), C4 * 2 ** (7 / 12), C4 * 2 ** (10 / 12)]
    x = detuned_saws(sr, n, notes, cents=(-7, 0, 8), rng=rng, amps=[0.7, 1, 0.85, 0.85, 0.7])
    x += 0.5 * np.sign(np.sin(2 * np.pi * C4 * t))
    fc = 900 + 6500 * np.exp(-t / 0.07)
    f = 2 * np.sin(np.pi * np.minimum(fc, sr / 6) / sr)
    low = band = 0.0
    y = np.empty(n)
    for i in range(n):
        low += f[i] * band
        high = x[i] - low - 0.45 * band
        band += f[i] * high
        y[i] = low
    y = biquad(y, 'hp', 140, sr)
    y *= (1 - np.exp(-t / 0.002)) * np.exp(-t / 0.2)
    wet = fft_convolve(y, room(rng, sr, length=0.5, rt60=0.4))[:n]
    y = y + 0.25 * wet / np.max(np.abs(wet)) * np.max(np.abs(y))
    y *= np.minimum(1, (0.42 - t) / 0.03)       # the end, faded
    return to_int8(decimate(y, os_)), rate, None


def crash(rate=16000):
    """A crash, ~1 s. Played backwards (+G1B01) it is the swell before a drop."""
    rng = np.random.default_rng(49)
    os_ = 4
    sr = rate * os_
    y = cymbal(rng, sr, length=1.05, hi=min(7400.0, rate * 0.46))
    t = np.arange(len(y)) / sr
    y *= np.minimum(1, (1.05 - t) / 0.25)
    return to_int8(decimate(y, os_)), rate, None


def hoover(rate=11025):
    """The hoover: three detuned pulse-saws (a saw less a delayed copy of
    itself, the delay swept: PWM) swooping up into the note from a fifth
    below, chorused; the sustain loops. Root C3."""
    rng = np.random.default_rng(55)
    os_ = 4
    sr = rate * os_
    total = 1.35
    n = int(total * sr)
    t = np.arange(n) / sr
    swoop = 2 ** ((-7 * np.exp(-t / 0.045) + 0.35 * np.exp(-t / 0.12) * np.sin(2 * np.pi * 7 * t)) / 12)
    y = np.zeros(n)
    for c, lfo in ((-14, 0.9), (0, 1.3), (13, 1.7)):
        f = C3 * 2 ** (c / 1200) * swoop
        ph = np.cumsum(f) / sr + rng.uniform(0, 1)
        saw = 2 * (ph % 1.0) - 1
        width = 0.5 + 0.35 * np.sin(2 * np.pi * lfo * t + rng.uniform(0, 6))
        saw2 = 2 * ((ph + width) % 1.0) - 1
        y += saw - 0.8 * saw2
        y += 0.5 * (2 * ((ph * 0.5) % 1.0) - 1)       # a saw an octave down
    y = biquad(y, 'lp', 3800, sr, 0.8)
    y = biquad(y, 'hp', 110, sr)
    y = chorus(y, sr)
    y = np.tanh(1.4 * y / np.max(np.abs(y)))
    y = even_out(y, sr, 0.2)
    y *= np.minimum(1, t / 0.01)
    y = decimate(y, os_)
    start, length = int(0.42 * rate), int(0.75 * rate)
    y = crossfade_loop(y, start, length, int(0.3 * rate))
    return to_int8(y, 0.95), rate, (start, length)


SAMPLES = {
    # name: (builder, root note -- None for a break or a drum)
    'break_a': (lambda: (break_a(), BREAK_RATE, None), None),
    'break_b': (lambda: (break_b(), BREAK_RATE, None), None),
    'reese': (reese, C2),
    'pad': (pad, C3),
    'stab': (stab, C4),
    'crash': (crash, None),
    'hoover': (hoover, C3),
}


def main(names=None):
    os.makedirs(OUT, exist_ok=True)
    total = 0
    for name, (build, root) in SAMPLES.items():
        if names and name not in names:
            continue
        pcm, rate, loop = build()
        pcm = list(pcm)
        save_wav(os.path.join(OUT, name + '.wav'), pcm, rate, root=root, loop=loop)
        total += len(pcm)
        print(f'  {name}.wav: {len(pcm)} frames at {rate} Hz ({len(pcm) / rate:.2f} s)' +
              (f', loop {loop[0]}+{loop[1]}' if loop else ''))
    print(f'  {total} bytes of samples')


if __name__ == '__main__':
    main(sys.argv[1:])
