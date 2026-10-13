// Overturn's techno rock (2026): three loops after the Amiga pinball tracker tunes (Psycho
// Pinball's) -- four-on-the-floor techno drums with rock fills and crashes, distorted electric
// guitars (instruments.cjs G: plucked strings, each guitar's stem through one amp in master.cjs),
// a synth bass locked to the kick, a lead guitar for the hooks, rave stabs, an acid line,
// orchestra hits -- all in A minor, the key Overturn's target bells (the A minor pentatonic) ring in.
//   menu   attract mode, 140 BPM, 16 bars: the riff, the hook, a techno break, the hook in twin leads
//   play   the table, 132 BPM, 32 bars: a chugging groove, the riff, the hook, a breakdown that
//          builds, the hook doubled
//   multi  multiball, 166 BPM, 16 bars: the big riff, a lead over it, a chromatic climb, the lead in thirds
// Each returns one mastered loop (-14.5 LUFS) that runs seamlessly into its own start.
//   node ../render.cjs overturn_rock.cjs --out out --prefix music_ --adpcm --preview preview --mix
'use strict';

const S = require('../synth.cjs');
const { I, CH, G } = require('../instruments.cjs');
const { master, AMPS } = require('../master.cjs');
const { dB } = S;

// the chord table and two more for the rock loops: B flat (the phrygian step down onto A) and A flat
const CHX = Object.assign({}, CH, {
  Bb: { bass: 46, stab: [58, 62, 65], orch: [46, 53, 58, 62, 65] },
  Ab: { bass: 44, stab: [56, 60, 63], orch: [44, 51, 56, 60, 63] },
});

const { at, bars, drum, voice, rhythm, bassFrom, riff, lead, ring, chords, hit, harmony, arp, toms } =
  require('../compose.cjs')(CHX, { bassDown: true });

// stem loudness, LUFS: the kit and the guitars lead, the bass under them, colour under that
const LEVELS = {
  kick: -15, snare: -18, clap: -20.5, hat: -27, ohat: -26.5, crash: -25, tom: -18, riser: -25,
  bass: -16.5, gtr: -16, gtr2: -21, lead: -15, lead2: -20.5, clean: -19.5, pad: -24, acid: -21.5,
  stab: -21.5, pluck: -24.5, orch: -17, hoover: -20,
};
const VERB = { snare: 0.22, clap: 0.3, tom: 0.2, orch: 0.3, lead: 0.14, lead2: 0.14, clean: 0.3, pad: 0.3, stab: 0.2, pluck: 0.15, hoover: 0.15 };

// ---------------------------------------------------------------- menu: attract mode

