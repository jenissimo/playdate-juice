// Overturn's first soundtrack (2026, commit f26c1b6): three loops of 90s tracker rave after
// Psycho Pinball -- a hard-hitting kit, orchestra hits, rave stabs and hoovers, a galloping saw
// bass, a square lead, a calliope for the fairground -- in A minor.
//   menu   attract mode, 140 BPM, 16 bars: the hook, a circus march, the hook again
//   play   the table, 136 BPM, 32 bars: a groove, the hook, a breakdown that builds, the hook doubled
//   multi  multiball, 168 BPM, 16 bars: a breakbeat, hoovers, a siren lead, a chromatic climb
// Mastered here by master.cjs without its amps and stem EQ; the original's own master folded the
// stems after their sends and had no soft clip, so a render differs from the shipped files by
// that much.
'use strict';

const S = require('../synth.cjs');
const { I, CH } = require('../instruments.cjs');
const { master: masterWith } = require('../master.cjs');
const { at, drum, voice, riff, chords, hit, harmony, arp } = require('../compose.cjs')(CH, { bassDown: false });
const master = (song, spec, report) => masterWith(song, Object.assign({ amps: false, eq: false }, spec), report);

// stem loudness, LUFS: the kit and the bass lead, the stabs sit under the tune
const LEVELS = {
  kick: -15, snare: -17.5, clap: -19, hat: -28, ohat: -26, crash: -25, tom: -18, riser: -24,
  bass: -16.5, lead: -16, lead2: -21, calliope: -16.5, brass: -20, pluck: -25, hoover: -18,
  stab: -22, organ: -21, orch: -16.5,
};
const VERB = { snare: 0.25, clap: 0.35, orch: 0.3, lead: 0.12, lead2: 0.12, calliope: 0.2, brass: 0.2, stab: 0.2, organ: 0.15, tom: 0.2 };

// ---------------------------------------------------------------- menu: attract mode

