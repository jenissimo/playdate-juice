# chiptune

Three tracker sound families for Playdate: Game Boy, SID-style synthesis,
and a studio PCM band in the style of 16-bit-era sample trackers.

The engine is **GBM**, a tracker music/SFX driver written for the original Game
Boy (instruments with LSDj-style tables, arpeggios, slides, vibrato, two SFX
slots that borrow a channel from the music, ducking, drum samples). Here it is
ported from SM83 assembly to portable C and runs inside a Playdate audio
callback, with three formats on two synth backends:

- **gbapu**, the DMG's APU emulated register by register, for **format 1**:
  four Game Boy channels, exactly. `python tools/chiptune.py test` replays
  sessions recorded from the original driver in the binjgb emulator (songs,
  SFX storms, mute, pause, seek, hold, drum samples) and checks that the port
  makes the **same APU register writes, in the same order, on the same frame**:
  about 173,000 writes across seven scenarios.
- **vox**, for **format 2**: 1-8 voices, each instrument choosing its
  oscillator (pulse with any width, wave, noise, sample, triangle, saw), a
  table able to switch it frame by frame (the SID drum trick), pulse-width
  modulation, ring modulation, hard sync, and one resonant multimode filter.
  Pitch and envelopes keep the Game Boy's semantics, so everything else --
  rows, commands, tables, SFX, ducking -- is the same driver.
- **vox PCM**, for **format 3**: the studio's guitars, drums, pads and
  supersaws as signed PCM8, with a source rate and root note per sample,
  linear interpolation and sustain loops. A separate shared bank can exceed
  64 KiB. Samples and vox's synthetic voices can play in the same song;
  rows, mute, sync, hold, SFX and ducking still use the GBM driver. This is
  Amiga/MOD-like sample playback, not YM2612/Genesis FM emulation.

Songs are tiny: the demo songs are 0.2-5.4 KB each. The three PCM examples share
one 207,412-byte bank; their patterns are 960-1,086 bytes each.

```
chiptune/
  gbm.c gbm.h         the driver: rows, notes, commands, tables, SFX, ducking; all three formats
  gbapu.c gbapu.h     the DMG APU, register-level (format 1)
  vox.c vox.h         SID-style synth and studio sample player (formats 2/3)
  chip.c chip.h       driver + synth inside an audio callback, with a command queue
  bank_codec.c/.h     lossless bank decoding on the loader's thread
  chiptune_pd.c/.h    the Playdate side: a sound source, Lua bindings
  chiptune_main.c     a stand-in eventHandler for games with no C of their own
  chiptune.cmake      the source list for a Playdate CMake project
  music/              the demo songs, SFX library and shared rock.gbank
chiptune.lua          the Lua module (repo root, like the other modules)
tools/chiptune.py     build the songs, encode, render, benchmark, run the tests
```

## Using it from Lua

The C half has to be compiled into the game: a Lua game becomes a Lua + C
game. With the repo as `Source/juice`, the smallest `CMakeLists.txt` (next to
`Source/`) is the SDK's template plus three lines:

```cmake
include(${CMAKE_CURRENT_SOURCE_DIR}/Source/juice/chiptune/chiptune.cmake)
if (TOOLCHAIN STREQUAL "armgcc")
	add_executable(${PLAYDATE_GAME_DEVICE} ${CHIPTUNE_SOURCES} ${CHIPTUNE_MAIN})
else()
	add_library(${PLAYDATE_GAME_NAME} SHARED ${CHIPTUNE_SOURCES} ${CHIPTUNE_MAIN})
endif()
```

`demo/CMakeLists.txt` is a complete one. A game that already has C leaves out
`CHIPTUNE_MAIN` and calls `chiptune_register(pd)` from its own `eventHandler`
on `kEventInitLua`.

