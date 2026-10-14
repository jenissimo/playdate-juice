---
name: comics
description: Make interactive comics, story intros and cutscenes for Playdate with Panels (cadin/panels) and playdate-juice. Plans pages with Scott McCloud's principles (closure, the six panel transitions, time as space, words vs pictures), writes the comicData table (sequences, panels, layers, parallax, animations, effects, text, branching), specs the 1-bit layered art, wires in juice - Transitions in, between and out of cutscenes, Chiptune music and SFX on scroll cues, Shake, Particles, Backgrounds inside panels, a Credits roll - then lints the data and checks real frames in the simulator. Use when the user wants a comic, a cutscene, an intro or ending story, a storyboard or a motion comic on Playdate, or asks about Panels, comicData, layers, scrollTrigger, TYPE_ON, choice lists or branching. Ключевые слова - комикс, катсцена, интро, концовка, сюжетная вставка, раскадровка, панели, Panels, comicData, параллакс, Маклауд.
---

# Comics for Playdate: Panels + McCloud + playdate-juice

You turn a story into a Panels comic that feels made for a crank: planned
with McCloud's craft, written as comicData, dressed with playdate-juice, and
checked on real frames before anyone sees it.

Read as you go — not all up front:
- `references/mccloud.md` — the craft, mapped to Panels and juice. Read before planning.
- `references/panels.md` — every Panels 2.2 property, settings, cutscene API, and
  what only the source tells you. Read before writing comicData.
- `references/juice.md` — simulator-verified recipes: the cutscene host loop,
  cues, wipes, music, backgrounds, credits, integration gotchas. Read before wiring.
- `scripts/lint_comic.lua` — checks a comicData file (typos, wrong-level keys,
  missing files, crashes waiting to happen). Run it on every change.

Paths: this skill ships inside playdate-juice (`.claude/skills/comics/`); in a
game that submodules the repo it is `Source/juice/.claude/skills/comics/`, and the juice
modules import as `import "juice/transitions"` etc.

## Workflow

### 1. Pick the shape

| The user wants | Shape | Entry point |
|---|---|---|
| a comic as the product (chapters, continue, menu) | standalone | `Panels.start(comicData)` — Panels owns the loop |
| an intro, an ending, a story beat inside a game | cutscene | `Panels.startCutscene(data, done)` + your loop |
| a comic that should also have juice wipes, whole-screen shake, music changes | cutscene, even as the whole game | juice.md §1 |

If the request does not say, a story inside a game is a cutscene. Ask only
if a standalone comic's menus/chapters matter and nothing tells you.

### 2. Plan the beats (McCloud) before any Lua

Fill the worksheet in `references/mccloud.md` §10, one row per panel: the
beat, the transition from the previous panel (moment / action / subject /
scene / aspect / non-sequitur), its time (panel length, gap, autoAdvance),
the frame (distance), who carries the meaning (words or picture), and the
juice (wipe, SFX, shake, music). Then check it:

- Is one transition type doing all the work? Mix them.
- Is there a silent panel? Is every wipe a scene or mood change (wipes on
  every panel read as lag)?
- Does every big image have a sound and every sound an image?
- Is any must-see beat skippable by cranking fast? Make it AUTO or scroll-driven.

For more than a handful of panels, show the user this table first — it is
the storyboard, and it is far cheaper to change than art or data.

### 3. Write comicData

Translate row by row (details: `references/panels.md`):

