# chiptune

Tracker music and sound effects for Playdate, in C, with a Lua API.

The driver is **GBM**, a music/SFX driver for the original Game Boy
(instruments with LSDj-style tables, arpeggios, slides, vibrato, two SFX slots
that borrow a channel from the music, ducking). This is a port of it from SM83
assembly to C, running in a Playdate audio callback, with two synth backends:

- **gbapu** -- the DMG's APU, register by register. Format 1 songs play
  exactly as on a Game Boy; `python tools/chiptune.py test` replays sessions
  recorded from the original driver in an emulator and checks the port makes
  the same register writes on the same frames.
- **vox** -- 1-8 voices for formats 2-4. Each instrument picks its oscillator
  (pulse of any width, wave, noise, 4-bit sample, triangle, saw), with PWM,
  ring mod, hard sync and one resonant filter (SID-style). Format 3 adds an
  FT2-style 8-bit sampler with samples embedded in the song; format 4 plays
  instruments from a shared external `.gbank`.

```
chiptune/
  gbm.c gbm.h         the driver: rows, notes, commands, tables, SFX, ducking
  gbapu.c gbapu.h     DMG APU (format 1)
  vox.c vox.h         the synth and sample player (formats 2-4)
  chip.c chip.h       driver + synth inside an audio callback, with a command queue
  bank_codec.c/.h     packed .gbank decoding
  chiptune_pd.c/.h    Playdate sound source and Lua bindings
  chiptune_main.c     an eventHandler for games with no C of their own
  chiptune.cmake      source list for a Playdate CMake project
  music/              demo songs, the SFX bank and sample banks
  music/src/          the format 1/2 songs and SFX as .gbm.json projects
  samples/            WAVs embedded by the format 3 songs
chiptune.lua          the Lua module (repo root)
tools/chiptune.py     build songs, render, benchmark, test
```

## Using it from Lua

The C half has to be compiled into the game. With the repo as `Source/juice`,
the SDK's `CMakeLists.txt` template needs three more lines:

```cmake
include(${CMAKE_CURRENT_SOURCE_DIR}/Source/juice/chiptune/chiptune.cmake)
if (TOOLCHAIN STREQUAL "armgcc")
	add_executable(${PLAYDATE_GAME_DEVICE} ${CHIPTUNE_SOURCES} ${CHIPTUNE_MAIN})
else()
	add_library(${PLAYDATE_GAME_NAME} SHARED ${CHIPTUNE_SOURCES} ${CHIPTUNE_MAIN})
endif()
```

See `demo/CMakeLists.txt`. A game with its own C leaves out `CHIPTUNE_MAIN`
and calls `chiptune_register(pd)` from its `eventHandler` on `kEventInitLua`.

```lua
import "juice/chiptune"

Chiptune.load{
    songs = { title = "juice/chiptune/music/cloud_garden.gbm",
              battle = "juice/chiptune/music/crimson_clash.gbm" },
    sfx = "juice/chiptune/music/sfx.gbm",      -- effects by name
    duck = { amount = 6, speed = 2 },          -- music dips under effects
}

Chiptune.play("title")        -- no-op if already playing
Chiptune.sfx("coin")
Chiptune.mute({ 3, 5 })       -- mute layers; the song keeps time
Chiptune.onSync(function(v) boss:enter() end)   -- an Exx command in the song
Chiptune.onEnd(function(name) showMenu() end)   -- a song without a loop ended

function playdate.update()
    Chiptune.update()         -- runs callbacks; playback doesn't need it
end
function playdate.gameWillPause() Chiptune.pause() end
function playdate.gameWillResume() Chiptune.resume() end
```

Also: `stop`, `stopSfx`, `duck(amount, speed)`, `hold(order)` (loop one order
until released), `setVolume(l, r)`, `position()` (order, row), `levels()` (per
channel, for meters), `sfxNames()`, `isPlaying()`, `current()`. Channels for
`mute` are 1-8 or `"pu1" "pu2" "wav" "noi"`. Without the C extension
`Chiptune.available` is false and every call is a no-op.

Songs with a sample bank:

```lua
Chiptune.load{
    banks = { band = "music/rock.gbank" },
    songs = { rock = { path = "music/steel_circuit.gbm", bank = "band" } },
    sfx = "music/sfx.gbm",
}
```

