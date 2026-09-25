# chiptune

Game Boy music and sound effects for Playdate, from a real tracker driver --
and an extended mode that goes past the Game Boy: up to 8 voices, SID-style.

The engine is **GBM**, a tracker music/SFX driver written for the original Game
Boy (instruments with LSDj-style tables, arpeggios, slides, vibrato, two SFX
slots that borrow a channel from the music, ducking, drum samples). Here it is
ported from SM83 assembly to portable C and runs inside a Playdate audio
callback, on one of two synths:

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

Songs are tiny: the demo songs are 0.2-3.4 KB each.

```
chiptune/
  gbm.c gbm.h         the driver: rows, notes, commands, tables, SFX, ducking; both formats
  gbapu.c gbapu.h     the DMG APU, register-level (format 1)
  vox.c vox.h         the extended synth (format 2)
  chip.c chip.h       driver + synth inside an audio callback, with a command queue
  chiptune_pd.c/.h    the Playdate side: a sound source, Lua bindings
  chiptune_main.c     a stand-in eventHandler for games with no C of their own
  chiptune.cmake      the source list for a Playdate CMake project
  music/              the demo songs and the SFX library, encoded
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

## The demo songs

Each is a style and a set of chiptune techniques.

| file | style | format | techniques |
|---|---|---|---|
| `cloud_garden.gbm` | main menu, D major, 90 BPM | 2, 6 voices | a PWM pad holding its chord by arpeggio through a low-pass that opens across the song; a triangle flute with delayed vibrato and its echo three rows behind; broken chords panned left |
| `tidal_twang.gbm` | surf rock, E, 179 BPM | 1 (DMG) | tremolo picking by retrigger (`9x2`); a glissando by slide; a pulse kick sharing PU2 with the chord stabs; a pluck bass on the wave synth |
| `jungle_pulse.gbm` | drum & bass, F minor, 170 BPM | 2, 8 voices | a sampled 808 break with retrigger rolls on two voices of its own; a reese of two saws detuned in a table, through a resonant low-pass swinging open and shut; a triangle sub; a sync marker at the drop |
| `crimson_clash.gbm` | JRPG battle, A minor, 163 BPM | 2, 7 voices | a hard-sync lead (a silent master, a saw above it sweeping through a table); SID drums (noise then a falling triangle; tone then noise; a pulse tom); PWM brass stabs; 16th-note broken chords |
| `willow_lane.gbm` | village waltz, G major, 3/4 | 1 (DMG) | duty swept by table, the Game Boy's PWM; 12-row bars; oom-pa-pa by arpeggio with auto-cut; a walking bass; a borrowed C minor; a countermelody |
| `hollow_deep.gbm` | dungeon, D phrygian, 100 BPM | 2, 7 voices | a ring-modulated bell (a triangle times a silent square a tritone and octave up); a wave drone through a resonant band-pass drifting by cutoff slides; portamento and echo; the 808 kick sample two octaves down as a boom |
| `neon_acid.gbm` | acid house, A minor, 128 BPM | 2, 6 voices | the 303: a saw through a screaming low-pass whose cutoff each note sweeps down through its table, accents, slides by portamento; four-on-the-floor 808 samples; PWM stabs moving in opposite directions |
| `victory.gbm` | fanfare | 2, 5 voices | PWM brass in two parts; a SID snare roll; a song that ends (`onEnd`) |
| `fade_out.gbm` | game over | 1 (DMG) | a slow fall over a chromatic bass and its quieter echo |

The songs are code, in `tools/chiptune_songs.py`; `python tools/chiptune.py
songs` rebuilds `music/`.

## The SFX library

`music/sfx.gbm`, 38 effects, fired by name:

| | |
|---|---|
| interface | `cursor` `select` `back` `error` `pause` `text` `toggle` `score` |
| movement | `jump` `double_jump` `land` `step` `dash` `bounce` `splash` |
| combat | `hit` `hurt` `laser` `shoot` `explosion` `small_boom` `fuse` `sweep_shot` `death` |
| rewards | `coin` `pickup` `powerup` `oneup` `chest` `heal` `key` `magic` `win` `lose` |
| world | `door` `charge` `warp` `alarm` |

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

A pattern stream, per row: `[instrument] [command...]` then a note (`0x00-0x5F`),
`0x60` note off, `0x61` end of an SFX, or `0x80+n` (this row and n more are
empty). Instrument `0xC0+i` for 0-31, `0xF0 i` for any; command `0xE0|cmd val`,
extended command `0xF1 cmd val`.

After the blob, where the driver never looks, the encoder may add the SFX
names: `count { len bytes }*`, then the u16 length of that, then `NM`.

## Tests

```bash
python tools/chiptune.py test    # format 1 against the original ROM, format 2 and vox, the encoder, the songs
lua test/run.lua                 # chiptune.lua, among the rest
```

## Credits

GBM, its song format, the tracker it comes from, the drum recipes and the wave
synth are from gameboy-lab (jenissimo). The drum techniques follow the LSDj
manual, its wiki and lsdpatch, as that project documents; the extended mode
borrows its ideas from the MOS 6581 SID.