function menu(report) {
  const song = new S.Song({ bpm: 140, bars: 16 });
  const ORDER = ['Am', 'Am', 'F', 'G', 'Am', 'Am', 'F', 'E', 'Dm', 'Am', 'Dm', 'E', 'Am', 'Am', 'F', 'E'];
  const K = I.kick({ f0: 260, d: 0.14 }), SN = I.snare({}), CL = I.clap({}), HH = I.hat({}), OH = I.ohat({ d: 0.07, len: 0.3 }), CR = I.crash({});

  // the hook's sections: four on the floor, a clap on the backbeat, open hats on the off-beats
  for (const bar of [1, 2, 3, 4, 5, 6, 7, 8, 13, 14, 15, 16]) {
    drum(song, 'kick', K, bar === 8 ? 'x...x...x...x.x.' : bar === 16 ? 'x...x...x.......' : 'x...x...x...x...', bar);
    drum(song, 'snare', SN, bar === 4 ? '....x.......x.ox' : bar === 8 ? '....x.......xxXX' : bar === 16 ? '....x...........' : '....x.......x...', bar);
    drum(song, 'clap', CL, bar === 16 ? '....x...........' : '....x.......x...', bar);
    drum(song, 'hat', HH, bar === 16 ? '.o.o.o.o........' : '.o.o.o.o.o.o.o.o', bar);
    drum(song, 'ohat', OH, bar === 16 ? '..x...x.........' : '..x...x...x...x.', bar);
  }
  // the circus march: the bass drum on the beat, the snare on the off-beat, a roll into the hook
  for (const bar of [9, 10, 11, 12]) {
    drum(song, 'kick', K, 'x...x...x...x...', bar);
    drum(song, 'snare', SN, bar === 12 ? '..x...x.5678xxXX' : '..x..ox...x..ox.', bar);
  }
  for (const bar of [1, 5, 9, 13]) drum(song, 'crash', CR, 'x', bar);
  // bar 16: toms down with the run
  [262, 233, 208, 196, 175, 156, 139, 123].forEach((f, k) => song.put('tom', at(16, 8 + k), I.tom({ f: f / 2 }), 0.7 + 0.04 * k));

  // the bass: a galloping octave in the hook, oom-pah in the march, a run down into the top
  ORDER.forEach((ch, k) => {
    const bar = k + 1;
    let line;
    if (bar >= 9 && bar <= 11) line = riff('R - . . 5 - . . R - . . 5 - . .', ch);
    else if (bar === 12) line = riff('R - . . R - . . R - . . R . R R', ch);
    else if (bar === 16) line = 'e2 . e2 e3 . e2 e3 . e3 d3 c3 b2 c3 b2 a2 g#2';
    else line = riff('R . R O . R O . R . R O . R O R', ch);
    voice(song, 'bass', I.bass, line, bar, 1, 0.8);
  });

  // stabs on the off-beat eighths in the hook; the calliope's chords on them in the march
  ORDER.forEach((ch, k) => {
    const bar = k + 1;
    if (bar >= 9 && bar <= 12) chords(song, 'organ', I.organ, '..x...x...x...x.', bar, ch);
    else if (bar !== 16) chords(song, 'stab', I.stab, '..x...x...x...x.', bar, ch);
  });

  // the hook (bars 1-8, again 13-16): a dotted 3-3-2 figure, up the octave the second time
  const HOOK = [
    'a4 - - a4 - - c5 - e5 - - d5 - - c5 -', 'd5 - - c5 - - a4 - g4 - - - a4 - . .',
    'a4 - - a4 - - c5 - f5 - - e5 - - c5 -', 'd5 - - - b4 - - - g4 - b4 - d5 - g5 -',
    'e5 - - e5 - - a5 - c6 - - b5 - - a5 -', 'g5 - - e5 - - c5 - d5 - - - e5 - . .',
    'f5 - - e5 - - c5 - a4 - - c5 - - f5 -', 'e5 - - . . . . . g#4 - b4 - d5 - e5 -',
  ];
  voice(song, 'lead', I.lead, HOOK.join(' | '), 1);
  voice(song, 'lead', I.lead, HOOK.slice(0, 3).join(' | ') + ' | b4 - - g#4 - - e4 - e5 d5 c5 b4 c5 b4 a4 g#4', 13);
  voice(song, 'brass', I.brass, HOOK.slice(0, 3).map(harmony).join(' | '), 13);
  // the march: a calliope with a chromatic wobble, and a diminished fall on orchestra hits
  voice(song, 'calliope', I.calliope, [
    'a5 - g#5 a5 - . f5 - d5 - . f5 a5 - - .', 'e5 - d#5 e5 - . c5 - a4 - . c5 e5 - - .',
    'f5 - e5 f5 - . a5 - d6 - . c6 a5 - f5 -', 'g#5 - - - f5 - - - d5 - - - b4 - g#4 -',
  ].join(' | '), 9);

  // orchestra hits: the downbeats of the sections, the E's three knocks, the diminished fall
  hit(song, 'Am', 1); hit(song, 'F', 3); hit(song, 'G', 4);
  hit(song, 'Am', 5); hit(song, 'F', 7); hit(song, 'E', 8, 0); hit(song, 'E', 8, 3); hit(song, 'E', 8, 6);
  hit(song, 'Dm', 9); hit(song, 'Dm', 11);
  [[56, 62, 65, 68], [53, 59, 62, 65], [50, 56, 59, 62], [47, 53, 56, 59]].forEach((ns, k) => hit(song, ns, 12, k * 4, 0.9));
  hit(song, 'Am', 13); hit(song, 'F', 15); hit(song, 'E', 16);

  return master(song, {
    levels: LEVELS, verb: VERB, room: { room: 0.62, damp: 0.5 },
    echo: [{ stem: 'lead', steps: 3, fb: 0.3, send: 0.22 }], pump: -6, loud: -14.5,
  }, report);
}

// ---------------------------------------------------------------- play: the table

