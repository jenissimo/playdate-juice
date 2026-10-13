# studio

Rendered music for Playdate: the other half of chiptune. The driver plays tiny songs live on
emulated chips; the studio renders what no chip of that size plays -- distorted guitars
through an amp and a cabinet, orchestra hits, rooms, bus compression, a mastered mix -- into
seamless loops that `jukebox.lua` streams, and into instrument samples a tracker can play.
The sound of a 1994 Amiga or Mega Drive pinball game: Psycho Pinball's tracker rock.

It was made for Overturn (flipperless pinball, HappyDog), which plays its three techno-rock
loops and every one-shot from it. Node, no dependencies; ffmpeg for ADPCM and resampling.

```bash
cd chiptune/studio
node test.cjs                                          # "10 checks, 0 failures"
node render.cjs songs/overturn_rock.cjs --out out --prefix music_ --adpcm --preview preview --mix
node samples.cjs banks/rock.cjs out/rock               # 21 instrument samples + bank.json
```

```
studio/
  synth.cjs        the DSP: oscillators, drums, strings and an amp, effects, dynamics, loudness, lines, Song
  instruments.cjs  I (the 90s kit, basses, leads...), G (the techno-rock band), CH (chords in A minor)
  compose.cjs      writing a song: drum, voice, rhythm guitar, lead guitar, chords, hits, twin leads...
  master.cjs       stems to a finished loop: levels by loudness, amps, buses, pump, clip, limiter
  render.cjs       a song module to WAV loops (PCM or IMA ADPCM), previews, the mix report
  samples.cjs      a bank module to instrument samples + bank.json (root note, sustain loop)
  banks/rock.cjs   the techno-rock band as 21 samples
  songs/           overturn_rock.cjs (2026), overturn_tracker.cjs (Overturn's first soundtrack),
                   example.cjs (the example below)
  test.cjs         the smoke test
```

## Live or rendered

| | chiptune (the driver) | studio |
|---|---|---|
| a song is | 0.2-3.4 KB of rows | a loop of ~22 KB a second (IMA ADPCM, 44.1 kHz) |
| plays on | the audio thread, C, ~5-12% of a core | `jukebox.lua`, a fileplayer streaming from disk |
| can | mute parts, sync markers, effects borrowing voices | anything a DAW can: amps, reverb, a mastered mix |
| cannot | a distorted guitar, a room, mastering | change at runtime beyond volume and a filter |

Both at once is the usual game: rendered loops for the music, the driver's SFX bank for the
interface. Part 2 below joins them: studio samples played by the driver.

## Writing a song

A song module exports `{ name: (report) => Float32Array }`: one mastered loop at 44100 Hz.

```js
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
```

**Lines.** One token a 16th, bars of 16 between `|` (a bar of the wrong length throws: a token
too many would shift the rest of the song).

