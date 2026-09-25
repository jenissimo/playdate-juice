/* vox: see vox.h. */
#include "vox.h"
#include <string.h>


void vox_init(Vox *x, uint32_t rate)
{
    int i;
    memset(x, 0, sizeof *x);
    x->rate = rate;
    x->master = 1.0f;
    for (i = 0; i < VOX_VOICES; i++) { x->v[i].pan = 3; x->v[i].width = 0.5f; x->v[i].lfsr = 0x7FFF; }
    vox_voices(x, 4);
    vox_filter(x, 255, 0, VOX_LP);
}

void vox_voices(Vox *x, int n)
{
    /* A Game Boy mix puts four channels at +-15 each under full scale. Past
       four the per-voice level shrinks as 1/sqrt(n), not 1/n: voices seldom
       peak together, and 1/n made an 8-voice song half as loud as a
       4-voice one. The output clamp catches the rare pile-up. */
    /* 4 voices sit a notch lower: measured, a format-1 song on vox is
       otherwise louder than on gbapu, whose DAC loses some swing */
    static const float INV_SQRT[9] = {0.385f, 0.385f, 0.385f, 0.385f, 0.385f, 0.4472f, 0.4082f, 0.3780f, 0.3536f};
    if (n < 4) n = 4;
    if (n > 8) n = 8;
    x->gain = 0.23f * 2.0f * INV_SQRT[n];
}

void vox_master(Vox *x, uint8_t level) { x->master = (float)((level & 7) + 1) / 8.0f; }

/* Pitch: the Game Boy's own formulas, so the driver's periods mean the same
   note. A wave cycle is 32 steps at 2 MHz / (2048 - p), i.e. half the
   pulse's rate for the same period -- the driver adds an octave for it, as
   it does on the DMG. */
static float freq_of(uint8_t osc, uint16_t p)
{
    float d = (float)(2048 - (p & 2047));
    if (osc == OSC_WAVE) return 65536.0f / d;
    return 131072.0f / d;
}

static float noise_rate(uint8_t nr43)
{
    int s = nr43 >> 4, r = nr43 & 7;
    if (s >= 14) return 0.0f;
    return 524288.0f / (r ? (float)r : 0.5f) / (float)(2 << s);
}

static void set_pitch(Vox *x, VoxVoice *v, uint16_t pitch)
{
    if (v->osc == OSC_NOISE) {
        v->short_mode = (pitch >> 3) & 1;
        v->inc = noise_rate((uint8_t)pitch) / (float)x->rate;
    } else if (v->osc == OSC_SAMPLE) {
        /* A sample plays at 8192 Hz at C5 (period 1798) and follows the note. */
        v->inc = freq_of(OSC_PULSE, pitch) / 523.25f * 8192.0f / (float)x->rate;
    } else {
        v->inc = freq_of(v->osc, pitch) / (float)x->rate;
    }
    v->period = pitch;
}

static void set_env(Vox *x, VoxVoice *v, uint8_t env)
{
    v->vol = env >> 4;
    v->env_dir = (env >> 3) & 1;
    v->env_pace = env & 7;
    v->env_count = (int32_t)(x->rate * v->env_pace / 64);
}

void vox_trigger(Vox *x, int i, uint8_t osc, uint16_t pitch, uint8_t env)
{
    VoxVoice *v = &x->v[i];
    v->osc = osc < OSC_COUNT ? osc : OSC_PULSE;
    v->on = (env & 0xF8) != 0;       /* the DMG's DAC rule: volume 0, decreasing, is off */
    set_env(x, v, env);
    set_pitch(x, v, pitch);
    v->phase = 0.0f;
    v->smp_pos = 0.0f;
    v->lfsr = 0x7FFF;
    v->sweep_timer = (v->sweep >> 4) & 7;
    v->sweep_count = (int32_t)(x->rate / 128);
}

void vox_pitch(Vox *x, int i, uint16_t pitch) { set_pitch(x, &x->v[i], pitch); }

/* A new oscillator mid-note: the envelope and phase run on, as when a SID
   voice changes waveform. The caller sends the pitch next, since it means
   something else for noise. The LFSR is left as it is: reset, a low noise
   would start with 15 steps of silence. */
