# Scott McCloud, applied to a 400×240 one-bit crank

From *Understanding Comics* (1993), *Reinventing Comics* (2000) and *Making
Comics* (2006). Not a summary of the books — each principle is followed by
what it turns into in comicData and in playdate-juice. Plan with these before
writing a single layer.

## Contents
1. Closure and the gutter
2. The six panel-to-panel transitions → Panels + juice
3. Time is space
4. Motion
5. Words and pictures: the seven combinations
6. Amplification through simplification, and the masking effect
7. The five choices (Making Comics)
8. The infinite canvas — why the crank is a comics device
9. Mood: lines, backgrounds, sound
10. A planning worksheet

---

## 1. Closure and the gutter

Comics are "juxtaposed pictorial and other images in deliberate sequence".
The reader sees two panels and invents what happened between them — closure.
The gutter is where the story actually happens, and the reader does that work
willingly; every cut is a small act of trust.

- Leave the reader something to close. Showing every step (wind-up, swing,
  impact, fall) is animation, not comics, and on Playdate it costs art and
  memory for less effect. Show the wind-up and the aftermath; let the gap or
  the cut carry the hit — then put the sound and the shake ON the cut.
- The size of the jump is a dial: small jumps feel continuous, big jumps feel
  meaningful. Match the dial to the beat (§2).
- In Panels the gutter is literally `frame.gap` in a scrolling sequence, the
  instant cut of `direction = NONE`, or a juice transition between panels.

## 2. The six transitions

McCloud's taxonomy of what changes between two panels. Western mainstream
comics are dominated by action-to-action, then subject-to-subject and
scene-to-scene; Japanese comics use far more aspect-to-aspect. Count yours:
a comic that is all one type reads flat.

| Transition | What changes | Closure | In Panels | Juice |
|---|---|---|---|---|
| Moment-to-moment | almost nothing — a blink, a drip | very little | one panel: an `images` layer swapping at a scroll point, an `imageTable`, or `direction = NONE` with the same composition | no wipe; a tiny `Shake` bump, a soft SFX (`step`, `text`) |
| Action-to-action | one subject through one action | little | AUTO, horizontal, short `transitionDuration` (300–400 ms, outQuad); or MANUAL with small gaps | the impact SFX + `Shake` trauma on the panel that lands the action |
| Subject-to-subject | another subject, same scene or idea | moderate | AUTO or MANUAL, standard gaps; parallax keeps the scene continuous | `Dissolve` / `Slide` between panels in a NONE slideshow |
| Scene-to-scene | jump in time or space | high — "ten years later" | a NEW sequence: its own `backgroundColor`, `audio`, often a caption panel | `Fade`, `Circle`, `Blink` between sequences or cutscenes; change the music (`Chiptune.play`) |
| Aspect-to-aspect | wandering eye over one place or mood; time stands still | high, but calm | MANUAL crank, wide `gap`, `borderless`, slow parallax, no text, ambient loop; maybe `VERTICAL` | no wipes; an animated `Backgrounds` loop (rain, stars) in a `renderFunction`; quiet music |
| Non-sequitur | no logical link | — | anything | `Pixel Shift`, `Scanline`, `Wind` — glitches read as "this does not follow"; use once |

Rule of thumb for the cut tools:
- **Scroll** (continuous) = we are in the same place and time.
- **Instant cut** (`NONE`) = the next moment; the reader's eye did not move.
- **Juice wipe** = punctuation. A wipe on every panel stops reading as
  punctuation and starts reading as lag (the same reason `Transitions.setPlan`
  has a bare list). Wipes belong on scene and mood changes.

## 3. Time is space

In comics, time is drawn as space. The reader spends longer in a wider panel,
a silent panel, a panel with more words. On Playdate you control it four ways:

1. **Panel length on the scroll axis** — `frame.width > 400` (horizontal) makes
   the reader crank through the moment: a long panel IS a long moment. A
   panorama is an establishing shot and a pause in one.
2. **Gutters** — `frame.gap`: 8–20 px for continuous action, 50 (default) for
   ordinary beats, 120+ px of empty background for "time passes".
3. **Duration** — `autoAdvance` (ms) in AUTO sequences for beats that must
   land at a set tempo; the default is the reader's own pace — prefer it.
4. **Silence** — a panel with no text is read slowly. A repeated panel (same
   art, `direction = NONE`) is a beat of silence: the comedy pause.

A borderless panel (`borderless = true`) bleeds into the page and feels
timeless — good for establishing shots, dreams, the last panel.

## 4. Motion

- **Motion lines** — bake them into the art; one bit draws them crisply.
- **Multiple images / polyptych** — one moving figure over a background that
  continues across panels: a horizontal strip with small gaps and the figure
  in a different place in each panel.
- **Subjective motion** — the camera moves with the subject, the background
  streaks: a background layer with `parallax = 1` plus streak art, the
  subject at `parallax = 0`.
- **Scroll-driven animation** — `animate` without triggers ties motion to the
  crank. The reader literally scrubs time: the purest comics/animation hybrid
  Panels has. Use it for a fall, a door, a sunrise.
- **Vibration vs impact** — Panels' `SHAKE` effects are constant jitter
  (engines, fear, cold). Juice `Shake` is trauma that decays: one hit. Use
  the right one; never both on the same beat.

