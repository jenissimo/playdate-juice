# playdate-juice docs

Reference pages and recipes for each module. Every module is independent: take one, take all of them. The code and the host tests in `test/` are the source of truth.

| Module | Page | One line |
|---|---|---|
| `transitions.lua` | [transitions.md](transitions.md) | 23 scene transitions, and a plan that maps scene hops to effects |
| `jukebox.lua` | [jukebox.md](jukebox.md) | streamed music: crossfades, ducking, pause handling |
| `chiptune.lua` | [chiptune.md](chiptune.md) | Lua API for the tracker music and SFX engine |
| `tween.lua` | [tween.md](tween.md) | easings, sequences, parallel groups, springs |
| `shake.lua` | [shake.md](shake.md) | trauma-based screen shake |
| `particles.lua` | [particles.md](particles.md) | pooled 1-bit particle system |
| `backgrounds.lua` | [backgrounds.md](backgrounds.md) | 18 looping procedural backgrounds |
| `credits.lua` | [credits.md](credits.md) | end credits: rolls, held rows and cards, fitted to the music |
| `ui.lua` | [ui.md](ui.md) | menus: lists, key repeat, panels |

Other references:

- [chiptune/README.md](../chiptune/README.md): the C engine, the song file format, SFX list and how to write songs.
- [CONVENTIONS.md](../CONVENTIONS.md): the rules every module follows (host-testable, nothing touches the SDK at load time).

## Install

Copy the `.lua` files you want into your `Source/` folder, or add the repo as a submodule:

```bash
git submodule add https://github.com/jenissimo/playdate-juice Source/juice
```

```lua
import "juice/transitions"
import "juice/tween"
```

Each module defines one global (`Transitions`, `Jukebox`, `Chiptune`, `Tween`, `Shake`, `Particles`, `Backgrounds`, `Credits`) and also returns it, so `require` works under host Lua.

Notes:

- `pdc` compiles every `.lua` in your source tree, so a submodule also brings `test/` and `demo/` along as dead `.pdz` files.
- `transitions.lua` needs the `images/` folder next to it for the Paw Walk effect only.
- `chiptune.lua` needs the C extension built into the game. See [chiptune.md](chiptune.md).

## Demo

The Zoo is a demo app with one exhibit per module, and the chiptune songs as its soundtrack.

```bash
python tools/build_demo.py            # Lua + the chiptune extension
python tools/build_demo.py --lua-only # no C compiler: runs without chiptune
```

Then open `demo/Juice.pdx` in the simulator. The build needs the Playdate SDK, CMake and a host C compiler. The demo source is in `demo/`, and it is the best place to see the modules wired together.

## Tests

```bash
lua test/run.lua
python tools/chiptune.py test
```

The first runs every Lua module's host tests with no SDK. The second builds and runs the C engine tests.
