// The README's example: four bars of techno rock -- the kit, a riff of chords and chugs, the
// bass under it, a lead with a scoop and a bend, an orchestra hit.
//   node ../render.cjs example.cjs --out out --preview preview --mix
'use strict';

const S = require('../synth.cjs');
const { I, CH, G } = require('../instruments.cjs');
const { master } = require('../master.cjs');
const W = require('../compose.cjs')(CH);           // the chord table and the key (A minor)

function theme(report) {
  const song = new S.Song({ bpm: 140, bars: 4 });  // 16ths; stems fold into a seamless loop
  const K = I.kick({ f0: 240, f1: 52, d: 0.16, click: 0.6 });
  for (let bar = 1; bar <= 4; bar++) {
    W.drum(song, 'kick', K, 'x...x...x...x...', bar);
    W.drum(song, 'snare', I.snare({}), '....x.......x...', bar);
    W.drum(song, 'hat', I.hat({}), '5393539353935393', bar);
  }
  const RIFF = W.bars('A2 - - a2 a2 - C3 - - a2 D3 - - a2 C3 -', 'A2 - - a2 a2 - G2 - - a2 F2 - - - E2 -');
  W.rhythm(song, 'gtr', RIFF, 1); W.rhythm(song, 'gtr', RIFF, 3);
  W.voice(song, 'bass', G.bass, W.bassFrom(RIFF + ' | ' + RIFF), 1, 1, 0.85);
  W.lead(song, 'lead', W.bars('e5/ - . e5 - . d5 - e5 - . . g5 - a5^ -', 'g5 - - - e5 - - - . . . . . . . .'), 3);
  W.hit(song, 'Am', 1);
  return master(song, {
    levels: { kick: -15, snare: -18, hat: -27, gtr: -16, bass: -16.5, lead: -15, orch: -17 },
    verb: { snare: 0.22, lead: 0.14, orch: 0.3 }, room: { room: 0.6, damp: 0.5 },
    echo: [{ stem: 'lead', steps: 3, fb: 0.3, send: 0.2 }], pump: -5, gpump: -2, loud: -14.5,
  }, report);
}

module.exports = { theme };