| line | tokens |
|---|---|
| notes (`S.notes`, `W.voice`) | `a4` `c#5` `eb3` or a MIDI number; `-` holds; `.` rests |
| drums (`S.beats`, `W.drum`) | `X` accent, `x` hit, `o` ghost, `1`-`9` a level in tenths, `.` |
| rhythm guitar (`W.rhythm`) | `A2` an open power chord on that root, `a2` palm-muted (a chug), `x` a dead strum, `/` a pick scrape, `-` holds, `.` stops the strings; strokes alternate down/up by 16th |
| lead guitar (`W.lead`) | notes with marks after them: `/` scoop, `^` bend up a tone into it, `~` wide vibrato, `\` fall away, `*` pinch harmonic |
| chords (`W.chords`) | `x` / `X` a stab of the chord on that step, `-` holds |
| a bass template (`W.riff`) | `R` the chord's root, `O` its octave, `5` the fifth, `7` the seventh in key |

`W.bassFrom(rhythmLine)` follows a guitar line's roots an octave down; `W.harmony(line)` is the
diatonic third under a line (the twin lead); `W.arp` a 16th arpeggio over a run of chords;
`W.toms` a fill; `W.hit` an orchestra hit; `W.ring` a let-ring clean arpeggio.

## Instruments

- **I** -- the 90s kit (a kick sweeping from ~250 Hz with a beater's click, a snare with a
  body, clap, 808-style metal hats and crash, toms, a riser), a saw bass with a sub, an FM slap
  bass, a square lead, a calliope, brass, a pluck, the 1992 hoover, FM piano stabs, an organ,
  the orchestra hit (detuned saws through a falling filter, the chord sagging, a formant,
  noise and a timpani boom).
- **G** -- the band. `S.string` is an extended Karplus-Strong string: excited by a plucked
  string's triangle (so the fundamental leads -- white noise made clipping turn an octave into
  the root), a pick-position comb, a loss per round set by t60, a cubic fractional delay (in
  tune within a cent from A2 to E6), bends, vibrato, glides, a fretting hand damping it after
  the gate. `G.chord` (root, fifth, octave, strummed 6 ms apart, each string a few cents off),
  `G.chug` (palm-muted), `G.dead`, `G.scrape`, `G.note` (the lead, with the marks above),
  `G.clean`, `G.bass` (two saws, driven), `G.acid` (a resonant saw), `G.pad`.
- **`S.amp(x, preset)`** -- a guitar stem's amp: a tight high-pass and a mid boost, 4x
  oversampling, an asymmetric tanh stage and a soft-kneed hard stage, then a cabinet (a
  4th-order high-pass at ~90 Hz, presence at 2.2-2.6 kHz, a dip in the box, a 4th-order
  low-pass at ~5-6 kHz). Presets in `master.cjs AMPS`: `gtr` (rhythm), `gtr2`, `lead`, `clean`.
- **CH** -- A minor chords with their bass root, stab voicing, orchestra-hit stack and the
  seventh a bass may walk to. Any table of the same shape works.

## Mixing and mastering

`master(song, spec, report)` (see its header): every stem folded into one lap, a guitar's
through its amp, each **levelled by its loudness** (LUFS while it sounds, so a mix is numbers,
the same on every render), sends to a room and echoes, the drum bus compressed with a slow
attack (the click passes), the bed pumping under the kick (`pump`, `gpump` for the guitars), a
glue compressor, 40 Hz high-pass, the loudness (`loud`), a soft clip of the top 3 dB, a
look-ahead limiter at -1 dBFS. Every non-linear stage runs cyclically (two laps, the second
kept), so the loop's start is warmed by its end: the seam has no jump.

With a `report` array (`render.cjs --mix`) it says each stem's loudness before levelling, the
buses' gain reduction, how much the clip and the limiter work and where, and the bands.

For the Playdate's speaker, which plays little below a few hundred Hz: give every part that
must carry harmonics (the basses are driven saws, the kick has a click, guitars are midrange
anyway), and watch `S.stats(x).speaker` (the energy above 500 Hz, dB) and the bands. Overturn's
loops: -14.5 LUFS, peaks -1 dBFS, the limiter under 1 dB of reduction, bands (dB of the
energy) <100 Hz -9, 100-300 -7, 300-1k -7, 1-3k -10.5, 3-8k -16, >8k -17.5.

## Loops in a game

```bash
node render.cjs songs/overturn_rock.cjs --out ../../../MyGame/Source/sound --prefix music_ --adpcm
```

```lua
Jukebox.load({ tracks = { play = "sound/music_play" }, volumes = { play = 0.5 } })
Jukebox.play("play")      -- loops forever, no gap
```

pdc keeps an IMA ADPCM WAV as it is and trims its last block to the true length (from the
`fact` chunk), so a looping fileplayer has no gap at the seam. `--rate 22050` halves the size.
Overturn's balance, measured by replaying bot games through its mixer: loops mastered to
-14.5 LUFS at volume 0.5 put the music about 4 LU under the game's sounds; a multiball's loop at
0.7. A high-pass on the music's channel (320 Hz) audibly takes the bass out ("danger").

## Samples for a tracker

```bash
node samples.cjs banks/rock.cjs out/rock [--rate 22050] [--only gtr_chord,kick]
```

A bank module exports `[{ name, root, make, loop, peak }]`: `root` the MIDI note the sample
sounds as it is (an unpitched one says 72, C5, where chiptune's sample oscillator plays a
sample as recorded); `loop` `false` (a one-shot, its silent tail trimmed), `'auto'` (a sustain
loop in the steady part: whole periods of the root between rising zero crossings, the end
crossfaded into the start) or `[start, end]` seconds; `peak` dBFS (default -1). Out come the
WAVs (PCM 16-bit mono) and `bank.json`:

```json
[{ "name": "gtr_lead", "file": "gtr_lead.wav", "root": 69, "rate": 44100, "length": 32255,
   "loop": [26943, 32255], "peak": -1, "lufs": -10.1 }]
