// The studio's synthesizer: everything offline, in the manner of mid-90s tracker and console
// music -- drums with a hard attack, orchestra hits, rave stabs and hoovers, saw and FM
// basses the Playdate's small speaker hears through their harmonics, plucked strings and a
// guitar amp with its cabinet, filters, a room, echoes, compressors, a sidechain pump, a
// look-ahead limiter, loudness (BS.1770), a tracker's note and drum lines, and a Song whose
// stems fold into a seamless loop. Deterministic (seeded noise): the same code renders the same
// samples. No dependencies. (Made for Overturn, where it renders the music and every one-shot.)
'use strict';

const SR = 44100;
const TAU = 2 * Math.PI;
const hz = n => 440 * Math.pow(2, (n - 69) / 12);
const dB = d => Math.pow(10, d / 20);
const toDb = a => 20 * Math.log10(Math.max(Math.abs(a), 1e-9));
const len = s => Math.max(1, Math.round(s * SR));

// mulberry32: seeded, so a noise burst renders the same every time
function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------------------------------------------------------------- buffers

function mix(dst, src, at = 0, gain = 1) {
  const from = Math.max(0, -at), to = Math.min(src.length, dst.length - at);
  for (let j = from; j < to; j++) dst[at + j] += src[j] * gain;
  return dst;
}

function scale(x, g) { for (let j = 0; j < x.length; j++) x[j] *= g; return x; }

function peak(x) { let p = 0; for (let j = 0; j < x.length; j++) { const a = Math.abs(x[j]); if (a > p) p = a; } return p; }

// a few ms down to silence where a buffer stops: no click at its end
function fadeOut(x, s = 0.004) {
  const n = Math.min(x.length, len(s));
  for (let j = 0; j < n; j++) x[x.length - 1 - j] *= j / n;
  return x;
}

// soft saturation that keeps a full-scale peak at full scale: thickens, adds the harmonics a
// small speaker can play
function drive(x, k) {
  if (!k) return x;
  const norm = Math.tanh(k);
  for (let j = 0; j < x.length; j++) x[j] = Math.tanh(k * x[j]) / norm;
  return x;
}

// a buffer longer than the loop wraps round: the tail of the last bar sounds over the first
function fold(x, L) {
  const y = new Float32Array(L);
  for (let j = 0; j < x.length; j++) y[j % L] += x[j];
  return y;
}

// a non-linear process (compressor, pump, limiter) run on a loop as if it had always been
// looping: process two laps, keep the second, whose start is warmed by the first's end
function cyclic(fn, ...loops) {
  const L = loops[0].length;
  const twice = loops.map(x => { const y = new Float32Array(2 * L); y.set(x); y.set(x, L); return y; });
  return fn(...twice).slice(L);
}

// ---------------------------------------------------------------- filters

// Simper's trapezoidal state-variable filter: stable while its cutoff moves every sample.
// 'bp' is normalised to unity gain at the centre.
function svf() {
  let ic1 = 0, ic2 = 0;
  return (x, fc, q, mode) => {
    const g = Math.tan(Math.PI * Math.min(Math.max(fc, 10), SR * 0.47) / SR), k = 1 / q;
    const a1 = 1 / (1 + g * (g + k)), a2 = g * a1, a3 = g * a2;
    const v3 = x - ic2, v1 = a1 * ic1 + a2 * v3, v2 = ic2 + a2 * ic1 + a3 * v3;
    ic1 = 2 * v1 - ic1; ic2 = 2 * v2 - ic2;
    if (mode === 'lp') return v2;
    if (mode === 'bp') return k * v1;
    if (mode === 'hp') return x - k * v1 - v2;
    return x - k * v1;
  };
}

function filter(x, mode, fc, q = 0.707) {
  const f = svf(), y = new Float32Array(x.length);
  for (let j = 0; j < x.length; j++) y[j] = f(x[j], fc, q, mode);
  return y;
}

// ---------------------------------------------------------------- oscillators

function polyblep(t, dt) {
  if (t < dt) { t /= dt; return t + t - t * t - 1; }
  if (t > 1 - dt) { t = (t - 1) / dt; return t * t + t + t + 1; }
  return 0;
}

// one sample of a band-limited wave at phase ph (0..1), phase step dt
function wave(kind, ph, dt, pw) {
  switch (kind) {
    case 'saw': return 2 * ph - 1 - polyblep(ph, dt);
    case 'square': {
      let v = ph < pw ? 1 : -1;
      v += polyblep(ph, dt);
      v -= polyblep((ph + 1 - pw) % 1, dt);
      return v;
    }
    case 'tri': return 1 - 4 * Math.abs(ph - 0.5);
    case 'organ': // a calliope's pipe: a few harmonics, falling off
      return (Math.sin(TAU * ph) + 0.5 * Math.sin(2 * TAU * ph) + 0.22 * Math.sin(3 * TAU * ph) + 0.1 * Math.sin(4 * TAU * ph)) / 1.4;
    default: return Math.sin(TAU * ph);
  }
}

