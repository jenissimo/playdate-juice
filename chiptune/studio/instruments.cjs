// The instruments, each a memoised ({ n, d, ... }) -> buffer.
// I: the 90s tracker kit (kick, snare, clap, hats, crash, toms, a riser), basses (saw, FM
// slap), a square lead, a calliope, brass, a pluck, the hoover, stabs, an organ, the orchestra
// hit. CH: a chord table in A minor (a bass root, a stab voicing, an orchestra-hit stack, the
// seventh in key). G: the techno-rock band -- the electric guitar (plucked strings, played dry:
// master.cjs runs each guitar's whole stem through one S.amp()), a synth bass, an acid line, a
// pad. (In Overturn the one-shots play I too: a change here changes them.)
'use strict';

const S = require('./synth.cjs');
const { memo } = S;

const I = {
  kick: memo(o => S.kick(o)),
  snare: memo(o => S.snare(o)),
  clap: memo(o => S.clap(o)),
  hat: memo(o => S.hat(o)),
  ohat: memo(o => S.openHat(o)),
  crash: memo(o => S.crash(o)),
  tom: memo(o => S.tom(o)),
  riser: memo(o => S.sweep(Object.assign({ f0: 400, f1: 7000, shape: 'up', q: 1.5 }, o))),
  // saw and a square an octave down through a snapping filter: the speaker hears its harmonics
  bass: memo(({ n, d }) => S.tone({ n, len: d, wave: 'saw', sub: 0.3, cut: 220, famt: 3.3, fd: 0.06, fs: 0.2, q: 1.5,
    a: 0.002, d: 0.25, s: 0.6, r: 0.02, drive: 1.8 })),
  // FM slap under a saw: the table's bass, rounder and funkier
  slap: memo(({ n, d }) => {
    const x = S.tone({ n, len: d, wave: 'fm', ratio: 1, i: 4.5, i1: 0.7, a: 0.001, d: 0.16, s: 0.45, r: 0.02 });
    S.mix(x, S.tone({ n, len: d, wave: 'saw', cut: 300, famt: 2.5, fd: 0.05, q: 1.2, a: 0.002, d: 0.2, s: 0.5, r: 0.02 }), 0, 0.6);
    return S.drive(x, 1.6);
  }),
  lead: memo(({ n, d }) => S.tone({ n, len: d, wave: 'square', pw: 0.32, uni: 2, spread: 9, cut: 1500, famt: 1.3, fa: 0.004,
    fd: 0.18, fs: 0.35, q: 1.3, a: 0.004, d: 0.35, s: 0.75, r: 0.05, vib: 16, vibDelay: 0.18, drive: 1.4 })),
  calliope: memo(({ n, d }) => S.tone({ n, len: d, wave: 'organ', a: 0.012, d: 0.6, s: 0.8, r: 0.04,
    vib: 26, vibRate: 6.4, vibDelay: 0.02, drive: 1.2 })),
  brass: memo(({ n, d }) => S.tone({ n, len: d, wave: 'saw', uni: 2, spread: 8, cut: 450, famt: 2.4, fa: 0.035, fd: 0.3,
    fs: 0.45, q: 0.9, a: 0.02, d: 0.5, s: 0.8, r: 0.08, vib: 10, vibDelay: 0.25 })),
  pluck: memo(({ n, d }) => S.tone({ n, len: d, wave: 'square', pw: 0.25, cut: 900, famt: 2.5, fd: 0.05, q: 2,
    a: 0.001, d: 0.09, s: 0, r: 0.02 })),
  // the 1992 hoover: detuned saws scooping up into the note
  hoover: memo(({ n, d }) => S.tone({ n, len: d, wave: 'saw', uni: 5, spread: 34, pe: -7, pt: 0.035, sub: 0.35, cut: 2600,
    q: 0.8, a: 0.003, d: 0.5, s: 0.8, r: 0.06, drive: 1.3 })),
  stab: memo(({ ns, d }) => S.stab(ns, { len: d })),
  organ: memo(({ ns, d }) => S.chord(ns, { wave: 'organ', a: 0.004, d: 0.12, s: 0.3, len: d, r: 0.03,
    vib: 20, vibRate: 6.4, vibDelay: 0.02 })),
  orch: memo(({ ns }) => S.orch({ notes: ns })),
};

// the chords: a bass root, a stab voicing (closest to the one before), an orchestra-hit stack,
// and the seventh a bass may walk to without leaving A minor
const CH = {
  Am: { bass: 45, stab: [57, 60, 64], orch: [57, 64, 69, 72, 76], sev: 10 },
  F: { bass: 41, stab: [57, 60, 65], orch: [53, 60, 65, 69, 72], sev: 9 },
  G: { bass: 43, stab: [59, 62, 67], orch: [55, 62, 67, 71, 74], sev: 10 },
  E: { bass: 40, stab: [56, 59, 64], orch: [52, 59, 64, 68, 71], sev: 10 },
  Dm: { bass: 38, stab: [57, 62, 65], orch: [50, 57, 62, 65, 69], sev: 10 },
  C: { bass: 36, stab: [55, 60, 64], orch: [48, 55, 60, 64, 67], sev: 9 },
  D: { bass: 38, stab: [57, 62, 66], orch: [50, 57, 62, 66, 69], sev: 10 },
  'G#o': { bass: 44, stab: [56, 59, 62, 65], orch: [56, 62, 65, 68], sev: 9 },
};

// ---------------------------------------------------------------- the band (music only)

