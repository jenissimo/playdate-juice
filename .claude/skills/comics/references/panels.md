# Panels 2.2 — complete reference

Condensed from the official docs (cadin.github.io/panels) and checked line by
line against the `main` branch source (`Panels.lua`, `modules/*.lua`). Things
the docs do not mention but the source does are marked **(source)**. Panels
silently ignores keys it does not know, so a typo is a feature that quietly
never happens — run `scripts/lint_comic.lua` instead of trusting your eyes.

## Contents
1. Install and start
2. comicData shape and constants
3. Sequence properties
4. Panel properties
5. Layer properties (image / images / imageTable / text)
6. Layer animations (`animate`, `exit`)
7. Layer effects
8. Custom functions
9. Variables, choice lists, branching
10. Settings
11. Menus and credits
12. Cutscene mode
13. Behaviour you only learn from the source

---

## 1. Install and start

```
Source/
  main.lua
  images/          Panels.Settings.imageFolder ("images/")
  audio/           Panels.Settings.audioFolder ("audio/")
  libraries/panels Panels.Settings.path ("libraries/panels/")
```

```bash
git submodule add https://github.com/cadin/panels Source/libraries/panels
```

```lua
import "libraries/panels/Panels"     -- pulls in CoreLibs object/graphics/sprites/timer/animation/crank
import "comicData"                   -- defines comicData (or `local comicData = import ...` is NOT a thing: import returns nothing)
Panels.Settings.snapToPanels = true  -- every setting BEFORE start
Panels.start(comicData)              -- standalone: Panels owns playdate.update and playdate.cranked from here
```

Panels elsewhere in the tree → `Panels.Settings.path = "juice/libs/panels/"` (its
button images, typing beep and QR code load from there).

Paths in comic data: images relative to `imageFolder` (with or without
`.png` — the SDK finds both, checked in the 3.1 simulator; image tables by
base name: `walk` for `walk-table-64-64.png` or `walk-1.png, walk-2.png…`).
Audio relative to `audioFolder` (Panels strips a `.wav`). Fonts relative to
the Source root, without `.fnt` (Panels strips it but prints a warning).

## 2. comicData shape and constants

`comicData` is a plain list of sequences. Nothing else may sit at its top level.
Split long comics one sequence per file and assemble the list in one place.

```lua
comicData = { seq1, seq2, seq3 }
-- seq  = { panels = { panel, panel, ... }, ...sequence props }
-- panel = { layers = { layer, layer, ... }, ...panel props }
```

| Constant table | Values |
|---|---|
| `Panels.ScrollAxis` | `HORIZONTAL` (default), `VERTICAL` |
| `Panels.ScrollDirection` | `LEFT_TO_RIGHT`, `RIGHT_TO_LEFT`, `TOP_DOWN`, `BOTTOM_UP`, `NONE` (aliases **(source)**: `L_TO_R`, `R_TO_L`, `TOP_TO_BOTTOM`, `BOTTOM_TO_TOP`) |
| `Panels.ScrollType` | `MANUAL` (crank/d-pad, default), `AUTO` (button, panel by panel) |
| `Panels.Input` | `A`, `B`, `UP`, `DOWN`, `LEFT`, `RIGHT` (the `playdate.kButton*` values) |
| `Panels.Color` | `WHITE`, `BLACK`, `CLEAR` |
| `Panels.Effect` | panel: `SHAKE_UNISON`, `SHAKE_INDIVIDUAL`; layer: `SHAKE`, `BLINK`, `TYPE_ON` |
| `Panels.Font` | `NORMAL`, `BOLD`, `ITALIC` (font-family keys) |
| `Panels.TextAlignment` | `LEFT`, `CENTER`, `RIGHT` |
| `Panels.ControlSize` | `LARGE` (40), `MEDIUM` (30), `SMALL` (20) |
| `Panels.Audio.TypingSound` | `DEFAULT`, `NONE` |

**Scroll value** (every `scrollTrigger`): `0` just before the panel enters the
screen, `1` just after it leaves, `0.5` when a full-screen panel is centred.
For reversed directions it is flipped so it still runs 0 → 1 in reading order.

## 3. Sequence properties