// amplitude: a linear attack a, a fall to the sustain level s (time constant d), a release
// (time constant r) once the gate closes
function adsr(o, n, gate) {
  const na = Math.max(1, len(o.a ?? 0.002)), ng = len(gate), s = o.s ?? 0;
  const kd = Math.exp(-1 / ((o.d ?? 0.25) * SR)), kr = Math.exp(-1 / ((o.r ?? 0.03) * SR));
  const e = new Float32Array(n);
  let lvl = 0, dec = 1;
  for (let j = 0; j < n; j++) {
    if (j < ng) {
      if (j < na) lvl = j / na * (s + (1 - s) * dec);
      else { dec *= kd; lvl = s + (1 - s) * dec; }
    } else lvl *= kr;
    e[j] = lvl;
  }
  return e;
}

// One pitched voice. o:
//   n (MIDI) | f (Hz); len (gate, s); v (level)
//   wave 'saw' | 'square' (pw, pwm, pwmRate) | 'tri' | 'sine' | 'organ' | 'fm' (r ratio, i -> i1 index)
//   uni voices spread over `spread` cents; sub: a square an octave down
//   a, d, s, r: the amplitude envelope; tail: extra time rendered after the release
//   pe semitones falling to the note with time constant pt (a scoop, a kick's drop);
//   bend semitones over bendT s after bendAt s; from (Hz) glided from over `glide` s;
//   vib cents at vibRate Hz after vibDelay s
//   cut (Hz), q, fmode: a filter; famt octaves of filter envelope (fa, fd, fs)
//   drive: saturation after the envelope
function tone(o) {
  const f0 = o.f ?? hz(o.n), gate = o.len ?? 0.2, r = o.r ?? 0.03;
  const n = len(gate + r * 5 + (o.tail ?? 0));
  const env = adsr(o, n, gate), out = new Float32Array(n);
  const kind = o.wave ?? 'saw', pw0 = o.pw ?? 0.5, pwm = o.pwm ?? 0, pwmRate = o.pwmRate ?? 0.7;
  const uni = o.uni ?? 1, spread = o.spread ?? 0, rnd = rng(o.seed ?? 1);
  const det = [], ph = [], pm = [];
  for (let u = 0; u < uni; u++) {
    det.push(uni === 1 ? 1 : Math.pow(2, spread * (2 * u / (uni - 1) - 1) / 1200));
    ph.push(uni === 1 ? 0 : rnd()); pm.push(0);
  }
  const norm = 1 / Math.sqrt(uni);
  const sub = o.sub ?? 0; let sp = 0;
  const pe = o.pe ?? 0, pt = o.pt ?? 0.02;
  const bend = o.bend ?? 0, bendAt = o.bendAt ?? 0, bendT = o.bendT ?? gate;
  const glide = o.glide ?? 0, from = o.from ?? f0;
  const vib = o.vib ?? 0, vibRate = o.vibRate ?? 5.5, vibDelay = o.vibDelay ?? 0.12;
  const flt = o.cut ? svf() : null, q = o.q ?? 0.707, fmode = o.fmode ?? 'lp';
  const famt = o.famt ?? 0, nfa = Math.max(1, len(o.fa ?? 0.001)), kfd = Math.exp(-1 / ((o.fd ?? 0.1) * SR)), fs = o.fs ?? 0;
  const ratio = o.ratio ?? 1, i0 = o.i ?? 0, i1 = Math.max(0.01, o.i1 ?? i0 * 0.2);
  let fdec = 1;
  for (let j = 0; j < n; j++) {
    const t = j / SR;
    let f = f0;
    if (glide > 0) f *= Math.pow(from / f0, Math.exp(-t / glide));
    if (pe) f *= Math.pow(2, pe * Math.exp(-t / pt) / 12);
    if (bend && t > bendAt) f *= Math.pow(2, bend * Math.min(1, (t - bendAt) / bendT) / 12);
    if (vib && t > vibDelay) f *= Math.pow(2, vib * Math.min(1, (t - vibDelay) / 0.15) * Math.sin(TAU * vibRate * (t - vibDelay)) / 1200);
    const pw = pwm ? 0.5 + pwm * Math.sin(TAU * pwmRate * t) * 0.45 : pw0;
    let x = 0;
    for (let u = 0; u < uni; u++) {
      const dt = f * det[u] / SR;
      ph[u] += dt; if (ph[u] >= 1) ph[u] -= 1;
      if (kind === 'fm') {
        pm[u] += dt * ratio; if (pm[u] >= 1) pm[u] -= 1;
        const idx = i0 ? i0 * Math.pow(i1 / i0, Math.min(1, t / gate)) : 0;
        x += Math.sin(TAU * ph[u] + idx * Math.sin(TAU * pm[u]));
      } else x += wave(kind, ph[u], dt, pw);
    }
    x *= norm;
    if (sub) { const dt = f / 2 / SR; sp += dt; if (sp >= 1) sp -= 1; x += sub * wave('square', sp, dt, 0.5); }
    if (flt) {
      let fe;
      if (j < nfa) fe = j / nfa; else { fdec *= kfd; fe = fs + (1 - fs) * fdec; }
      x = flt(x, o.cut * Math.pow(2, famt * fe), q, fmode);
    }
    out[j] = x * env[j];
  }
  if (o.drive) drive(out, o.drive);
  return fadeOut(scale(out, o.v ?? 1));
}

// several voices on one envelope's terms: a chord
function chord(ns, o) {
  const parts = ns.map((n, k) => tone(Object.assign({}, o, { n, seed: (o.seed ?? 1) + k * 7 })));
  const out = new Float32Array(Math.max(...parts.map(p => p.length)));
  for (const p of parts) mix(out, p, 0, 1 / Math.sqrt(ns.length));
  return out;
}

