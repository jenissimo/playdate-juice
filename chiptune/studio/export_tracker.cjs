// Record the existing studio arrangement, including instrument calls and the
// master's measured stem gains. Song modules are loaded only after hooks.
'use strict';
const fs = require('fs');
const path = require('path');
const S = require('./synth.cjs');
const instruments = require('./instruments.cjs');
const M = require('./master.cjs');
const { LANES } = require('./prepare_tracker.cjs');

function exportTracker(modulePath, only = null) {
  const OriginalSong = S.Song, originalMaster = M.master, wrappers = [];
  let captured = null;
  for (const group of ['I', 'G']) for (const [name, fn] of Object.entries(instruments[group])) {
    if (typeof fn !== 'function') continue;
    wrappers.push([group, name, fn]);
    instruments[group][name] = function(o = {}) {
      const x = fn(o);
      x.trackerSource = { inst: group + '.' + name, ...o };
      return x;
    };
  }
  class RecordingSong extends OriginalSong {
    constructor(o) { super(o); this.events = []; }
    put(stem, step, buf, gain = 1) {
      if (!buf.trackerSource) throw new Error('untagged instrument on ' + stem + ':' + step);
      const src = JSON.parse(JSON.stringify(buf.trackerSource));
      this.events.push({ stem, step, ...src, gain });
      super.put(stem, step, buf, gain);
    }
  }
  S.Song = RecordingSong;
  M.master = function(song, spec) {
    const stemGains = {}, stemLufs = {};
    const lanes = Array.from({ length: 8 }, () => new Float32Array(song.L));
    for (const [name, raw] of song.stems) {
      let x = song.fold(raw);
      const a = M.AMPS[name];
      if (a) x = S.cyclic(y => S.eq(S.amp(y, a), a.post || []), x);
      else if (M.EQ[name]) x = S.cyclic(y => S.eq(y, M.EQ[name]), x);
      const was = S.lufs(x);
      stemLufs[name] = was;
      stemGains[name] = was > -69 ? S.dB(spec.levels[name] - was) : 1;
      const lane = LANES.findIndex(names => names.includes(name));
      if (lane >= 0) {
        S.scale(x, stemGains[name]);
        S.mix(lanes[lane], x);
        const send = spec.verb[name] || 0;
        if (send) S.mix(lanes[lane], S.cyclic(y => S.reverb(y, spec.room), x), 0, send);
        for (const e of spec.echo || []) if (e.stem === name)
          S.mix(lanes[lane], S.cyclic(y => S.echo(y, { time: e.steps * song.step, fb: e.fb, lp: e.lp || 3000 }), x), 0, e.send);
      }
    }
    captured = { bpm: song.bpm, bars: song.bars, steps: song.steps, spec,
      stemGains, stemLufs, laneTargets: lanes.map(x => S.stats(x)),
      events: song.events.sort((a, b) => a.step - b.step) };
    return new Float32Array(0);
  };
  const resolved = require.resolve(path.resolve(modulePath)), result = {};
  try {
    delete require.cache[resolved];
    const songs = require(resolved);
    for (const [name, fn] of Object.entries(songs)) {
      if (only && !only.includes(name)) continue;
      captured = null; fn();
      if (!captured) throw new Error(name + ': song never called master');
      result[name] = captured;
    }
    return result;
  } finally {
    S.Song = OriginalSong; M.master = originalMaster;
    for (const [group, name, fn] of wrappers) instruments[group][name] = fn;
    delete require.cache[resolved];
  }
}
module.exports = { exportTracker };
if (require.main === module) {
  const [file, dest, ...names] = process.argv.slice(2);
  if (!file || !dest) throw new Error('usage: node export_tracker.cjs songs.cjs out.json [menu play multi]');
  const data = exportTracker(file, names.length ? names : null);
  fs.mkdirSync(path.dirname(path.resolve(dest)), { recursive: true });
  fs.writeFileSync(dest, JSON.stringify(data, null, 1) + '\n');
  for (const [name, s] of Object.entries(data)) console.log(name + ': ' + s.events.length + ' events, ' + s.bars + ' bars, ' + s.bpm + ' BPM');
}