| Key | Default | Notes |
|---|---|---|
| `panels` | required | list of panels |
| `title` | nil | shown in the Chapters menu; untitled sequences are not listed (so several sequences can read as one chapter) |
| `axis` | HORIZONTAL | derived from `direction` if only that is set |
| `direction` | L→R or top-down | `NONE` = panels replace each other with no motion (slideshow); forces the horizontal axis |
| `scrollType` | MANUAL | `AUTO` = one panel per press |
| `autoAdvanceWithCrank` | false | AUTO only: crank detents advance too |
| `autoAdvanceTicks` | 6 | detents per revolution for the above |
| `audio` | nil | `{ file, loop, volume, continuePrevious }` background track for the whole sequence (fileplayer). With `continuePrevious`, still name `file` for chapter-menu jumps. No `audio` at all → the previous track fades out |
| `advanceControl` | arrow in scroll direction | button that leaves the LAST panel |
| `advanceControlSize` | LARGE | indicator size |
| `showAdvanceControl` | true | indicator on the last panel |
| `advanceControlPosition` | per direction | **(source)** `{ x, y }` for that indicator |
| `advanceControls` | nil | nonlinear: `{ { input, target, x, y, anchor } }` — `target` = sequence index or `id`; `anchor = true` **(source)** pins the button to the last panel instead of the screen |
| `showAdvanceControls` | true | nonlinear: hide built-in buttons |
| `backgroundColor` | WHITE | outside the panels; also flips the border colour |
| `foregroundColor` | inverse of bg | **(source)** border colour |
| `endSequence` | false | nonlinear dead end → back to the main menu |
| `rapidAdvance` | false | AUTO: allow presses while a panel is still moving (manuals, credits) |
| `transitionDuration` | 500 (panels) / 750 (sequence in/out) | ms. ONE key drives both the AUTO panel-to-panel move and the sequence slide-in/out |
| `transitionEase` | inOutQuad (panels) / inOutQuart (in/out) | any `playdate.easingFunctions.*` |
| `delay` | 0 | **(source)** ms before the sequence slides in |
| `defaultFrame` | `Settings.defaultFrame` | **(source)** frame for panels that set none |
| `font`, `fontFamily` | — | **(source)** inherited by every panel without its own |
| `backControl` | arrow against scroll | **(source)** AUTO: button for the previous panel |
| `preventBacktracking` | false | **(source)** default for every panel |
| `id` | nil | nonlinear: string id for targets |
| `nextSequence` | nil | nonlinear: id that follows this one |

## 4. Panel properties

| Key | Default | Notes |
|---|---|---|
| `layers` | required | omit only with a `renderFunction` |
| `frame` | `Settings.defaultFrame` = `{ gap = 50, margin = 8 }` | `{ width, height, x, y, margin, gap }`. Missing width/height = screen minus 2×margin. On the scroll axis Panels computes the position itself (x for horizontal, y for vertical) — set the OTHER coordinate for offset layouts. `gap` = space before this panel |
| `borderless` | false | |
| `backgroundColor` | none (sequence bg shows) | fill inside the frame |
| `parallaxDistance` | 1.2 × panel size on the axis | distance a `parallax = 1` layer travels across the whole scroll |
| `effect` | nil | `{ type = Panels.Effect.SHAKE_UNISON or SHAKE_INDIVIDUAL, strength }` — constant random jitter while on screen, scaled by each layer's parallax |
| `audio` | nil | `{ file, loop, scrollTrigger, pan, volume, triggerSequence, repeats }` sampleplayer; loops fade with scroll position |
| `font`, `fontFamily`, `lineHeightAdjustment`, `color`, `invertTextColor` | — | defaults for the panel's text layers |
| `transitionOffset` | 0 | shifts the image-swap points of `images` layers (−0.1 kills flicker at 0.5 with snapToPanels) |
| `choiceList` | nil | see §9 |
| `panels` | nil | **(source)** nested sub-panels drawn inside this one, each a full panel table |
| AUTO only: `advanceControl` | sequence's | button to the next panel |
| AUTO only: `showAdvanceControl`, `advanceControlSize`, `advanceControlPosition` `{x,y,delay}`, `advanceControlPositions` | false… | in-panel indicator(s) |
| AUTO only: `advanceControlSequence` | nil | presses required in order (`{A, A}`); each press can trigger layer animations |
| AUTO only: `advanceDelay` | 0 | ms after the last press before moving on (let `exit` animations finish) |
| AUTO only: `preventBacktracking` | false | |
| AUTO only: `autoAdvance` | nil | ms, then advance by itself — the tool for timed beats |
| `renderFunction(panel, offset)` | nil | takes over all drawing (draw offset = panel origin, clip = frame) |
| `updateFunction(panel, offset)` | nil | every frame on screen, before drawing; Panels still renders |
| `setupFunction(panel)` | nil | once as the panel first comes on screen (again after it left and returns) |
| `resetFunction(panel)` | nil | as it leaves the screen |
| `advanceFunction(panel)` | nil | AUTO: return true to advance (replaces button checks) |
| `targetSequenceFunction()` | nil | nonlinear: return the next sequence id. Called with NO arguments |