// ---------------------------------------------------------------- drums

// the kick: a sine falling from f0 to f1 (time constant pt), a beater's click on top -- the
// click is what a small speaker hears of a kick
function kick(o = {}) {
  const f0 = o.f0 ?? 240, f1 = o.f1 ?? 50, pt = o.pt ?? 0.03, d = o.d ?? 0.2, click = o.click ?? 0.5;
  const n = len(o.len ?? 0.45), out = new Float32Array(n), rnd = rng(o.seed ?? 11), hp = svf();
  let ph = 0, pc = 0;
  for (let j = 0; j < n; j++) {
    const t = j / SR;
    ph += (f1 + (f0 - f1) * Math.exp(-t / pt)) / SR;
    pc += (o.clickF ?? 3200) / SR;
    const body = Math.sin(TAU * ph) * Math.exp(-t / d) * Math.min(1, j / 16);
    const c = (hp(rnd() * 2 - 1, 1800, 0.7, 'hp') * 0.8 + Math.sin(TAU * pc) * 0.5) * Math.exp(-t / 0.0045);
    out[j] = body + c * click;
  }
  drive(out, o.drive ?? 2.4);
  return fadeOut(scale(out, o.v ?? 1));
}

// the snare: two tuned heads with the stick's pitch drop, a band of noise for the wires
// (gate: the 80s gated room -- full for `gate` s, then cut short)
function snare(o = {}) {
  const f = o.f ?? 185, td = o.td ?? 0.055, nd = o.nd ?? 0.13, n = len(o.len ?? 0.32);
  const out = new Float32Array(n), rnd = rng(o.seed ?? 23), hp = svf(), lp = svf(), hc = svf();
  let p1 = 0, p2 = 0;
  for (let j = 0; j < n; j++) {
    const t = j / SR, pf = 1 + 0.45 * Math.exp(-t / 0.008);
    p1 += f * pf / SR; p2 += f * 1.78 * pf / SR;
    const body = (Math.sin(TAU * p1) + 0.5 * Math.sin(TAU * p2)) * Math.exp(-t / td);
    const w = rnd() * 2 - 1;
    const wires = lp(hp(w, o.hp ?? 800, 0.7, 'hp'), o.lp ?? 9000, 0.7, 'lp');
    const g = o.gate ? (t < o.gate ? 1 : Math.exp(-(t - o.gate) / 0.012)) : 1;
    const crack = hc(w, 4000, 0.7, 'hp') * Math.exp(-t / 0.003);
    out[j] = (body * (o.tone ?? 0.7) + wires * Math.exp(-t / nd) * g * (o.noise ?? 1.3) + crack * 0.8) * Math.min(1, j / 8);
  }
  drive(out, o.drive ?? 2);
  return fadeOut(scale(out, o.v ?? 1));
}

// a hand clap: three or four quick slaps of band-passed noise, then the room
function clap(o = {}) {
  const n = len(o.len ?? 0.3), out = new Float32Array(n), rnd = rng(o.seed ?? 31), bp = svf(), hp = svf();
  const slaps = [0, 0.0105, 0.0215, 0.031];
  for (let j = 0; j < n; j++) {
    const t = j / SR;
    let e = 0;
    for (const s of slaps) if (t >= s) e = Math.max(e, Math.exp(-(t - s) / 0.0055));
    if (t >= 0.031) e = Math.max(e, 0.55 * Math.exp(-(t - 0.031) / (o.d ?? 0.1)));
    out[j] = hp(bp(rnd() * 2 - 1, o.f ?? 1150, 1.1, 'bp'), 500, 0.7, 'hp') * e;
  }
  drive(out, 1.8);
  return fadeOut(scale(out, (o.v ?? 1) * 1.6));
}

// cymbals: six detuned square waves (the 808's metal) and noise, high-passed; a closed hat
// is short, an open hat and a crash ring on
const METAL = [205.3, 304.4, 369.6, 522.7, 540, 800];
function metal(o) {
  const d = o.d ?? 0.035, n = len(o.len ?? (d * 7 + 0.01)), out = new Float32Array(n);
  const rnd = rng(o.seed ?? 41), h1 = svf(), h2 = svf(), lp = svf(), tune = o.tune ?? 1;
  const ph = METAL.map(() => rnd());
  const noise = o.noise ?? 0.7, cut = o.cut ?? 7000;
  for (let j = 0; j < n; j++) {
    const t = j / SR;
    let x = 0;
    for (let k = 0; k < METAL.length; k++) { ph[k] += METAL[k] * tune / SR; if (ph[k] >= 1) ph[k] -= 1; x += ph[k] < 0.5 ? 1 : -1; }
    x = x / 6 + (rnd() * 2 - 1) * noise;
    x = h2(h1(x, cut, 0.9, 'hp'), cut * 1.1, 0.7, 'hp');
    if (o.dark) x = lp(x, o.dark + (12000 - o.dark) * Math.exp(-t / 0.08), 0.7, 'lp');
    out[j] = x * Math.exp(-t / d) * Math.min(1, j / 10);
  }
  return fadeOut(scale(out, (o.v ?? 1) * 2.2));
}
const hat = (o = {}) => metal(Object.assign({ d: 0.03 }, o));
const openHat = (o = {}) => metal(Object.assign({ d: 0.16, len: 0.6, noise: 0.8 }, o));
const crash = (o = {}) => metal(Object.assign({ d: 0.55, len: 2.2, noise: 1.1, tune: 1.35, cut: 4200, dark: 6500 }, o));

