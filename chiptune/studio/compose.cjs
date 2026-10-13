// Writing a song: tracker lines -- one token a 16th, bars of 16 between '|' -- turned into
// notes on a Song's stems (synth.cjs). Bound to a chord table (instruments.cjs CH, or your own:
// { name: { bass, stab, orch, sev } }) and a key, so a line can say 'Am' and a bass template 'R'.
//   const W = require('./compose.cjs')(CH, { scale: [9, 11, 0, 2, 4, 5, 7], bassDown: true });
//   W.drum(song, 'kick', K, 'x...x...x...x...', 1);
//   W.rhythm(song, 'gtr', 'A2 - - a2 a2 - C3 - - a2 D3 - - a2 C3 -', 1);
//   W.lead(song, 'lead', 'e5/ - . e5 - . d5 - e5 - . . g5 - a5^ -', 5);
'use strict';

const S = require('./synth.cjs');
const { I, G } = require('./instruments.cjs');

const PC = { c: 0, d: 2, e: 4, f: 5, g: 7, a: 9, b: 11 };
const NAMES = ['c', 'c#', 'd', 'eb', 'e', 'f', 'f#', 'g', 'g#', 'a', 'bb', 'b'];
const A_MINOR = [9, 11, 0, 2, 4, 5, 7];

