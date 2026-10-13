// Bake the studio's amp/EQ/send colours into root-specific instruments.
// The event JSON is the sole source for notes and bank membership.
'use strict';
const fs = require('fs');
const path = require('path');
const S = require('./synth.cjs');
const { I, G } = require('./instruments.cjs');
const { AMPS, EQ } = require('./master.cjs');
const { exportBank, autoLoop } = require('./samples.cjs');

const LANES = [ ['gtr'], ['bass'], ['lead'], ['kick'], ['tom', 'snare', 'clap'],
  ['ohat', 'hat'], ['orch', 'crash', 'stab', 'hoover'], ['lead2', 'gtr2', 'clean', 'pluck', 'acid'] ];
const SUSTAIN = new Set(['G.chord', 'G.note', 'G.bass', 'G.clean', 'G.pad', 'I.hoover']);

function selectEvents(song) {
  const groups = new Map(), dropped = [];
  song.events.forEach((event, id) => {
    const lane = LANES.findIndex(stems => stems.includes(event.stem));
    const e = { ...event, id, lane };
    if (lane < 0) { dropped.push({ ...e, reason: 'no lane for optional layer' }); return; }
    const key = lane + ':' + event.step;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(e);
  });
  const selected = [];
  for (const events of groups.values()) {
    events.sort((a, b) => LANES[a.lane].indexOf(a.stem) - LANES[b.lane].indexOf(b.stem) || b.gain - a.gain);
    // A clap under a snare or a hat under an open hat is colour, not another
    // melodic voice. Bake simultaneous percussion into the same instrument
    // so the eight-voice reduction keeps those original hits and velocities.
    if ([4, 5, 6].includes(events[0].lane)) {
      events[0].layers = events.slice(1);
      selected.push(events[0]);
      continue;
    }
    selected.push(events[0]);
    for (const e of events.slice(1)) dropped.push({ ...e, reason: 'simultaneous higher-priority ' + events[0].stem });
  }
  return { selected: selected.sort((a, b) => a.step - b.step || a.lane - b.lane), dropped };
}

function sourceFor(e) {
  const o = { ...e };
  for (const key of ['id', 'stem', 'step', 'gain', 'lane', 'inst', 'layers', 'ratio']) delete o[key];
  let root = e.n ?? 72;
  if (e.inst === 'G.bass') { o.n = root = 33; o.d = 0.6; }
  else if (e.inst === 'G.note') { o.n = root = 69; o.d = 0.7; }
  else if (e.inst === 'G.acid') { o.n = root = 45; o.d = 0.2; }
  else if (e.inst === 'I.pluck') { o.n = root = 69; o.d = 0.2; }
  else if (e.inst === 'I.hoover') { o.n = root = 57; o.d = 0.6; }
  else if (e.inst === 'G.clean') { o.n = root = e.n < 67 ? 60 : 72; o.d = 0.6; }
  else if (e.inst === 'G.chord') { o.d = 0.6; o.up = false; }
  else if (e.inst === 'G.chug') { o.d = 0.18; o.up = false; }
  else if (e.inst === 'I.stab') { o.d = 0.15; root = Math.min(...o.ns); }
  else if (e.inst === 'I.orch') root = Math.min(...o.ns);
  else if (e.inst === 'G.scrape') o.d = 0.35;
  else if (e.inst === 'G.dead') { o.n = root = 45; o.up = false; }
  return { o, root };
}

function trimWet(x) {
  const peak = S.peak(x), window = S.len(0.02), threshold = peak * peak * 0.0001;
  let end = x.length;
  while (end > window) {
    let sum = 0;
    for (let j = end - window; j < end; j++) sum += x[j] * x[j];
    if (sum / window > threshold) break;
    end -= window;
  }
  return S.fadeOut(x.slice(0, Math.min(x.length, end + S.len(0.02))), 0.01);
}