// a tom: a kick pitched up, with a little skin noise
function tom(o = {}) {
  const f = o.f ?? 140;
  const x = kick({ f0: f * 1.7, f1: f, pt: 0.04, d: o.d ?? 0.16, click: 0.25, drive: 1.6, len: o.len ?? 0.4, seed: o.seed });
  return scale(x, o.v ?? 1);
}

// ---------------------------------------------------------------- the 90s

// the orchestra hit: a stack of detuned saws through a falling filter, the whole chord sagging
// a little in pitch, a formant, a burst of noise and a timpani boom under it
function orch(o) {
  const ns = o.notes, dur = o.len ?? 0.5;
  const body = chord(ns, { wave: 'saw', uni: 3, spread: 16, a: 0.002, d: o.d ?? 0.17, len: dur, r: 0.06,
    cut: 1300, famt: 2.4, fd: 0.07, q: 1.1, bend: o.sag ?? -0.4, seed: 3 });
  const n = body.length + len(0.05), out = new Float32Array(n);
  mix(out, body, 0, 1);
  mix(out, filter(body, 'bp', 1350, 1.4), 0, 0.8);
  const low = Math.min(...ns) - 12;
  mix(out, kick({ f0: hz(low) * 2.2, f1: hz(low), pt: 0.03, d: 0.14, click: 0.3, drive: 1.5, len: 0.4, seed: 5 }), 0, o.boom ?? 0.45);
  const rnd = rng(7), bp = svf();
  for (let j = 0; j < len(0.12); j++) out[j] += bp(rnd() * 2 - 1, 2400, 0.8, 'bp') * Math.exp(-j / SR / 0.02) * 0.5;
  drive(out, o.drive ?? 1.7);
  return fadeOut(scale(out, o.v ?? 1));
}

// a rave piano stab: two FM pairs per note, a body and a bright tine, both dying fast
function stab(ns, o = {}) {
  const dur = o.len ?? 0.22;
  const a = chord(ns, { wave: 'fm', ratio: 1, i: 2.2, i1: 0.4, a: 0.001, d: o.d ?? 0.18, len: dur, r: 0.05 });
  const b = chord(ns.map(n => n + 12), { wave: 'fm', ratio: 3.5, i: 1.4, i1: 0.05, a: 0.001, d: 0.05, len: dur, r: 0.03 });
  const out = new Float32Array(Math.max(a.length, b.length));
  mix(out, a, 0, 1); mix(out, b, 0, o.tine ?? 0.35);
  drive(out, o.drive ?? 1.3);
  return fadeOut(scale(out, o.v ?? 1));
}

// a sweep of filtered noise from f0 to f1 Hz over `len` s: a riser (shape 'up'), a fall
// ('down') or a whoosh that swells and dies ('swell')
function sweep(o) {
  const n = len(o.len), out = new Float32Array(n), rnd = rng(o.seed ?? 51), f = svf();
  for (let j = 0; j < n; j++) {
    const u = j / n, fc = o.f0 * Math.pow(o.f1 / o.f0, u);
    const amp = o.shape === 'up' ? u * u : o.shape === 'down' ? (1 - u) * (1 - u) : Math.sin(Math.PI * u);
    out[j] = f(rnd() * 2 - 1, fc, o.q ?? 2, o.mode ?? 'bp') * amp;
  }
  return fadeOut(scale(out, o.v ?? 1));
}

// ---------------------------------------------------------------- effects (wet signal out)

// Freeverb, mono: eight damped combs into four allpasses; the send is high-passed (a room
// full of bass is mud)
const COMBS = [1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617], APS = [556, 441, 341, 225];
function reverb(x, o = {}) {
  const fb = (o.room ?? 0.7) * 0.28 + 0.7, d1 = (o.damp ?? 0.5) * 0.4, d2 = 1 - d1, pre = len(o.pre ?? 0.012);
  const combs = COMBS.map(n => ({ b: new Float32Array(n), i: 0, s: 0 })), aps = APS.map(n => ({ b: new Float32Array(n), i: 0 }));
  const y = new Float32Array(x.length), hp = svf(), hpf = o.hp ?? 350;
  for (let j = 0; j < x.length; j++) {
    const inp = hp(j >= pre ? x[j - pre] : 0, hpf, 0.7, 'hp') * 0.015;
    let acc = 0;
    for (const c of combs) {
      const v = c.b[c.i];
      c.s = v * d2 + c.s * d1;
      c.b[c.i] = inp + c.s * fb;
      if (++c.i >= c.b.length) c.i = 0;
      acc += v;
    }
    for (const a of aps) {
      const v = a.b[a.i], outp = v - acc;
      a.b[a.i] = acc + v * 0.5;
      if (++a.i >= a.b.length) a.i = 0;
      acc = outp;
    }
    y[j] = acc * 3;
  }
  return y;
}

// a tape-ish echo: each repeat darker than the one before
function echo(x, o) {
  const d = len(o.time), fb = o.fb ?? 0.35, line = new Float32Array(d), lp = svf(), y = new Float32Array(x.length);
  let i = 0;
  for (let j = 0; j < x.length; j++) {
    const out = lp(line[i], o.lp ?? 3500, 0.7, 'lp');
    line[i] = x[j] + out * fb;
    if (++i >= d) i = 0;
    y[j] = out;
  }
  return y;
}

