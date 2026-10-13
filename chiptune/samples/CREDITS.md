# Sample credits

Every sample here was synthesised from nothing by `tools/jungle_kit.py`
(numpy): oscillators, noise, filters, a synthetic room and a bus
compressor, rendered and quantised to 8 bits. No recording, no sample
library, no break from a record and no third-party audio went into any of
them -- in particular none of the classic breaks (Amen, Think, Apache, Funky
Drummer): the breaks here are programmed performances of a synthesised kit,
their patterns generic breakbeat figures.

They were made for this repository and are covered by its licence (MIT,
`LICENSE` at the repo root); rebuild them with
`python tools/jungle_kit.py`.

| file | what | rate | frames | loop | root | source |
|---|---|---|---|---|---|---|
| `break_a.wav` | funky break, 1 bar, 16ths every 2048 frames (170 BPM at this rate) | 23211 Hz | 32768 | -- | -- | `jungle_kit.break_a()`: modal kick, snare and ghost snares, 808-style metallic hats, room, bus compression, saturation |
| `break_b.wav` | tight break, 1 bar, with tambourine | 23211 Hz | 32768 | -- | -- | `jungle_kit.break_b()`: the same kit tuned higher and harder |
| `reese.wav` | three detuned saws, fundamental turned down, driven | 11025 Hz | 16182 | whole | C2 | `jungle_kit.reese()`: built in the frequency domain over one loop, periodic by construction |
| `pad.wav` | open-fifth chord (root, 5th, 9th, 12th, octave), detuned saws, filtered, chorus, room | 8820 Hz | 18698 | 5468 + 13230 | C3 | `jungle_kit.pad()`: crossfaded loop |
| `stab.wav` | minor-seventh rave stab, filter snapping shut | 16000 Hz | 6720 | -- | C4 | `jungle_kit.stab()` |
| `crash.wav` | crash cymbal, inharmonic partials over hiss | 16000 Hz | 16800 | -- | -- | `jungle_kit.crash()` |
| `hoover.wav` | pulse-saw hoover swooping up from a fifth below | 11025 Hz | 12898 | 4630 + 8268 | C3 | `jungle_kit.hoover()`: crossfaded loop |

137 KB in all. The songs embed what they use: `jungle_ride` break A, reese,
pad, stab, crash; `jungle_race` break B, reese, hoover, stab, crash;
`jungle_menu` break A, pad, crash.
