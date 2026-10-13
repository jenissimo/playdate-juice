// Shared band for the live PCM tracker demos: rock, jungle and trance.
'use strict';
const S = require('../synth.cjs');
const { I, G } = require('../instruments.cjs');
module.exports = [...require('./rock.cjs'),
  { name: 'reese', root: 45, loop: 'auto', make: () => S.tone({ n: 45, len: 1.0,
    wave: 'saw', uni: 2, spread: 28, cut: 1300, q: 0.8, drive: 2.6,
    a: 0.006, d: 0.1, s: 0.9, r: 0.025 }) },
  { name: 'trance_saw', root: 60, loop: 'auto', make: () => S.tone({ n: 60, len: 1.1,
    wave: 'saw', uni: 7, spread: 17, cut: 3400, q: 0.8, drive: 1.2,
    a: 0.006, d: 0.18, s: 0.8, r: 0.08 }) },
  { name: 'trance_pluck', root: 69, loop: false, make: () => I.pluck({ n: 69, d: 0.23 }) },
  { name: 'pad_f', root: 53, loop: 'auto', make: () => G.pad({ ns: [57, 60, 65], d: 1.3 }) },
  { name: 'pad_g', root: 55, loop: 'auto', make: () => G.pad({ ns: [59, 62, 67], d: 1.3 }) },
];