// ---------------------------------------------------------------- dynamics

// a feed-forward compressor; sc: the key signal (the input itself unless given)
function compress(x, o = {}, sc = x) {
  const thr = o.thr ?? -18, ratio = o.ratio ?? 4, knee = o.knee ?? 6, makeup = o.makeup ?? 0;
  const ka = Math.exp(-1 / ((o.att ?? 0.005) * SR)), kr = Math.exp(-1 / ((o.rel ?? 0.1) * SR));
  const kh = Math.exp(-1 / (0.01 * SR));
  const y = new Float32Array(x.length);
  y.grMax = 0;   // the deepest gain reduction, dB: for the mix report
  let lvl = 0, g = 0;
  for (let j = 0; j < x.length; j++) {
    lvl = Math.max(Math.abs(sc[j]), lvl * kh);   // peak, held a little: no ripple on a bass cycle
    const over = toDb(lvl) - thr;
    let want = 0;
    if (2 * over >= knee) want = (1 / ratio - 1) * over;
    else if (2 * over > -knee) want = (1 / ratio - 1) * (over + knee / 2) * (over + knee / 2) / (2 * knee);
    g = want < g ? ka * g + (1 - ka) * want : kr * g + (1 - kr) * want;
    y[j] = x[j] * dB(g + makeup);
    if (g < y.grMax) y.grMax = g;
  }
  return y;
}

// the rave pump: a gain curve over one loop that dips under every kick (at: sample offsets)
// and swells back; cyclic, so the dip before the loop point carries over it
function pump(L, at, o = {}) {
  const depth = 1 - dB(o.depth ?? -8), na = len(o.att ?? 0.004), kr = (o.rel ?? 0.11) * SR;
  const g = new Float32Array(L).fill(1), ts = at.slice().sort((a, b) => a - b);
  if (!ts.length) return g;
  for (let j = 0, p = -1; j < L; j++) {
    while (p + 1 < ts.length && ts[p + 1] <= j) p++;
    const k = j - (p >= 0 ? ts[p] : ts[ts.length - 1] - L);
    g[j] = k < na ? 1 - depth * (k / na) : 1 - depth * Math.exp(-(k - na) / kr);
  }
  return g;
}

// a look-ahead limiter: the gain every sample needs, held over +-look and smoothed by a box of
// the same width (so it is already down when the peak arrives), released slowly
function limit(x, ceil = dB(-1), o = {}) {
  const n = x.length, w = len(o.look ?? 0.0015), kr = Math.exp(-1 / ((o.rel ?? 0.06) * SR));
  const need = new Float32Array(n);
  for (let j = 0; j < n; j++) need[j] = Math.min(1, ceil / Math.max(1e-9, Math.abs(x[j])));
  // the least over [j - w, j + w]: a monotonic deque
  const held = new Float32Array(n), dq = new Int32Array(n);
  let h = 0, t = 0;
  for (let j = 0, k = 0; j < n; j++) {
    while (k < n && k <= j + w) { while (t > h && need[dq[t - 1]] >= need[k]) t--; dq[t++] = k; k++; }
    while (dq[h] < j - w) h++;
    held[j] = need[dq[h]];
  }
  const pre = new Float64Array(n + 1);
  for (let j = 0; j < n; j++) pre[j + 1] = pre[j] + held[j];
  const y = new Float32Array(n);
  let g = 1;
  for (let j = 0; j < n; j++) {
    const a = Math.max(0, j - (w >> 1)), b = Math.min(n, j + (w >> 1) + 1);
    const box = (pre[b] - pre[a]) / (b - a);
    g = box < g ? box : g * kr + box * (1 - kr);
    y[j] = Math.max(-ceil, Math.min(ceil, x[j] * g));
  }
  return y;
}

// ---------------------------------------------------------------- measuring

// a biquad from RBJ's cookbook, run over a buffer
function biquad(x, kind, f0, Q, gainDb = 0) {
  const A = Math.pow(10, gainDb / 40), w0 = TAU * f0 / SR, c = Math.cos(w0), al = Math.sin(w0) / (2 * Q);
  let b0, b1, b2, a0, a1, a2;
  if (kind === 'shelf') {
    const s = 2 * Math.sqrt(A) * al;
    b0 = A * ((A + 1) + (A - 1) * c + s); b1 = -2 * A * ((A - 1) + (A + 1) * c); b2 = A * ((A + 1) + (A - 1) * c - s);
    a0 = (A + 1) - (A - 1) * c + s; a1 = 2 * ((A - 1) - (A + 1) * c); a2 = (A + 1) - (A - 1) * c - s;
  } else { // high-pass
    b0 = (1 + c) / 2; b1 = -(1 + c); b2 = (1 + c) / 2; a0 = 1 + al; a1 = -2 * c; a2 = 1 - al;
  }
  const y = new Float64Array(x.length);
  let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
  for (let j = 0; j < x.length; j++) {
    const v = (b0 * x[j] + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2) / a0;
    x2 = x1; x1 = x[j]; y2 = y1; y1 = v; y[j] = v;
  }
  return y;
}