function menu(report) {
  const song = new S.Song({ bpm: 140, bars: 16 });
  const K = I.kick({ f0: 240, f1: 52, d: 0.16, click: 0.6 }), SN = I.snare({ f: 190, nd: 0.15, noise: 1.2, tone: 0.85 });
  const CL = I.clap({}), HH = I.hat({}), OH = I.ohat({ d: 0.08, len: 0.32 }), CR = I.crash({});

  // drums: four on the floor, the snare and a clap on the backbeat (the clap alone in the
  // techno break), 16th hats leaning on the off-beat, open hats between the kicks
  for (let bar = 1; bar <= 16; bar++) {
    const brk = bar >= 9 && bar <= 12;
    drum(song, 'kick', K, bar === 16 ? 'x...x...x.......' : 'x...x...x...x...', bar);
    if (!brk) drum(song, 'snare', SN, bar === 4 ? '....x.......x.xx' : bar === 8 ? '....x.......x...' : bar === 16 ? '....x...........' : '....x.......x...', bar);
    if (bar === 12) drum(song, 'snare', SN, '4.4.5.5.67677889', bar);
    drum(song, 'clap', CL, bar === 16 || bar === 12 ? '....x...........' : '....x.......x...', bar);
    drum(song, 'hat', HH, bar === 16 ? '53935393........' : '5393539353935393', bar);
    drum(song, 'ohat', OH, bar === 16 ? '..x...x.........' : '..x...x...x...x.', bar);
  }
  for (const bar of [1, 5, 9, 13]) drum(song, 'crash', CR, 'x', bar);
  toms(song, 8, 12, [220, 175, 147, 110]);
  toms(song, 16, 8, [262, 220, 196, 165, 147, 131, 110, 98], 0.75);
  song.put('riser', at(11), I.riser({ len: song.step * 32 }));

  // the riff (bars 1-4): A, chug-chug, C, chug, D, chug, C -- answered A, G, F, E -- the chords
  // pushed onto the off-beats against the four on the floor; bar 4 climbs D, Eb, E into the hook
  const RIFF = bars(
    'A2 - - a2 a2 - C3 - - a2 D3 - - a2 C3 -',
    'A2 - - a2 a2 - G2 - - a2 F2 - - - E2 -',
    'A2 - - a2 a2 - C3 - - a2 D3 - - a2 C3 -',
    'A2 - - a2 a2 - C3 - - a2 D3 - Eb3 - E3 -');
  rhythm(song, 'gtr', RIFF, 1);
  voice(song, 'bass', G.bass, bassFrom(RIFF), 1, 1, 0.85);
  // a pinch harmonic squealing over the E that answers the riff
  lead(song, 'lead', '. . . . . . . . . . . . . . e4* -', 2, 0.8);

  // the hook's chords (5-8, 13-16): F G Am E, driven in eighths, open on the 3-3-2 accents
  const drive = r => `${r} - ${r.toLowerCase()} . ${r.toLowerCase()} . ${r} - ${r.toLowerCase()} . ${r.toLowerCase()} . ${r} - ${r.toLowerCase()} .`;
  const HOOKCH = ['F', 'G', 'Am', 'E'], ROOT = { F: 'F2', G: 'G2', Am: 'A2', E: 'E2' }, HIGH = { F: 'F3', G: 'G3', Am: 'A3', E: 'E3' };
  for (const b0 of [5, 13]) {
    HOOKCH.forEach((ch, k) => {
      const bar = b0 + k, last = bar === 16;
      rhythm(song, 'gtr', last ? 'E2 - e2 . e2 . E2 - . . . . / - - -' : drive(ROOT[ch]), bar);
      if (!last) rhythm(song, 'gtr2', `${HIGH[ch]} - - - - - ${HIGH[ch]} - - - - - ${HIGH[ch]} - - -`, bar);
      voice(song, 'bass', G.bass, riff(last ? 'R . O . R . O . . . . . . . . .' : 'R . O . R . O . R . O . R . O .', ch), bar, 1, 0.8);
    });
  }

  // the hook (5-8): each chord climbed from its third and fallen back, a step higher each bar --
  // A C F E C A over F, B D G F D B over G, C E A G E C over Am, then the E chord's G# --
  // the second time (13-16) in twin leads a third apart, the last bar a harmonic-minor run home
  const HOOK = [
    'a4 - - c5 - - f5 - e5 - - - c5 - a4 -',
    'b4 - - d5 - - g5 - f5 - - - d5 - b4 -',
    'c5 - - e5 - - a5^ - g5 - - - e5 - c5 -',
    'b4 - - e5 - - g#5 - a5 - - - g#5~ - - -',
  ];
  lead(song, 'lead', bars(...HOOK), 5);
  const RUN = 'b4 - - e5 - - g#5 - a5 g#5 f5 e5 d5 c5 b4 g#4';
  lead(song, 'lead', bars(...HOOK.slice(0, 3), RUN), 13);
  // (the run's thirds in the harmonic minor: G# under B, not the natural minor's G)
  lead(song, 'lead2', bars(...HOOK.slice(0, 3).map(harmony), 'g#4 - - c5 - - e5 - f5 e5 d5 c5 b4 a4 g#4 e4'), 13);

  // the techno break (9-12): Dm Am Bb E -- the guitar only rings the chord in, stabs push a
  // 3-3-4-3-3 rhythm, a pluck arpeggio runs, the bass rolls between the kicks, the E builds
  const BRK = ['Dm', 'Am', 'Bb', 'E'];
  rhythm(song, 'gtr', bars('D3 - - - - - - - - - - - . . . .', 'A2 - - - - - - - - - - - . . . .',
    'Bb2 - - - - - - - - - - - . . . .', 'E2 - - - e2 . e2 . e2 e2 e2 e2 E2 E2 E2 E2'), 9);
  BRK.forEach((ch, k) => {
    const bar = 9 + k;
    chords(song, 'stab', I.stab, bar === 12 ? 'x..x..x.x.x.x.x.' : 'x..x..x...x..x..', bar, ch);
    voice(song, 'bass', G.bass, riff(bar === 12 ? 'R R R R R R R R O O O O O O O O' : '. . R R . . O . . . R R . . O .', ch), bar, 1, 0.75);
  });
  arp(song, 'pluck', BRK, 9, [0, 1, 2, 3, 2, 1, 2, 3], 1);

  // orchestra hits: the riff's and the hook's downbeats, the break's changes, the E's three knocks
  hit(song, 'Am', 1); hit(song, 'F', 5); hit(song, 'Dm', 9); hit(song, 'Bb', 11);
  hit(song, 'E', 12, 0); hit(song, 'E', 12, 3); hit(song, 'E', 12, 6); hit(song, 'F', 13); hit(song, 'E', 16, 0, 0.8);

  return master(song, {
    levels: LEVELS, verb: VERB, room: { room: 0.6, damp: 0.5 },
    echo: [{ stem: 'lead', steps: 3, fb: 0.3, send: 0.2 }, { stem: 'lead2', steps: 3, fb: 0.3, send: 0.15 }],
    pump: -5, gpump: -2, loud: -14.5,
  }, report);
}