Banks are validated and loaded once on the game thread and kept for the
session; the audio callback never reads files or allocates.

**Which synth plays:** gbapu while everything loaded is format 1, vox as soon
as anything is format 2 or later. The shipped SFX bank is format 2, so with it
loaded Game Boy songs play on vox (same pitches and envelopes, band-limited
pulses). Load a format-1 SFX bank, or none, for the exact DMG.

**Timing:** SFX, ducking and formats 1-2 tick at the Game Boy's 59.73 Hz.
Format 3 can set BPM and format 4 a tick rate; music then runs on its own
clock and SFX keep theirs.

**Compile-time knobs:**

| | default | |
|---|---|---|
| `CHIPTUNE_RATE` | 44100 | render rate (`chiptune_pd.c`). 22050 renders half the samples and loses the top above 11 kHz. |
| `VOX_BLOCK` | 64 | samples per block. Buffers are on the audio callback's stack, ~26 bytes per sample of block. |
| `CHIP_TICK_LATE_US` | 1500 | how late a tick may be to land on a block boundary. 0: sample-exact. Format 4 is always sample-exact. |

Measure CPU with `python tools/chiptune.py render song.gbm x.wav --bench`
(host timing, not a device percentage).

**pdc copies everything.** If the repo is a submodule inside `Source/`, the C
sources and tools end up in the `.pdx`. `pdc -k` would also skip the `.gbm`
files. Copy just the `.gbm`/`.gbank` files you use into your own `Source/`.

### Without the C extension

Render to files and play them with `jukebox.lua`:

```bash
python tools/chiptune.py render-all music_wav --adpcm --rate 22050
```

Each song becomes a mono ADPCM WAV (~11 KB/s) and each effect `sfx_<name>.wav`.
Looping songs print their loop start for `fileplayer:setLoopRange`. You lose
sync markers, muting and channel stealing.

## Demo songs

| file | style | format |
|---|---|---|
| `cloud_garden` | menu, D major, 90 BPM | 2, 6 voices |
| `tidal_twang` | surf rock, E, 179 BPM | 1 (DMG) |
| `jungle_pulse` | drum & bass, F minor, 170 BPM | 2, 8 voices |
| `crimson_clash` | battle, A minor, 163 BPM | 2, 7 voices |
| `willow_lane` | village waltz, G major, 3/4 | 1 (DMG) |
| `hollow_deep` | dungeon, D phrygian, 100 BPM | 2, 7 voices |
| `neon_acid` | acid house, A minor, 128 BPM | 2, 6 voices |
| `victory` | fanfare, no loop | 2, 5 voices |
| `fade_out` | game over, no loop | 1 (DMG) |
| `iron_spire` | NES-style action theme, D minor, 179 BPM | 2, 4 voices |
| `jungle_ride` `jungle_race` `jungle_menu` | jungle, 164-176 BPM | 3, samples embedded (69-94 KB) |
| `steel_circuit` `chrome_breaks` `prism_drive` | rock, jungle, trance | 4, `rock.gbank` |
| `studio_menu` `studio_play` `studio_multi` | rock | 4, `overturn.gbank`, tick rate + mastering |

Formats 1 and 2 have their sources in `music/src/` as `.gbm.json` projects;
`python tools/chiptune.py songs` rebuilds the `.gbm` files from them and
`test` checks they match. Formats 3 and 4 ship compiled.

`python tools/build_demo.py --jukebox --song iron_spire` opens the demo's
Jukebox on a song; left/right switches between live playback and its ADPCM
render.

## SFX

`music/sfx.gbm`, 84 effects, fired by name:

| | |
|---|---|
| interface | `cursor` `select` `back` `error` `pause` `text` `toggle` `score` |
| movement | `jump` `double_jump` `land` `step` `dash` `bounce` `splash` |
| combat | `hit` `hurt` `laser` `shoot` `explosion` `small_boom` `fuse` `sweep_shot` `death` |
| rewards | `coin` `pickup` `powerup` `oneup` `chest` `heal` `key` `magic` `win` `lose` |
| world | `door` `charge` `warp` `alarm` |
| transitions | `tr_<name>_fwd` / `tr_<name>_back` for each of `transitions.lua`'s 23 effects |