void vox_osc(Vox *x, int i, uint8_t osc)
{
    VoxVoice *v = &x->v[i];
    v->osc = osc < OSC_COUNT ? osc : OSC_PULSE;
    if (v->osc == OSC_SAMPLE) v->smp_pos = 0.0f;
}
void vox_width(Vox *x, int i, uint8_t w)
{
    /* never exactly 0 or 1: a pulse that stops toggling is a DC offset */
    float f = (float)w / 256.0f;
    x->v[i].width = f < 0.01f ? 0.01f : f > 0.99f ? 0.99f : f;
}
void vox_wave(Vox *x, int i, const uint8_t *wave) { x->v[i].wave = wave; }
void vox_sample(Vox *x, int i, const uint8_t *d, uint32_t n) { x->v[i].smp = d; x->v[i].smp_len = n; x->v[i].smp_pos = 0; }
void vox_sweep(Vox *x, int i, uint8_t nr10) { x->v[i].sweep = nr10; }
void vox_flags(Vox *x, int i, uint8_t f) { x->v[i].flags = f; }
void vox_pan(Vox *x, int i, uint8_t pan) { x->v[i].pan = pan & 3; }
void vox_duck(Vox *x, int i, uint8_t steps) { x->v[i].duck = steps; }
void vox_off(Vox *x, int i) { x->v[i].on = 0; }

void vox_filter(Vox *x, uint8_t cutoff, uint8_t resonance, uint8_t mode)
{
    /* Cutoff 0-255, exponential from 40 Hz to about 12 kHz, like a SID
       register sweep sounds; resonance 0-15. A Chamberlin state-variable
       filter: cheap, and it rings the way the SID's does. */
    float hz = 40.0f;
    int k;
    for (k = 0; k < cutoff; k++) hz *= 1.0226f;   /* 40 * 1.0226^255 ~ 12 kHz */
    {
        /* 2 sin(pi f / rate), by its series: good to well under Nyquist/4 */
        float w = 3.14159265f * hz / (float)x->rate, w3 = w * w * w;
        float f = 2.0f * (w - w3 / 6.0f + w3 * w * w / 120.0f);
        x->f = f > 1.2f ? 1.2f : f;
    }
    x->q = 1.0f - (float)(resonance & 15) / 16.5f;   /* damping: 1 dull .. ~0.1 ringing */
    x->cutoff = cutoff;
    x->resonance = resonance & 15;
    x->mode = mode & 7;
}

void vox_cutoff_slide(Vox *x, int8_t per_tick) { x->cutoff_slide = per_tick; }

void vox_frame(Vox *x)
{
    if (x->cutoff_slide) {
        int c = x->cutoff + x->cutoff_slide;
        if (c < 0) { c = 0; x->cutoff_slide = 0; }
        if (c > 255) { c = 255; x->cutoff_slide = 0; }
        vox_filter(x, (uint8_t)c, x->resonance, x->mode);
    }
}

int vox_active(const Vox *x)
{
    int i;
    for (i = 0; i < VOX_VOICES; i++) if (x->v[i].on) return 1;
    return 0;
}

int vox_level(const Vox *x, int i)
{
    const VoxVoice *v = &x->v[i];
    int l = v->on ? v->vol - v->duck : 0;
    return l < 0 ? 0 : l;
}

/* PolyBLEP: the step's aliasing, subtracted around each discontinuity. */
static float blep(float t, float dt)
{
    if (t < dt) { t /= dt; return t + t - t * t - 1.0f; }
    if (t > 1.0f - dt) { t = (t - 1.0f) / dt; return t * t + t + t + 1.0f; }
    return 0.0f;
}

/* 64 Hz envelopes and 128 Hz sweeps, per voice, counted in samples and run
   once per block: a step lands up to a block (0.7 ms) late, which no ear
   can place, and the per-sample loop stays free of it. */
static void housekeeping(Vox *x, int m)
{
    int i;
    for (i = 0; i < VOX_VOICES; i++) {
        VoxVoice *v = &x->v[i];
        if (!v->on) continue;
        if (v->env_pace && (v->env_count -= m) <= 0) {
            v->env_count += (int32_t)(x->rate * v->env_pace / 64);
            if (v->env_dir && v->vol < 15) v->vol++;
            else if (!v->env_dir && v->vol > 0) v->vol--;
        }
        if (v->osc == OSC_PULSE && (v->sweep & 0x77) && (v->sweep_count -= m) <= 0) {
            v->sweep_count += (int32_t)(x->rate / 128);
            if ((v->sweep >> 4) & 7) {
                if (v->sweep_timer) v->sweep_timer--;
                if (!v->sweep_timer) {
                    int p = v->period, d = p >> (v->sweep & 7);
                    v->sweep_timer = (v->sweep >> 4) & 7;
                    p = (v->sweep & 8) ? p - d : p + d;
                    if (p > 2047) v->on = 0;
                    else if (v->sweep & 7) set_pitch(x, v, (uint16_t)p);
                }
            }
        }
    }
}

