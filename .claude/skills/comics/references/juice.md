# Wiring a Panels comic to playdate-juice

Every snippet here ran in the Playdate Simulator (SDK 3.1) against Panels 2.2
with the juice modules, frame-dumped and looked at: a game scene → Blink into
a cutscene → Dissolve and Wave Wipe between slideshow panels → an impact cue
(SFX + trauma shake + particle burst) → a Starfield panel → a scrolling strip
with a Plasma panel → a Credits roll inside the last panel → Circle back into
the game → the game's own end credits. Keep the code close to this; the
comments say which line exists because something broke without it.

## Contents
1. Two shapes, and what juice can reach in each
2. The host loop for a cutscene
3. Helpers: scroll progress, cues, screen coordinates, wipes
4. Impact beats: SFX + shake + particles on a cue
5. Wipes between panels and between scenes
6. Music
7. Animated backgrounds inside a panel
8. Tween in custom panels
9. Credits: after the comic, or as its last panel
10. Integration gotchas (all observed)

---

## 1. Two shapes

| | Standalone comic (`Panels.start`) | Cutscene in a game (`Panels.startCutscene`) |
|---|---|---|
| Who owns `playdate.update` | Panels | you |
| Juice transitions into/out of the comic | no | yes (§2) |
| Wipes between panels/scenes | via `setupFunction`, but nothing composites them — no | yes (§5) |
| Shake of the whole comic, screen-space particles | no | yes (§4) |
| Juice inside panels (Backgrounds, Credits, Tween, Chiptune calls) | yes — custom functions | yes |
| Chapters menu, save/continue, main menu | yes | no |

A standalone comic that wants transitions is still easiest as a "game" whose
only scene is a cutscene: you get the loop, and keep `Panels.vars`.

## 2. The host loop for a cutscene

```lua
import "libraries/panels/Panels"   -- FIRST: it defines playdate.gameWillTerminate & co.,
                                   -- so YOUR definitions below must come after it
import "juice/transitions"
import "juice/shake"
import "juice/particles"
import "juice/chiptune"

local gfx <const> = playdate.graphics
Shake.load(); Particles.load()
local jolt   = Shake.new("hit")
local sparks = Particles.new(200, { color = "white" })   -- match the comic's paper
local mode   = "game"

local function playComic(data, after)
    Transitions.start("Blink", "fwd", 20)          -- snapshot: the game as it is now
    mode = "comic"
    Panels.startCutscene(data, function(target)
        Transitions.start("Circle", "back", 24)    -- snapshot: the comic's last frame
        mode = "game"
        if after then after(target) end
    end)
end

function playdate.update()
    if mode == "comic" then
        jolt:update(); sparks:update()
        gfx.clear(gfx.kColorBlack)                 -- the strip a shake uncovers
        Shake.apply(jolt)
        local was = Transitions.active
        Transitions.draw(Panels.update)            -- frozen during a wipe; Panels pauses with it
        if Transitions.active and not was then
            -- a panel's setupFunction started a wipe mid-frame (§5): this frame
            -- already shows the new panel; cover it with the old one
            gfx.getDisplayImage():draw(0, 0)
        end
        sparks:draw()                              -- outside the frozen capture: keeps moving
        Shake.pop()
    else
        playdate.timer.updateTimers()              -- ONLY here: Panels.update runs them itself
        Transitions.draw(updateGame, drawGame)
    end
end
```

Why each line:
- Shaking works because Panels renders into its own canvas and blits it to
  the screen at (0, 0) — under your draw offset.
- `Transitions.draw(Panels.update)` uses the one-function form: Panels mixes
  update and draw, so during a wipe it simply does not run. Its timers and
  `autoAdvance` pause with it; the sequence slide-in (a wall-clock animator)
  does not.
- The exit wipe snapshots `getDisplayImage()` — the last COMPLETED frame. The
  callback fires inside `Panels.update` after the comic's final frame was
  drawn, so the snapshot is the comic, not a blank.
- The entry wipe captures the comic's FIRST frame. A sequence normally slides
  in from off-screen, so that frame is empty paper (the wipe reveals paper,
  then the panel slides in — acceptable). With `direction = NONE` on the first
  sequence the wipe reveals panel 1 itself.

## 3. Helpers

