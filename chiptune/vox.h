/* vox: the extended-mode synth. Up to 8 voices, each any kind of
   oscillator, with the Game Boy's pitch and envelope semantics kept (so the
   driver's tables, periods and envelope bytes mean the same thing) and the
   C64 SID's extras added: continuous pulse width, a triangle and a saw,
   ring modulation, hard sync, and one resonant multimode filter that any
   voice can be routed through.

   It is a parameter-level synth, not a register-level emulation: gbapu is
   the faithful DMG and stays the backend for format-1 songs. vox renders in
   float -- the Cortex-M7 has a single-precision FPU -- and band-limits its
   pulse and saw with PolyBLEP, so a high note does not alias the way a naive
   square at 44.1 kHz would. The wave and noise voices stay stepped and
   crunchy on purpose: that is their sound. */
#ifndef VOX_H
#define VOX_H
#include <stdint.h>

#define VOX_VOICES 8

enum { OSC_PULSE, OSC_WAVE, OSC_NOISE, OSC_SAMPLE, OSC_TRIANGLE, OSC_SAW, OSC_COUNT };

/* Voice flags. */
#define VOX_RING   0x01   /* multiply by the previous voice's square */
#define VOX_SYNC   0x02   /* restart the phase when the previous voice's does */
#define VOX_FILTER 0x04   /* through the filter */

/* Filter modes, combinable as on the SID. */
#define VOX_LP 1
#define VOX_BP 2
#define VOX_HP 4

typedef struct {
    uint8_t on, osc, flags, pan;    /* pan: bit 0 right, bit 1 left */
    float phase, inc;               /* 0..1 per cycle */
    float width;                    /* pulse, 0..1 */
    /* envelope, Game Boy style: vol 0-15, a step every pace/64 s */
    uint8_t vol, env_dir, env_pace;
    int32_t env_count;
    uint8_t duck;                   /* steps taken off the volume (music ducking) */
    /* sweep (pulse), NR10 semantics: 128 Hz */
    uint8_t sweep;
    int32_t sweep_count, sweep_timer;
    uint16_t period;                /* the 11-bit period the pitch came from */
    /* wave */
    const uint8_t *wave;            /* 16 bytes, 32 nibbles */
    /* noise */
    uint16_t lfsr;
    uint8_t short_mode;
    /* Legacy 4-bit PCM, or studio PCM8 with an exclusive sustain-loop end. */
    const uint8_t *smp;
    uint32_t smp_len;               /* in samples */
    float smp_pos;
    uint8_t smp_bits;
    uint32_t smp_loop_start, smp_loop_end;
    float smp_scale;                /* source rate / root Hz / output rate */
    float mix_gain, release_gain, release_step;
    uint8_t release_ms, releasing;
} VoxVoice;

typedef struct {
    VoxVoice v[VOX_VOICES];
    VoxVoice tail[VOX_VOICES];       /* bounded release overlap on retrigger */
    uint32_t rate;
    float master;                   /* NR50-like, 0..1 */
    float gain;                     /* per voice, by how many voices the song has */
    uint8_t cutoff, resonance, mode;
    int8_t cutoff_slide;
    float f, q;                     /* the filter's coefficients, from the above */
    float low, band;                /* its state */
    uint32_t frac;                  /* cycle remainder, as in gbapu */
    float output_gain, limiter_gain, hp_coeff, comp_power;
    float hp_in[2], hp_out[2];
} Vox;

void vox_init(Vox *x, uint32_t rate);
/* How many voices the song uses: the mix is scaled so 8 voices do not clip
   where 4 would not. */
void vox_voices(Vox *x, int n);
void vox_master(Vox *x, uint8_t level);         /* 0-7, as NR50 */

/* Starts a note on voice `i`. `pitch` is an 11-bit period (pulse, wave,
   triangle, saw: Game Boy semantics) or a noise shape (NR43 byte, bit 3 =
   7-bit mode). `env` is an NRx2 envelope byte. */
void vox_trigger(Vox *x, int i, uint8_t osc, uint16_t pitch, uint8_t env);
void vox_pitch(Vox *x, int i, uint16_t pitch);  /* no restart */
void vox_osc(Vox *x, int i, uint8_t osc);       /* no restart either */
void vox_width(Vox *x, int i, uint8_t width);   /* 0-255 */
void vox_wave(Vox *x, int i, const uint8_t *wave);
void vox_sample(Vox *x, int i, const uint8_t *data, uint32_t samples);
/* PCM8 pitch is unsigned 8.8 semitones from C1, independent of DMG periods.
   Data and loop bounds must have been checked by the loader. No ownership
   is transferred: the bank must outlive every voice reading it. */
void vox_sample8(Vox *x, int i, const uint8_t *data, uint32_t samples,
                 uint32_t rate, uint32_t root_millihz, uint32_t start, uint32_t end);
void vox_sweep(Vox *x, int i, uint8_t nr10);
void vox_flags(Vox *x, int i, uint8_t flags);
void vox_pan(Vox *x, int i, uint8_t pan);
void vox_duck(Vox *x, int i, uint8_t steps);
void vox_off(Vox *x, int i);
void vox_release(Vox *x, int i);
void vox_note_tail(Vox *x, int i);
void vox_articulation(Vox *x, int i, uint8_t release_ms, uint16_t gain_q8);
void vox_output(Vox *x, uint16_t gain_q8); /* zero: original output path */
void vox_filter(Vox *x, uint8_t cutoff, uint8_t resonance, uint8_t mode);
void vox_cutoff_slide(Vox *x, int8_t per_tick);
/* Called by the driver once a frame: filter sweeps. */
void vox_frame(Vox *x);

/* Renders `n` samples; returns the Game Boy CPU cycles they cover, like
   gbapu_render, so one scheduler serves both. */
uint32_t vox_render(Vox *x, int16_t *left, int16_t *right, int n);
int vox_active(const Vox *x);
/* A voice's current level 0-15, for meters. */
int vox_level(const Vox *x, int i);
#endif