// table: the chords by name; opts.scale: the key's seven pitch classes from its tonic (the
// twin lead's thirds stay in it); opts.bassDown: a bass template's root an octave under the
// table's (as long as that stays at or over A1)
module.exports = function compose(table, opts = {}) {
  const scale = opts.scale || A_MINOR, bassDown = opts.bassDown ?? true;

  // a step from the start of the loop: bar 1, step 0 is 0
  const at = (bar, step = 0) => (bar - 1) * 16 + step;

  // a line's tokens, one a 16th, in whole bars of 16 ('|' marks bars for the eye)
  function steps(line, what) {
    const toks = line.split(/[\s|]+/).filter(Boolean);
    line.split('|').forEach((b, k) => {
      const n = b.split(/\s+/).filter(Boolean).length;
      if (n % 16) throw new Error(what + ': bar ' + (k + 1) + ' has ' + n + ' steps: ' + b);
    });
    return toks;
  }
  const bars = (...ls) => ls.join(' | ');

  // a drum line from a bar on (it may run over several bars): 'X' accent, 'x' hit, 'o' ghost,
  // '1'..'9' a level in tenths. The kick's hits key the master's pump.
  function drum(song, stem, buf, line, bar, gain = 1) {
    for (const b of S.beats(line, at(bar))) {
      song.put(stem, b.step, buf, gain * b.v);
      if (stem === 'kick') song.kicks.push(song.at(b.step) % song.L);
    }
  }

  // a melody line from a bar on on any instrument ({ n, d } -> buffer); gate: how much of each
  // note's length it is held
  function voice(song, stem, inst, line, bar, gain = 1, gate = 0.9) {
    steps(line, stem);
    for (const e of S.notes(line, at(bar))) song.put(stem, e.step, inst({ n: e.n, d: e.len * song.step * gate }), gain);
  }

  // A rhythm guitar line: 'A2' an open power chord on that root (it rings until the next token),
  // 'a2' the same palm-muted (a chug), '-' holds, '.' stops the strings, 'x' a dead strum, '/' a
  // pick scrape (for its holds). Strokes alternate as a picking hand does: down on the even
  // 16ths, up on the odd.
  function chordRoot(tok) {
    const m = /^([A-Ga-g])([#b]?)(\d)$/.exec(tok);
    if (!m) return null;
    return { n: 12 * (Number(m[3]) + 1) + PC[m[1].toLowerCase()] + (m[2] === '#' ? 1 : m[2] === 'b' ? -1 : 0), open: m[1] !== m[1].toLowerCase() };
  }
  function rhythm(song, stem, line, bar, gain = 1) {
    const toks = steps(line, stem), base = at(bar);
    let last = 45;
    toks.forEach((tk, k) => {
      if (tk === '-' || tk === '.') return;
      let hold = 1;
      while (toks[k + hold] === '-') hold++;
      const d = hold * song.step, up = (base + k) % 2 === 1;
      if (tk === 'x') return song.put(stem, base + k, G.dead({ n: last, up }), gain);
      if (tk === '/') return song.put(stem, base + k, G.scrape({ d }), gain);
      const c = chordRoot(tk);
      if (!c) throw new Error(stem + ': not a chord: ' + tk);
      last = c.n;
      song.put(stem, base + k, c.open ? G.chord({ n: c.n, d, up }) : G.chug({ n: c.n, d: Math.min(d, 2 * song.step) * 0.9, up }), gain);
    });
  }

  // the bass under a rhythm guitar line: each chord's root, an octave down where that stays at
  // or over A1 (55 Hz), held as the guitar holds it
  function bassFrom(line) {
    return steps(line, 'bassFrom').map(tk => {
      const c = chordRoot(tk);
      if (c) return String(c.n - 12 >= 33 ? c.n - 12 : c.n);
      return tk === '-' ? '-' : '.';
    }).join(' ');
  }

  // a bass template over a chord: R the root, O its octave, 5 its fifth, 7 the seventh in key
  function riff(tmpl, ch) {
    const c = table[ch];
    const r = bassDown && c.bass - 12 >= 33 ? c.bass - 12 : c.bass;
    const map = { R: r, O: r + 12, 5: r + 7, 7: r + (c.sev ?? 10) };
    return tmpl.split(/\s+/).filter(Boolean).map(t => (t in map ? String(map[t]) : t)).join(' ');
  }

  // A lead guitar line: notes as in S.notes ('a4', 'c#5', '-' held, '.' a rest), with G.note's
  // marks after a note: '/' scoop, '^' bend, '~' wide vibrato, '\' fall, '*' pinch harmonic
  function lead(song, stem, line, bar, gain = 1) {
    const toks = steps(line, stem), base = at(bar);
    toks.forEach((tk, k) => {
      if (tk === '-' || tk === '.') return;
      let hold = 1;
      while (toks[k + hold] === '-') hold++;
      const m = /^([a-g][#b]?-?\d)([~/^\\*]*)$/.exec(tk);
      if (!m) throw new Error(stem + ': not a note: ' + tk);
      song.put(stem, base + k, G.note({ n: S.note(m[1]), d: hold * song.step * 0.96, mark: m[2] }), gain);
    });
  }

  // a let-ring arpeggio: each note sounds for ringSteps 16ths whatever follows it
  function ring(song, stem, line, bar, ringSteps, gain = 1) {
    steps(line, stem);
    for (const e of S.notes(line, at(bar))) song.put(stem, e.step, G.clean({ n: e.n, d: ringSteps * song.step }), gain);
  }

  // chords on the given steps of a bar: 'x' a hit, 'X' an accent, '-' holds it
  function chords(song, stem, inst, line, bar, ch, gain = 1, gate = 0.85) {
    const toks = line.replace(/[\s|]/g, '');
    for (let k = 0; k < toks.length; k++) {
      if (toks[k] !== 'x' && toks[k] !== 'X') continue;
      let n = 1; while (toks[k + n] === '-') n++;
      song.put(stem, at(bar, k), inst({ ns: table[ch].stab, d: n * song.step * gate }), gain * (toks[k] === 'X' ? 1.25 : 1));
    }
  }

  // an orchestra hit: a chord's stack, or any notes
  function hit(song, ch, bar, step = 0, gain = 1) {
    song.put('orch', at(bar, step), I.orch({ ns: Array.isArray(ch) ? ch : table[ch].orch }), gain);
  }

  // a diatonic third under a note in the key (a note out of it falls a major third): the twin
  // lead. The lower voice does not bend (a tone up from under its note would leave the key)
  function under(n) {
    const k = scale.indexOf(n % 12);
    if (k < 0) return n - 4;
    return n - ((n % 12 - scale[(k + 5) % 7] + 12) % 12);
  }
  function harmony(line) {
    return line.split(/\s+/).filter(Boolean).map(t => {
      if (t === '-' || t === '.' || t === '|') return t;
      const m = /^([a-g][#b]?-?\d)(.*)$/.exec(t), n = under(S.note(m[1]));
      return NAMES[n % 12] + (Math.floor(n / 12) - 1) + m[2].replace('^', '');
    }).join(' ');
  }

  // a 16th arpeggio over the chords of a run of bars: idx steps through the stab voicing, `up` octaves higher
  function arp(song, stem, order, bar, idx, up = 1, gain = 1) {
    order.forEach((ch, k) => {
      const v = table[ch].stab;
      for (let s = 0; s < 16; s++) {
        const i = idx[s % idx.length];
        song.put(stem, at(bar + k, s), I.pluck({ n: v[i % v.length] + 12 * (up + Math.floor(i / v.length)), d: song.step * 0.8 }), gain);
      }
    });
  }

  // toms down a run of 16ths from a step
  function toms(song, bar, step, fs, gain = 0.8) {
    fs.forEach((f, k) => song.put('tom', at(bar, step + k), I.tom({ f }), gain + 0.03 * k));
  }

  return { at, steps, bars, drum, voice, chordRoot, rhythm, bassFrom, riff, lead, ring, chords, hit, under, harmony, arp, toms };
};
