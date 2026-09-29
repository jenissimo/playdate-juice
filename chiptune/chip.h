/* chip: the GBM driver and a DMG APU running inside an audio callback.

   The Game Boy ticks its music on VBlank, 59.73 times a second. Ticking it
   from a game's update loop instead would tie the tempo to the frame rate --
   a 30 fps game would play everything at half speed, and a dropped frame
   would be a stumble in the music. So time here is the audio's: chip_render
   runs the driver's frame tick every 70224 emulated CPU cycles and the
   drum-sample timer every 16384, exactly as the hardware would, between
   the samples it renders.

   That puts the driver on the audio thread (an interrupt, on the device).
   The game talks to it through a single-producer queue drained at the top of
   each render, so no call from the game ever races the driver. Reads
   (position, sync) are single bytes and safe from anywhere.

   A format-3 song with a tempo (FT2's BPM) ticks its music on a clock of
   its own, music_cd, every g->tick_cycles; the frame tick goes on for the
   effects and the ducking.

   A tick does not cut the render short where it falls: it waits for the
   next quantum -- the largest power of two samples under CHIP_TICK_LATE_US,
   32 at 22050 Hz, 64 at 44100 -- so vox renders whole blocks rather than
   slivers between ticks. A tick is then up to 1.5 ms late, never early, and
   the clocks keep their exact rate (the lateness is not carried forward).
   The drum-sample timer keeps its exact time: it feeds the wave channel.
   Build with -DCHIP_TICK_LATE_US=0 for ticks to the sample. */
#ifndef CHIP_H
#define CHIP_H
#include "gbm.h"

enum {
    CHIP_PLAY, CHIP_STOP, CHIP_PAUSE, CHIP_SFX_BANK, CHIP_SFX, CHIP_SFX_STOP,
    CHIP_DUCK, CHIP_MUTE, CHIP_HOLD, CHIP_VOLUME
};

typedef struct {
    uint8_t op, a, b;
    const uint8_t *blob;
} ChipCmd;

#define CHIP_QUEUE 64

#ifndef CHIP_TICK_LATE_US
#define CHIP_TICK_LATE_US 1500
#endif

typedef struct {
    GbApu apu;                      /* format 1: the exact DMG */
    Vox vox;                        /* format 2 (and anything mixed with it) */
    Gbm gbm;
    int32_t tick_cd, timer_cd, music_cd;
    int quantum;                    /* samples a tick may wait for, a power of two */
    ChipCmd queue[CHIP_QUEUE];
    volatile uint32_t head, tail;   /* head: the game's; tail: the audio's */
    volatile uint8_t idle;          /* nothing to play: the last render was silent */
    volatile uint32_t ticks;        /* frame ticks so far, for pacing and tests */
} Chip;

void chip_init(Chip *c, uint32_t sample_rate);
/* From the game's side. Returns 0 if the queue is full (64 commands between
   two audio callbacks: a runaway loop, not normal use). */
int chip_post(Chip *c, uint8_t op, uint8_t a, uint8_t b, const uint8_t *blob);
/* From the audio side: the callback. Returns 0 when it produced silence, so
   the host may skip mixing it. */
int chip_render(Chip *c, int16_t *left, int16_t *right, int n);
/* Runs the queue now: for hosts that render off-line (tests, tools). */
void chip_drain(Chip *c);
#endif
