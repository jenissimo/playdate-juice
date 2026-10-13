// The techno-rock band as samples, for a tracker: the guitars through their amps (as
// master.cjs plays them), the synth bass and acid, the pad, the 90s kit, the hits.
//   node ../samples.cjs rock.cjs out/rock [--rate 22050]
// Roots: a guitar chord on A2 (45, its root string), a lead note on A4, the bass on A1; the
// drums unpitched at C5 (72). A tracker transposes from the root.
'use strict';

const S = require('../synth.cjs');
const { I, G } = require('../instruments.cjs');
const { AMPS } = require('../master.cjs');

// a guitar through one of the master's amps, its mix EQ after the cabinet
const amp = (x, name) => S.eq(S.amp(x, AMPS[name]), AMPS[name].post || []);

module.exports = [
  // guitars
  { name: 'gtr_chord', root: 45, loop: false, make: () => amp(G.chord({ n: 45, d: 1.6 }), 'gtr') },
  { name: 'gtr_chord_sus', root: 45, loop: 'auto', make: () => amp(G.chord({ n: 45, d: 1.6 }), 'gtr') },
  { name: 'gtr_chug', root: 45, loop: false, make: () => amp(G.chug({ n: 45, d: 0.2 }), 'gtr') },
  { name: 'gtr_dead', root: 72, loop: false, make: () => amp(G.dead({ n: 45 }), 'gtr') },
  { name: 'gtr_scrape', root: 72, loop: false, make: () => amp(G.scrape({ d: 0.5 }), 'gtr') },
  { name: 'gtr_lead', root: 69, loop: 'auto', make: () => amp(G.note({ n: 69, d: 1.4 }), 'lead') },
  { name: 'gtr_pinch', root: 64, loop: false, make: () => amp(G.note({ n: 64, d: 0.8, mark: '*' }), 'lead') },
  { name: 'gtr_clean', root: 57, loop: false, make: () => amp(G.clean({ n: 57, d: 1.2 }), 'clean') },
  // synths
  { name: 'bass', root: 33, loop: 'auto', make: () => S.eq(G.bass({ n: 33, d: 0.8 }), [['hp', 38, 0.7]]) },
  { name: 'acid', root: 45, loop: false, make: () => G.acid({ n: 45, d: 0.25, acc: 0.6 }) },
  { name: 'pad', root: 57, loop: 'auto', make: () => G.pad({ ns: [57, 60, 64], d: 1.6 }) },
  { name: 'hoover', root: 57, loop: 'auto', make: () => I.hoover({ n: 57, d: 0.8 }) },
  { name: 'stab', root: 57, loop: false, make: () => I.stab({ ns: [57, 60, 64], d: 0.25 }) },
  { name: 'orch_am', root: 57, loop: false, make: () => I.orch({ ns: [57, 64, 69, 72, 76] }) },
  // the kit
  { name: 'kick', root: 72, loop: false, make: () => I.kick({ f0: 240, f1: 52, d: 0.16, click: 0.6 }) },
  { name: 'snare', root: 72, loop: false, make: () => I.snare({ f: 190, nd: 0.15, noise: 1.2, tone: 0.85 }) },
  { name: 'clap', root: 72, loop: false, make: () => I.clap({}) },
  { name: 'hat', root: 72, loop: false, make: () => I.hat({}) },
  { name: 'ohat', root: 72, loop: false, make: () => I.ohat({ d: 0.08, len: 0.32 }) },
  { name: 'crash', root: 72, loop: false, make: () => I.crash({}) },
  { name: 'tom', root: 72, loop: false, make: () => I.tom({ f: 147 }) },
];