// a strum: the strings struck one after another, `strum` s apart, low to high (a downstroke) or
// high to low (up); each string a few cents from true, as real strings are
const DETUNE = [0, 0.04, -0.03, 0.02];
function strum(ns, o) {
  const k = o.strum ?? 0.006;
  const parts = ns.map((n, i) => {
    const place = o.up ? ns.length - 1 - i : i;
    return { at: Math.round(place * k * S.SR),
      x: S.string(Object.assign({}, o, { n: n + DETUNE[i % 4], len: Math.max(0.02, o.d - place * k), seed: 11 + n * 3 + i * 17 })) };
  });
  const out = new Float32Array(Math.max(...parts.map(p => p.at + p.x.length)));
  for (const p of parts) S.mix(out, p.x, p.at, 1 / Math.sqrt(ns.length));
  return out;
}

const G = {
  // an open power chord -- root, fifth, octave -- ringing for d s
  chord: memo(({ n, d, up = false }) => strum([n, n + 7, n + 12], { d, up, t60: 3, damp: 0.35, bright: 0.7, pick: 0.14,
    noise: 0.35, mute: 0.05 })),
  // palm-muted: root and fifth with the side of the hand on them -- short, dark, a thump
  chug: memo(({ n, d, up = false }) => S.scale(S.eq(strum([n, n + 7], { d, up, strum: 0.003, t60: 0.14, damp: 0.5,
    bright: 0.5, pick: 0.12, noise: 0.4, mute: 0.02 }), [['lp', 650, 0.7]]), 1.4)),
  // a dead strum: the fretting hand lying on the strings, a pitchless 'chk'
  dead: memo(({ n, up = false }) => S.scale(S.eq(strum([n, n + 7, n + 12], { d: 0.02, up, strum: 0.003, t60: 0.012,
    bright: 0.95, noise: 0.9, mute: 0.01 }), [['lp', 3000, 0.7]]), 0.8)),
  // the pick scraped down the wound strings: a ridged screech falling for d s
  scrape: memo(({ d }) => {
    const n = S.len(d), x = new Float32Array(n), rnd = S.rng(77), bp = S.svf();
    for (let j = 0; j < n; j++) {
      const u = j / n, t = j / S.SR;
      const ridge = 0.55 + 0.45 * Math.sin(S.TAU * (90 - 50 * u) * t);
      x[j] = bp(rnd() * 2 - 1, 3200 * Math.pow(0.12, u), 5, 'bp') * ridge * Math.min(1, j / 200) * (1 - 0.5 * u);
    }
    return S.fadeOut(S.scale(x, 1.6), 0.02);
  }),
  // a lead note: a long-sustaining string, a little vibrato when it is held; marks: '/' scooped
  // up from a tone under, '^' bent up into it from a tone under, '~' a wide vibrato, '\'
  // falling away at its end, '*' a pinch harmonic (it squeals an octave and a fifth up)
  note: memo(({ n, d, mark = '' }) => {
    const o = { n, len: d, t60: 3.5, damp: 0.25, bright: 0.8, pick: 0.18, noise: 0.3, mute: 0.05, seed: 7 + n };
    if (d > 0.3) Object.assign(o, { vib: 16, vibRate: 5.6, vibDelay: 0.22 });
    if (mark.includes('~')) Object.assign(o, { vib: 40, vibRate: 5.8, vibDelay: 0.1 });
    if (mark.includes('/')) Object.assign(o, { from: S.hz(n - 2), glide: 0.022 });
    if (mark.includes('^')) Object.assign(o, { n: n - 2, bend: 2, bendAt: Math.min(0.03, d * 0.1), bendT: Math.min(0.13, d * 0.45),
      vib: Math.max(o.vib ?? 0, 22), vibDelay: Math.max(o.vibDelay ?? 0, 0.28) });
    if (mark.includes('\\')) Object.assign(o, { bend: -7, bendAt: Math.max(0.02, d - 0.15), bendT: 0.15 });
    if (mark.includes('*')) Object.assign(o, { n: n + 19, bright: 1, noise: 0.6, pick: 0.07, t60: 2, vib: 45, vibRate: 6.5, vibDelay: 0.05 });
    return S.string(o);
  }),
  // a let-ring arpeggio's note for the clean(er) guitar
  clean: memo(({ n, d }) => S.string({ n, len: d, t60: 2.5, damp: 0.3, bright: 0.6, pick: 0.2, noise: 0.25, mute: 0.08, seed: 3 + n })),
  // the synth bass: two saws, a filter snapping shut, driven -- its harmonics carry it on a
  // small speaker, its fundamental (55-110 Hz) is what the danger high-pass takes
  bass: memo(({ n, d }) => S.tone({ n, len: d, wave: 'saw', uni: 2, spread: 7, cut: 240, famt: 3.1, fd: 0.07, fs: 0.22,
    q: 1.5, a: 0.002, d: 0.22, s: 0.7, r: 0.02, drive: 2.3 })),
  // the acid line: a resonant saw, its filter opened by `acc` (0..1)
  acid: memo(({ n, d, acc = 0 }) => S.tone({ n, len: d, wave: 'saw', cut: 300, famt: 2.4 + 1.6 * acc, fd: 0.07 + 0.08 * acc, fs: 0,
    q: 4.5, a: 0.001, d: 0.25, s: 0.5, r: 0.015, drive: 2.4 })),
  // a string pad for the breakdown
  pad: memo(({ ns, d }) => S.chord(ns, { wave: 'saw', uni: 3, spread: 14, a: 0.35, d: 1.2, s: 0.85, r: 0.5, len: d, cut: 1500,
    q: 0.7, vib: 5, vibDelay: 0.3 })),
};

module.exports = { I, CH, G };
