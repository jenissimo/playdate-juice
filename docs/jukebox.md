# jukebox

Streamed music on top of `playdate.sound.fileplayer`. It handles the bookkeeping that every game rewrites: not restarting a track that is already playing, not letting two crossfades race, and ducking under dialog or the system menu. Every fade uses the fileplayer's own fade argument, so it runs on the audio thread and costs nothing in `playdate.update`.

Use it for ordinary audio files. For tracker music from the chiptune engine, see [chiptune.md](chiptune.md). The two modules do not depend on each other. If a moment needs both, your scene calls both.

## Setup

```lua
import "juice/jukebox"

Jukebox.load{
    tracks  = { menu = "sound/menu", level = "sound/level" },
    volumes = { menu = 0.45, level = 0.55 },
}

function playdate.gameWillPause()  Jukebox.pause()  end
function playdate.gameWillResume() Jukebox.resume() end
```

Wire both pause hooks. Without the resume hook the music stays ducked for the rest of the session after the first time the system menu opens.

## Minimal example

```lua
Jukebox.play("menu")    -- loops; does nothing if "menu" is already playing
-- later
Jukebox.switch("menu", "level", 0.35, 0.30)   -- fade out 0.35 s, fade in 0.30 s
```

## Recipes

### Return to a menu without restarting its music

`play` is safe to call on every return, because it checks whether that track is already the current one.

```lua
function MenuScene:enter()
    Jukebox.play("menu")
end
```

### Duck under a dialog

`duck(level, seconds)` goes to an absolute volume. `restore(seconds)` goes back to the track's nominal volume.

```lua
function Dialog:open()
    Jukebox.duck(0.15, 0.2)
end

function Dialog:close()
    Jukebox.restore(0.6)
end
```

Call `duck()` with no arguments to dip to 40 percent of the nominal volume over 0.15 s.

### Rapid scene changes

Several `switch` calls in a row collapse to the last one asked for, so starting a level and backing out of it inside the fade does not leave two fades fighting.

```lua
Jukebox.switch("menu", "level")
Jukebox.switch("level", "menu")   -- ends on "menu"
```

### Per-track volume

Nominal volumes live in `Jukebox.VOL`, so the files stay at their natural level. Tracks without an entry use `Jukebox.DEFAULT_VOL` (0.5).

```lua
Jukebox.VOL.boss = 0.7
```

### Quieter pause

The pause hook ducks to `DUCK_PAUSE` times the nominal volume. Change it if the default (0.25) is too quiet or too loud.

```lua
Jukebox.DUCK_PAUSE = 0.4
```

## API reference

| Function | Description |
|---|---|
| `Jukebox.load(spec)` | Creates one fileplayer per track and returns true if all were created. `spec.tracks` is `{ name = path }`. `spec.volumes` is `{ name = 0..1 }`, merged into `Jukebox.VOL`. `spec.buffer` is the stream buffer in seconds, default `1.0` (the SDK default is 0.25). Does nothing without the SDK. A bad path is not detected here, only on `play`. |
| `Jukebox.play(name)` | Plays the track from the start, looping, at its nominal volume. Returns true on success, false for an unknown name, an unloaded jukebox or a file that could not start. If the track is already current and playing (or about to start from a switch), it does nothing and returns true. |
| `Jukebox.switch(from, to, out_s, in_s)` | Crossfades. Fades `from` out over `out_s` seconds (default 0.5), stops it, then starts `to` and fades it in over `in_s` seconds (default 0.5). If `from` is not the current track, it plays `to` directly. |
| `Jukebox.stop()` | Stops the current track. |
| `Jukebox.duck(level, seconds)` | Fades the current track to `level` over `seconds`. Defaults: `0.4` times the nominal volume, and `0.15` s. |
| `Jukebox.restore(seconds)` | Fades the current track back to its nominal volume. Default `1.20` s. |
| `Jukebox.pause()` | For `playdate.gameWillPause`. Ducks to `nominal * DUCK_PAUSE` over 0.12 s. |
| `Jukebox.resume()` | For `playdate.gameWillResume`. Restores over 0.25 s. |
| `Jukebox.current()` | Name of the current track, or nil. |
| `Jukebox.nominal(name)` | Nominal volume of `name`, default the current track. Falls back to `DEFAULT_VOL`. |

| Field | Description |
|---|---|
| `Jukebox.VOL` | Table of nominal volumes by track name. |
| `Jukebox.DEFAULT_VOL` | Volume for tracks not in `VOL`. Default `0.5`. |
| `Jukebox.DUCK_PAUSE` | Multiplier used by `pause`. Default `0.25`. |
| `Jukebox.players` | The fileplayers by track name, set by `load`. |

## Gotchas

- `play` does not stop other tracks. To change music, use `switch` or call `stop` first.
- `duck` and `restore` act on the current track only.
- If a track is not in `volumes`, its volume is `DEFAULT_VOL`, not 1.0.
- `Jukebox.load` returns false if a fileplayer could not be created, and also if no tracks were given. All other functions then do nothing.
- The default 1 second buffer is deliberate: a heavy frame can starve a 0.25 s buffer and the track restarts from the top.
- After `stop`, there is no current track, so `duck` and `restore` do nothing until the next `play`.
