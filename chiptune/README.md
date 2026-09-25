# chiptune

Game Boy music and sound effects for Playdate, from a real tracker driver.

The engine is **GBM**, a tracker music/SFX driver written for the original Game
Boy (four channels, instruments with LSDj-style tables, two SFX slots that
borrow a channel from the music, ducking, drum samples). Here it is ported from
SM83 assembly to portable C and runs against an emulated DMG APU inside a
Playdate audio callback. Songs are tiny: every demo song below is under 1.3 KB.

The port is not "inspired by" the original. `python tools/chiptune.py test`
replays recorded sessions of the original driver running in the binjgb
emulator (songs, SFX storms, mute, pause, seek, hold, drum samples) and
checks that the C port makes the **same APU register writes, in the same
order, on the same frame**: about 173,000 writes across seven scenarios. The
song encoder is checked byte for byte against the original's in the same run.

```
chiptune/
  gbm.c gbm.h         the driver: rows, notes, commands, tables, SFX, ducking
  gbapu.c gbapu.h     the DMG APU: 2 pulse, wave, noise; renders 16-bit stereo
  chip.c chip.h       both inside an audio callback, with a command queue
  chiptune_pd.c/.h    the Playdate side: a sound source, Lua bindings
  chiptune_main.c     a stand-in eventHandler for games with no C of their own
  chiptune.cmake      the source list for a Playdate CMake project
  music/              the demo songs and the SFX library, encoded
chiptune.lua          the Lua module (repo root, like the other modules)
tools/chiptune.py     encode, render, build the songs, run the tests
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
Chiptune.mute({ "wav" })      -- layered music: the song keeps time
Chiptune.onSync(function(v) boss:enter() end)   -- an Exx command in the song
Chiptune.onEnd(function(name) showMenu() end)   -- a song without a loop ended

function playdate.update()
    Chiptune.update()         -- runs the callbacks; the music does not need it
end
function playdate.gameWillPause() Chiptune.pause() end
function playdate.gameWillResume() Chiptune.resume() end
```

