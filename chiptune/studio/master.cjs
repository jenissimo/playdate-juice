// Mastering a loop: a Song's stems into one seamless, finished loop.
//
// Each stem is folded into one lap; a guitar's stem goes through its amp (cyclic: the loop as
// if it had always been looping), any other through its EQ; each is brought to its loudness
// (LUFS while it sounds) -- a mix by numbers, the same on every render -- then: a room and
// echoes on the stems that send to them, the drums glued with a slow-attack compressor (the
// click passes, the body is held), the bed pumping under the kick and the guitars a little, a
// gentle glue over the whole, the loudness, a soft clip of the rare pile-ups, a limiter at
// -1 dBFS. With a report array it says each stem's loudness, the buses' gain reduction, how
// hard the clip and the limiter work and where, the bands.
//
// spec = {
//   levels: { stem: LUFS },            every stem must have one
//   verb: { stem: send }, room: { room, damp },
//   echo: [{ stem, steps, fb, send, lp }],
//   pump: dB, gpump: dB,               the bed's and the guitars' dip under each kick
//   loud: LUFS,                        the loop's loudness (-14.5 for Overturn)
//   amps: { stem: preset } | false,    merged over AMPS; false: no amps (a song with no guitars)
//   eq: { stem: [[type, f, q, gain]] } | false,   merged over EQ; false: none
//   drums: Set,                        the stems on the drum bus (default DRUMS)
// }
'use strict';

const S = require('./synth.cjs');
const { dB } = S;

const DRUMS = new Set(['kick', 'snare', 'clap', 'hat', 'ohat', 'crash', 'tom', 'riser']);

// the amps: the rhythm guitars tight and mid-forward, the lead with more gain and a singing
// mid, the clean(er) guitar barely breaking up. `post`: the mix's EQ after the cabinet -- the
// rhythm guitars leave the lows to the bass and the kick.
const AMPS = {
  gtr: { gain: 26, tight: 130, mid: [800, 5], cab: { box: [400, -1] }, post: [['hp', 150, 0.7], ['peak', 170, 0.8, -2.5]] },
  gtr2: { gain: 24, tight: 160, mid: [900, 5], post: [['hp', 220, 0.7]] },
  lead: { gain: 30, tight: 200, mid: [900, 7], fizz: 7000, bias: 0.35, cab: { pres: [2500, 4, 0.7], lp: 5500 }, post: [['hp', 180, 0.7]] },
  clean: { gain: -6, tight: 90, mid: [700, 2], fizz: 7000, bias: 0.1, hard: 1, cab: { hp: 80, pres: [2600, 3, 0.7], box: [450, -1], lp: 6000 } },
};
AMPS.lead2 = AMPS.lead;

// the other stems' EQ before they are levelled: the pluck's pulse carries DC, nothing else
// needs anything under the bass's lowest note
const EQ = {
  pluck: [['hp', 150, 0.7]], stab: [['hp', 120, 0.7]], pad: [['hp', 150, 0.7]], acid: [['hp', 70, 0.7]],
  bass: [['hp', 38, 0.7]], hoover: [['hp', 100, 0.7]],
};