```lua
import "juice/chiptune"

Chiptune.load{
    songs = { title = "juice/chiptune/music/cloud_garden.gbm",
              battle = "juice/chiptune/music/crimson_clash.gbm" },
    sfx = "juice/chiptune/music/sfx.gbm",      -- effects by name
    duck = { amount = 6, speed = 2 },          -- the music dips under effects
}

Chiptune.play("title")        -- no-op if it is already playing
Chiptune.sfx("coin")
Chiptune.mute({ 3, 5 })       -- layered music: the song keeps time
Chiptune.onSync(function(v) boss:enter() end)   -- an Exx command in the song
Chiptune.onEnd(function(name) showMenu() end)   -- a song without a loop ended

function playdate.update()
    Chiptune.update()         -- runs the callbacks; the music does not need it
end
function playdate.gameWillPause() Chiptune.pause() end
function playdate.gameWillResume() Chiptune.resume() end
```

Also: `stop`, `stopSfx`, `duck(amount, speed)`, `hold(order)` (loop one order
until released), `setVolume(l, r)`, `position()` (order, row), `levels()` (a
level per channel, for meters), `sfxNames()`, `isPlaying()`, `current()`.
Channels to `mute` are numbers 1-8 or `"pu1" "pu2" "wav" "noi"`. Without the C
extension `Chiptune.available` is false and every call is a no-op.