Also: `stop`, `stopSfx`, `duck(amount, speed)`, `hold(order)` (loop one order
until released), `setVolume(l, r)`, `position()` (order, row), `levels()` (the
four channels' current levels, for meters), `sfxNames()`, `isPlaying()`,
`current()`. Without the C extension `Chiptune.available` is false and every
call is a no-op, so a game still runs.

**Why the audio thread.** The driver ticks 59.73 times a second, like the Game
Boy's VBlank. Ticked from a 30 fps `playdate.update`, every song would play at
half speed and every slow frame would stumble. So `chip_render` runs the
driver's tick and the drum-sample timer between the samples it renders, in
emulated CPU cycles, and the game's calls reach it through a queue.

**What it costs.** About 11 KB of code on the device. On a desktop core it
renders about 430x faster than real time; from that, a Cortex-M7 at 168 MHz
should spend roughly 5-10% of a core on it. That is an estimate, not a
measurement on hardware. Nothing is rendered while nothing plays.

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

| file | style | shows |
|---|---|---|
| `cloud_garden.gbm` | main menu, airy, D major, 90 BPM | bell lead fading on each note, harp-like broken chords, a breathing wave pad |
| `tidal_twang.gbm` | surf rock, E, 179 BPM | tremolo picking by retrigger (`9x2`) over E phrygian dominant, a glissando, walking bass |
| `jungle_pulse.gbm` | drum & bass, F minor, 170 BPM | chopped noise breaks, ghost snares and retrigger rolls, a reese bass on the wave synth, a sync marker at the drop |
| `crimson_clash.gbm` | JRPG battle, A minor, 163 BPM | a pedal-tone riff, 16th-note broken chords, octave bass, a heroic lead |
| `willow_lane.gbm` | village waltz, G major, 3/4 | 12-row bars, oom-pa-pa chords, a borrowed C minor |
| `hollow_deep.gbm` | dungeon ambient, D minor | a growling drone, portamento, an echo on the second pulse, dripping water |
| `victory.gbm` | fanfare | a song that ends (`onEnd`) |
| `fade_out.gbm` | game over | a slow fall over a chromatic bass |

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

Interface sounds are on the second pulse at priority 1, so a menu blip never
cuts a gameplay sound; impacts are on the noise channel; bells and magic
borrow the wave channel for as long as they ring. A stronger effect takes a
slot from a weaker one; a weaker one is dropped.

## Writing music

`tools/gbm_compose.py` writes songs as code:

```python
from gbm_compose import Song, noise_kick, noise_snare, synth

s = Song('My Song', groove=(6, 6))                 # frames per row: 149 BPM in 16ths
s.inst('pulse', 'lead', duty=2, volume=12, vibSpeed=4, vibDepth=2, vibDelay=12)
synth(s, 'bass', 'pluckBass')                      # a wave-channel synth
kick, snare = noise_kick(s), noise_snare(s)
s.bar(['C5@lead . E5 . G5 . . . A5+047 . . . G5 . . .',   # PU1
       '.',                                                # PU2
       'C3@bass . . . G3 . . . A3 . . . E3 . . .',         # WAV
       '#28@kick . . . #33@snare . . . #28@kick . #28 . #33@snare . . .'])
```

One token per row: `.` empty, `-` note off, `C4` / `C#4` / `Db4` a note
(C1 is 0), `#26` a raw note (noise: 0 dark to 45 bright), `@name` an
instrument, `+xyy` a command. `Song.project()` is a `.gbm.json` project in the
format of gameboy-lab's GBM tracker, and `python tools/chiptune.py encode`
turns one into a `.gbm`.

### Channels

| | hardware | a note is | the instrument sets |
|---|---|---|---|
| PU1 | pulse + sweep | a period, C2-B8 | duty, envelope, sweep |
| PU2 | pulse | a period, C2-B8 | duty, envelope |
| WAV | wave | a period, an octave lower | a 32x4-bit wave, level 0-3 |
| NOI | noise | one of 46 shapes, ~1/3 octave apart | envelope, 7-bit mode, a drum sample |

### Commands

Several per row. Arpeggio, slides and vibrato hold until cancelled with `00`;
a new note resets slides.

| | | |
|---|---|---|
| `0xy` | arpeggio | note, +x, +y semitones, a frame each: a chord on one channel |
| `1xx` / `2xx` | slide up / down | xx period units a frame |
| `3xx` | portamento to this row's note | speed xx |
| `4xy` | vibrato | speed x, depth y |
| `5xx` | envelope (WAV: level 0-3) | restarts the note |
| `6xx` | duty / wave / noise mode | pulse 0-3; WAV wave index; NOI 8 = 7-bit |
| `7xx` | note delay | xx frames |
| `8xx` | pan | bit 0 right, bit 1 left |
| `9xy` | retrigger | every y frames; x: 1-7 quieter by x, 9-F louder by x-8 |
| `Axx` | cut | after xx frames |
| `Bxx` | jump to order xx | |
| `Cxx` | PU1 sweep | raw NR10 |
| `Dxx` | next order, from row xx | |
| `Exx` | sync marker | the game reads it: `Chiptune.onSync` |
| `Fxx` | groove xx | tempo: frames per row |

### Instruments and tables

An instrument sets the starting duty or wave, the envelope, the sweep, an
auto-cut length, a delayed vibrato and a **table**: a per-frame macro of rows
`[transpose, envelope, duty/wave, pitch offset, command]` with a loop point,
as in LSDj. Tables make the drums (`noise_kick`: the shape falling fast), the
pulse kick (a slide down, cut before it wraps), chords of 4+ notes, PWM, and
wave synthesis: `synth()` builds a run of waves (a filtered, shaped
oscillator, every parameter moving across the run) and a table that steps
through them. Presets: `pluckBass`, `pwmBass`, `wah`, `growl`, `breath`,
`reese`.

Drum **samples** (4-bit, 8192 Hz) play on the wave channel, borrowing it from
the music while they sound: `sample_inst(song, synth_kit()[0], 'kick')`.

## The blob

All offsets are u16 little-endian from the start of the blob, so a blob plays
from wherever it is loaded.

```
0   'G' 'B' 1        magic, version
3   rows             per pattern (1-255)
4   order_count
5   loop_order       0xFF: stop at the end
6   sfx_count
8   orders           order_count x [pattern x4, transpose x4]
10  pattern dirs     5 x u16: channels 0-3, then SFX
12  instruments      x 10: duty, vib, vib_delay, env, sweep, length, table (u16), t_speed, 0
14  tables           u16 x n -> [len, loop, len x (transpose, env, duty, pitch, cmd, val)]
16  waves            x 16 bytes (32 x 4-bit)
18  grooves          u16 x n -> [len, frames...]
20  sfx              x 4: pattern, channel, priority, speed
22  samples          u16 x n -> [blocks, blocks x 16 bytes]
```

A pattern stream, per row: `[instrument] [command...]` then a note (`0x00-0x5F`),
`0x60` note off, `0x61` end of an SFX, or `0x80+n` (this row and n more are
empty). Instrument `0xC0+i` for 0-31, `0xF0 i` for any; command `0xE0|cmd val`.

After the blob, where the driver never looks, the encoder may add the SFX
names: `count { len bytes }*`, then the u16 length of that, then `NM`.

## Tests

```bash
python tools/chiptune.py test    # the port against the original ROM, the encoder, the songs
lua test/run.lua                 # chiptune.lua, among the rest
```

## Credits

GBM, its song format, the tracker it comes from, the drum recipes and the wave
synth are from gameboy-lab (jenissimo). The drum techniques follow the LSDj
manual, its wiki and lsdpatch, as that project documents.