`transitions.lua` plays them if the game defines a hook:

```lua
TransitionSounds = { play = function(name, dir)
    return Chiptune.sfx("tr_" .. name:lower():gsub(" ", "_") .. "_" .. dir)
end }
```

The bank is format 2 on voices 6 and 7, so songs of up to 6 voices (and every
Game Boy song) lose no channels to effects; the music only ducks. Interface
sounds are on voice 7 at priority 1, so a menu blip never cuts a gameplay
sound. A stronger effect takes a slot from a weaker one; a weaker one is
dropped.

## Writing music

Songs are `.gbm.json` projects (format 1 is the GBM tracker's own format);
`python tools/chiptune.py encode song.gbm.json song.gbm` compiles one.
`tools/gbm_compose.py` builds them from Python if you'd rather script:

```python
import json
from gbm_compose import Song, sid_kick, sid_snare, sample_voice, synth_kit

s = Song('My Song', groove=(6, 6), version=2, voices=5,
         filter=dict(cutoff=90, resonance=10, mode=1))
s.voice('pulse', 'lead', volume=12, width=96, pwm=3, vibSpeed=4, vibDepth=2, vibDelay=12)
s.voice('saw', 'bass', volume=11, filter=True)
sid_kick(s); sid_snare(s)
sample_voice(s, synth_kit()[3], 'hat')
s.bar(['C5@lead . E5 . G5 . . . A5+047 . . . G5 . . .',
       'C2@bass+G1204 . . . G2 . . . A2 . . . E2+G12FC . . .',
       '.', 'D4@skick . . . A3@ssnare . . . D4@skick . D4 . A3@ssnare . . .',
       'C5@hat . C5 . C5 . C5 . C5 . C5 . C5 . C5 .'])
open('my_song.gbm.json', 'w').write(json.dumps(s.project()))
```

One token per row: `.` empty, `-` note off, `C4` / `C#4` / `Db4` a note
(C1 = 0), `#26` a raw note (noise: 0 dark to 45 bright), `@name` an
instrument, `+xyy` a command, `+Gxxyy` an extended command (format 2+).

`tools/nes.py` has NES-style presets for a four-voice format-2 song (pulses on
voices 1-2, triangle on 3, noise on 4): `bright_pulse` / `riff_harmony` (25%),
`air_square` / `pulse_echo` (50%), `thin_lead` / `thin_riff` (12.5%),
`wide_lead` (75%), `reprise_square` / `reprise_echo`, `final_pulse` /
`final_harmony`, `triangle_bass`, `triangle_tom`, `noise_hat` / `noise_open`
(#43), `noise_snare` (#32), `noise_kick` (#30). Each second name is the quieter
twin, for an echo or harmony on the other pulse.

**Small speaker:** the Playdate's speaker plays little below a few hundred
Hz, so a pure triangle bass or sine kick nearly disappears on the device.
Give parts that must carry some harmonics: `bass_wave()` (a low-passed saw)
for bass, `punch_kit()` for sampled drums. `articulation()` builds a lead's
attack table (accent and scoop).

### Channels

Format 1: four fixed channels.

| | hardware | a note is | the instrument sets |
|---|---|---|---|
| PU1 | pulse + sweep | a period, C2-B8 | duty, envelope, sweep |
| PU2 | pulse | a period, C2-B8 | duty, envelope |
| WAV | wave | a period, an octave lower | a 32x4-bit wave, level 0-3 |
| NOI | noise | one of 46 shapes, ~1/3 octave apart | envelope, 7-bit mode, a drum sample |

Format 2: 1-8 voices, any instrument on any voice.

| oscillator | | the instrument's `duty` byte |
|---|---|---|
| `pulse` | band-limited, any width | width 0-255 (`pwm` sweeps it, bouncing 16-240); hardware sweep |
| `wave` | 32 x 4-bit, stepped | the wave |
| `noise` | the DMG's LFSR | 8 = 7-bit (metallic) |
| `sample` | 4-bit PCM, 8192 Hz at C5, follows the note | -- |
| `triangle`, `saw` | band-limited | -- |

Every oscillator has a 0-15 envelope. `ring` multiplies a voice by the
previous voice's square, `sync` restarts it with the previous voice (a voice at
volume 0 still runs, so it can be a silent master). `filter` routes a voice
through the single filter (low/band/high-pass, combinable).

### Commands

Several per row. Arpeggio, slides and vibrato hold until cancelled with `00`;
a new note resets slides.

| | | |
|---|---|---|
| `0xy` | arpeggio | note, +x, +y semitones, a frame each |
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
| `Exx` | sync marker | `Chiptune.onSync` |
| `Fxx` | groove xx | frames per row |

Format 2 adds, written `+Gccvv`:

| | | |
|---|---|---|
| `G10xx` | filter cutoff | 0-255, ~40 Hz to ~12 kHz |
| `G11rm` | resonance r (0-F), mode m | 1 low-pass, 2 band-pass, 4 high-pass, sums combine |
| `G12xx` | cutoff slide | signed, per frame |
| `G13xx` | route this voice through the filter | 0 / 1 |
| `G14xx` | pulse width | 0-255 |
| `G15xx` | PWM | signed step per frame |
| `G16xx` | oscillator | 0 pulse, 1 wave, 2 noise, 3 sample, 4 triangle, 5 saw |
| `G17xx` / `G18xx` | ring / sync | 0 / 1 |

Any of these can also go in a table's command column (e.g. a per-note filter
envelope as a table of `G10` cutoffs).

