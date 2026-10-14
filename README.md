# playdate-juice

Drop-in game-feel modules for [Playdate](https://play.date/): scene
transitions, chiptune music and sound effects, streamed music, tweens, screen
shake, particles, animated backgrounds and end credits.

Eight independent modules. Take one, take all of them — nothing here imports
anything else in the repo. Seven are single Lua files; chiptune is a Lua file
plus a C extension (`chiptune/`).

| Module | Global | What it is |
|---|---|---|
| `transitions.lua` | `Transitions` | 23 direction-aware scene transitions + a scene-hop plan |
| `jukebox.lua` | `Jukebox` | streamed music: crossfades, ducking, pause handling |
| `chiptune.lua` + `chiptune/` | `Chiptune` | Game Boy, 8-voice SID-style and studio PCM tracker music; 18 songs, 84 effects |
| `tween.lua` | `Tween` | 31 easings, sequences, parallel groups, springs — zero per-frame allocation |
| `shake.lua` | `Shake` | trauma-based screen shake with deterministic noise |
| `particles.lua` | `Particles` | pooled 1-bit particle system |
| `backgrounds.lua` | `Backgrounds` | 17 looping procedural backgrounds |
| `credits.lua` | `Credits` | end credits: rolls, held rows and cards that dissolve, fitted to the music |

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
import "juice/chiptune"
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
rate. Three sound families: format 1 is four Game Boy channels on an emulated DMG APU,
held to the original driver write for write (173,000 APU writes match the
original ROM's in an emulator); format 2 goes past the Game Boy with up to 8
voices, an oscillator per instrument that a table can switch frame by frame
(SID drums), PWM, ring modulation, hard sync and a resonant filter. It ships
with eighteen songs, each a style and a set of chiptune techniques -- sampled and
synthesised drums, arpeggio chords, a 303 acid line, a sync lead, a
ring-modulated bell, a reese bass, tremolo by retrigger -- and an 84-effect SFX
library (a set of game sounds, and a whoosh each way for every transition), all written as code you can read and change.

Format 3 preserves FastTracker 2's embedded sampler: sample offsets,
backwards play, volume/slide, pan and BPM, including three jungle tracks.
Format 4 adds studio instruments: guitars through an amp, drums, supersaws
and pads as interpolated PCM8 with sustain loops, played live by the same
driver. Three new themes -- rock, jungle and trance -- share a 203 KiB bank.
`python tools/chiptune.py studio` rebuilds them;
`python tools/build_demo.py --jukebox` builds a demo starting in the player,
with live/ADPCM switching.
The original studio menu/play/multi arrangements are also ported, with exact
musical clocks, release overlaps and mastering. Their shared bank is 401 KiB
on disk (703 KiB decoded); the demo offers A/B with the original studio mix.

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

## credits

```lua
local roll = Credits.new({
    { title = "NYANDOKU", sub = "a cat puzzle" },
    { heading = "Code" },
    { role = "Programming", name = "Zhenya" },
    { role = "Music", names = { "gameboy-lab", "Zhenya" } },
    { heading = "Backers" },
    { names = { "Ann", "Bob", "Cyd", "Dee", "Eve" } },
    { image = "images/logo", ink = true, hold = 45, on = function() Chiptune.sfx("magic") end },
    { card = "THE END", hold = 60 },
    { card = { { heading = "Thanks for playing" } } },
}, { fit = 30 * 95, invert = true, background = function() Backgrounds.draw(5) end })

function playdate.update()
    roll:update()   -- the crank scrubs, A fast-forwards, B skips to the last card
    roll:draw()
end
```

A script of titles, headings, role/name pairs (film-style split, dotted
leaders or stacked), name grids, paragraphs, logos and dividers becomes a roll
that stops on the rows you `hold`, handing over to centred cards that dissolve
in and out. Headings type themselves in, names slide in, and every row dithers
out at the screen edges with `drawFaded` — over any backdrop, not just a flat
paper colour. `fit` solves the scroll speed so the last card lands on the
song's last bar, and an entry's `on` cue fires as it reaches the centre: a
jingle, a shake, a burst of particles.

What is on screen is a pure function of one frame clock, which is why the crank
can scrub backwards (a heading un-types itself) and why the timeline is pinned
by host tests. Text goes through `font:drawText`, so a handle like `pixel_witch`
keeps its underscore instead of turning italic. The system font has no
Cyrillic; pass `fonts` that do.

## Demo

The Zoo: one exhibit per module, with the chiptune songs as its soundtrack.

```bash
python tools/build_demo.py            # Lua + the chiptune extension (simulator, and device with arm-none-eabi-gcc)
python tools/build_demo.py --lua-only # no C compiler: runs without chiptune
```

Then open `demo/Juice.pdx`. The build needs the Playdate SDK, CMake and a host
C compiler for the extension; `ARM_GCC_BIN` can point at a toolchain that is
not on PATH.

## Comics skill

`.claude/skills/comics/` is a [Claude Code](https://claude.com/claude-code) skill for
making comics and cutscenes with [Panels](https://github.com/cadin/panels) and
these modules: planning with Scott McCloud's principles, a complete Panels 2.2
reference (including what only its source tells you), recipes for wiring
transitions, chiptune cues, shake, particles, backgrounds and credits into a
cutscene — each one run in the simulator — and `lint_comic.lua`, which catches
the misspelt keys and wrong-level properties Panels ignores silently. It lives
where Claude Code looks for project skills, so opening the repo is enough; in a
game that submodules the repo it sits in the nested `juice/.claude/skills/`.
The linter also runs alone:

```bash
lua .claude/skills/comics/scripts/lint_comic.lua Source/comicData.lua --source Source
```

## Tests

```bash
lua test/run.lua                # expect "N checks, 0 failures" (modules + the comics linter)
python tools/chiptune.py test   # ROM traces, formats 2/3/4, banks, encoder and shipped songs
```

## License

MIT. The transition driver, the sound engine and the paw/blink effects were
extracted from [Nyandoku](https://github.com/jenissimo/nyandoku). The chiptune
driver, its format, drum recipes and wave synth come from gameboy-lab.