function play(report) {
  const song = new S.Song({ bpm: 136, bars: 32 });
  const GROOVE = ['Am', 'Am', 'C', 'D', 'Am', 'Am', 'F', 'G'];
  const HOOKCH = ['Am', 'F', 'C', 'G', 'Am', 'F', 'G', 'E'];
  const BREAK = ['Dm', 'Dm', 'F', 'F', 'Dm', 'Dm', 'E', 'E'];
  const ORDER = [...GROOVE, ...HOOKCH, ...BREAK, ...HOOKCH];
  const K = I.kick({ f0: 250, d: 0.15 }), SN = I.snare({ f: 175 }), CL = I.clap({}), HH = I.hat({}), OH = I.ohat({ d: 0.09, len: 0.35 }), CR = I.crash({});

  // drums
  for (let bar = 1; bar <= 32; bar++) {
    const half = bar >= 17 && bar <= 20, build = bar === 23 || bar === 24;
    drum(song, 'kick', K, half ? 'x.........x.....' : bar === 16 || bar === 32 ? 'x...x...x...x.x.' : 'x...x...x...x...', bar);
    if (half) drum(song, 'snare', SN, '........x.......', bar);
    else if (bar === 23) drum(song, 'snare', SN, '4.4.5.5.6.6.7.7.', bar);
    else if (bar === 24) drum(song, 'snare', SN, '6767787889x9xXXX', bar);
    else if (bar === 16) drum(song, 'snare', SN, '....x.......xxXX', bar);
    else if (bar >= 5) drum(song, 'snare', SN, '....x.......x...', bar);
    if (!half && !build) drum(song, 'clap', CL, '....x.......x...', bar);
    if (half) drum(song, 'hat', HH, 'x.x.x.x.x.x.x.x.', bar, 0.7);
    else drum(song, 'hat', HH, 'xoxoxoxoxoxoxoxo', bar, 0.8);
    if (!half && bar >= 3 && bar !== 32) drum(song, 'ohat', OH, bar % 2 === 0 ? '..x...x...x...x.' : '..x...x...x.....', bar);
  }
  for (const bar of [1, 9, 13, 17, 21, 25, 29]) drum(song, 'crash', CR, 'x', bar);
  song.put('riser', at(23), I.riser({ len: song.step * 32 }));
  [196, 175, 156, 131].forEach((f, k) => song.put('tom', at(32, 12 + k), I.tom({ f: f / 2 }), 0.8 + 0.05 * k));

  // the bass: off the beat, between the kicks; long roots in the breakdown
  ORDER.forEach((ch, k) => {
    const bar = k + 1;
    const line = bar >= 17 && bar <= 20 ? riff('R - - - - - - - R - - - O - - -', ch) : riff('. . R . . R O . . . R . . R O 7', ch);
    voice(song, 'bass', I.slap, line, bar, 1, 0.8);
  });

  // stabs: a 3-3 push on the odd bars, its answer on the even ones (not in the breakdown)
  ORDER.forEach((ch, k) => {
    const bar = k + 1;
    if (bar >= 17 && bar <= 24) return;
    chords(song, 'stab', I.stab, bar % 2 ? 'x..x..x.........' : '..........x..x..', bar, ch);
  });
  // a 16th arpeggio under the second half of the groove and the doubled hook
  arp(song, 'pluck', GROOVE.slice(4), 5, [0, 1, 2, 3, 2, 1, 2, 3]);
  arp(song, 'pluck', HOOKCH, 25, [0, 2, 1, 3, 2, 4, 3, 1]);

  // the hook: call and answer (bars 9-16), the same doubled a third under (25-32)
  const HOOK = [
    'a4 - . c5 - . e5 - . d5 - . c5 - a4 -', 'c5 - - - . . a4 - - - . . . . . .',
    'g4 - . c5 - . e5 - . g5 - . e5 - c5 -', 'd5 - - - . . b4 - - - . . . . . .',
    'a4 - . c5 - . e5 - . a5 - . g5 - e5 -', 'f5 - - - e5 - - - c5 - - - a4 - - -',
    'b4 - . d5 - . g5 - . f5 - . e5 - d5 -', 'e5 - - - - - - - g#4 - - - b4 - - -',
  ].join(' | ');
  voice(song, 'lead', I.lead, HOOK, 9);
  voice(song, 'lead', I.lead, HOOK, 25);
  voice(song, 'lead2', I.lead, harmony(HOOK), 25);

  // the breakdown: brass holding the chords, the calliope's tune, hits on the changes
  BREAK.forEach((ch, k) => { if (k % 2 === 0) for (const n of CH[ch].stab) song.put('brass', at(17 + k), I.brass({ n, d: song.step * 30 }), 0.6); });
  voice(song, 'calliope', I.calliope, [
    'd5 - - - f5 - - - a5 - - - g#5 - a5 -', 'f5 - - - d5 - - - . . . . . . . .',
    'c5 - - - f5 - - - a5 - - - g5 - f5 -', 'e5 - - - c5 - - - . . . . . . . .',
    'd5 - f5 - a5 - d6 - c6 - a5 - f5 - d5 -', 'f5 - e5 - d5 - c5 - b4 - a4 - g#4 - a4 -',
    'b4 - - - g#4 - - - e5 - - - d5 - - -', 'g#5 - - - - - - - . . . . . . . .',
  ].join(' | '), 17);
  hit(song, 'Am', 9); hit(song, 'Am', 13); hit(song, 'Dm', 17); hit(song, 'F', 19); hit(song, 'Dm', 21);
  hit(song, 'E', 23, 0); hit(song, 'E', 23, 3); hit(song, 'E', 23, 6);
  hit(song, 'Am', 25); hit(song, 'Am', 29); hit(song, 'E', 32, 0, 0.9);

  return master(song, {
    levels: Object.assign({}, LEVELS, { kick: -15.5, lead: -16.5 }), verb: VERB, room: { room: 0.55, damp: 0.55 },
    echo: [{ stem: 'lead', steps: 3, fb: 0.28, send: 0.2 }], pump: -5, loud: -14.5,
  }, report);
}

// ---------------------------------------------------------------- multi: multiball