Format 3 adds FT2's commands:

| | | |
|---|---|---|
| `G19xx` | sample offset (FT2 `9xx`) | start xx x 256 frames in; retriggers start there too |
| `G1Axy` | volume slide (FT2 `Axy`) | x up, y down per tick, 0-64; holds until `00` or the next note |
| `G1B01` | backwards | play the row's note backwards |
| `G1Cxx` | volume (FT2 volume column) | 0-40 hex; on its own row it changes the sounding note |
| `G1Exx` | pan position (FT2 `8xx`) | 0 left, 80 centre, FF right |
| `G1Fxx` | BPM (FT2 `Fxx` above 1F) | tick every 2.5 / xx s; `00` back to the Game Boy frame |

### Format 3 samples

```python
from gbm_compose import Song, load_wav, pcm_voice

s = Song('Break', groove=(6,), version=3, voices=4, bpm=170, amp=32)
brk = load_wav('chiptune/samples/break_a.wav', rate=round(2048 * 170 / 15))
pcm_voice(s, brk, 'brk', level=64)
s.bar(['C5@brk+G1900 . . . C5+G1920 . . . C5+G1900 . C5+G1910 . C5+G1920 . . C5+G1960+904',
       '.', '.', '.'])
```

A sample is signed 8-bit at the rate it plays at on C5, resampled with linear
interpolation. `load_wav` reads 8/16-bit mono WAVs and their `smpl` chunk
(root note, loop). For a break recorded one bar long with a 16th every 2048
frames, `rate = 2048 * BPM / 15` lines its 16ths up with the song's, and 16th
n is offset `8n`. `bpm` makes the tick 2.5 / BPM s as in FT2; `amp` is FT2's
amplification in 16ths. Cut or retriggered samples fade over ~1 ms instead of
clicking.

### Format 4 banks

```python
from gbm_compose import Song, sample_bank
from gbm_format import encode_song
s = Song('Band', version=4, voices=2, groove=(6, 7))
sample_bank(s, 'my_samples', rate=16384, only=['gtr_lead', 'kick'], out='band.gbank')
s.bar(['A4@gtr_lead . E5+318 . . . -', 'C5@kick . . . C5 . . .'])
open('band.gbm', 'wb').write(encode_song(s.project()))
```

`sample_bank` reads a folder of PCM16 mono WAVs plus a `bank.json` (name,
file, rate, root, loop per sample), resamples with ffmpeg and quantises to
8 bits with dither. Songs sharing a bank must use the same selection and rate.
`python tools/chiptune.py bank DIR out.gbank --rate 16384` builds just the
bank. Pattern notes are GBM numbers (C1 = 0); bank roots are MIDI (C1 = 24).
An instrument may set `release` (ms; 0 is a hard cut) and `mixGain`. A song
may set `tickRate` (ticks/s) and `mixGain`, which enables the output stage
(DC blocker, compressor, soft clip, -1 dBFS limiter).

