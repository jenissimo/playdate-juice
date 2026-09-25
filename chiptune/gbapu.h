/* gbapu: the DMG's sound hardware, rendered to 16-bit stereo.

   Register-level: whoever drives it writes NR10-NR52 and wave RAM exactly as
   a Game Boy program would, and gbapu_render() turns the next stretch of
   time into samples. That is what lets the GBM driver above it be a
   line-for-line port that is held, write for write, to the real ROM's APU
   log (test/chiptune/).

   Every output sample is the exact average of each channel's level over the
   ~95 CPU cycles it covers (a box filter), not a point sample: a 4 MHz
   square wave point-sampled at 44.1 kHz aliases audibly on high notes, and
   this costs one multiply per channel edge. No SDK, no allocation. */
#ifndef GBAPU_H
#define GBAPU_H
#include <stdint.h>

#define GBAPU_CLOCK 4194304u

typedef struct {
    /* Pulse 1-2, wave 3, noise 4, indexed 0-3. */
    uint8_t on, dac;
    uint8_t length_on;
    uint16_t length;
    uint16_t freq;             /* 11-bit period register */
    int32_t timer;             /* cycles to the next step */
    uint8_t pos;               /* duty step / wave position */
    uint8_t level;             /* current digital output, 0-15 */
    /* envelope (1, 2, 4) */
    uint8_t vol, env_dir, env_pace, env_timer;
    /* sweep (1) */
    uint8_t sweep_on, sweep_timer;
    uint16_t shadow;
    /* wave (3) */
    uint8_t buffer;
    /* noise (4) */
    uint16_t lfsr;
} GbApuChan;

typedef void GbApuWriteHook(void *user, uint16_t addr, uint8_t value);

typedef struct {
    uint8_t reg[0x30];          /* 0xFF10-0xFF3F as last written */
    GbApuChan ch[4];
    uint8_t fs_step;            /* frame sequencer, 512 Hz */
    int32_t fs_timer;
    uint32_t rate, frac;        /* output rate, and the cycle remainder */
    int32_t hp_l, hp_r;         /* DC blocker state (Q16) */
    int32_t hp_xl, hp_xr;
    int32_t hp_k;               /* its charge factor per sample (Q16) */
    GbApuWriteHook *hook;       /* sees every register write (tests) */
    void *hook_user;
} GbApu;

void gbapu_init(GbApu *a, uint32_t sample_rate);
void gbapu_write(GbApu *a, uint16_t addr, uint8_t value);
uint8_t gbapu_read(const GbApu *a, uint16_t addr);
/* Renders `n` samples. Returns the CPU cycles they covered (it varies by one
   between calls: 4194304 does not divide by 44100). */
uint32_t gbapu_render(GbApu *a, int16_t *left, int16_t *right, int n);
/* How many samples cover `cycles` from now, rounding up. */
int gbapu_samples_for(const GbApu *a, uint32_t cycles);
/* Is any channel sounding? (silence lets a host skip mixing) */
int gbapu_active(const GbApu *a);
#endif