// integrated loudness after ITU-R BS.1770 (K-weighting, 400 ms blocks, the two gates);
// a sound shorter than a block is measured as one block
function lufs(x) {
  const k = biquad(biquad(x, 'shelf', 1681.974, 0.70718, 3.99984), 'hp', 38.135, 0.50033);
  const B = len(0.4), hop = len(0.1), ms = [];
  if (k.length <= B) { let s = 0; for (const v of k) s += v * v; ms.push(s / Math.max(1, k.length)); }
  for (let a = 0; a + B <= k.length; a += hop) { let s = 0; for (let j = a; j < a + B; j++) s += k[j] * k[j]; ms.push(s / B); }
  const L = m => -0.691 + 10 * Math.log10(Math.max(m, 1e-12));
  const abs = ms.filter(m => L(m) > -70);
  if (!abs.length) return -70;
  const rel = L(abs.reduce((a, b) => a + b, 0) / abs.length) - 10;
  const kept = abs.filter(m => L(m) > rel);
  return L(kept.reduce((a, b) => a + b, 0) / kept.length);
}

// what a sound is made of: peak, RMS, loudness, how much of its energy lies where the
// Playdate's speaker can play it (above ~500 Hz), and its share (dB) in six bands
const BANDS = [[0, 100], [100, 300], [300, 1000], [1000, 3000], [3000, 8000], [8000, 0]];
function energy(x) { let s = 0; for (const v of x) s += v * v; return Math.max(s, 1e-12); }
function stats(x) {
  const all = energy(x);
  const hi = filter(filter(x, 'hp', 500, 0.707), 'hp', 500, 0.707);
  const bands = BANDS.map(([lo, up]) => {
    let y = x;
    if (lo) y = filter(filter(y, 'hp', lo, 0.707), 'hp', lo, 0.707);
    if (up) y = filter(filter(y, 'lp', up, 0.707), 'lp', up, 0.707);
    return 10 * Math.log10(energy(y) / all);
  });
  return { peak: toDb(peak(x)), rms: toDb(Math.sqrt(all / x.length)), lufs: lufs(x), speaker: 10 * Math.log10(energy(hi) / all), bands };
}

// ---------------------------------------------------------------- patterns