### Instruments and tables

An instrument sets the starting duty or wave, envelope, sweep, auto-cut
length, delayed vibrato and a **table**: a per-frame macro of rows
`[transpose, envelope, duty/wave, pitch offset, command]` with a loop point,
as in LSDj, plus an oscillator column in format 2. Tables make the drums
(`noise_kick`, `sid_kick`: a frame of noise, then a falling triangle), chords
of 4+ notes, PWM on a Game Boy, filter envelopes, detune and wave synthesis
(`synth()`; presets `pluckBass`, `pwmBass`, `wah`, `growl`, `breath`, `reese`).

Drum samples (4-bit, 8192 Hz, `synth_kit()`: kick, snare, rim, hat, clap):
format 1 borrows the wave channel while one plays (`sample_inst`); in format 2
a sample is just an oscillator (`sample_voice`) and follows the note.

A low noise shape starts silent: after a trigger the LFSR shifts 15 times
before its first 0 reaches the output, a frame or more at low rates. Trigger
high and let a table walk the shape down.

## The blob

All offsets are u16 little-endian from the start of the blob, so it plays from
wherever it's loaded.

```
0   'G' 'B' v        magic, format (1-4)
3   rows             per pattern (1-255)
4   order_count
5   loop_order       0xFF: stop at the end
6   sfx_count
7   voices           format 2+: 1-8 (format 1: 0, meaning 4)
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

**Format 3** has a 30-byte header: sample count at 26, BPM at 27 (0 = Game Boy
frame), amplification in 16ths at 28, byte 29 reserved. Instrument byte 13 is
channel volume 0-64. The sample directory points to 24-byte records: flags
(bit 0 loops), 3 reserved bytes, then u32 rate at C5, PCM offset, frame count,
loop start, loop length. Signed PCM8 follows the song streams, plus one guard
frame per sample, and may extend past 64 KiB. Max 2^19 frames per sample.

**Format 4** keeps format 2's layout with a 32-byte header: u16 at 26 is the
external sample count, u32 at 28 the bank's identity. Bit 15 of the count marks
a 40-byte header: u32 at 32 is the tick rate in mHz, u16 at 36 the output gain
in Q8.8. Instrument byte 13 is release in ms; bytes 14-15 a Q8.8 gain (0 =
unity).

The `.gbank` layout (little-endian):

```
0   'G' 'B' 'K' 1
4   count:u16, reserved:u16=0, identity:u32
12  count x [offset:u32, length:u32, rate:u32, root_millihz:u32,
             loop_start:u32, loop_end:u32]
... signed PCM8, one byte per mono sample
```

Loop end is exclusive; both bounds are zero for a one-shot. Identity is
FNV-1a over the whole bank with bytes 8-11 as zero. The loader checks bounds,
rates, loops and identity before the audio thread sees the bank, and that the
song names that bank.

`GBZ1` is a lossless packed bank: `GBZ` + 1, decoded size:u32, identity:u32,
count:u16, reserved:u16, then delta/context arithmetic-coded data.
`bank_codec.c` restores the GBK1 bytes before validation (a temporary
263168-byte model). C callers use `bank_raw_size`/`bank_unpack` before
`gbm_sample_bank_check`.

A pattern stream, per row: `[instrument] [command...]` then a note
(`0x00-0x5F`), `0x60` note off, `0x61` end of an SFX, or `0x80+n` (this row and
n more are empty). Instrument `0xC0+i` for 0-31, `0xF0 i` for any; command
`0xE0|cmd val`, extended command `0xF1 cmd val`. After the blob the encoder
may append SFX names: `count { len bytes }*`, the u16 length of that, then
`NM`.

## Tests

```bash
python tools/chiptune.py test    # ROM traces, formats 2-4, banks, encoder, shipped songs
lua test/run.lua                 # the Lua modules
```

## Credits

GBM, its song format, tracker, drum recipes and wave synth are from
gameboy-lab (jenissimo). Drum techniques follow the LSDj manual, its wiki and
lsdpatch; the extended mode borrows from the MOS 6581 SID; the sampler follows
FastTracker 2. See `samples/CREDITS.md`.