function master(song, spec, report) {
  const L = song.L, names = [...song.stems.keys()];
  const amps = spec.amps === false ? {} : Object.assign({}, AMPS, spec.amps || {});
  const eqs = spec.eq === false ? {} : Object.assign({}, EQ, spec.eq || {});
  const drumSet = spec.drums || DRUMS;
  const stems = new Map();
  for (const name of names) {
    let x = song.fold(song.stem(name));
    const a = amps[name];
    if (a) x = S.cyclic(y => S.eq(S.amp(y, a), a.post || []), x);
    else if (eqs[name]) x = S.cyclic(y => S.eq(y, eqs[name]), x);
    const want = spec.levels[name];
    if (want === undefined) throw new Error('no level for stem ' + name);
    const was = S.lufs(x);
    if (was > -69) S.scale(x, dB(want - was));
    stems.set(name, x);
    if (report) report.push(name.padEnd(9) + ' ' + was.toFixed(1).padStart(6) + ' -> ' + want);
  }
  const send = new Float32Array(L);
  for (const [name, amt] of Object.entries(spec.verb || {})) if (stems.has(name)) S.mix(send, stems.get(name), 0, amt);
  const wets = [S.cyclic(x => S.reverb(x, spec.room || {}), send)];
  for (const e of spec.echo || []) {
    if (stems.has(e.stem)) wets.push(S.scale(S.cyclic(x => S.echo(x, { time: e.steps * song.step, fb: e.fb, lp: e.lp ?? 3000 }), stems.get(e.stem)), e.send));
  }
  const drums = new Float32Array(L), bed = new Float32Array(L), gtrs = new Float32Array(L);
  for (const name of names) S.mix(drumSet.has(name) ? drums : amps[name] ? gtrs : bed, stems.get(name));
  for (const w of wets) S.mix(bed, w);
  let grDrums = 0, grGlue = 0;
  const punch = S.cyclic(x => { const y = S.compress(x, { thr: -14, ratio: 3, att: 0.012, rel: 0.09, knee: 6, makeup: 2 }); grDrums = y.grMax; return y; }, drums);
  const g = S.pump(L, song.kicks, { depth: spec.pump ?? -6, rel: 0.11 }), gg = S.pump(L, song.kicks, { depth: spec.gpump ?? -2, rel: 0.09 });
  for (let j = 0; j < L; j++) { bed[j] *= g[j]; gtrs[j] *= gg[j]; }
  let out = new Float32Array(L);
  S.mix(out, punch); S.mix(out, bed); S.mix(out, gtrs);
  // nothing under 40 Hz: no speaker plays it, and it eats the limiter's headroom
  out = S.cyclic(x => S.filter(S.filter(x, 'hp', 40, 0.707), 'hp', 40, 0.707), out);
  S.scale(out, dB(-16 - S.lufs(out)));
  out = S.cyclic(x => { const y = S.compress(x, { thr: -12, ratio: 2, att: 0.02, rel: 0.2, knee: 8 }); grGlue = y.grMax; return y; }, out);
  S.scale(out, dB(spec.loud - S.lufs(out)));
  // where every attack lands at once (a kick, the backbeat, a chord and the bass on beat 4) the
  // sum's top 3 dB are rounded off sample by sample -- a few milliseconds of soft clipping
  // under distorted guitars -- rather than the limiter ducking everything for 60 ms after them
  const intoClip = S.peak(out), t = dB(-3);
  let clipped = 0;
  for (let j = 0; j < L; j++) {
    const a = Math.abs(out[j]);
    if (a > t) { out[j] = Math.sign(out[j]) * (t + (1 - t) * Math.tanh((a - t) / (1 - t))); clipped++; }
  }
  S.scale(out, dB(spec.loud - S.lufs(out)));
  const pre = S.peak(out);
  // where the limiter works: the bars of the worst peaks, and (below) the time it spends over 0.5 dB of reduction
  const worst = [], into = out;
  for (let j = 0; j < L; j++) {
    const a = Math.abs(out[j]);
    if (a > dB(-1)) {
      const w = worst[worst.length - 1], st = Math.floor(j / song.at(1));
      if (w && st - w.st < 2) { if (a > w.a) Object.assign(w, { a, st }); } else worst.push({ a, st });
    }
  }
  worst.sort((p, q) => q.a - p.a);
  out = S.cyclic(x => S.limit(x, dB(-1)), out);
  let over = 0, seen = 0;
  for (let j = 0; j < L; j++) if (Math.abs(into[j]) > 0.05) { seen++; if (Math.abs(out[j]) < Math.abs(into[j]) * dB(-0.5)) over++; }
  if (report) {
    const st = S.stats(out);
    report.push('drum bus GR ' + grDrums.toFixed(1) + ' dB, glue GR ' + grGlue.toFixed(1) + ' dB, peak into the clipper ' + S.toDb(intoClip).toFixed(1) +
      ' dBFS (it rounds ' + (100 * clipped / L).toFixed(3) + '% of the samples), into the limiter ' + S.toDb(pre).toFixed(1) +
      ' dBFS (limiter GR ' + Math.max(0, S.toDb(pre) + 1).toFixed(1) + ' dB, over 0.5 dB GR ' + (100 * over / Math.max(1, seen)).toFixed(2) + '% of the time; worst at ' +
      worst.slice(0, 5).map(w => (1 + (w.st >> 4)) + ':' + (w.st & 15) + ' ' + S.toDb(w.a).toFixed(1)).join(', ') + ')');
    report.push('out ' + st.lufs.toFixed(1) + ' LUFS, peak ' + st.peak.toFixed(1) + ' dBFS, bands <100 ' + st.bands.map(v => v.toFixed(1)).join(' ') + ' >8k');
  }
  return out;
}

module.exports = { master, AMPS, EQ, DRUMS };
