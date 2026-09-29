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
   crunchy on purpose: that is their sound.

   Format 3 adds a tracker's sampler voice, OSC_PCM, in the manner of
   FastTracker 2: 8-bit signed frames at the sample's own rate, resampled
   to the note with linear interpolation, a forward loop, a start offset,
   backwards play, a 0-64 channel volume and a pan position. Its position is
   20.12 fixed point (no float drift over a long break), its gains ramp
   across each block so a volume change does not click, and a note that is
   cut or retriggered hands its last output to a short decay rather than
   stopping dead -- a chopped break retriggers a voice sixteen times a bar. */
#ifndef VOX_H
#define VOX_H
#include <stdint.h>

#define VOX_VOICES 8

enum { OSC_PULSE, OSC_WAVE, OSC_NOISE, OSC_SAMPLE, OSC_TRIANGLE, OSC_SAW, OSC_PCM, OSC_COUNT };

/* A PCM sample may be at most this many frames: its 20.12 position must
   stay under 2^31 so that playing backwards past frame 0 shows as the top
   bit. 2^19 frames is 23 s at 22 kHz. */
#define VOX_PCM_MAX (1u << 19)

/* Voice flags. */
#define VOX_RING   0x01   /* multiply by the previous voice's square */
#define VOX_SYNC   0x02   /* restart the phase when the previous voice's does */
#define VOX_FILTER 0x04   /* through the filter */

/* Filter modes, combinable as on the SID. */
#define VOX_LP 1
#define VOX_BP 2
#define VOX_HP 4

typedef struct {
    /* What the renderer moves, together and in this order: vox_render keeps
       it in locals for a whole call and writes back what changed, once, in
       one run (on the Playdate the voices live in the heap, where a scattered
       store is a slow trip to external RAM). The busiest first. */
    uint32_t pos;                   /* pcm: 20.12 fixed point */
    float out_l, out_r;             /* pcm: the last output, for a declick */
    float phase;                    /* 0..1 per cycle */
    int32_t env_count;
    float gl, gr;                   /* pcm: the gains the last block ended on */
    float dc_l, dc_r;               /* an interrupted note's last output, decaying */
    float smp_pos;                  /* sample */
    int32_t sweep_count, sweep_timer;
    uint16_t lfsr;                  /* noise */
    uint8_t vol;                    /* envelope, Game Boy style: 0-15, a step every pace/64 s */
    uint8_t on;
    uint8_t ramp;                   /* pcm: 0, the next block jumps to its gains */

    uint8_t osc, flags, pan;        /* pan: bit 0 right, bit 1 left */
    float inc;                      /* phase per sample */
    float width;                    /* pulse, 0..1 */
    uint8_t env_dir, env_pace;
    uint8_t duck;                   /* steps taken off the volume (music ducking) */
    /* sweep (pulse), NR10 semantics: 128 Hz */
    uint8_t sweep;
    uint16_t period;                /* the 11-bit period the pitch came from */
    /* wave */
    const uint8_t *wave;            /* 16 bytes, 32 nibbles */
    /* noise */
    uint8_t short_mode;
    /* sample: 4-bit, two per byte */
    const uint8_t *smp;
    uint32_t smp_len;               /* in samples */
    /* pcm (format 3): 8-bit signed, a guard frame after the last */
    const int8_t *pcm;
    uint32_t pcm_len, loop_start, loop_len;   /* frames; loop_len 0: one-shot */
    int32_t step;                   /* per output sample; negative plays backwards */
    float pcm_k;                    /* step x (2048 - period): the rate at C5, scaled */
    uint32_t from;                  /* where a trigger starts, in frames (0: the start, or backwards the end) */
    uint8_t rev;
    float level;                    /* channel volume 0..1 (every oscillator); 1 unless format 3 sets it */
    float bal_l, bal_r;             /* pan position as two gains, 1 at the centre (pcm) */
} VoxVoice;

typedef struct {
    VoxVoice v[VOX_VOICES];
    uint32_t rate;
    float master;                   /* NR50-like, 0..1 */
    float gain;                     /* per voice, by how many voices the song has */
    uint8_t cutoff, resonance, mode;
    int8_t cutoff_slide;
    float f, q;                     /* the filter's coefficients, from the above */
    float low, band;                /* its state */
    uint32_t frac;                  /* cycle remainder, as in gbapu */
    float dc_k;                     /* the declick's decay per sample */
    uint8_t declicks;               /* any voice's declick running: the per-voice test is skipped without */
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
void vox_sweep(Vox *x, int i, uint8_t nr10);
void vox_flags(Vox *x, int i, uint8_t flags);
void vox_pan(Vox *x, int i, uint8_t pan);
void vox_duck(Vox *x, int i, uint8_t steps);
void vox_off(Vox *x, int i);
/* Format 3's sampler. `data` holds `frames` 8-bit signed frames and one
   guard frame after them (the loop start's frame for a loop); `rate` is the
   rate in Hz the sample plays at on C5 (period 1798). */
void vox_pcm(Vox *x, int i, const int8_t *data, uint32_t frames, uint32_t loop_start, uint32_t loop_len, uint32_t rate);
/* Where the next trigger starts (a frame), and which way it plays: backwards
   from `frame`, or from the end when `frame` is 0. */
void vox_pcm_from(Vox *x, int i, uint32_t frame, uint8_t reverse);
/* FT2's channel volume, 0-64, times an amplification in 16ths (16 is 1:
   FT2's mixing "amplification", a format-3 song's own); any oscillator. */
void vox_volume(Vox *x, int i, uint8_t level, uint8_t amp);
void vox_balance(Vox *x, int i, uint8_t pan);   /* 0 left, 128 centre, 255 right (pcm) */
void vox_filter(Vox *x, uint8_t cutoff, uint8_t resonance, uint8_t mode);
void vox_cutoff_slide(Vox *x, int8_t per_tick);
/* Called by the driver once a frame: filter sweeps. */
void vox_frame(Vox *x);

/* Renders `n` samples; returns the Game Boy CPU cycles they cover, like
   gbapu_render, so one scheduler serves both. It works VOX_BLOCK samples at
   a time: envelopes and sweeps step, and gains ramp, per block. */
#ifndef VOX_BLOCK
#define VOX_BLOCK 64
#endif
uint32_t vox_render(Vox *x, int16_t *left, int16_t *right, int n);
int vox_active(const Vox *x);
/* A voice's current level 0-15, for meters. */
int vox_level(const Vox *x, int i);
#endif