## 5. Layer properties

A layer is exactly one of: `image`, `images`, `imageTable`, `text` — or
**(source)** `img`, a ready `playdate.graphics.image` (handy for art you render
in code). Never two of them.

Common keys:

| Key | Default | Notes |
|---|---|---|
| `x`, `y` | **−frame.margin** (source) | relative to the panel's top-left; the default makes a 400×240 full-frame PNG line up with the SCREEN. Save layers full-frame with transparency and you never set x/y |
| `parallax` | 0 | 0..1; far things move more. Foreground ≈ 0, sky ≈ 0.6–1 |
| `opacity` | 1 | start value for an opacity animation (drawn faded with Bayer dither — not free) |
| `animate` | nil | §6 |
| `exit` | nil | §6, AUTO only |
| `effect` | nil | §7 (one per layer) |
| `transitionOffset` | 0 | `images` swap points |
| `pixelLock` | 1 | 2+ snaps movement to every Nth pixel: stops dither shimmer while scrolling |
| `renderCondition` | nil | `{ var, value }` or `{ var, valueNot }` against `Panels.vars` |
| `stencil` | nil | image layers: mask image; animations move the image inside the mask |
| `name` | — | **(source)** free field; filter on it in custom render functions |

`images` layers: swap by scroll position (2 images → at 0.5);
`manuallySetImageIndex = true` lets an update function set `layer.currentImage`;
`advanceControl = Panels.Input.A` swaps on presses instead.

`imageTable` layers: `scrollTrigger` (0), `trigger` (button; holds frame 1
until pressed), `delay` (200 ms a frame), `reduceFlashingDelay`, `startDelay`,
`loop` (false).

Text layers: `text`, `font`, `fontFamily` (`*bold*`, `_italic_` markup),
`color` (BLACK; auto-white on a black `background`), `invertTextColor`,
`background` (WHITE/BLACK box), `border` (px, opposite colour),
`borderRadius`, `margin` `{ top=1, right=4, bottom=1, left=4 }`, `rect`
`{ width, height }` (wrapping box), `alignment`, `lineHeightAdjustment`.
A captioned box = text + background + border + margin.

## 6. Layer animations

```lua
-- scroll-driven: no trigger keys; runs with the scroll, backwards too
{ image = "s1/cloud", x = 10, animate = { x = 200, y = -20 } }
-- time-driven: starts at a scroll point (or autoStart = true, same as 0)
{ image = "s1/light", opacity = 0, animate = { opacity = 1, duration = 500, scrollTrigger = 0.5 } }
-- button-driven
{ image = "s1/door", animate = { x = -100, duration = 250, ease = playdate.easingFunctions.outQuint,
                                 trigger = Panels.Input.A, audio = { file = "s1/door" } } }
```