**Which synth plays.** gbapu while everything loaded is format 1, so a Game
Boy song is exactly a Game Boy; vox as soon as anything loaded is format 2.
The shipped SFX bank is format 2, so with it loaded the Game Boy songs play on
vox too, which renders the same channels with the same pitches and envelopes
(with band-limited pulses rather than the DMG's aliasing). A game that wants
the exact DMG loads a format-1 SFX bank or none.

**Why the audio thread.** The driver ticks 59.73 times a second, like the Game
Boy's VBlank. Ticked from a 30 fps `playdate.update`, every song would play at
half speed and every slow frame would stumble. So `chip_render` runs the
driver's tick and the drum-sample timer between the samples it renders, in
emulated CPU cycles, and the game's calls reach it through a queue.

**What it costs.** About 18 KB of code on the device. `python tools/chiptune.py
render song.gbm x.wav --bench` times the callback. On a desktop core: 21-27 ns
a sample for a Game Boy song on gbapu, 32 ns for a 6-voice format-2 song on
vox. From that, a Cortex-M7 at 168 MHz should spend roughly 5-12% of a core --
an estimate, not a measurement on hardware. The render is shaped for that CPU:
single-precision float only, no division per sample, vox works in 32-sample
blocks a voice at a time with one tight loop per oscillator, envelopes and
sweeps are stepped per block, and a note that has faded to silence is skipped
rather than computed. Nothing is rendered while nothing plays.

**pdc copies everything.** A submodule inside `Source/` brings the C sources,
tools and test fixtures into the `.pdx` too: about 300 KB of dead weight.
`pdc -k` (`--skip-unknown`) would leave those out, but it would leave out the
`.gbm` songs as well, since pdc does not know that type either. If the 300 KB
matters, copy just the `.gbm` files you use into your own `Source/` instead of
submoduling the repo there.

### Without the C extension

Render the music to files and play it with Jukebox and a sampleplayer:

```bash
python tools/chiptune.py render-all music_wav --adpcm --rate 22050
```

Each song becomes a mono ADPCM WAV (about 11 KB a second; pdc keeps it as
it is) and each effect `sfx_<name>.wav`. A looping song prints where its loop
starts, for `fileplayer:setLoopRange`. You lose what only a live driver can
do: sync markers, muting parts, effects stealing a channel.

### Rendered music: the studio

`studio/` renders what the chips cannot -- distorted guitars through an amp, orchestra hits,
a mastered mix -- into seamless ADPCM loops for `jukebox.lua`, and into instrument samples
(`studio/samples.cjs`, a sustain loop and a root note each) for a tracker. Node, no
dependencies. See `studio/README.md` for its sound recipes and bank exporter.

### Live studio samples: format 3

```bash
python tools/chiptune.py studio                    # Node + ffmpeg: build the shared bank and three themes
python tools/build_demo.py --jukebox               # starts in the music player; simulator + device if toolchain is present
python tools/chiptune.py render chiptune/music/steel_circuit.gbm build/steel_circuit.wav --bank chiptune/music/rock.gbank --mono
python tools/chiptune.py render chiptune/music/steel_circuit.gbm unused.wav --bank chiptune/music/rock.gbank --bench
```

The demo Jukebox includes fifteen songs. Up/down selects a track, A plays,
left/right switches live tracking and its rendered ADPCM stream. The mixer
in the Chiptune exhibit still mutes individual live layers.

```lua
Chiptune.load{
    banks = { band = "music/rock.gbank" },
    songs = {
        rock = { path = "music/steel_circuit.gbm", bank = "band" },
        jungle = { path = "music/chrome_breaks.gbm", bank = "band" },
        trance = { path = "music/prism_drive.gbm", bank = "band" },
    },
    sfx = "music/sfx.gbm",
}
Chiptune.play("rock")
```

Existing string song paths continue to work. SFX may also use `{path, bank}`.
The native loader validates and deduplicates immutable banks; it retains them
for the game session, so repeated songs do not duplicate the PCM in RAM.
Loading and copying happen on the game thread. The queue delivers a song and
its bank together; the audio callback never reads files or allocates memory.

To compose with your own studio bank:

```python
from gbm_compose import Song, studio_bank
from gbm_format import encode_song
s = Song('Band', version=3, voices=2, groove=(6, 7))
studio_bank(s, 'out/rock', rate=16384, only=['gtr_lead', 'kick'], out='band.gbank')
s.bar(['A4@gtr_lead . E5+318 . . . -', 'C5@kick . . . C5 . . .'])
open('band.gbm', 'wb').write(encode_song(s.project()))
```

`studio_bank` reads PCM16 mono WAVs and `bank.json`, filters/resamples with
ffmpeg, reassembles the loop seam, and quantises with deterministic TPDF
dither. Use the same selection and rate for every song sharing a bank.
Alternatively `python tools/chiptune.py bank out/rock band.gbank --rate 16384`
builds just the bank. Pattern notes are GBM numbers from C1=0; bank roots are
MIDI (C1=24). PCM8 slides, vibrato and table pitch offsets use 1/16-semitone
steps; synth voices and formats 1/2 keep their original period semantics.
An instrument may set `release` (milliseconds, zero keeps the original hard
cut) and `mixGain`. A PCM retrigger retains one bounded release overlap per
voice. Pause, mute and stop still silence it immediately.

### Porting the studio arrangement

`python tools/build_studio_port.py --publish` records the original menu,
play and multi songs, builds their shared bank, calibrates LUFS, mechanically
checks the encoded notes/gates and generates A/B reports before copying the
accepted assets to `music/`. The Jukebox starts on Studio Menu and compares
the live port with the original studio master. See
[studio/README.md](studio/README.md#the-original-studio-arrangements).

The original ports use `tickRate` (ticks/second) with a straight `(6,)`
groove, and `mixGain` to enable the output stage: 40 Hz DC blocker, block RMS
glue compressor, soft clip and a -1 dBFS peak limiter. Existing songs use the
original scheduler and output unless these extended format-3 fields are set.

## The demo songs

The PCM themes in `tools/studio_theme.py` all use format 3, eight voices and
`music/rock.gbank` (17 instruments, signed PCM8 at 16384 Hz):

| Song | Style | Live arrangement |
|---|---|---|
| `steel_circuit.gbm` | rock, ~138 BPM | amplified power chords and chugs, a looped lead with portamento/vibrato, bass, kit, orchestra hit and a vox acid break |
| `chrome_breaks.gbm` | jungle, ~171 BPM | chopped drum rows and ghost snares, looped reese, rave stabs, a pluck and pulse bleeps |
| `prism_drive.gbm` | trance, ~133 BPM | four-on-the-floor kit, offbeat bass, looped supersaw, Am/F/G pads, pluck arpeggio, breakdown and acid build |

Host callback benchmark: three runs of 60 seconds of audio in 256-frame
buffers, MSVC `/O2` on Windows. Median cost per output stereo frame was
13.2 ns (rock), 12.1 ns (jungle) and 13.6 ns (trance). `neon_acid` measured
14.0 ns both before and after the sampler change. These are host timings,
not a Cortex-M7 CPU percentage. Both SDK simulator and ARM builds pass;
physical-device profiling remains separate.

With release overlaps and mastering enabled, the original studio ports
measured 23.4 ns (menu), 23.1 ns (play) and 25.3 ns (multi) per output stereo
frame on the same host. The legacy `neon_acid` render remains byte-identical
to the pre-change renderer (14.4 ns in the current run). Bank decoding runs
before this benchmark, on the loader's thread.

Each is a style and a set of chiptune techniques.

| file | style | format | techniques |
|---|---|---|---|
| `cloud_garden.gbm` | main menu, D major, 90 BPM, a light swing | 2, 6 voices | a PWM pad holding its chord by arpeggio through a low-pass that opens by timed stages and closes for the loop; a triangle flute with an articulated attack (accent, scoop) and delayed vibrato, its echo three rows behind; broken chords panned left; a warm saw-wave bass |
| `tidal_twang.gbm` | surf rock, E, 179 BPM | 1 (DMG) | tremolo picking by retrigger (`9x2`); a glissando by slide; an articulated twang; a pulse kick sharing PU2 with the chord stabs; a pluck bass on the wave synth; ghost snares, accented hats, a crash on each section |
| `jungle_pulse.gbm` | drum & bass, F minor, 170 BPM | 2, 8 voices | a sampled break with dynamics (ghost snares, accented hats) and crescendo rolls (`9A2`), from a kit driven for the speaker; a reese of two saws detuned in a table through a resonant low-pass swinging between set bounds; the filter opening over the intro and closing the bass out of the breakdown; a sync marker at the drop |
| `crimson_clash.gbm` | JRPG battle, A minor, 163 BPM | 2, 7 voices | a hard-sync lead (a silent master; a saw above it sweeping up and settling, with an accent); SID drums (noise then a falling triangle; tone then noise; a pulse tom); 16th arps, then 8ths an octave up for the bridge; a saw bass walking in a semitone under each chord; PWM brass on a 3+3+2 accent |
| `willow_lane.gbm` | village waltz, G major, 3/4 | 1 (DMG) | duty swept by table with a scoop into each note, the Game Boy's PWM; 12-row bars; oom-pa-pa by arpeggio with auto-cut; a walking bass on a warm saw wave; a borrowed C minor; a countermelody |
| `hollow_deep.gbm` | dungeon, D phrygian, 100 BPM, 16 bars | 2, 7 voices | a ring-modulated bell (a triangle times a silent square a tritone and octave up); a wave drone through a resonant band-pass drifting within set bounds; a ghost line resolving phrygian-wise (F over E-flat, sliding to D), its echo; the snare sample two octaves down as a rumble; a B-flat to A cadence |
| `neon_acid.gbm` | acid house, A minor, 128 BPM, house swing | 2, 6 voices | the 303: a saw through a screaming low-pass whose cutoff each note sweeps down through its table, accents, slides sized to each jump (3-7 frames) that do not restart the filter; the build: closed then open tables and more resonance, a two-bar break without the kick, a clap roll; kick driven for the speaker; PWM stabs in opposite directions |
| `victory.gbm` | fanfare | 2, 5 voices | PWM brass in two parts, the lead articulated; a pulse bass walking up; a SID snare roll; a song that ends (`onEnd`) |
| `fade_out.gbm` | game over | 1 (DMG) | a slow fall over a chromatic bass, sighs of chord tones under it, F minor borrowed at the end |

The songs are code, in `tools/chiptune_songs.py`; `python tools/chiptune.py
songs` rebuilds `music/`.

## The SFX library

`music/sfx.gbm`, 84 effects, fired by name:

| | |
|---|---|
| interface | `cursor` `select` `back` `error` `pause` `text` `toggle` `score` |
| movement | `jump` `double_jump` `land` `step` `dash` `bounce` `splash` |
| combat | `hit` `hurt` `laser` `shoot` `explosion` `small_boom` `fuse` `sweep_shot` `death` |
| rewards | `coin` `pickup` `powerup` `oneup` `chest` `heal` `key` `magic` `win` `lose` |
| world | `door` `charge` `warp` `alarm` |
| transitions | `tr_<name>_fwd` / `tr_<name>_back` for each of `transitions.lua`'s 23 effects (`tr_slide_fwd`, `tr_clock_wipe_back`, ...) |

The transition whooshes are a noise shape walking up (forward) or down (back)
through a table, some with a tone on their first frames; `transitions.lua`
plays them when a game defines a `TransitionSounds.play(name, dir)` hook:

```lua
TransitionSounds = { play = function(name, dir)
    return Chiptune.sfx("tr_" .. name:lower():gsub(" ", "_") .. "_" .. dir)
end }
```

It is a format-2 bank on voices 6 and 7: every Game Boy song and every
format-2 song of up to 6 voices keeps all of its own channels -- an effect
steals nothing and the music only ducks. The interface is on voice 7 at
priority 1, so a menu blip never cuts a gameplay sound. A stronger effect
takes a slot from a weaker one; a weaker one is dropped.

## Writing music

`tools/gbm_compose.py` writes songs as code:

```python
from gbm_compose import Song, sid_kick, sid_snare, sample_voice, synth_kit

s = Song('My Song', groove=(6, 6), version=2, voices=5,        # 149 BPM in 16ths
         filter=dict(cutoff=90, resonance=10, mode=1))
s.voice('pulse', 'lead', volume=12, width=96, pwm=3, vibSpeed=4, vibDepth=2, vibDelay=12)
s.voice('saw', 'bass', volume=11, filter=True)
sid_kick(s); sid_snare(s)
sample_voice(s, synth_kit()[3], 'hat')
s.bar(['C5@lead . E5 . G5 . . . A5+047 . . . G5 . . .',
       'C2@bass+G1204 . . . G2 . . . A2 . . . E2+G12FC . . .',
       '.', 'D4@skick . . . A3@ssnare . . . D4@skick . D4 . A3@ssnare . . .',
       'C5@hat . C5 . C5 . C5 . C5 . C5 . C5 . C5 .'])
```

One token per row: `.` empty, `-` note off, `C4` / `C#4` / `Db4` a note
(C1 is 0), `#26` a raw note (noise: 0 dark to 45 bright), `@name` an
instrument, `+xyy` a command, `+Gxxyy` an extended command (format 2).
`Song.project()` is a `.gbm.json` project -- format 1 is the GBM tracker's own
-- and `python tools/chiptune.py encode` turns one into a `.gbm`. Format 1
(`Song(name)`, `s.inst('pulse' | 'wave' | 'noise', ...)`) plays on a real
Game Boy's terms; the recipes `noise_kick`, `noise_snare`, `pulse_kick`,
`sweep_kick`, `wave_kick`, `synth` and `sample_inst` work there.

### Mixing for a small speaker

A speaker the size of the Playdate's plays little below a few hundred Hz,
so a part that is all fundamental -- a triangle bass, a sine kick -- is full
in headphones and nearly gone on the device. What survives is harmonics. The
songs give every part that must carry on the device some: `bass_wave()` (a
warm low-passed saw) for basses, `punch_kit()` (a kick sweeping from ~350 Hz
under a click, driven into soft clipping; a snare with a body) for sampled
drums, pulse and SID recipes for the rest, and keep pure triangles for
doubling (a sub for headphones). As measured through a 300 Hz high-pass
standing in for the speaker, `punch_kit`'s kick delivers about three times
the old kick's energy there, and the songs' basses 1.4 to 2 times what they had.

`articulation()` builds a lead's attack table -- an accent fading into a
held sustain, and a scoop up into the pitch -- which is most of what makes a
chip lead sound played rather than switched on.

### Channels

Format 1: four fixed channels.

| | hardware | a note is | the instrument sets |
|---|---|---|---|
| PU1 | pulse + sweep | a period, C2-B8 | duty, envelope, sweep |
| PU2 | pulse | a period, C2-B8 | duty, envelope |
| WAV | wave | a period, an octave lower | a 32x4-bit wave, level 0-3 |
| NOI | noise | one of 46 shapes, ~1/3 octave apart | envelope, 7-bit mode, a drum sample |

Format 2: 1-8 voices, any instrument on any voice. The oscillators:

| | | the instrument's `duty` byte |
|---|---|---|
| `pulse` | band-limited, any width | width 0-255 (`pwm` walks it each frame, bouncing 16-240); the hardware sweep |
| `wave` | 32 x 4-bit, stepped | the wave |
| `noise` | the DMG's LFSR | 8 = 7-bit (metallic) |
| `sample` | 4-bit PCM, 8192 Hz at C5, follows the note | -- |
| `triangle`, `saw` | band-limited (saw), smooth | -- |

Every oscillator takes a full 0-15 envelope. `ring` multiplies a voice by the
previous voice's square and `sync` restarts it with the previous voice: a
voice at volume 0 still runs, which is how a silent master drives either.
`filter` routes a voice through the one filter (mono, low/band/high-pass,
combinable as on the SID).

### Commands

Several per row. Arpeggio, slides and vibrato hold until cancelled with `00`;
a new note resets slides.

| | | |
|---|---|---|
| `0xy` | arpeggio | note, +x, +y semitones, a frame each: a chord on one channel |
| `1xx` / `2xx` | slide up / down | xx period units a frame |
| `3xx` | portamento to this row's note | speed xx |
| `4xy` | vibrato | speed x, depth y |
| `5xx` | envelope (format-1 WAV: level 0-3) | restarts the note |
| `6xx` | duty / wave / noise mode | format 2 pulse: width |
| `7xx` | note delay | xx frames |
| `8xx` | pan | bit 0 right, bit 1 left |
| `9xy` | retrigger | every y frames; x: 1-7 quieter by x, 9-F louder by x-8 |
| `Axx` | cut | after xx frames |
| `Bxx` | jump to order xx | |
| `Cxx` | PU1 sweep | raw NR10 |
| `Dxx` | next order, from row xx | |
| `Exx` | sync marker | the game reads it: `Chiptune.onSync` |
| `Fxx` | groove xx | tempo: frames per row |

Format 2 adds, written `+Gccvv`:

| | | |
|---|---|---|
| `G10xx` | filter cutoff | 0-255, ~40 Hz to ~12 kHz |
| `G11rm` | resonance r (0-F), mode m | 1 low-pass, 2 band-pass, 4 high-pass, sums combine |
| `G12xx` | cutoff slide | signed, per frame; stops at the ends |
| `G13xx` | route this voice through the filter | 0 / 1 |
| `G14xx` | pulse width | 0-255 |
| `G15xx` | PWM | signed step per frame |
| `G16xx` | oscillator | 0 pulse, 1 wave, 2 noise, 3 sample, 4 triangle, 5 saw |
| `G17xx` / `G18xx` | ring / sync | 0 / 1 |

Any of them, and any pattern command, can sit in a table's command column: a
filter envelope per note is a table of `G10` cutoffs (`neon_acid`).

### Instruments and tables

An instrument sets the starting duty or wave, the envelope, the sweep, an
auto-cut length, a delayed vibrato and a **table**: a per-frame macro of rows
`[transpose, envelope, duty/wave, pitch offset, command]` with a loop point,
as in LSDj -- plus, in format 2, **an oscillator column**. Tables make the
drums (`noise_kick`: the shape falling fast; `sid_kick`: a frame of noise, then
a triangle falling), chords of 4+ notes, PWM on a Game Boy (the duty column
stepping), filter envelopes, detune (a constant pitch offset) and wave
synthesis: `synth()` builds a run of waves (a filtered, shaped oscillator, every
parameter moving across the run) and a table that steps through them. Presets:
`pluckBass`, `pwmBass`, `wah`, `growl`, `breath`, `reese`.

Drum **samples** (4-bit, 8192 Hz, `synth_kit()`: kick, snare, rim, hat, clap):
in format 1 they borrow the wave channel from the music while they sound
(`sample_inst`); in format 2 a sample is a voice's oscillator like any other
(`sample_voice`), steals nothing, and follows the note -- the kick two octaves
down is a boom.

A low **noise** shape starts silent: after a trigger the LFSR shifts 15 times
before its first 0 reaches the output, which at a few hundred Hz is a frame or
more. On a Game Boy as here. Trigger low sounds high and let a table walk the
shape down: a new shape without a restart keeps the LFSR running.

## The blob

All offsets are u16 little-endian from the start of the blob, so a blob plays
from wherever it is loaded.

```
0   'G' 'B' v        magic, format (1 or 2)
3   rows             per pattern (1-255)
4   order_count
5   loop_order       0xFF: stop at the end
6   sfx_count
7   voices           format 2: 1-8 (format 1: 0, meaning 4)
8   orders           order_count x [pattern x N, transpose x N]
10  pattern dirs     (N + 1) x u16: the channels, then the SFX
12  instruments      format 1 x 10: duty, vib, vib_delay, env, sweep, length, table (u16), t_speed, 0
                     format 2 x 16: osc, then those 10 (duty is the width for a pulse), then
                     sample+1, pwm, flags (1 ring, 2 sync, 4 filter), 0, 0, 0
14  tables           u16 x n -> [len, loop, len x (transpose, env, duty, pitch, cmd, val[, osc])]
16  waves            x 16 bytes (32 x 4-bit)
18  grooves          u16 x n -> [len, frames...]
20  sfx              x 4: pattern, channel (format 2: voice 0-7), priority, speed
22  samples          u16 x n -> format 1: [blocks, blocks x 16 bytes (CH3 frames)]
                                format 2: [u16 count, count 4-bit samples, high nibble first]
24  filter           format 2: cutoff, resonance << 4 | mode
```

Format 3 keeps format 2's instruments, tables and pattern streams. Its header
is 32 bytes: byte 2 is `3`, u16 at 26 is the external sample count, and u32 at
28 is the bank's content identity. Offset 22 addresses an empty legacy
sample directory. Song offsets remain u16; PCM is external.

Bit 15 of the count marks the extended 40-byte header: u32 at 32 is tick
rate in millihertz, u16 at 36 is output gain in Q8.8, bytes 38-39 reserved.
Instrument byte 13 is release milliseconds; bytes 14-15 are per-voice Q8.8
gain (zero means unity). Old 32-byte v3 songs keep their original behaviour.

The `.gbank` layout (all integers little-endian):

```
0   'G' 'B' 'K' 1
4   count:u16, reserved:u16=0, identity:u32
12  count x [offset:u32, length:u32, rate:u32, root_millihz:u32,
             loop_start:u32, loop_end:u32]
... signed PCM8, one byte per mono sample
```

Loop end is exclusive; both loop bounds are zero for a one-shot. Data offsets
are from the bank start. Identity is FNV-1a over the whole bank with bytes
8-11 treated as zero, including metadata and PCM. The loader checks bounds,
rates, loop geometry and identity before publishing the bank to the audio
thread, then verifies that a song names that bank.

`GBZ1` is a lossless on-disk wrapper: magic `GBZ` + byte 1, decoded size:u32,
raw bank identity:u32, count:u16, reserved:u16, then delta/context arithmetic
data. `bank_codec.c` reproduces the raw GBK1 bytes before validation. Its
263168-byte model is temporary, never used by a playing voice. Both the
native loader and host renderer accept raw or packed banks. Pure-C callers
use `bank_raw_size`/`bank_unpack` before `gbm_sample_bank_check`.

A pattern stream, per row: `[instrument] [command...]` then a note (`0x00-0x5F`),
`0x60` note off, `0x61` end of an SFX, or `0x80+n` (this row and n more are
empty). Instrument `0xC0+i` for 0-31, `0xF0 i` for any; command `0xE0|cmd val`,
extended command `0xF1 cmd val`.

After the blob, where the driver never looks, the encoder may add the SFX
names: `count { len bytes }*`, then the u16 length of that, then `NM`.

## Tests

```bash
python tools/chiptune.py test    # ROM traces, formats 2/3, bank import, encoder and shipped songs; ffmpeg for resampling
lua test/run.lua                 # chiptune.lua, among the rest
```

## Credits

GBM, its song format, the tracker it comes from, the drum recipes and the wave
synth are from gameboy-lab (jenissimo). The drum techniques follow the LSDj
manual, its wiki and lsdpatch, as that project documents; the extended mode
borrows its ideas from the MOS 6581 SID.