function prepare(songs, directory) {
  const definitions = [], lookup = new Map(), arrangements = {};
  // A shared composite uses the median of the measured stem ratios. The
  // per-loop lane calibration then restores each loop's LUFS target. This
  // avoids a second PCM copy for a sub-dB change in master balance.
  const ratios = new Map();
  for (const song of Object.values(songs)) for (const e of selectEvents(song).selected)
    for (const layer of e.layers || []) {
      const key = e.stem + ':' + layer.stem;
      if (!ratios.has(key)) ratios.set(key, []);
      ratios.get(key).push(song.stemGains[layer.stem] / song.stemGains[e.stem]);
    }
  for (const [key, values] of ratios) { values.sort((a, b) => a - b); ratios.set(key, values[Math.floor(values.length / 2)]); }
  for (const [name, song] of Object.entries(songs)) {
    const { selected, dropped } = selectEvents(song);
    const velocityMax = {};
    for (const e of selected) velocityMax[e.stem] = Math.max(velocityMax[e.stem] || 0, e.gain);
    for (const e of selected) {
      const { o, root } = sourceFor(e);
      if (e.inst === 'I.hoover' && e.layers?.length) o.n = e.n;
      const sustain = SUSTAIN.has(e.inst);
      // The same waveform is shared across loops. Per-loop stem gain stays
      // in the GBM instrument record, rather than making another PCM copy.
      const layers = (e.layers || []).map(layer => ({ ...layer,
        ratio: layer.gain / e.gain * ratios.get(e.stem + ':' + layer.stem) }));
      const key = JSON.stringify([e.stem, e.inst, o, layers.map(l => [l.inst, sourceFor(l).o, l.ratio])]);
      let def = lookup.get(key);
      if (!def) {
        const instName = 'p' + String(definitions.length).padStart(3, '0');
        const high = ['gtr', 'gtr2', 'lead', 'lead2', 'clean', 'hat', 'ohat', 'crash'].includes(e.stem);
        const meta = { key, stem: e.stem, inst: e.inst, sustain, release: sustain ? 30 : 5 };
        def = { name: instName, root: e.inst === 'I.hoover' && e.layers?.length ? e.n : root,
          rate: high ? 22050 : 16384, loop: false, meta,
          make() {
            const [group, fn] = e.inst.split('.');
            let x = (group === 'I' ? I : G)[fn](o).slice();
            const amp = AMPS[e.stem];
            if (amp) x = S.eq(S.amp(x, amp), amp.post || []);
            else if (EQ[e.stem]) x = S.eq(x, EQ[e.stem]);
            const wet = new Float32Array(x.length + S.len(sustain ? 0.1 : 1.3));
            wet.set(x);
            const send = song.spec.verb[e.stem] || 0;
            if (send) S.mix(wet, S.reverb(wet.slice(), song.spec.room), 0, send);
            for (const echo of song.spec.echo || []) if (echo.stem === e.stem)
              S.mix(wet, S.echo(wet.slice(), { time: echo.steps * 60 / song.bpm / 4, fb: echo.fb, lp: echo.lp || 3000 }), 0, echo.send);
            for (const layer of layers) {
              const src = sourceFor(layer).o, [g, f] = layer.inst.split('.');
              if (layer.inst === 'I.hoover' && layer.n !== undefined) src.n = layer.n;
              let y = (g === 'I' ? I : G)[f](src).slice();
              if (EQ[layer.stem]) y = S.eq(y, EQ[layer.stem]);
              const ys = new Float32Array(Math.max(wet.length, y.length + S.len(1.3)));
              ys.set(y);
              const send = song.spec.verb[layer.stem] || 0;
              if (send) S.mix(ys, S.reverb(ys.slice(), song.spec.room), 0, send);
              S.mix(wet, ys, 0, layer.ratio);
            }
            if (sustain) {
              const head = wet.slice(0, Math.min(wet.length, S.len(e.inst === 'G.note' ? 0.65 : 0.5)));
              const bounds = autoLoop(head, def.root);
              def.loop = bounds.map(n => n / S.SR);
              x = head;
            } else x = trimWet(wet);
            meta.rawPeak = S.peak(x);
            meta.rawLufs = S.lufs(x);
            return x;
          } };
        lookup.set(key, def); definitions.push(def);
      }
      e.sample = def.name;
      e.root = def.root;
      e.sustain = sustain;
      e.note = e.n ?? def.root;
      e.velocityMax = velocityMax[e.stem];
      const next = selected.find(other => other.lane === e.lane && other.step > e.step);
      const first = selected.find(other => other.lane === e.lane);
      const gap = (next ? next.step - e.step : song.steps - e.step + first.step) * 60 / song.bpm / 4;
      const pitchRatio = 2 ** ((e.note - def.root) / 12);
      def.meta.maxLife = Math.max(def.meta.maxLife || 0, (gap + def.meta.release / 1000) * pitchRatio);
    }
    arrangements[name] = { ...song, selected, dropped };
  }
  const bank = exportBank(definitions, directory);
  const output = { songs: arrangements, bank };
  fs.writeFileSync(path.join(directory, 'port.json'), JSON.stringify(output, null, 1) + '\n');
  let bytes = 0;
  for (const sample of bank) bytes += sample.length;
  console.log(bank.length + ' instruments, ' + bytes + ' PCM8 bytes');
  for (const [name, a] of Object.entries(arrangements)) console.log(name + ': ' + a.selected.length + ' kept, ' + a.dropped.length + ' dropped');
  return output;
}
module.exports = { prepare, selectEvents, LANES };
if (require.main === module) {
  const [events, directory] = process.argv.slice(2);
  if (!events || !directory) throw new Error('usage: node prepare_tracker.cjs events.json outdir');
  prepare(JSON.parse(fs.readFileSync(events, 'utf8')), directory);
}