Targets: `x`, `y`, `opacity` (from the layer's own values). Modifiers:
`scrollTrigger`, `autoStart`, `trigger`, `triggerSequence` (`{A, B}`: only
after those presses in order — chain several animations in one panel),
`delay` (ms), `duration` (250; 200 when only scrollTrigger is set),
`ease`, `audio` `{ file, delay, loop }` (starts with the animation).

`exit` (AUTO sequences): same keys, played when the panel's advance control
fires; pair with the panel's `advanceDelay` so it is seen.

Button triggers in a MANUAL sequence can be scrolled past unseen — fine for
secrets, wrong for story beats.

## 7. Layer effects

| `type` | Keys | |
|---|---|---|
| `Panels.Effect.SHAKE` | `strength` (2) | random ±strength px per frame, × parallax |
| `Panels.Effect.BLINK` | `durations = { on, off }` (required), `delay`, `reduceFlashingDurations`, `audio = { file }` **(source)** (plays each time it turns on) | invisible during `delay` |
| `Panels.Effect.TYPE_ON` | `duration` (500), `delay`, `scrollTrigger` | text layers only; plays `Settings.typingSound` |

Respect Playdate's Reduce Flashing setting: give every BLINK a
`reduceFlashingDurations` and every fast imageTable a `reduceFlashingDelay`.

## 8. Custom functions

```lua
local function render(panel, offset)          -- you draw everything
    Backgrounds.draw(5)                       -- clipped to the frame, origin = panel corner
    for _, layer in ipairs(panel.layers) do
        if layer.name ~= "secret" or Panels.vars.found then
            Panels.renderLayerInPanel(layer, panel, offset)  -- parallax, animation, effects for free
        end
    end
end
```

- Drawing by hand: image layers carry their image in `layer.img`.
- Scroll percentage by hand (horizontal; vertical swaps x/y, width/height):
  `pct = 1 - (frame.x - frame.margin + frame.width + offset.x) / (400 + frame.width)`;
  parallax x = `layer.x + (panel.parallaxDistance * pct - panel.parallaxDistance / 2) * layer.parallax`.
- `advanceFunction` is polled every frame: reset its condition in
  `resetFunction`, or returning to the panel advances instantly.
- `resetFunction` is the place to stop sounds, timers, the accelerometer.

## 9. Variables, choice lists, branching

`Panels.vars` — saved with progress (cleared on game over unless
`Settings.resetVarsOnGameOver = false`; always cleared by Start Over).
`Panels.persistentVars` **(source)** — saved, never auto-cleared.

```lua
choiceList = {
    buttons = {
        { label = "Open the door", target = "room", var = { key = "brave", value = true } },
        { label = "Leave", target = "street", selected = true },
    },
    x = nil, y = nil, width = nil, height = nil,      -- nil = centred / auto-sized
    color = Panels.Color.BLACK, borderRadius = 4, spacing = 6, fontFamily = nil,
    onSelectionChange = function(index, button) end,
    buttonRenderFunction = function(label, x, y, w, h, radius, fontFamily, selected) end,
}
```

The comic moves to `target` only when the sequence's advance control is
pressed. `var` is set the moment a button is selected. Pointer art:
`libraries/panels/assets/images/pointer.png`.

Branching alternatives: sequence `advanceControls` (A → one id, B → another),
a panel's `targetSequenceFunction`, `nextSequence` to stitch out-of-order
sequences, `endSequence` for dead ends. Set
`Settings.listLockedSequences = false` so the chapter menu does not spoil
unvisited branches.

## 10. Settings (all before `start`)

| Key | Default | |
|---|---|---|
| `path` | `"libraries/panels/"` | |
| `imageFolder`, `audioFolder` | `"images/"`, `"audio/"` | `""` for full paths |
| `defaultFont`, `defaultFontFamily`, `menuFontFamily` | system | |
| `resetVarsOnGameOver` | true | |
| `defaultFrame` | `{ gap = 50, margin = 8 }` | |
| `snapToPanels` | false | gentle snap at panel edges in MANUAL |
| `sequenceTransitionDuration` | 750 | ms |
| `borderWidth`, `borderRadius` | 2, 2 | |
| `typingSound` | DEFAULT | NONE, or a path in audioFolder (the docs call it `typingSounds`; the source reads `typingSound`) |
| `maxScrollSpeed` | 8 | d-pad only |
| `menuImage` | `"menuImage.png"` | 400×240; the bottom 45 px sit under the menu |
| `showMenuOnLaunch`, `skipMenuOnFirstLaunch`, `playMenuSounds` | false, false, true | |
| `showMainMenuOption`, `mainMenuOptionLabel` **(source)** | false, `"Main Menu"` | system-menu item |
| `listLockedSequences`, `chapterMenuHeaderImage`, `useChapterMenu` | true, nil, true | |
| `useCreditsMenu` **(source)** | true | "Credits" in the system menu |
| `showCreditsOnGameOver` **(source)** | false | appends a scrolling credits sequence after the last one |
| `debugControlsEnabled` | false | simulator key `0` unlocks all sequences |
| `listUnnamedSequences` | false | debug: untitled sequences show as "--" |
| `showFPS` **(source)** | false | |

## 11. Menus and credits

Main menu: Start / Continue / Start Over / Chapters over `menuImage`.
`Panels.mainMenuDrawingCallBack = function(fadeValue) end` (capital B, as
the source spells it) draws over it; `Panels.percentageComplete` is ready to show.

Built-in credits screen:

```lua
Panels.credits = {
    autoScroll = true, hideStandardHeader = true, alignment = Panels.TextAlignment.CENTER, font = nil,
    lines = { { image = "logo" }, { text = "by *Name*", spacing = 16, alignment = ..., font = ... } },
}
```

It always appends the "Built with Panels" block with the QR code. For a
proper end roll use playdate-juice's `Credits` (see juice.md) and keep the
attribution yourself — Panels is CC BY 4.0: keep "Built with Panels —
cadin.github.io/panels" (with the QR, `libraries/panels/assets/images/panelsPagesQR.png`)
in your credits; for cutscenes "Cutscenes built with Panels: cadin.github.io/panels".

## 12. Cutscene mode

```lua
Panels.startCutscene(comicData, function(target) ... end)  -- target: chosen advanceControls target, if any
-- then, every frame until the callback:
Panels.update()
Panels.haltCutscene()   -- if you abort early (system menu): stops audio, pops its input handler
```

Never call `Panels.start` in a game. Calling `Panels.update` before
`startCutscene` crashes; forgetting it shows nothing; calling it after the
callback leaves the comic stuck on its last panel.

## 13. Behaviour you only learn from the source

- **Panels.update() runs `playdate.timer.updateTimers()` itself.** While a
  cutscene runs, do not also call it, or every timer in the game runs at
  double speed.
- **Importing Panels redefines `playdate.gameWillTerminate`,
  `playdate.deviceWillSleep`, `playdate.deviceWillLock` and
  `playdate.keyPressed`.** The first three save Panels' progress with
  `playdate.datastore.write(t)` — the DEFAULT datastore file, the same one a
  game's `datastore.write(save)` uses — so a game embedding cutscenes loses
  its own save hooks and gets its save overwritten. Import Panels BEFORE you
  define those callbacks (yours then win), and save your game under an
  explicit name: `playdate.datastore.write(save, "game")`.
- It leaks globals: `round`, `printError`, `reverseTable`, `hasValue`,
  `getScrollPercentages`, `getPanelScrollLocation`, `doLayerEffect`,
  `layerShouldRender`, `calculateControlPercent`, `validateSettings`,
  `setDefaultFont`, `onBGFinished`, `onAlertDidStartOver`, `onAlertDidHide`,
  `shouldShowMainMenu`, `createMenus`, `createMainMenu`, `updateMenus`,
  `updateMenuData`, `createPointerTimer`, `buttonIndicators`, `panelNum`,
  `table.shallow_copy`. Do not name your own globals that.
- `Panels.start` replaces `playdate.update` and `playdate.cranked`;
  `startCutscene` pushes an input handler with `cranked` and pops it when the
  cutscene ends. Your own `playdate.cranked`/button callbacks keep firing
  during a cutscene unless you gate them.
- `modules/Credits.lua` loads the QR image at import time — importing Panels
  allocates even if you never show its credits.
- **Cutscene crash on a background change.** Between two sequences with
  different `backgroundColor`, Panels cross-fades through a buffer only
  `Panels.start` creates; under `startCutscene` that is
  `Panels.lua:971: attempt to index a nil value (upvalue 'transitionFader')`
  (reproduced in the simulator). Keep one colour per cutscene, or chain
  cutscenes (juice.md §5).
- In cutscene mode every sequence change rebuilds Panels' main menu: without
  `images/menuImage.png` the console prints `Error loading main menu image`
  and a gridview error. Harmless.
- A sequence slides in from off-screen (`startTransitionIn`), so the first
  frame of a fresh sequence is empty background. `direction = NONE` makes the
  first panel visible at once — what a transition into the comic wants to
  snapshot.
- Images of a sequence are loaded when the sequence starts (`Panels.Panel.new`)
  and the cache is cleared when it ends: memory follows the largest sequence,
  not the comic. Split huge sequences.
- `targetSequenceFunction` is called with no arguments; `setupFunction`,
  `resetFunction`, `advanceFunction` receive the panel; `updateFunction` and
  `renderFunction` receive `(panel, offset)`.