```lua
-- Reading-order scroll progress of a panel: 0 entering, 0.5 centred, 1 gone.
-- The same number Panels' own scrollTrigger uses.
local function scrollPct(panel, offset)
    local f = panel.frame
    local p
    if panel.axis == Panels.ScrollAxis.VERTICAL then
        p = 1 - (f.y - f.margin + f.height + offset.y) / (240 + f.height)
    else
        p = 1 - (f.x - f.margin + f.width + offset.x) / (400 + f.width)
    end
    if panel.scrollingIsReversed then p = 1 - p end
    return p
end

-- An updateFunction that fires each { at, fn } once as the scroll passes `at`
-- going forward (crank back past it and forward again: it fires again).
-- One cues() per panel -- the closure holds that panel's position.
local function cues(list)
    local prev = -1
    return function(panel, offset)
        local T = rawget(_G, "Transitions")
        if T and T.active then return end      -- land the beat once the panel is really on screen
        local p = scrollPct(panel, offset)
        for i = 1, #list do
            local c = list[i]
            if prev < c[1] and c[1] <= p then c[2](panel, offset) end
        end
        prev = p
    end
end

-- Panel-local point -> screen point (for particles, which you draw in screen space).
local function toScreen(panel, offset, x, y)
    return offset.x + panel.frame.x + x, offset.y + panel.frame.y + y
end

-- A setupFunction that starts a juice wipe as the panel arrives.
local function wipe(effect, dir, frames)
    return function() Transitions.start(effect, dir or "fwd", frames or 18) end
end
```

In a `direction = NONE` slideshow every panel sits at 0.5 the moment it
appears, so `{ 0.5, fn }` means "when this panel is shown".

## 4. Impact beats

```lua
{   -- the BOOM panel
    updateFunction = cues({ { 0.5, function(panel, offset)
        local x, y = toScreen(panel, offset, 200, 120)
        Chiptune.sfx("explosion")      -- or any of the 84 effects
        jolt:add(0.8)                  -- trauma: blooms, then decays
        sparks:emit(x, y, "burst", 24)
    end } }),
    layers = { { image = "s2/boom" } },   -- draw the BOOM; play it on the same beat
}
```

Panels' own `SHAKE_UNISON` / layer `SHAKE` is constant jitter (an engine, a
cold hand). Juice `Shake` is one hit that fades. Do not stack both on one beat.
An impact belongs on a CUT (`NONE` or AUTO), not under a wipe: closure in the
gutter plus the sound on the cut is what sells it.

## 5. Wipes between panels and between scenes

Between panels — a slideshow sequence whose panels start wipes as they arrive:

```lua
{
    direction = Panels.ScrollDirection.NONE, scrollType = Panels.ScrollType.AUTO,
    advanceControl = Panels.Input.A,     -- NONE has no default advance button
    showAdvanceControl = false,          -- (it would draw a meaningless arrow)
    backgroundColor = Panels.Color.BLACK,
    panels = {
        { frame = { margin = 0 }, borderless = true, layers = { ... } },   -- no wipe on panel 1
        { frame = { margin = 0 }, borderless = true, setupFunction = wipe("Dissolve"), layers = { ... } },
        { frame = { margin = 0 }, borderless = true, setupFunction = wipe("Wave Wipe"), layers = { ... } },
    },
}
```

Needs the `was`/`getDisplayImage` lines of the host loop. Going back to a
panel replays its wipe. Pick wipes by meaning (mccloud.md §2): Dissolve =
time passes, Fade/Circle/Blink = scene change, glitches = non-sequitur.

Between scenes — prefer one cutscene per scene and chain them; the wipe, the
music change and the new `backgroundColor` all happen in your code:

```lua
playComic(scene1, function() playComic(scene2, function() playComic(scene3) end) end)
```

This is also the fix for the cutscene background crash (§10).

`TransitionSounds` (a global with `play(name, dir)`) gives every juice wipe a
whoosh from the chiptune bank: `Chiptune.sfx("tr_" .. name:lower():gsub(" ", "_") .. "_" .. dir)`.

## 6. Music