```

The loop's end is exclusive: the sample stops there and playback jumps to its start.
`banks/rock.cjs`: `gtr_chord` (A2, rings), `gtr_chord_sus` (looped), `gtr_chug`, `gtr_dead`,
`gtr_scrape`, `gtr_lead` (A4, looped), `gtr_pinch`, `gtr_clean`, `bass` (A1, looped), `acid`,
`pad` (looped), `hoover` (looped), `stab`, `orch_am`, `kick`, `snare`, `clap`, `hat`, `ohat`,
`crash`, `tom` -- 1.26 MB as PCM16 at 44.1 kHz, about 230 KB as 8-bit at 16 kHz.

## The songs

- `songs/overturn_rock.cjs` -- **menu** (140 BPM, 16 bars: a riff of chords pushed onto the
  off-beats between chugs; a hook climbing from each chord's third over F G Am E; a techno
  break Dm Am Bb E with stabs 3-3-4-3-3 and a pluck arpeggio; the hook in twin leads, a
  harmonic-minor run home), **play** (132 BPM, 32 bars: a chugging groove leaving the bells'
  range free, the riff, the hook, a breakdown with a clean let-ring guitar and a pad, a build
  with tremolo picking, an acid line opening and a snare roll, the hook doubled), **multi**
  (166 BPM, 16 bars: a chord on every beat, a lead, a chromatic climb F G Ab Bb with hoovers,
  twin leads screaming up to E). A minor, the key Overturn's target bells ring in.
- `songs/overturn_tracker.cjs` -- Overturn's first soundtrack: 90s tracker rave (a galloping
  saw bass, a square lead, rave stabs, a circus march on a calliope, a breakbeat with hoovers).
  Mastered here by `master.cjs` without amps; the shipped files had the older master.

Rendered from here, the rock loops are bit-identical to Overturn's (`tools/music.cjs`).

## Tests

`node test.cjs`: a two-bar song renders to a loop of exactly two bars, at -14.5 LUFS, under
-1 dBFS, with no jump at the seam; a wrongly sized bar throws; a bank exports its samples, a
one-shot without a loop, a sustain loop inside its sample.

## The live tracker: format 4

**Port brief: [TRACKER_PORT.md](TRACKER_PORT.md)** -- the measured starting point and acceptance
criteria for the original studio arrangement. The brief used the development
name format 3; the shared-bank layout is now format 4 to preserve master’s
existing embedded FT2 format 3. Both use the same driver and vox mixer.
The implemented ports are described below.

**Goal.** The rock sound playing live on chiptune's driver: instrument samples rendered here
(guitars through the amp, the synth bass, the kit, the hits), played by a GBM song of a few
KB -- a tracker theme in the manner of an Amiga MOD -- so a game gets the band without
megabytes of streams, and keeps what only the driver gives (muting layers, sync markers,
effects ducking the music). Exact reproduction of the rendered loops is not the aim; a good
tracker arrangement is.

**Implemented.** `samples.cjs` exports the source WAVs; `studio_bank()` in
`tools/gbm_compose.py` resamples and quantises them into a shared `.gbank`.
GBM format 4 plays signed PCM8 with per-sample rate/root, linear interpolation
and sustain loops on vox. Format 1's DMG and format 2's legacy 4-bit sample
path remain compatible. All runtime work stays in the existing driver and
32-sample renderer, with no allocations or per-sample division.

```bash
python tools/chiptune.py studio
python tools/build_demo.py --jukebox
python tools/chiptune.py render chiptune/music/steel_circuit.gbm build/steel_circuit.wav --bank chiptune/music/rock.gbank --mono --loops 2
```

`banks/tracker.cjs` adds a reese, a supersaw, a pluck and F/G pads to the rock
bank. Three live themes -- Steel Circuit (rock), Chrome Breaks (jungle) and
Prism Drive (trance) -- share 17 instruments in 207,412 bytes, below the
256 KiB budget. Each song's patterns are about 1 KiB. The demo Jukebox
switches between live playback and ADPCM streams of the same arrangements.
See `../README.md` for Lua loading, the bank ABI and host benchmark results.

### The original studio arrangements

`export_tracker.cjs` runs `overturn_rock.cjs` on a recording Song and captures
every instrument call, note, start, gate, velocity and master setting.
`prepare_tracker.cjs` bakes root-specific guitar chords/chugs through their
amps and EQ, plus room/echo sends. Simultaneous percussion is layered into
one sample; optional melodic collisions are listed in the audit.
`tools/studio_port.py` compiles the events and checks the actual GBM stream's
note starts/pitches and gates against the recorded events.

```bash
python tools/build_studio_port.py --publish
python tools/build_demo.py --jukebox
```

The pipeline measures every rendered lane against the studio's LUFS target,
then calibrates the driver's block compressor, soft clip and -1 dBFS peak
limiter to -14.5 LUFS. Six frames per row use a per-song clock: 56 Hz for
menu (140 BPM), 52.8 Hz for play (132 BPM), 66.4 Hz for multi (166 BPM).
PCM note off/retrigger overlaps fade for 5-30 ms instead of stopping abruptly.

All three share `music/overturn.gbank`. It is about 401 KiB on disk, losslessly
decoded once to about 703 KiB of PCM8 in RAM; decoder workspace is temporary
(257 KiB). No decompression, allocation or file access runs in audio.
Chord samples retain their original roots, with 22050 Hz for guitars, leads
and cymbals, 16384 Hz for the lower instruments. Only unreachable one-shot
tails (past the next retrigger and release overlap) are removed.

| Port | Encoded starts checked | Layered source hits | Omitted events | LUFS | 50 ms RMS spread |
|---|---:|---:|---:|---:|---:|
| menu | 780 | 96 | 10 | -14.57 | 4.14 dB |
| play | 1496 | 148 | 39 | -14.60 | 4.72 dB |
| multi | 855 | 83 | 17 | -14.55 | 4.00 dB |

All three pass the brief's A/B limits: within 0.06 LU of the studio, within
1.1 dB in 100 Hz-3 kHz and 1.3 dB above 8 kHz. The JSON ledger
`music/studio_ports.json` preserves the comparisons, omitted events and bank
sizes. WAVs and full reports are in `build/studio-port/`; comparisons use
44100 Hz mono and the warmed second lap, including the breakdowns.

The Jukebox's `Studio Menu`, `Studio Play` and `Studio Multi` entries switch
between live tracking and the original studio master with left/right.
Steel Circuit, Chrome Breaks and Prism Drive remain separate examples.
This mode is Amiga/MOD-like; Genesis-style FM remains a possible extension.

## Credits

Made for Overturn (HappyDog, 2026). The tracker-music idiom follows Psycho Pinball
(Codemasters, 1994; music by Tim Bartlett); nothing of it is copied. Freeverb's tunings
(Jezar at Dreampoint, public domain); the loudness after ITU-R BS.1770.