- scene → sequence; `title` only on sequences that are chapters
- tempo → `scrollType`: MANUAL for reading and wandering (the crank is the
  reader's hand), AUTO for beats, dialogue and cutscenes; `direction = NONE`
  for slideshow cuts
- time → `frame.width` beyond 400 (horizontal) for long moments, `frame.gap`
  for elapsed time, `autoAdvance` (ms) for set tempo
- depth → layers with `parallax`: foreground 0, middle 0.2–0.4, sky 0.6–1
- motion → `animate` without triggers (scroll-driven, scrubbable) or with
  `trigger`/`scrollTrigger`/`autoStart`; `exit` for AUTO panels (+ `advanceDelay`)
- words → text layers (captions: `background` + `border` + `margin`), or
  lettering baked into the art; `TYPE_ON` where words should arrive in time
- choices → `choiceList` or `advanceControls` + sequence `id`s

One sequence per file once a comic grows (`comicData/s01.lua`…), assembled in
one list. Constants are `Panels.*` values, times are milliseconds.

### 4. Spec the art (one bit, 400×240)

- Every layer that moves, animates or has its own parallax is its own PNG.
  Save layers full-frame with transparency so `x`/`y` stay at the default (a
  400×240 layer lines up with the screen).
- `images/sNN/<panel>-<name>.png`, one folder per sequence.
- Characters iconic and clean (the masking effect); texture and dither in
  backgrounds; `pixelLock = 2` on dithered layers that scroll.
- Blink and fast imageTables get `reduceFlashingDurations` / `reduceFlashingDelay`.
- No art yet? Draft with text layers and `renderFunction` sketches, and hand
  over an asset list: file, size, layer role, parallax, notes. The system font
  has no Cyrillic: Russian text needs a font that has it (`fonts`, `fontFamily`).

### 5. Wire the juice (`references/juice.md`)

- Cutscene loop: `Transitions.start` before `Panels.startCutscene`, again in
  its callback; `Transitions.draw(Panels.update)`; particles after it; shake
  around it.
- Beats on scroll: `updateFunction = cues({ { 0.5, fn } })` → `Chiptune.sfx`,
  `jolt:add`, `sparks:emit`.
- Panel wipes in `NONE` slideshows via `setupFunction = wipe("Dissolve")`.
- Scene changes: chain cutscenes; change the song with `Chiptune.play`.
- Moods: a `Backgrounds` loop in a `renderFunction`.
- The end: a `Credits` roll after the comic or as its last panel — with the
  Panels attribution (CC BY 4.0).

### 6. Validate

1. `lua scripts/lint_comic.lua Source/comicData.lua --source Source [--cutscene]`
   — fix every error, read every warning; hints are craft notes.
2. Build with `pdc` and run in the simulator; read the console (Panels
   prints load errors there and keeps going).
3. Look at the beats, not just "it runs": in a debug build dump frames and
   view them —
   ```lua
   if tick % 5 == 0 then
       playdate.simulator.writeToFile(playdate.graphics.getWorkingImage(), "C:/tmp/f" .. tick .. ".png")
   end
   ```
   Check: does each wipe start from the old panel; does each cue land when
   its panel is visible; is text readable over the art; does anything shimmer.
4. On device if you can: dithers and fades look different on the real panel.

## Rules that bite (all observed in the simulator or the Panels source)

- Import Panels BEFORE defining `playdate.gameWillTerminate` /
  `deviceWillSleep` / `deviceWillLock` / `keyPressed` — it overwrites them —
  and save the game under its own datastore name; Panels writes the default one.
- `Panels.update()` runs `playdate.timer.updateTimers()`; never call both in a frame.
- One `backgroundColor` per cutscene: a change between sequences crashes
  `startCutscene` (`Panels.lua:971`, `transitionFader`). Chain cutscenes instead.
- `direction = NONE` needs an explicit `advanceControl`.
- A layer is exactly one of `image`, `images`, `imageTable`, `text` (or `img`).
- AUTO-only keys (`autoAdvance`, `advanceControl` on panels, `exit`, …) do
  nothing in MANUAL sequences; misspelt keys do nothing anywhere. Lint.
- Times are milliseconds; scroll points are 0..1 (0 entering, 0.5 centred, 1 gone).
- Don't name globals `round`, `printError`, `panelNum`… — Panels leaks them
  (full list in panels.md §13).
- Keep the Panels credit: "Built with Panels — cadin.github.io/panels" (or
  "Cutscenes built with Panels") with its QR code.

## What to hand back

- The plan table (step 2) when it was non-trivial.
- comicData file(s), and the main.lua wiring if it is a cutscene.
- The asset list for anything not drawn yet.
- Lint output (clean or explained) and what you checked in the simulator.