- Per scene: `Chiptune.play("hollow_deep")` in `playComic` (or in the first
  panel's `setupFunction`), the game's song again in the callback.
  `Chiptune.play` does not restart a song that is already playing.
- Do not run Panels' sequence `audio` and Chiptune music at once. Without the
  C extension, render the songs to ADPCM (`python tools/chiptune.py render-all`)
  and use them as Panels `audio.file` or through `Jukebox`.
- Drop-outs keep time: `Chiptune.mute({ "pu1", "pu2" })` on a tense panel,
  `Chiptune.mute({})` to bring the band back on the beat.
- Silence before a shock: `cues({ { 0.9, function() Chiptune.stop() end } })`
  on the panel before; the SFX on the shock panel lands in silence.
- Advance on the music (needs the C extension and `Chiptune.update()` every
  frame in the host loop):

  ```lua
  local beat = false
  Chiptune.onSync(function(v) beat = true end)      -- an Exx marker in the song
  { advanceFunction = function() if beat then beat = false; return true end end, ... }
  ```
- Pause: wire `playdate.gameWillPause`/`gameWillResume` to
  `Chiptune.pause()`/`resume()` (after importing Panels). Panels only pauses its
  own fileplayer, and only for its own menus.
- `TYPE_ON` beeps with Panels' sampleplayer; `Panels.Settings.typingSound =
  Panels.Audio.TypingSound.NONE` turns it off. It cannot call Chiptune per letter.

## 7. Animated backgrounds inside a panel

```lua
{
    updateFunction = function() Backgrounds.update(rain) end,
    renderFunction = function(panel, offset)
        Backgrounds.draw(rain)                 -- origin = panel corner, clipped to the frame
        for _, layer in ipairs(panel.layers) do
            Panels.renderLayerInPanel(layer, panel, offset)
        end
    end,
    layers = { { image = "s3/window" } },      -- art on top of the loop
}
```

Checked: the Backgrounds renderers `gfx.clear`, and `gfx.clear` honours the
clip rect Panels sets to the frame, so a loop never paints over neighbouring
panels while a strip scrolls. Look up indices once:
`local rain = Backgrounds.indexOf("Matrix Rain")`.

## 8. Tween in custom panels

`Tween.update()` once a frame in the host loop (comic mode too). Frame-counted,
so it pauses with the comic during wipes only if you put it inside the frozen
function. A spring for a character that follows the scroll:

```lua
local x = Tween.newSpring(0, 6)
renderFunction = function(panel, offset)
    local target = 300 * scrollPct(panel, offset)
    hero:draw(math.floor(x:update(target)), 120)
end
```

## 9. Credits

After the comic, in the game — the usual place:

```lua
local roll = Credits.new({
    { title = "THE LIGHTHOUSE" },
    { heading = "Story" }, { role = "Words", name = "Someone" },
    { space = 16 },
    { text = "Cutscenes built with Panels" },                         -- CC BY 4.0 attribution
    { image = "libraries/panels/assets/images/panelsPagesQR", hold = 30 },
    { text = "cadin.github.io/panels", hold = true },
}, { fit = 30 * 45 })
-- each frame: roll:update(); roll:draw()
```

As the last panel of a comic — works in standalone `Panels.start` comics too:

```lua
{   -- a sequence of its own, same backgroundColor as the rest
    direction = Panels.ScrollDirection.NONE, scrollType = Panels.ScrollType.AUTO,
    advanceControl = Panels.Input.A, showAdvanceControl = false,
    panels = { {
        frame = { margin = 0 }, borderless = true, layers = {},
        setupFunction   = function() endRoll:restart() end,
        updateFunction  = function() endRoll:update() end,
        renderFunction  = function() endRoll:draw() end,
        advanceFunction = function() return endRoll.done end,   -- ends the comic when the roll does
    } },
}
```

Build `endRoll` with `Credits.new` at load, not inside the panel.

## 10. Integration gotchas (all observed)

- **Different `backgroundColor`s in one cutscene crash.** Moving between two
  sequences with different background colours runs Panels' background
  cross-fade, whose buffer only `Panels.start` creates:
  `Panels.lua:971: attempt to index a nil value (upvalue 'transitionFader')`.
  Keep one colour per cutscene; change colour by chaining cutscenes (§5).
- **Double timers.** `Panels.update` calls `playdate.timer.updateTimers()`.
  Call it yourself only when the comic is not running.
- **Your lifecycle callbacks.** Importing Panels redefines
  `gameWillTerminate`/`deviceWillSleep`/`deviceWillLock`/`keyPressed`, and its
  save writes the DEFAULT datastore file. Import Panels first, define yours
  after, save under your own name (`playdate.datastore.write(t, "game")`).
- **Early cues.** A cue on a panel that enters under a wipe would fire on the
  capture frame, before the panel is visible — hence the `Transitions.active`
  guard in `cues`.
- **Frozen effects.** Anything drawn inside `Transitions.draw(fn)` freezes for
  the wipe. Draw particles (and anything else that must keep moving) after it.
- **Shake smear.** Clear the screen before `Shake.apply`, or the strip the
  offset uncovers keeps last frame's pixels.
- **NONE has no advance button.** Set `advanceControl` (and usually
  `showAdvanceControl = false` with `autoAdvance` or an `advanceFunction`).
- **Menu noise.** In cutscene mode every sequence change rebuilds Panels' main
  menu and prints `Error loading main menu image` unless
  `images/menuImage.png` exists. Harmless; add a 400×240 image to silence it.
- **Input leaks.** Your `playdate.cranked` and button callbacks still fire
  during a cutscene: gate them on `mode`.