## 5. Words and pictures

McCloud's seven combinations — decide per panel which side carries meaning:

| Combination | Meaning carried by | Panels practice |
|---|---|---|
| Word-specific | words; picture illustrates | caption text layer; picture can be simple |
| Picture-specific | picture; words are a sound track | no text, or a single SFX word; let the art work |
| Duo-specific | both say the same thing | avoid — redundant on a tiny screen |
| Additive | words amplify or elaborate the picture | short caption that adds what the art cannot |
| Parallel | words and picture follow separate courses | narration over unrelated imagery — memory, irony |
| Montage | words are part of the picture | lettering baked into art (signs, BOOM) |
| Interdependent | together they say what neither can alone | the goal for key beats |

Lettering on Playdate:
- 400×240 holds about 20–30 words before the art disappears. Split long text
  across panels or use `TYPE_ON` with `delay` to pace two lines.
- Captions: text layer with `background`, `border`, `margin`. Balloons:
  draw them into the art (tails need it) and put the words in a text layer —
  or bake both if the font is part of the look.
- Sound effects are lettering AND sound: draw the BOOM, and fire the
  matching chiptune SFX at the same scroll point (juice.md, cues).
- `TYPE_ON` is dialogue timing, not decoration: use it where the reader
  should hear the words arrive, not on every caption.

## 6. Amplification through simplification

A cartoon face is not less — it is focused. The simpler the face, the more
readers there are who can see themselves in it. The **masking effect**:
iconic characters over detailed, realistic backgrounds (Hergé) — the reader
wears the character and is shown the world.

One-bit Playdate art is built for this:
- Characters: clean outlines, solid black/white, few dithers. They must read
  at 60 px tall while scrolling.
- Backgrounds: carry the texture — dither, hatching, `Backgrounds` loops.
  Give dithered layers `pixelLock = 2` so they do not shimmer while scrolling.
- Contrast is depth: dark foreground silhouette (`parallax ≈ 0`) over a light
  dithered middle and a sparse far layer.

## 7. The five choices (Making Comics)

For every panel, decide deliberately:

1. **Moment** — which instant shows the beat best (not the middle of the
   motion: the wind-up or the aftermath). Cut beats that carry nothing.
2. **Frame** — distance (establishing / long / medium / close-up / extreme
   close-up) and angle. Establish each new scene once, early, wide; return to
   a wide shot after the geography changes. A close-up is a small panel
   (`frame.width ≈ 200–260`), an establishing shot a wide or borderless one.
3. **Image** — clarity first: silhouette test every character pose (fill it
   black — still readable?). Body language and the six basic expressions
   (anger, disgust, fear, joy, sadness, surprise) and their blends.
4. **Word** — fewest words that do the job; see §5.
5. **Flow** — the reader must never wonder where to look next. One axis per
   sequence; a change of axis or direction is a new sequence. Keep the
   scroll direction the reading direction; keep advance controls where the
   eye ends.

Clarity versus intensity: every flourish (wipe, shake, flash, type-on)
spends the reader's attention. Spend it on the beats that matter.

## 8. The infinite canvas

*Reinventing Comics*: on a screen, comics need not be cut into pages. The
canvas can be one continuous trail where distance is time, and the reader
moves along it. Panels is exactly this, and the crank is the reader's hand:

- A MANUAL sequence is a trail; the reader sets the tempo and can back up —
  the comic is navigable time.
- Turning the axis (vertical drop after a horizontal walk) is a change of
  tempo the reader feels in the hand.
- Scroll-driven animation and parallax happen only because the reader moves:
  reward cranking, never punish it (no beat should be missable by cranking
  fast; put must-see beats in AUTO sequences or on scroll-driven layers).

## 9. Mood: lines, backgrounds, sound

McCloud: lines carry emotion (jagged = anger, anxiety; soft curves = calm),
and backgrounds can show feeling instead of place (expressionist patterns).
On Playdate:
- Expressionist backdrop = a `Backgrounds` loop in a `renderFunction`
  (Lightning, Fire, Matrix Rain, Plasma for dread; Starfield, Confetti for
  wonder and joy).
- Panel border style: `borderless` for dreams and memories, normal borders
  for the present, black `backgroundColor` sequences for night or flashback.
- Music is the background of time: a scene change gets a song change
  (`Chiptune.play`), an aspect-to-aspect pause gets the music alone, a shock
  gets silence (`Chiptune.stop()` one panel before the hit, SFX on the hit).

## 10. Planning worksheet

Write this table before touching comicData; it becomes the data almost line
by line.

| # | Beat (one line) | Transition from previous | Time (gap / width / autoAdvance) | Frame (distance) | Words (who carries meaning) | Juice (wipe / SFX / shake / music) |
|---|---|---|---|---|---|---|
| 1 | The lighthouse at night | — (opening) | wide 640 px, MANUAL | establishing, borderless | picture-specific | `Fade` in from title; music `hollow_deep` |
| 2 | Keeper hears a knock | subject-to-subject | gap 50 | medium | additive caption "knock." | SFX `door` at 0.5 |
| … | | | | | | |

Then sanity-check: Is any type of transition doing all the work? Is there a
silent panel anywhere? Is every wipe a scene or mood change? Does every SFX
have a picture, and does every big picture have a sound?