/* The renderer works a block at a time and a voice at a time: each voice's
   state lives in registers for its whole block and the oscillator switch is
   taken once per block, not once per sample. Ring and sync need, sample by
   sample, what the previous voice did, so each voice leaves its square and
   its wraps in two small arrays for the next. That is the whole reason the
   voices are rendered in order. */
#define BLOCK 32

uint32_t vox_render(Vox *x, int16_t *left, int16_t *right, int n)
{
    float bl[BLOCK], br[BLOCK], bf[BLOCK], scratch[BLOCK];
    float sq_a[BLOCK], sq_b[BLOCK];
    uint8_t wr_a[BLOCK], wr_b[BLOCK];
    uint64_t total = (uint64_t)n * 4194304u + x->frac;
    uint32_t cyc = (uint32_t)(total / x->rate);
    x->frac = (uint32_t)(total % x->rate);

    while (n > 0) {
        int m = n < BLOCK ? n : BLOCK, i, k, routed = 0, prev_on = 0;
        float *prev_sq = sq_a, *cur_sq = sq_b;
        uint8_t *prev_wr = wr_a, *cur_wr = wr_b;
        const float scale = x->gain * x->master * 32767.0f / 15.0f;
        for (k = 0; k < m; k++) bl[k] = br[k] = bf[k] = 0.0f;

        for (i = 0; i < VOX_VOICES; i++) {
            VoxVoice *v = &x->v[i];
            int ring = (v->flags & VOX_RING) && prev_on && v->osc != OSC_NOISE;
            int sync = (v->flags & VOX_SYNC) && prev_on;
            float ph = v->phase, dt = v->inc, amp, *dl, *dr;
            int vol;
            if (!v->on) { prev_on = 0; continue; }
            vol = v->vol - v->duck;
            amp = (float)(vol > 0 ? vol : 0) * scale;
            /* Most notes end by fading to 0 and are never switched off: skip
               a silent voice that will stay silent -- unless the next voice
               syncs or rings off it, since a silent master is a SID
               technique of its own. */
            if (amp == 0.0f && !(v->env_dir && v->env_pace) &&
                !(i + 1 < VOX_VOICES && x->v[i + 1].on && (x->v[i + 1].flags & (VOX_RING | VOX_SYNC)))) {
                prev_on = 0;
                continue;
            }
            if (v->flags & VOX_FILTER) { dl = bf; dr = scratch; routed = 1; }   /* the filter bus is mono */
            else { dl = (v->pan & 2) ? bl : scratch; dr = (v->pan & 1) ? br : scratch; }

            /* One tight loop per oscillator: the per-sample body carries no
               test the block has already answered. A voice panned to one
               side, or through the filter, writes its other side into a
               scratch buffer rather than branching on it. */
#define TONAL_LOOP(EXPR)                                                  \
            for (k = 0; k < m; k++) {                                     \
                float o;                                                  \
                if (sync && prev_wr[k]) ph = 0.0f;                        \
                EXPR;                                                     \
                if (ring) o *= prev_sq[k];                                \
                cur_sq[k] = ph < 0.5f ? 1.0f : -1.0f;                     \
                ph += dt;                                                 \
                cur_wr[k] = ph >= 1.0f;                                   \
                if (ph >= 1.0f) ph -= 1.0f;                               \
                o *= amp;                                                 \
                dl[k] += o;                                               \
                dr[k] += o;                                               \
            }
            switch (v->osc) {
            case OSC_PULSE: {
                const float w = v->width;
                TONAL_LOOP(
                    float t = ph - w;
                    o = (ph < w ? 1.0f : -1.0f) + blep(ph, dt);
                    if (t < 0.0f) t += 1.0f;
                    o -= blep(t, dt))
                v->phase = ph;
                break;
            }
            case OSC_SAW:
                TONAL_LOOP(o = 1.0f - 2.0f * ph + blep(ph, dt))
                v->phase = ph;
                break;
            case OSC_TRIANGLE:
                TONAL_LOOP(o = ph < 0.5f ? 4.0f * ph - 1.0f : 3.0f - 4.0f * ph)
                v->phase = ph;
                break;
            case OSC_WAVE: {
                /* the 32 nibbles, unpacked once a block */
                static const float LEVEL[16] = {-1.0f, -0.8667f, -0.7333f, -0.6f, -0.4667f, -0.3333f, -0.2f, -0.0667f,
                                                0.0667f, 0.2f, 0.3333f, 0.4667f, 0.6f, 0.7333f, 0.8667f, 1.0f};
                float tab[32];
                int j;
                if (v->wave) for (j = 0; j < 16; j++) { tab[2 * j] = LEVEL[v->wave[j] >> 4]; tab[2 * j + 1] = LEVEL[v->wave[j] & 15]; }
                else for (j = 0; j < 32; j++) tab[j] = 0.0f;
                TONAL_LOOP(o = tab[(int)(ph * 32.0f) & 31])
                v->phase = ph;
                break;
            }
#undef TONAL_LOOP
            case OSC_NOISE: {
                uint16_t lfsr = v->lfsr;
                const int short_mode = v->short_mode;
                for (k = 0; k < m; k++) {
                    float o = (lfsr & 1) ? -amp : amp;
                    cur_sq[k] = (lfsr & 1) ? -1.0f : 1.0f;
                    cur_wr[k] = 0;
                    ph += dt;
                    while (ph >= 1.0f) {
                        uint16_t b = (lfsr ^ (lfsr >> 1)) & 1;
                        ph -= 1.0f;
                        lfsr = (uint16_t)((lfsr >> 1) | (b << 14));
                        if (short_mode) lfsr = (uint16_t)((lfsr & ~0x40) | (b << 6));
                    }
                    dl[k] += o;
                    dr[k] += o;
                }
                v->lfsr = lfsr;
                v->phase = ph;
                break;
            }
            case OSC_SAMPLE: {
                float pos = v->smp_pos;
                const uint8_t *d = v->smp;
                const float end = (float)v->smp_len;
                for (k = 0; k < m; k++) {
                    float o = 0.0f;
                    if (d && pos < end) {
                        uint32_t st = (uint32_t)pos;
                        uint8_t b = d[st >> 1];
                        o = ((float)((st & 1) ? (b & 15) : (b >> 4)) * (2.0f / 15.0f) - 1.0f) * amp;
                        pos += dt;
                    }
                    cur_sq[k] = 1.0f;
                    cur_wr[k] = 0;
                    dl[k] += o;
                    dr[k] += o;
                }
                v->smp_pos = pos;
                if (pos >= end) v->on = 0;
                break;
            }
            }
            prev_on = 1;
            { float *t = prev_sq; prev_sq = cur_sq; cur_sq = t; }
            { uint8_t *t = prev_wr; prev_wr = cur_wr; cur_wr = t; }
        }

        /* The filter runs while anything goes through it, and on after, until
           its ringing has died away. */
        if (x->mode && (routed || x->band > 1.0f || x->band < -1.0f || x->low > 1.0f || x->low < -1.0f)) {
            float low = x->low, band = x->band;
            const float f = x->f, q = x->q;
            const int mode = x->mode;
            for (k = 0; k < m; k++) {
                float high, out = 0.0f;
                low += f * band;
                high = bf[k] - low - q * band;
                band += f * high;
                if (band > 262144.0f) band = 262144.0f; else if (band < -262144.0f) band = -262144.0f;
                if (mode & VOX_LP) out += low;
                if (mode & VOX_BP) out += band;
                if (mode & VOX_HP) out += high;
                bl[k] += out;
                br[k] += out;
            }
            x->low = low; x->band = band;
        }

        for (k = 0; k < m; k++) {
            float sl = bl[k], sr = br[k];
            if (sl > 32767.0f) sl = 32767.0f; else if (sl < -32768.0f) sl = -32768.0f;
            if (sr > 32767.0f) sr = 32767.0f; else if (sr < -32768.0f) sr = -32768.0f;
            if (left) left[k] = (int16_t)sl;
            if (right) right[k] = (int16_t)sr;
        }
        if (left) left += m;
        if (right) right += m;
        n -= m;
        housekeeping(x, m);
    }
    return cyc;
}