// note names: c4 is MIDI 60, a4 69
const PC = { c: 0, d: 2, e: 4, f: 5, g: 7, a: 9, b: 11 };
function note(tok) {
  if (/^\d+$/.test(tok)) return Number(tok);   // a MIDI number as it is
  const m = /^([a-g])([#b]?)(-?\d)$/.exec(tok);
  if (!m) throw new Error('not a note: ' + tok);
  return 12 * (Number(m[3]) + 1) + PC[m[1]] + (m[2] === '#' ? 1 : m[2] === 'b' ? -1 : 0);
}

// bars written between '|' must be whole: a token too many or too few shifts the rest of the line
function whole(chunks, what) {
  if (chunks.length < 2) return;
  chunks.forEach((c, k) => { if (c.length !== 16) throw new Error(what + ': bar ' + (k + 1) + ' has ' + c.length + ' steps'); });
}

// A tracker line, one token a 16th: a note ('a4', 'c#5', 'eb3', or a MIDI number), '-' holds
// the note before for another step, '.' is a rest; '|' marks bars. -> [{ step, n, len }]
function notes(str, first = 0) {
  whole(str.split('|').map(b => b.split(/\s+/).filter(Boolean)), 'notes');
  const out = [];
  let step = first, held = null;
  for (const tok of str.split(/[\s|]+/).filter(Boolean)) {
    if (tok === '-') { if (held) held.len++; }
    else if (tok === '.') held = null;
    else { held = { step, n: note(tok), len: 1 }; out.push(held); }
    step++;
  }
  return out;
}

// A drum line, one character a 16th: 'X' an accent, 'x' a hit, 'o' a ghost note, '1'..'9' a
// level in tenths, '.' nothing; '|' and spaces for the eye. -> [{ step, v }]
function beats(str, first = 0) {
  whole(str.split('|').map(b => [...b.replace(/\s/g, '')]), 'beats');
  const out = [];
  let step = first;
  for (const ch of str.replace(/[\s|]/g, '')) {
    const v = ch === 'X' ? 1.25 : ch === 'x' ? 1 : ch === 'o' ? 0.45 : (ch >= '1' && ch <= '9') ? (ch.charCodeAt(0) - 48) / 10 : 0;
    if (v > 0) out.push({ step, v });
    step++;
  }
  return out;
}

// the same instrument call renders once
function memo(fn) {
  const cache = new Map();
  return o => {
    const key = JSON.stringify(o);
    if (!cache.has(key)) cache.set(key, fn(o));
    return cache.get(key);
  };
}

// A loop under construction: named stems, each the loop plus a tail that folds back over
// its start. Steps are 16ths, rounded to whole samples from the start of the loop.
class Song {
  constructor({ bpm, bars, tail = 3 }) {
    this.bpm = bpm; this.bars = bars;
    this.step = 60 / bpm / 4;
    this.steps = bars * 16;
    this.L = this.at(this.steps);
    this.N = this.L + len(tail);
    this.stems = new Map();
    this.kicks = [];
  }
  at(step) { return Math.round(step * this.step * SR); }
  stem(name) {
    if (!this.stems.has(name)) this.stems.set(name, new Float32Array(this.N));
    return this.stems.get(name);
  }
  put(name, step, buf, gain = 1) { mix(this.stem(name), buf, this.at(step), gain); }
  fold(x) { return fold(x, this.L); }
}

// ---------------------------------------------------------------- the electric guitar
// (added for the techno-rock loops; nothing above uses it)

// RBJ's cookbook biquad at any rate: 'lp' | 'hp' | 'bp' (peak gain Q) | 'peak' | 'ls' | 'hs'
// (shelves) -> [b0, b1, b2, a1, a2] over a0
function bqc(kind, f0, Q = 0.707, gainDb = 0, rate = SR) {
  const A = Math.pow(10, gainDb / 40), w0 = TAU * Math.min(f0, rate * 0.49) / rate, c = Math.cos(w0), al = Math.sin(w0) / (2 * Q);
  let b0, b1, b2, a0, a1, a2;
  if (kind === 'lp') { b0 = (1 - c) / 2; b1 = 1 - c; b2 = (1 - c) / 2; a0 = 1 + al; a1 = -2 * c; a2 = 1 - al; }
  else if (kind === 'hp') { b0 = (1 + c) / 2; b1 = -(1 + c); b2 = (1 + c) / 2; a0 = 1 + al; a1 = -2 * c; a2 = 1 - al; }
  else if (kind === 'bp') { b0 = Q * al; b1 = 0; b2 = -Q * al; a0 = 1 + al; a1 = -2 * c; a2 = 1 - al; }
  else if (kind === 'peak') { b0 = 1 + al * A; b1 = -2 * c; b2 = 1 - al * A; a0 = 1 + al / A; a1 = -2 * c; a2 = 1 - al / A; }
  else if (kind === 'ls' || kind === 'hs') {
    const k = 2 * Math.sqrt(A) * al, s = kind === 'ls' ? 1 : -1;
    b0 = A * ((A + 1) - s * (A - 1) * c + k); b1 = s * 2 * A * ((A - 1) - s * (A + 1) * c); b2 = A * ((A + 1) - s * (A - 1) * c - k);
    a0 = (A + 1) + s * (A - 1) * c + k; a1 = -s * 2 * ((A - 1) + s * (A + 1) * c); a2 = (A + 1) + s * (A - 1) * c - k;
  } else throw new Error('biquad kind ' + kind);
  return [b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0];
}

// a chain of biquads over a buffer, [[kind, Hz, Q, dB], ...]; a new buffer out
function eq(x, bands, rate = SR) {
  const y = Float32Array.from(x);
  for (const b of bands) {
    const [b0, b1, b2, a1, a2] = bqc(b[0], b[1], b[2] ?? 0.707, b[3] ?? 0, rate);
    let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
    for (let j = 0; j < y.length; j++) {
      const u = y[j], v = b0 * u + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2;
      x2 = x1; x1 = u; y2 = y1; y1 = v; y[j] = v;
    }
  }
  return y;
}

// the frequency of a voice at time t, on tone()'s terms: glide `from`, a scoop pe/pt, `bend`
// semitones over bendT after bendAt, vibrato `vib` cents after vibDelay
function pitch(o, f0) {
  const glide = o.glide ?? 0, from = o.from ?? f0, pe = o.pe ?? 0, pt = o.pt ?? 0.02;
  const bend = o.bend ?? 0, bendAt = o.bendAt ?? 0, bendT = o.bendT ?? 0.1;
  const vib = o.vib ?? 0, vibRate = o.vibRate ?? 5.5, vibDelay = o.vibDelay ?? 0.12;
  return t => {
    let f = f0;
    if (glide > 0) f *= Math.pow(from / f0, Math.exp(-t / glide));
    if (pe) f *= Math.pow(2, pe * Math.exp(-t / pt) / 12);
    if (bend && t > bendAt) f *= Math.pow(2, bend * Math.min(1, (t - bendAt) / bendT) / 12);
    if (vib && t > vibDelay) f *= Math.pow(2, vib * Math.min(1, (t - vibDelay) / 0.15) * Math.sin(TAU * vibRate * (t - vibDelay)) / 1200);
    return f;
  };
}

// A plucked string after Karplus and Strong, with Jaffe and Smith's extensions: the pick -- the
// string's shape where it was pulled aside (a triangle, its apex at `pick`, that point's
// fraction of the string: the harmonics with a node there are missing) and a share `noise` of
// the pick's scrape, darker for a softer pick (bright 0..1) -- runs round a delay line one
// period long. Each lap averages neighbouring samples (damp 0..0.5: the highs die first) and
// loses enough that the fundamental falls 60 dB in t60 s; once the gate closes the fretting hand
// stops it within `mute` s. The line is read between samples (cubic), so the pitch is true
// and may move as in tone(): bend, vibrato, glide, a scoop. -> the string's motion, about +-1
function string(o) {
  const f0 = o.f ?? hz(o.n), gate = o.len ?? 0.5, mute = o.mute ?? 0.04;
  const n = len(gate + mute * 2.5 + (o.tail ?? 0)), y = new Float32Array(n), E = Math.max(4, Math.round(SR / f0));
  const rnd = rng(o.seed ?? 5), raw = new Float32Array(E), ca = Math.min(1, Math.max(0.01, o.bright ?? 0.6));
  let lp = 0;
  for (let j = 0; j < E; j++) { lp += (rnd() * 2 - 1 - lp) * ca; raw[j] = lp; }
  const pf = Math.min(0.5, Math.max(0.02, o.pick ?? 0.13)), pk = Math.max(1, Math.round(pf * E)), ex = new Float32Array(E);
  for (let j = 0; j < E; j++) ex[j] = raw[j] - raw[(j - pk + E) % E];
  scale(ex, (o.noise ?? 0.35) / Math.max(1e-9, peak(ex)));
  const tri = new Float32Array(E);
  let mean = 0;
  for (let j = 0; j < E; j++) { const u = (j + 0.5) / E; tri[j] = u < pf ? u / pf : (1 - u) / (1 - pf); mean += tri[j] / E; }
  for (let j = 0; j < E; j++) ex[j] += (1 - (o.noise ?? 0.35)) * 2 * (tri[j] - mean);
  scale(ex, 1 / Math.max(1e-9, peak(ex)));
  const sd = o.damp ?? 0.5, f = pitch(o, f0);
  const g = Math.pow(10, -3 / ((o.t60 ?? 2) * f0)), gm = Math.pow(10, -3 / (mute * f0));
  let prev = 0;
  for (let j = 0; j < n; j++) {
    const t = j / SR, p = j - (SR / f(t) - sd);
    let v = 0;
    if (p >= 1) {
      const i = Math.floor(p), fr = p - i, xm = y[i - 1], x0 = y[i], x1 = y[i + 1], x2 = y[i + 2];
      const c1 = 0.5 * (x1 - xm), c2 = xm - 2.5 * x0 + 2 * x1 - 0.5 * x2, c3 = 0.5 * (x2 - xm) + 1.5 * (x0 - x1);
      v = ((c3 * fr + c2) * fr + c1) * fr + x0;
    }
    const w = (1 - sd) * v + sd * prev;
    prev = v;
    y[j] = (j < E ? ex[j] : 0) + (t < gate ? g : gm) * w;
  }
  return fadeOut(scale(y, o.v ?? 1), 0.003);
}

// the second clipping stage: hard, but with a rounded knee (|u|^4), clipping at +1 and -neg
function knee(u, neg) {
  if (u >= 0) return u / Math.sqrt(Math.sqrt(1 + u * u * u * u));
  const w = u / neg;
  return neg * w / Math.sqrt(Math.sqrt(1 + w * w * w * w));
}

// A guitar amplifier and its cabinet, the high-gain recipe: the input tightened (the lows that
// would flub cut before the gain) and its mids pushed, two clipping stages -- the first soft
// and biased (asymmetric: even harmonics, a valve's warmth), the second harder -- run at four
// times the rate so the harmonics they make do not fold back, then the cabinet: nothing under
// ~90 Hz, a broad presence bump, a little less box, nothing over ~5 kHz (a speaker cone plays
// no fizz). o: gain (dB into the first stage), tight (Hz), mid [Hz, dB], fizz (Hz, the
// pickup's top), bias, hard (the second stage's gain), neg (its negative ceiling),
// cab { hp, pres: [Hz, dB, Q], box: [Hz, dB], lp, q }. Takes the dry guitar, returns about +-1.
function amp(x, o = {}) {
  const OS = 4, R = SR * OS, mid = o.mid ?? [800, 6];
  const pre = eq(x, [['hp', o.tight ?? 110, 0.6], ['peak', mid[0], 0.7, mid[1]], ['lp', o.fizz ?? 6000, 0.7]]);
  const AA = [['lp', 18000, 0.5098], ['lp', 18000, 0.6013], ['lp', 18000, 0.9], ['lp', 18000, 2.5629]];
  let z = new Float32Array(pre.length * OS);
  for (let j = 0; j < pre.length; j++) z[j * OS] = pre[j] * OS;
  z = eq(z, AA, R);
  const g1 = dB(o.gain ?? 26), bias = o.bias ?? 0.3, b0 = Math.tanh(bias), g2 = o.hard ?? 2.5, neg = o.neg ?? 0.8;
  for (let j = 0; j < z.length; j++) z[j] = Math.tanh(g1 * z[j] + bias) - b0;
  z = eq(z, [['hp', 25, 0.7], ['lp', 10000, 0.7]], R);
  for (let j = 0; j < z.length; j++) z[j] = knee(g2 * z[j], neg);
  z = eq(z, AA, R);
  const out = new Float32Array(pre.length);
  for (let j = 0; j < out.length; j++) out[j] = z[j * OS];
  const c = o.cab ?? {}, hp = c.hp ?? 90, lp = c.lp ?? 5000, pres = c.pres ?? [2200, 4, 0.6], box = c.box ?? [450, -2];
  return eq(out, [['hp', hp, 0.54], ['hp', hp, 1.31], ['peak', pres[0], pres[2], pres[1]], ['peak', box[0], 1, box[1]],
    ['lp', lp, 0.54], ['lp', lp, c.q ?? 1.31]]);
}

module.exports = {
  SR, TAU, hz, dB, toDb, len, rng,
  mix, scale, peak, fadeOut, drive, fold, cyclic,
  svf, filter, wave, adsr, tone, chord,
  kick, snare, clap, hat, openHat, crash, tom, metal, orch, stab, sweep,
  reverb, echo, compress, pump, limit,
  lufs, stats,
  note, notes, beats, memo, Song,
  bqc, eq, pitch, string, amp,
};