// ---------------------------------------------------------------- play: the table

function play(report) {
  const song = new S.Song({ bpm: 132, bars: 32 });
  const K = I.kick({ f0: 230, f1: 50, d: 0.17, click: 0.6 }), SN = I.snare({ f: 185, nd: 0.15, noise: 1.2, tone: 0.85 });
  const CL = I.clap({}), HH = I.hat({}), OH = I.ohat({ d: 0.09, len: 0.35 }), CR = I.crash({});
  const HOOKCH = ['Am', 'F', 'C', 'G', 'Am', 'F', 'G', 'E'];
  const ROOT = { Am: 'A2', F: 'F2', C: 'C3', G: 'G2', E: 'E2' }, HIGH = { Am: 'A3', F: 'F3', C: 'C4', G: 'G3', E: 'E3' };

  // drums
  for (let bar = 1; bar <= 32; bar++) {
    const calm = bar >= 17 && bar <= 18, half = bar >= 19 && bar <= 20;
    if (half) drum(song, 'kick', K, 'x.........x.....', bar);
    else if (!calm) drum(song, 'kick', K, bar === 24 ? 'x...x...x.......' : bar === 32 ? 'x...x...x.......' : 'x...x...x...x...', bar);
    // the clap from the start, the snare joins at the riff; a roll through the build
    if (half) drum(song, 'clap', CL, '........x.......', bar);
    else if (!calm && bar !== 23 && bar !== 24) drum(song, 'clap', CL, '....x.......x...', bar);
    if (bar === 22) drum(song, 'snare', SN, '....x...x.x.x.x.', bar);
    else if (bar === 23) drum(song, 'snare', SN, '4.4.5.5.6.6.7.7.', bar);
    else if (bar === 24) drum(song, 'snare', SN, '5656676778788999', bar);
    else if (bar === 4) drum(song, 'snare', SN, '............x.xx', bar, 0.8);
    else if (bar === 8 || bar === 16) drum(song, 'snare', SN, '....x.......x...', bar);
    else if (bar === 12 || bar === 28) drum(song, 'snare', SN, '....x.......x.xx', bar);
    else if (bar >= 5 && !calm && !half && bar !== 21) drum(song, 'snare', SN, '....x.......x...', bar);
    if (calm || half) drum(song, 'hat', HH, 'x.x.x.x.x.x.x.x.', bar, 0.55);
    else drum(song, 'hat', HH, bar === 32 ? '42824282........' : '4282428242824282', bar);
    if (bar >= 3 && !calm && !half && bar !== 24 && bar !== 32) drum(song, 'ohat', OH, '..x...x...x...x.', bar);
  }
  for (const bar of [1, 5, 9, 13, 17, 25, 29]) drum(song, 'crash', CR, 'x', bar, bar === 1 ? 0.8 : 1);
  toms(song, 8, 12, [196, 165, 131, 110]);
  toms(song, 16, 12, [220, 175, 147, 110]);
  toms(song, 32, 8, [262, 220, 196, 165, 147, 131, 110, 98], 0.75);
  song.put('riser', at(23), I.riser({ len: song.step * 30 }));

  // the groove (1-4): chugs on A every three 16ths against the four on the floor -- dark, low,
  // the bells' range left to the bells -- the bass rolling between the kicks
  rhythm(song, 'gtr', bars(
    'a2 . . a2 . . a2 . . a2 . . a2 . x .',
    'a2 . . a2 . . a2 . . a2 . . a2 . a2 a2',
    'a2 . . a2 . . a2 . . a2 . . a2 . x .',
    'a2 . . a2 . . a2 . . a2 . . C3 - D3 -'), 1);
  voice(song, 'bass', G.bass, bars(...[1, 2, 3].map(() => '. . a1 a1 . . a2 . . . a1 a1 . . a2 .'), '. . a1 a1 . . a2 . . . a1 a1 c2 - d2 -'), 1, 1, 0.8);
  // with the open hats an acid line creeps in under the bells, its filter barely open
  const GACID = 'a2 a2 a3 a2 . a2 a3 a2 a2 . a3 a2 c3 a2 g3 a2';
  for (let bar = 3; bar <= 8; bar++) {
    S.notes(GACID, at(bar)).forEach((e, s) => song.put('acid', e.step, G.acid({ n: e.n, d: song.step * 0.8, acc: [0, 3, 6, 12].includes(s) ? 0.12 : 0 }), 0.5));
  }

  // the riff (5-8): A, chug-chug, G, chug-chug, C, D -- answered by a low E; bar 8 climbs into the hook
  const RIFF = bars(
    'A2 - - a2 a2 - G2 - - a2 a2 - C3 - D3 -',
    'A2 - - a2 a2 - G2 - - a2 a2 - E2 - - -',
    'A2 - - a2 a2 - G2 - - a2 a2 - C3 - D3 -',
    'A2 - - a2 a2 - G2 - - a2 C3 - D3 - E3 -');
  rhythm(song, 'gtr', RIFF, 5);
  voice(song, 'bass', G.bass, bassFrom(RIFF), 5, 1, 0.85);

  // the hook's chords (9-16, 25-32): Am F C G, Am F G E, open on the 3-3-2 accents, chugs between;
  // the second time a second guitar an octave up on the accents and stabs with them
  const push = r => `${r} - - ${r.toLowerCase()} ${r.toLowerCase()} - ${r} - - ${r.toLowerCase()} ${r.toLowerCase()} - ${r} - ${r.toLowerCase()} ${r.toLowerCase()}`;
  for (const b0 of [9, 25]) {
    HOOKCH.forEach((ch, k) => {
      const bar = b0 + k, line = bar === 32 ? 'E2 - - e2 e2 - E2 - . . . . / - - -' : push(ROOT[ch]);
      rhythm(song, 'gtr', line, bar);
      voice(song, 'bass', G.bass, bassFrom(line), bar, 1, 0.85);
      if (b0 === 25 && bar !== 32) {
        rhythm(song, 'gtr2', `${HIGH[ch]} - - - - - ${HIGH[ch]} - - - - - ${HIGH[ch]} - - -`, bar);
        chords(song, 'stab', I.stab, 'x.....x.....x...', bar, ch);
      }
    });
  }

  // the hook: E E D E G E (a scoop into the first E) -- D C A -- again over C reaching up to A,
  // G D B over G; again, and B C D G D, then the E chord's E bent up and its arpeggio home.
  // In the bells' octave only its peaks; the second time in twin leads a third apart
  const HOOK = [
    'e5/ - . e5 - . d5 - e5 - . . g5 - e5 -', 'd5 - - - - - c5 - a4 - - - . . . .',
    'e5/ - . e5 - . d5 - e5 - . . g5 - a5 -', 'g5 - - - - - d5 - b4 - - - . . . .',
    'e5/ - . e5 - . d5 - e5 - . . g5 - e5 -', 'd5 - - - - - c5 - a4 - - - c5 - d5 -',
    'b4 - . b4 - . c5 - d5 - . . g5 - d5 -', 'e5^ - - - - - - - . . g#4 - b4 - d5 -',
  ];
  lead(song, 'lead', bars(...HOOK), 9);
  const END = 'e5^ - - - - - - - - - - - . . . .';
  lead(song, 'lead', bars(...HOOK.slice(0, 7), END), 25);
  // (over F the third under D would be B, a tritone on F: a fourth under, A, instead)
  const TWIN = HOOK.slice(0, 7).map(harmony);
  TWIN[1] = 'a4 - - - - - a4 - f4 - - - . . . .';
  TWIN[5] = 'a4 - - - - - a4 - f4 - - - a4 - a4 -';
  lead(song, 'lead2', bars(...TWIN, 'b4^ - - - - - - - - - - - . . . .'), 25);

  // the breakdown (17-20): Dm, F -- the drums thin out, a clean guitar lets an arpeggio ring,
  // a pad, the bass on long roots
  ring(song, 'clean', bars(
    'd3 . a3 . d4 . f4 . a4 . f4 . d4 . a3 .', 'd3 . a3 . d4 . f4 . a4 . d5 . a4 . f4 .',
    'f3 . c4 . f4 . a4 . c5 . a4 . f4 . c4 .', 'f3 . c4 . f4 . a4 . c5 . e5 . c5 . a4 .',
    'bb2 . f3 . bb3 . d4 . f4 . d4 . bb3 . f3 .', 'bb2 . f3 . bb3 . d4 . f4 . d4 . bb3 . f3 .'), 17, 6);
  song.put('pad', at(17), G.pad({ ns: [62, 65, 69], d: song.step * 31 }));
  song.put('pad', at(19), G.pad({ ns: [60, 65, 69], d: song.step * 31 }));
  song.put('pad', at(21), G.pad({ ns: [58, 62, 65], d: song.step * 30 }));
  voice(song, 'bass', G.bass, bars('d2 - - - - - - - - - - - - - - -', 'd2 - - - - - - - a1 - - - - - - -',
    'f2 - - - - - - - - - - - - - - -', 'f2 - - - - - - - c2 - - - - - - -'), 17, 0.55, 0.95);

  // the build (21-24): Bb to E -- the kick back, the guitar chugging eighths then sixteenths,
  // an acid line opening up, a snare roll, the riser, the E tremolo-picked up the octave, a gap
  rhythm(song, 'gtr', bars(
    'Bb2 - - - - - - - bb2 . bb2 . bb2 . bb2 .',
    'bb2 . bb2 . bb2 . bb2 . bb2 bb2 bb2 bb2 bb2 bb2 bb2 bb2',
    'E2 - - - - - - - e2 e2 e2 e2 e2 e2 e2 e2',
    'E2 E2 E2 E2 E2 E2 E2 E2 E3 E3 E3 E3 E3 E3 . .'), 21);
  voice(song, 'bass', G.bass, bars('bb1 . bb1 . bb1 . bb1 . bb1 . bb1 . bb1 . bb2 .', 'bb1 bb1 bb1 bb1 bb1 bb1 bb1 bb1 bb1 bb1 bb1 bb1 bb2 bb2 bb2 bb2',
    'e2 . e2 . e2 . e2 . e2 e2 e2 e2 e2 e2 e2 e2', 'e2 e2 e2 e2 e2 e2 e2 e2 e3 e3 e3 e3 e3 e3 . .'), 21, 1, 0.8);
  const ACID = ['bb2 bb2 bb3 bb2 f3 bb2 bb3 bb2 bb2 bb2 bb3 bb2 f3 bb2 bb3 c4', 'bb2 bb2 bb3 bb2 f3 bb2 bb3 bb2 bb2 bb2 bb3 bb2 f3 bb2 c4 d4',
    'e2 e2 e3 e2 b2 e2 e3 e2 e2 e2 e3 e2 b2 e2 e3 g#3', 'e2 e2 e3 e2 b2 e2 e3 e2 e3 e3 e4 e3 b3 e3 . .'];
  const ACC = '1001001010010010';
  ACID.forEach((l, k) => {
    S.notes(l, at(21 + k)).forEach((e, s) => song.put('acid', e.step, G.acid({ n: e.n, d: song.step * 0.85, acc: Math.min(1, 0.15 + 0.22 * k + (ACC[s] === '1' ? 0.3 : 0)) })));
  });

  // orchestra hits: into the hook, the breakdown's chords, the E's three knocks, the drop
  hit(song, 'Am', 9); hit(song, 'Dm', 17); hit(song, 'F', 19); hit(song, 'Bb', 21);
  hit(song, 'E', 23, 0); hit(song, 'E', 23, 3); hit(song, 'E', 23, 6);
  hit(song, 'Am', 25); hit(song, 'Am', 29); hit(song, 'E', 32, 0, 0.85);

  return master(song, {
    levels: Object.assign({}, LEVELS, { kick: -15.5 }), verb: VERB, room: { room: 0.55, damp: 0.55 },
    // the bells (target:*, 440-1570 Hz) ring through a dip in the guitars where they sit
    amps: {
      gtr: Object.assign({}, AMPS.gtr, { post: [...AMPS.gtr.post, ['peak', 1250, 0.9, -3]] }),
      gtr2: Object.assign({}, AMPS.gtr2, { post: [['hp', 220, 0.7], ['peak', 1250, 0.9, -3]] }),
    },
    echo: [{ stem: 'lead', steps: 3, fb: 0.28, send: 0.18 }, { stem: 'clean', steps: 3, fb: 0.35, send: 0.25 }],
    pump: -5, gpump: -2, loud: -14.5,
  }, report);
}

