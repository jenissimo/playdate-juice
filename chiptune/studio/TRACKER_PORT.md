# Porting the studio's rock to the tracker: what to do next

A brief for the agent working on chiptune's format 3 (PCM8 samples in vox, `rock.gbank`,
`tools/studio_theme.py`). Format 3 works; the music does not yet sound like the studio's.
The tracker version may be simpler than the rendered loops -- fewer layers, no amp on a whole
stem, no real reverb -- but a listener should recognise **the same tune, the same groove and
the same weight**. This lists why it does not today, measured, and what to change, in order.

## What is wrong now (measured)

`steel_circuit.gbm` (rendered with `tools/chiptune.py render ... --bank rock.gbank --mono`)
against the studio's `menu` loop (`studio/songs/overturn_rock.cjs`):

| | studio | tracker |
|---|---|---|
| loudness | -14.6 LUFS | -23.2 LUFS |
| 50 ms RMS, 10th to 90th percentile | 3.5 dB | 8.5 dB (holes) |
| energy share under 100 Hz | -9.3 dB | -4.1 dB (boomy) |
| 300 Hz-1 kHz / 1-3 kHz (where the guitars live) | -7.0 / -10.4 dB | -12.8 / -15.6 dB |
| over 8 kHz | -17.5 dB | -27.2 dB |

1. **It is a different song.** `studio_theme.py` says so: "a fresh tracker arrangement, rather
   than an export of studio's mastered loops". One one-bar riff transposed through Am F G E, a
   lead fragment, a kick on `x.....x.x.....x.` instead of four on the floor; none of the
   original's riff, hook, break or form.
2. **Notes are cut.** In GBM `-` is a note off; in the studio's lines `-` *holds*. So
   `A2@gtr_chord . - ...` stops the chord after two rows where the original lets it ring, and
   a bar ending in `C3@gtr_chord -` ends in near silence (visible once a bar). A note off also
   cuts with no release.
3. **No mix.** Half the studio's sound is `master.cjs`: every stem levelled by loudness, the
   drum bus compressed, the bed pumping under the kick, a room and echoes, a glue compressor,
   a soft clip and a limiter. The tracker sums dry samples at guessed 4-bit volumes.
4. **Fidelity.** A 16384 Hz bank has nothing over 8 kHz (hats, crash, the guitar's edge); one
   A2 chord sample transposed down 4-5 semitones for F and E is darker still (~6 kHz) and moves
   the cabinet's resonance with it.
5. **Groove.** `groove=(6, 7)` alternates 16ths of 100 and 117 ms: a shuffle. The original
   is straight.
6. **Voices.** Eight voices, the guitar's chords and chugs sharing one: fine for a guitar (a
   new strum stops the last), but there is no second guitar, twin lead, crash, toms, clap.

## What to do

### 1. Port the arrangement, do not rewrite it

Write `studio/export_tracker.cjs`: run a song module (`songs/overturn_rock.cjs`, `menu` first)
against a **recording** Song, and write its note events as JSON.

- Tag every instrument call before the song module is required: wrap each function of
  `instruments.cjs` `I` and `G` in place so the buffer it returns carries its source, e.g.
  `buf.src = { inst: 'G.chord', n, d, up }` (the functions are memoised, so the same arguments
  give the same tagged buffer). A subclass of `S.Song` whose `put(stem, step, buf, gain)` logs
  `{ stem, step, src: buf.src, gain }` instead of (or as well as) mixing.
- Output per loop: `{ bpm, bars, steps, events: [{ stem, step, inst, n, d, gain, up, mark }] }`
  and the song's `LEVELS`, `VERB`, `echo`, `pump` from its `master()` call.
- In Python, turn the events into GBM rows. Studio lines vs GBM:

  | | studio line | GBM |
  |---|---|---|
  | hold | `-` | `.` (an empty row lets the note go on) |
  | stop | `.` (a rest) / the next note | `-` (note off) -- only where the original really stops |
  | notes | MIDI, C4 = 60 | C1 = 0 (MIDI - 24), banks keep MIDI roots |

  A note's length is its `d` (seconds): emit a note off at its end only if nothing else on that
  voice starts first and the instrument has no natural decay to rely on.
- Voices (8), for the menu, by priority where a lane is busy:

  | voice | stems |
  |---|---|
  | 1 | `gtr` (chords and chugs, as one guitarist plays them) |
  | 2 | `bass` |
  | 3 | `lead` |
  | 4 | `kick` |
  | 5 | `snare`, `clap`, `tom` |
  | 6 | `hat`, `ohat` |
  | 7 | `orch`, `crash`, `stab` |
  | 8 | `lead2` / `gtr2` (whichever plays), else `pluck`, `acid` |

  Dropping `pad`, `riser`, `pluck` when a lane is taken is fine. Write down what was dropped.