function multi(report) {
  const song = new S.Song({ bpm: 168, bars: 16 });
  const ORDER = ['Am', 'Am', 'F', 'G', 'Am', 'Am', 'F', 'E', 'F', 'G', 'G#o', 'Am', 'Am', 'Am', 'F', 'E'];
  const K = I.kick({ f0: 280, d: 0.12, len: 0.32 }), SN = I.snare({ f: 200, nd: 0.11 }), HH = I.hat({}), OH = I.ohat({ d: 0.07, len: 0.28 }), CR = I.crash({});

  // a breakbeat all through, four on the floor under it where the lead plays
  for (let bar = 1; bar <= 16; bar++) {
    const fill = bar === 8 || bar === 16 || bar === 12;
    drum(song, 'kick', K, 'x.x.......xx....', bar);
    if ((bar >= 5 && bar <= 8) || bar >= 13) drum(song, 'kick', K, 'x...x...x...x...', bar, 0.8);
    drum(song, 'snare', SN, fill ? '....X..o.oxxXXXX' : '....X..o.o..X..o', bar);
    drum(song, 'hat', HH, 'x.x.x.x.x.x.x.x.', bar);
    drum(song, 'ohat', OH, '..............x.', bar);
  }
  for (const bar of [1, 5, 9, 13]) drum(song, 'crash', CR, 'x', bar);
  song.put('riser', at(11), I.riser({ len: song.step * 32 }));
  song.put('riser', at(16), I.riser({ len: song.step * 16, f0: 800 }));

  // the bass: eighths, root and octave
  ORDER.forEach((ch, k) => voice(song, 'bass', I.bass, riff('R . O . R . O . R . O . R . O .', ch), k + 1, 1, 0.8));

  // hoovers carry bars 1-4 and the climb (9-12), a fifth stacked on the root
  const HOOV = [
    'a3 - - a3 - - a3 - - - a3 - g3 - a3 -', 'a3 - - a3 - - a3 - c4 - - - b3 - g3 -',
    'f3 - - f3 - - f3 - - - f3 - e3 - f3 -', 'g3 - - g3 - - g3 - b3 - - - d4 - b3 -',
  ];
  const CLIMB = ['f3 - - f3 - - f3 - - - f3 - - - f3 -', 'g3 - - g3 - - g3 - - - g3 - - - g3 -',
    'g#3 - - g#3 - - g#3 - - - g#3 - - - g#3 -', 'a3 - - a3 - - a3 - . . . . . . . .'];
  for (const [lines, bar] of [[HOOV, 1], [CLIMB, 9]]) {
    voice(song, 'hoover', I.hoover, lines.join(' | '), bar, 1, 0.85);
    voice(song, 'hoover', I.hoover, lines.map(l => l.split(' ').map(t => (t === '-' || t === '.') ? t : String(S.note(t) + (t.startsWith('g#') ? 6 : 7))).join(' ')).join(' | '), bar, 0.7, 0.85);
  }
  // stabs on the off-beats under the siren
  ORDER.forEach((ch, k) => { const bar = k + 1; if ((bar >= 5 && bar <= 8) || bar >= 13) chords(song, 'stab', I.stab, '..x...x...x...x.', bar, ch); });

  // the siren: fifths and octaves going round
  const SIREN = [
    'e5 - a5 - e5 - a5 - c6 - b5 - a5 - e5 -', 'g5 - - - e5 - - - a5 - - - - - - -',
    'f5 - a5 - f5 - a5 - c6 - a5 - f5 - c5 -', 'b5 - - - g#5 - - - e5 - - - . . . .',
  ];
  voice(song, 'lead', I.lead, SIREN.join(' | '), 5);
  voice(song, 'lead', I.lead, [
    'c6 - - - a5 - - - f5 - - - a5 - c6 -', 'd6 - - - b5 - - - g5 - - - b5 - d6 -',
    'd6 - - - b5 - - - g#5 - - - f5 - d5 -', 'e5 - - - - - - - . . . . . . . .',
  ].join(' | '), 9);
  voice(song, 'lead', I.lead, SIREN.slice(0, 3).join(' | ') + ' | b5 - - - g#5 - - - e5 - g#5 - b5 - d6 -', 13);

  hit(song, 'Am', 1); hit(song, 'Am', 5); hit(song, 'F', 7); hit(song, 'E', 8);
  hit(song, 'F', 9); hit(song, 'G', 10); hit(song, 'G#o', 11); hit(song, 'Am', 12, 0); hit(song, 'Am', 12, 3); hit(song, 'Am', 12, 6);
  hit(song, 'Am', 13); hit(song, 'F', 15); hit(song, 'E', 16); hit(song, 'E', 16, 8);

  return master(song, {
    levels: Object.assign({}, LEVELS, { snare: -16.5, hat: -26 }), verb: VERB, room: { room: 0.5, damp: 0.5 },
    echo: [{ stem: 'lead', steps: 3, fb: 0.25, send: 0.18 }], pump: -7, loud: -14.5,
  }, report);
}

module.exports = { menu, play, multi };
