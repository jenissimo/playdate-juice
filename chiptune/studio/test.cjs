#!/usr/bin/env node
// The studio's smoke test: a two-bar song renders to a seamless loop at its loudness, under
// -1 dBFS, exactly two bars long; a bank exports its samples, a one-shot without a loop and a
// sustain loop inside its sample.
//   node test.cjs        (expect "N checks, 0 failures")
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const S = require('./synth.cjs');
const { I, CH, G } = require('./instruments.cjs');
const { master } = require('./master.cjs');
const W = require('./compose.cjs')(CH);
const { exportBank } = require('./samples.cjs');

let checks = 0, fails = 0;
function ok(cond, what) { checks++; if (!cond) { fails++; console.log('FAIL: ' + what); } }

const RIFF = 'A2 - - a2 a2 - C3 - - a2 D3 - - a2 C3 - | A2 - - a2 a2 - G2 - - a2 F2 - - - E2 -';
function demo(report) {
  const song = new S.Song({ bpm: 140, bars: 2 });
  W.drum(song, 'kick', I.kick({}), 'x...x...x...x... | x...x...x...x...', 1);
  W.drum(song, 'snare', I.snare({}), '....x.......x... | ....x.......x.xx', 1);
  W.drum(song, 'hat', I.hat({}), '5393539353935393 | 5393539353935393', 1);
  W.rhythm(song, 'gtr', RIFF, 1);
  W.voice(song, 'bass', G.bass, W.bassFrom(RIFF), 1, 1, 0.85);
  W.lead(song, 'lead', 'e5/ - . e5 - . d5 - e5 - . . g5 - a5^ - | g5 - - - e5 - - - . . . . . . . .', 1);
  return master(song, { levels: { kick: -15, snare: -18, hat: -27, gtr: -16, bass: -16.5, lead: -15 },
    verb: { snare: 0.2, lead: 0.14 }, room: { room: 0.6, damp: 0.5 }, pump: -5, gpump: -2, loud: -14.5 }, report);
}

const report = [];
const x = demo(report);
const st = S.stats(x);
ok(report.length > 0, 'the master reports');
ok(Math.abs(st.lufs + 14.5) < 0.6, 'the loop at its loudness, -14.5 LUFS (' + st.lufs.toFixed(2) + ')');
ok(st.peak <= -0.95, 'the loop under -1 dBFS (' + st.peak.toFixed(2) + ')');
ok(x.length === Math.round(2 * 16 * (60 / 140 / 4) * S.SR), 'the loop exactly two bars long');
let step = 0;
for (let j = 1; j < x.length; j++) step = Math.max(step, Math.abs(x[j] - x[j - 1]));
ok(Math.abs(x[0] - x[x.length - 1]) <= step, 'no jump at the seam');

let threw = false;
try { W.voice(new S.Song({ bpm: 120, bars: 1 }), 'lead', G.bass, 'a4 - - | c5', 1); } catch (e) { threw = true; }
ok(threw, 'a bar of the wrong length is an error, not a shifted song');

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'studio-test-'));
const meta = exportBank([
  { name: 'kick', root: 72, loop: false, make: () => I.kick({}) },
  { name: 'bass', root: 33, loop: 'auto', make: () => G.bass({ n: 33, d: 0.8 }) },
], dir);
ok(meta.length === 2 && fs.existsSync(path.join(dir, 'bank.json')) && fs.existsSync(path.join(dir, 'kick.wav')), 'a bank writes its samples and bank.json');
ok(meta[0].loop === null, 'a one-shot has no loop');
const b = meta[1];
ok(b.loop && b.loop[0] > 0 && b.loop[1] === b.length && b.loop[1] - b.loop[0] >= 0.1 * b.rate, 'a sustain loop inside its sample, at least 0.1 s');
ok(Math.abs(b.peak + 1) < 0.05, 'a sample normalised to -1 dBFS (' + b.peak + ')');
fs.rmSync(dir, { recursive: true, force: true });

console.log(checks + ' checks, ' + fails + ' failures');
process.exitCode = fails ? 1 : 0;
