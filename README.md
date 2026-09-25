# playdate-juice

Drop-in game-feel modules for [Playdate](https://play.date/): scene
transitions, a procedural sound engine, music, Game Boy chiptune, tweens,
screen shake, particles and animated backgrounds.

Eight independent modules. Take one, take all of them — nothing here imports
anything else in the repo. Seven are single Lua files; chiptune is a Lua file
plus a C extension (`chiptune/`).

| Module | Global | What it is |
|---|---|---|
| `transitions.lua` | `Transitions` | 23 direction-aware scene transitions + a scene-hop plan |
| `sfxkit.lua` | `SfxKit` | procedural SFX: voice pool, time-based allocator, recipes as data |
| `jukebox.lua` | `Jukebox` | streamed music: crossfades, ducking, pause handling |
| `chiptune.lua` + `chiptune/` | `Chiptune` | tracker music and SFX: a C port of a real Game Boy driver, plus an 8-voice SID-style mode; 9 songs, 38 effects |
| `tween.lua` | `Tween` | 31 easings, sequences, parallel groups, springs — zero per-frame allocation |
| `shake.lua` | `Shake` | trauma-based screen shake with deterministic noise |
| `particles.lua` | `Particles` | pooled 1-bit particle system |
| `backgrounds.lua` | `Backgrounds` | 17 looping procedural backgrounds |

Everything is host-testable: `lua test/run.lua` runs the whole suite with no
SDK and no device. That is a deliberate design constraint, not a bonus — see
[CONVENTIONS.md](CONVENTIONS.md).

## Install

Copy the `.lua` files you want into your `Source/`, or take the lot as a
submodule:

```bash
git submodule add https://github.com/jenissimo/playdate-juice Source/juice
```

```lua
import "juice/sfxkit"
import "juice/transitions"
```

`pdc` compiles every `.lua` in your source tree, so a submodule brings its
`test/` and `demo/` along as a few dead `.pdz` files. Harmless, and the price
of not needing a build step.

## transitions

```lua
import "transitions"

function changeScene()
    Transitions.start("Slide", "fwd", 24)   -- name, direction, frames
    currentScene = newScene
end

function playdate.update()
    if not Transitions.active then handleInput() end
    Transitions.draw(function() currentScene:draw() end)
end
```

23 effects: Slide, Fade, Dissolve, Circle, Diamonds, Diamond Wave, Triangles,
Bubbles, Blinds, Clock Wipe, Wave Wipe, Interleave, Dither Bands, Spiral, Wind,
Melt, Shatter, Scanline, Pixel Shift, Hexagons, Diagonal, Paw Walk, Blink.

**Scene-hop plans.** Rather than picking an effect at each call site, declare
what every navigation hop means — and, just as importantly, which hops stay
bare:

```lua
Transitions.setPlan({
    ["menu>rules"] = { "Paw Walk", "fwd",  16 },
    ["menu>run"]   = { "Blink",    "fwd",  20 },
}, {
    ["loading>game"] = "the board already plays its own entry reveal",
})

Transitions.play("menu>rules")   -- unknown or bare hops are silently no-ops
```

`setPlan` validates effect names and refuses a hop listed in both tables, so a
typo is a startup error rather than a scene change that quietly does nothing
months later.

Paw Walk needs `images/paw_print.png` and `images/paw_plate.png`; they load
lazily on first use and degrade to an unstamped wipe if missing.
`Transitions.setImagePath("your/folder/")` repoints them.

## sfxkit

Procedural sound effects without hand-managing synths.

```lua
import "sfxkit"

SfxKit.load{
    buses  = { sfx = { volume = 0.85, crush = { amount = 0.22, mix = 0.35 } } },
    groups = { lead  = { wave = "square", count = 6, bus = "sfx" },
               riser = { wave = "square", count = 1, bus = "sfx", lfo = "sawtoothUp" } },
    budget = { synth = 2, sample = 1 },
}

SfxKit.define("confirm", { prio = 1, notes = {
    { group = "lead", hz = 392.00, vol = 0.30, len = 0.07, at = 0.000, adsr = { 0, 0.05, 0, 0.04 } },
    { group = "lead", hz = 523.25, vol = 0.30, len = 0.07, at = 0.055, adsr = { 0, 0.05, 0, 0.04 } },
} })

function playdate.update()
    SfxKit.frame()        -- must be first: resets this frame's emit budget
    ...
    SfxKit.emit("confirm")
end
```

A recipe can also be a `function(...)` returning a recipe, for sounds that read
game state.

**Why not just call `playdate.sound` directly:**

- **A synth holds exactly one note event.** Play a second note on a synth that
  is still holding one and the first is not mixed — it is *deleted*. The usual
  workaround is hand-assigning voices ("use `LEAD[4]` here, because the confirm
  sound took `LEAD[1..3]` this frame"), which encodes one specific scene graph
  and does not survive being moved. `sfxkit` allocates by audio time *and* by
  frame, which covers both the same-frame collision and the note scheduled 0.9 s
  ahead that a later emit would otherwise truncate.
- **Frame budget.** Six input branches can each want a sound in one frame.
  Priority 1 always sounds; 2 and 3 spend a budget and are dropped when it is
  gone. Charged per *sound*, not per note, so chords survive.
- **Glide maths that is actually right.** A frequency modulator is scaled in
  octaves, not Hz, and a sawtooth LFO covers its range in one period, so the
  rate is `1/T`. Both mistakes fail silently — `playNote` never complains.
  `SfxKit.glide(hi, lo, seconds)` returns the correct rate/centre/depth.
- **Recipes are data**, so `SfxKit.validate` turns a typo'd group name into a
  test failure instead of silence on hardware.

## jukebox

```lua
Jukebox.load{ tracks  = { menu = "sound/menu", level = "sound/level" },
              volumes = { menu = 0.45, level = 0.55 } }

Jukebox.play("menu")                      -- no-op if already playing it
Jukebox.switch("menu", "level", 0.35, 0.30)
Jukebox.duck(0.22, 0.15); Jukebox.restore()
```

Wire `Jukebox.pause` / `Jukebox.resume` to `playdate.gameWillPause` /
`gameWillResume` — without the resume hook the music stays ducked for the rest
of the session after the first pause.

Handles the things that get re-derived in every project: not restarting a track
that is already playing, not letting two crossfades race, and doing every fade
through the fileplayer's own fade argument (which runs on the audio thread)
rather than as a per-frame ramp on the busiest frames in the game.

## chiptune

```lua
Chiptune.load{ songs = { title = "juice/chiptune/music/cloud_garden.gbm" },
               sfx = "juice/chiptune/music/sfx.gbm" }
Chiptune.play("title")
Chiptune.sfx("coin")          -- the music ducks under it
Chiptune.mute({ "wav" })      -- the song keeps time
```

GBM, a tracker driver for the original Game Boy, ported from SM83 assembly to
C and run inside the audio callback, so the tempo never depends on your frame
rate. Two formats: format 1 is four Game Boy channels on an emulated DMG APU,
held to the original driver write for write (173,000 APU writes match the
original ROM's in an emulator); format 2 goes past the Game Boy with up to 8
voices, an oscillator per instrument that a table can switch frame by frame
(SID drums), PWM, ring modulation, hard sync and a resonant filter. It ships
with nine songs, each a style and a set of chiptune techniques -- sampled and
synthesised drums, arpeggio chords, a 303 acid line, a sync lead, a
ring-modulated bell, a reese bass, tremolo by retrigger -- and a 38-effect SFX
library, all written as code you can read and change.

It needs its C half built into the game (a few lines of CMake). Without it,
`tools/chiptune.py render-all` turns the same music into ADPCM files for
Jukebox. Everything else: [chiptune/README.md](chiptune/README.md).

## tween

```lua
Tween.to(sprite, 30, { x = 200, y = 120 }, "outBack"):onComplete(done)
Tween.sequence(Tween.field(o, 20, "y", 100), Tween.delay(10), Tween.call(fn))
local spring = Tween.newSpring(0, 0.2)

function playdate.update() Tween.update() end
```

The SDK already has `playdate.easingFunctions` and `playdate.timer`. This
module exists for what they don't do: run on the host (so your animation logic
is testable), step by frame count deterministically, sequence and group, and
avoid allocating per frame — measured at 64 bytes for 20 tweens × 5000 updates,
against 390 KB for the closure-per-frame equivalent. The easings are in
normalised `f(t) -> t` form so they compose and can live in a data table.

## shake, particles, backgrounds

```lua
local sh = Shake.new("hit")
sh:add(0.6)
function playdate.update()
    sh:update()
    Shake.apply(sh); drawWorld(); Shake.pop()
end

local ps = Particles.new(200)
ps:emit(x, y, "spark", 12)
ps:update(); ps:draw()

Backgrounds.update(); Backgrounds.draw(1)
```

`Shake` is trauma-based with seeded, reproducible noise. `Particles` preallocates
its pool and drops rather than allocating on overflow (`sys.dropped` tells you
to size up). `Backgrounds` has 17 loops; each wraps its phase to an exact period
so a long session never drifts.

## Demo

The Zoo: one exhibit per module, with the chiptune songs as its soundtrack.

```bash
python tools/build_demo.py            # Lua + the chiptune extension (simulator, and device with arm-none-eabi-gcc)
python tools/build_demo.py --lua-only # no C compiler: runs without chiptune
```

Then open `demo/Juice.pdx`. The build needs the Playdate SDK, CMake and a host
C compiler for the extension; `ARM_GCC_BIN` can point at a toolchain that is
not on PATH.

## Tests

```bash
lua test/run.lua                # expect "N checks, 0 failures"
python tools/chiptune.py test   # the C port against the original ROM, the encoder, the songs
```

## License

MIT. The transition driver, the sound engine and the paw/blink effects were
extracted from [Nyandoku](https://github.com/jenissimo/nyandoku). The chiptune
driver, its format, drum recipes and wave synth come from gameboy-lab.