// ---------------------------------------------------------------- multi: multiball

function multi(report) {
  const song = new S.Song({ bpm: 166, bars: 16 });
  const K = I.kick({ f0: 260, f1: 55, d: 0.13, click: 0.65, len: 0.32 }), SN = I.snare({ f: 200, nd: 0.12, noise: 1.25, tone: 0.8 });
  const CL = I.clap({}), HH = I.hat({}), OH = I.ohat({ d: 0.07, len: 0.28 }), CR = I.crash({});

  // drums: four on the floor, the backbeat doubled by a clap, a kick pickup into each fourth
  // bar, the climb's snare going from the backbeat to quarters, eighths, sixteenths
  for (let bar = 1; bar <= 16; bar++) {
    const climb = bar >= 9 && bar <= 12;
    drum(song, 'kick', K, bar === 16 ? 'x...x...x.......' : bar % 4 === 0 && !climb ? 'x...x...x...x.x.' : 'x...x...x...x...', bar);
    const sn = bar === 8 ? '....X.......xxXX' : bar === 16 ? '....X...........' : bar === 10 ? 'x...x...x...x...' :
      bar === 11 ? '5.5.6.6.7.7.8.8.' : bar === 12 ? '6666777788889999' : '....X.......X...';
    drum(song, 'snare', SN, sn, bar);
    if (!climb) drum(song, 'clap', CL, bar === 16 ? '....x...........' : '....x.......x...', bar);
    drum(song, 'hat', HH, bar === 16 ? '53935393........' : '5393539353935393', bar);
    if (!climb && bar !== 16) drum(song, 'ohat', OH, '..x...x...x...x.', bar);
  }
  for (const bar of [1, 5, 9, 13]) drum(song, 'crash', CR, 'x', bar);
  toms(song, 16, 8, [262, 220, 196, 165, 147, 131, 110, 98], 0.75);
  song.put('riser', at(11), I.riser({ len: song.step * 32 }));

  // the big riff: a chord on every beat with two chugs after it -- A C D Eb D, A C G F E --
  // bass in unison, a second guitar an octave up on the chords: a multiball starts at full tilt
  const R1 = 'A2 - a2 a2 C3 - a2 a2 D3 - a2 a2 Eb3 - D3 -', R2 = 'A2 - a2 a2 C3 - a2 a2 G2 - a2 a2 F2 - E2 -';
  const H1 = 'A3 - . . C4 - . . D4 - . . Eb4 - D4 -', H2 = 'A3 - . . C4 - . . G3 - . . F3 - E3 -';
  const END = 'A2 - a2 a2 C3 - a2 a2 E2 - - - / - - -';
  const RIFF = bars(R1, R2, R1, R2, R1, R2, R1, R2);
  rhythm(song, 'gtr', RIFF, 1);
  voice(song, 'bass', G.bass, bassFrom(RIFF), 1, 1, 0.85);
  rhythm(song, 'gtr', bars(R1, R2, R1, END), 13);
  voice(song, 'bass', G.bass, bassFrom(bars(R1, R2, R1, END)), 13, 1, 0.85);
  rhythm(song, 'gtr2', bars(H1, H2, H1, H2, H1, H2, H1, H2), 1);
  rhythm(song, 'gtr2', bars(H1, H2, H1, 'A3 - . . C4 - . . E3 - - - . . . .'), 13);
  // pinch harmonics squealing over the riff's E while it plays without the lead
  for (const bar of [2, 4]) lead(song, 'lead', '. . . . . . . . . . . . . . e4* -', bar, 0.8);

  // the climb (9-12): F G Ab Bb tremolo-picked, hoovers on the chords, a hit on each, then the
  // phrygian half-step down onto A
  rhythm(song, 'gtr', bars(...['F2', 'G2', 'Ab2', 'Bb2'].map(r => Array(16).fill(r).join(' '))), 9);
  voice(song, 'bass', G.bass, bars('f2 . f3 . f2 . f3 . f2 . f3 . f2 . f3 .', 'g2 . g3 . g2 . g3 . g2 . g3 . g2 . g3 .',
    'g#2 . g#3 . g#2 . g#3 . g#2 . g#3 . g#2 . g#3 .', 'bb1 . bb2 . bb1 . bb2 . bb1 bb1 bb2 bb2 bb1 bb1 bb2 bb2'), 9, 1, 0.8);
  [[53, 60, 65], [55, 62, 67], [56, 63, 68], [58, 65, 70]].forEach((ns, k) => {
    for (const n of ns) song.put('hoover', at(9 + k), I.hoover({ n, d: song.step * 15 }), 0.7);
  });
  hit(song, 'F', 9); hit(song, 'G', 10); hit(song, 'Ab', 11); hit(song, 'Bb', 12); hit(song, 'Bb', 12, 8, 0.9);

  // the lead: E held and A bent up to over the riff, an answer falling to A; again up to C;
  // in the climb a third over each chord; at the top 13-16 pentatonic runs in twin leads (the
  // second voice written out: a third or a fourth under, B flat and E flat on the riff's E
  // flat) climbing chromatically to a screaming E with a wide vibrato
  lead(song, 'lead', bars(
    'e5 - - - - - - - a5^ - - - - - - -', 'g5 - - - e5 - - - d5 - e5 - c5 - a4 -',
    'e5 - - - - - - - c6^ - - - - - - -', 'a5 - - - g5 - - - e5 - - - d5 - b4\\ -',
    'a4 - - - - - - - c5 - - - - - - -', 'b4 - - - - - - - d5 - - - - - - -',
    'c5 - - - - - - - eb5 - - - - - - -', 'd5 - - - - - - - f5~ - - - - - - -'), 5);
  lead(song, 'lead', bars('a5 - g5 - e5 - g5 - a5 - c6 - bb5 - a5 -', 'e5 - - - d5 - c5 - d5 - - - e5 - - -',
    'a5 - g5 - e5 - g5 - a5 - c6 - eb6 - e6 -', 'e6~ - - - - - - - - - - - . . . .'), 13);
  lead(song, 'lead2', bars('e5 - e5 - c5 - e5 - f5 - a5 - g5 - f5 -', 'c5 - - - b4 - a4 - b4 - - - c5 - b4 -',
    'e5 - e5 - c5 - e5 - f5 - a5 - bb5 - b5 -', 'b5~ - - - - - - - - - - - . . . .'), 13);

  hit(song, 'Am', 1); hit(song, 'Am', 5); hit(song, 'Am', 13); hit(song, 'E', 16, 8, 0.85);

  return master(song, {
    levels: Object.assign({}, LEVELS, { snare: -17, hat: -26 }), verb: VERB, room: { room: 0.5, damp: 0.5 },
    echo: [{ stem: 'lead', steps: 3, fb: 0.25, send: 0.16 }],
    pump: -6, gpump: -2.5, loud: -14.5,
  }, report);
}

module.exports = { menu, play, multi };