- Velocity: map `gain` (and drum line levels: `X` 1.25, `x` 1, `o` 0.45, digits) to the
  driver's per-note volume, or to two or three instruments per sample (accent, normal, ghost).
- Check the port mechanically: the GBM's notes, per voice, against the event list (pitch and
  start; length within a row).

### 2. A bank that carries the mix

Extend `banks/rock.cjs` (or generate a bank from the event list) so the samples bring what the
driver cannot:

- **One sample per chord root used** -- read them off the events (the menu's rhythm guitar
  alone plays on A2 C3 D3 Eb3 E3 E2 F2 G2 Bb2, its second guitar an octave up) -- chords and
  chugs both; no transposition of guitar chords. Single notes (bass, lead) may transpose from
  a root.
- **The master's EQ baked in**: `master.cjs` `EQ` (bass HP 38 Hz, stab HP 120...) and the amps'
  `post` EQ for the guitars (the rhythm guitar HP 150 Hz, -2.5 dB at 170 Hz). That is most of
  the boom.
- **The sends baked in**: snare, clap, orch, stab and lead rendered with their room (the song's
  `VERB` amount into `S.reverb` with its `room`), the lead with its echo (`steps` at the song's
  tempo). A tail costs bank size: keep it to the reverb's -40 dB.
- **Levels by loudness**: give each instrument the volume that makes it sound at the song's
  `LEVELS` (stem LUFS) -- measure the sample's LUFS once, at the bank's rate, and solve for the
  4-bit volume (or scale the PCM). No guessed volumes.
- **Rate**: 22050 Hz for hats, open hat, crash, the chords and the lead (the >8 kHz energy is
  the "air"); 16384 Hz is fine for kick, bass, toms. Keep TPDF dither. State the bank's size
  (a budget of ~400 KB for the three loops' samples is reasonable).

### 3. The driver

- **A release**: a note off (and a retrigger cutting a ringing note) fades over a few ms to
  ~40 ms (an instrument parameter) instead of cutting -- no clicks, no holes.
- **An exact tempo**: straight 16ths at the original BPM. Rows of whole frames at 59.73 Hz
  give 149.3 BPM (6) or 128 BPM (7), neither of which is 140. Prefer a per-song tick rate in
  the format-3 header (the driver's tick at `bpm * 4 * frames_per_row / 60` Hz), so 140 BPM is
  6 frames a row at 56 Hz. Failing that, pick the nearest straight speed and say so.
- **An output stage**: a soft clip and a peak limiter on the sum with a make-up gain, so a song
  can sit near -14.5 LUFS like the rendered loops (and like the game's volumes expect). Cheap:
  one gain per block from a peak follower.
- **Optional, the pump**: duck every non-drum voice on a kick note (about -5 dB, back over
  ~110 ms), as the studio's master does; a song-level flag. It is a big part of the groove.

### 4. Then play and multi

The same pipeline for `play` (32 bars) and `multi` (16 bars). Keep the bank shared.

## Accept when

- The tracker `menu` has the original's notes, form and tempo (the mechanical check of 1.),
  straight 16ths.
- Measured against the studio render (the table above): loudness within ~1 LU after the output
  stage; band shares 100 Hz-3 kHz within ~2 dB; over 8 kHz within ~4 dB; the 50 ms RMS spread
  under ~5 dB outside the breakdowns (no holes).
- `python tools/chiptune.py test` passes; existing songs render as before; the CPU per sample is
  benchmarked and stated; the bank size is stated.
- WAV renders of the tracker loops next to the studio's (`node render.cjs songs/overturn_rock.cjs
  --preview ...`) for listening A/B, and the chiptune README updated.

## Where things are

- The original: `studio/songs/overturn_rock.cjs` (the bodies, `LEVELS`, `VERB`, each loop's
  `master()` spec), `studio/instruments.cjs` (`I`, `G`), `studio/master.cjs` (`AMPS`, `EQ`, the
  chain), `studio/compose.cjs` (what each line token means).
- Render the original: `node studio/render.cjs studio/songs/overturn_rock.cjs --out out
  --preview preview --mix`.
- Measure: `S.stats(x)` in `studio/synth.cjs` gives LUFS, peak, the speaker share and the six
  band shares used in the table above.
