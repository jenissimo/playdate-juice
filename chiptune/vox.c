/* vox: see vox.h. */
#include "vox.h"
#include <string.h>


void vox_init(Vox *x, uint32_t rate)
{
    int i;
    memset(x, 0, sizeof *x);
    x->rate = rate;
    x->master = 1.0f;
    for (i = 0; i < VOX_VOICES; i++) {
        VoxVoice *v = &x->v[i];
        v->pan = 3; v->width = 0.5f; v->lfsr = 0x7FFF;
        v->level = 1.0f; v->bal_l = v->bal_r = 1.0f;
    }
    /* an interrupted sample's last level fades with a time constant of about
       0.75 ms: long enough not to click, too short to hear as a tail */
    x->dc_k = 1.0f - 1323.0f / (float)rate;
    if (x->dc_k < 0.5f) x->dc_k = 0.5f;
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
    } else if (v->osc == OSC_PCM) {
        /* C5 (period 1798) plays the sample at its own rate: the ratio is
           250 / (2048 - p), which keeps it in tune with the other voices */
        int32_t st = (int32_t)(v->pcm_k / (float)(2048 - (pitch & 2047)) + 0.5f);
        if (st < 1) st = 1;
        v->step = v->rev ? -st : st;
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

/* A PCM note starts at its offset -- or, backwards, just before it (from
   the end when there is none). */
static void pcm_restart(VoxVoice *v)
{
    uint32_t f = v->from;
    if (v->rev) {
        if (!f || f > v->pcm_len) f = v->pcm_len;
        v->pos = (f << 12) - 4096u;   /* 0 frames: the top bit, which ends it */
    } else v->pos = f << 12;
    v->ramp = 0;                      /* a new note's attack is not smoothed away */
}

/* A sampled note that stops mid-wave would click: its last output is handed
   to a short decay that the renderer adds in. */
static void pcm_release(Vox *x, VoxVoice *v)
{
    if (v->on && v->osc == OSC_PCM) {
        v->dc_l += v->out_l;
        v->dc_r += v->out_r;
        x->declicks = 1;
    }
    v->out_l = v->out_r = 0.0f;
}

void vox_trigger(Vox *x, int i, uint8_t osc, uint16_t pitch, uint8_t env)
{
    VoxVoice *v = &x->v[i];
    pcm_release(x, v);
    v->osc = osc < OSC_COUNT ? osc : OSC_PULSE;
    v->on = (env & 0xF8) != 0;       /* the DMG's DAC rule: volume 0, decreasing, is off */
    set_env(x, v, env);
    set_pitch(x, v, pitch);
    /* A Game Boy retrigger restarts the envelope, not the pulse's duty
       position; resetting the phase too clicks on every retrigger -- 30
       times a second in a 9x2 tremolo. The wave's position does restart. */
    if (v->osc == OSC_WAVE) v->phase = 0.0f;
    if (v->osc == OSC_PCM) pcm_restart(v);
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
    pcm_release(x, v);
    v->osc = osc < OSC_COUNT ? osc : OSC_PULSE;
    if (v->osc == OSC_SAMPLE) v->smp_pos = 0.0f;
    if (v->osc == OSC_PCM) pcm_restart(v);
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
/* The driver restates every voice's ducking every frame: store it only when
   it changes. */
void vox_duck(Vox *x, int i, uint8_t steps) { if (x->v[i].duck != steps) x->v[i].duck = steps; }
void vox_off(Vox *x, int i) { pcm_release(x, &x->v[i]); x->v[i].on = 0; }

void vox_pcm(Vox *x, int i, const int8_t *data, uint32_t frames, uint32_t loop_start, uint32_t loop_len, uint32_t rate)
{
    VoxVoice *v = &x->v[i];
    if (frames > VOX_PCM_MAX) frames = VOX_PCM_MAX;
    if (!loop_len || loop_start >= frames || loop_len > frames - loop_start) loop_start = loop_len = 0;
    v->pcm = data;
    v->pcm_len = data ? frames : 0;
    v->loop_start = loop_start;
    v->loop_len = loop_len;
    /* 4096 (the fraction) x 250 (C5's 2048 - period) / the output rate */
    v->pcm_k = (float)rate * (1024000.0f / (float)x->rate);
}

void vox_pcm_from(Vox *x, int i, uint32_t frame, uint8_t reverse)
{
    x->v[i].from = frame;
    x->v[i].rev = reverse ? 1 : 0;
}

void vox_volume(Vox *x, int i, uint8_t level, uint8_t amp)
{
    if (level > 64) level = 64;
    x->v[i].level = (float)(level * amp) * (1.0f / 1024.0f);
}

/* A balance law, not constant power: the centre is 1 on both sides, as a
   voice routed to both is on the other oscillators. */
void vox_balance(Vox *x, int i, uint8_t pan)
{
    VoxVoice *v = &x->v[i];
    v->bal_l = pan <= 128 ? 1.0f : (float)(255 - pan) * (1.0f / 127.0f);
    v->bal_r = pan >= 128 ? 1.0f : (float)pan * (1.0f / 128.0f);
}

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
    if (l < 0) l = 0;
    return v->level < 1.0f ? (int)((float)l * v->level + 0.5f) : l;
}

/* PolyBLEP: the step's aliasing, subtracted around each discontinuity. */
static float blep(float t, float dt)
{
    if (t < dt) { t /= dt; return t + t - t * t - 1.0f; }
    if (t > 1.0f - dt) { t = (t - 1.0f) / dt; return t * t + t + t + 1.0f; }
    return 0.0f;
}

/* The part of a voice the renderer moves -- VoxVoice's first fields, in
   their order -- copied to locals for a call. On the Playdate the audio
   callback's stack is fast internal RAM and the voices are in the heap, in
   external RAM behind a write-through cache, where each scattered store is
   a slow trip: a call writes back only what changed, once, in one run. */
typedef struct {
    uint32_t pos;
    float out_l, out_r, phase;
    int32_t env_count;
    float gl, gr, dc_l, dc_r, smp_pos;
    int32_t sweep_count, sweep_timer;
    uint16_t lfsr;
    uint8_t vol, on, ramp;
} Moving;

static void moving_load(Moving *h, const VoxVoice *v)
{
    h->pos = v->pos; h->out_l = v->out_l; h->out_r = v->out_r; h->phase = v->phase;
    h->env_count = v->env_count; h->gl = v->gl; h->gr = v->gr; h->dc_l = v->dc_l; h->dc_r = v->dc_r;
    h->smp_pos = v->smp_pos; h->sweep_count = v->sweep_count; h->sweep_timer = v->sweep_timer;
    h->lfsr = v->lfsr; h->vol = v->vol; h->on = v->on; h->ramp = v->ramp;
}

#define PUT(f) if (v->f != h->f) v->f = h->f
static void moving_store(VoxVoice *v, const Moving *h)
{
    PUT(pos); PUT(out_l); PUT(out_r); PUT(phase); PUT(env_count); PUT(gl); PUT(gr); PUT(dc_l); PUT(dc_r);
    PUT(smp_pos); PUT(sweep_count); PUT(sweep_timer); PUT(lfsr); PUT(vol); PUT(on); PUT(ramp);
}
#undef PUT

/* 64 Hz envelopes and 128 Hz sweeps, per voice, counted in samples and run
   once per block: a step lands up to a block (1.5 ms at 44.1 kHz) late,
   which no ear can place, and the per-sample loop stays free of it. */
static void housekeeping(Vox *x, Moving *mv, unsigned live, int m)
{
    int i;
    for (i = 0; i < VOX_VOICES; i++) {
        VoxVoice *v = &x->v[i];
        Moving *h = &mv[i];
        if (!((live >> i) & 1) || !h->on) continue;
        if (v->env_pace && (h->env_count -= m) <= 0) {
            h->env_count += (int32_t)(x->rate * v->env_pace / 64);
            if (v->env_dir && h->vol < 15) h->vol++;
            else if (!v->env_dir && h->vol > 0) h->vol--;
        }
        if (v->osc == OSC_PULSE && (v->sweep & 0x77) && (h->sweep_count -= m) <= 0) {
            h->sweep_count += (int32_t)(x->rate / 128);
            if ((v->sweep >> 4) & 7) {
                if (h->sweep_timer) h->sweep_timer--;
                if (!h->sweep_timer) {
                    int p = v->period, d = p >> (v->sweep & 7);
                    h->sweep_timer = (v->sweep >> 4) & 7;
                    p = (v->sweep & 8) ? p - d : p + d;
                    if (p > 2047) h->on = 0;
                    else if (v->sweep & 7) set_pitch(x, v, (uint16_t)p);
                }
            }
        }
    }
}

/* An interrupted PCM note's last output, decaying into wherever the voice
   is routed. Returns 1 if that is the filter. */
static int declick(const Vox *x, const VoxVoice *v, Moving *h, float *bl, float *br, float *bf, float *scratch,
                   int m)
{
    float cl = h->dc_l, cr = h->dc_r, *dl, *dr;
    const float k = x->dc_k;
    const int filt = (v->flags & VOX_FILTER) != 0;
    int j;
    if (filt) { dl = bf; dr = scratch; }
    else { dl = (v->pan & 2) ? bl : scratch; dr = (v->pan & 1) ? br : scratch; }
    for (j = 0; j < m; j++) { dl[j] += cl; dr[j] += cr; cl *= k; cr *= k; }
    if (cl < 1.0f && cl > -1.0f && cr < 1.0f && cr > -1.0f) cl = cr = 0.0f;
    h->dc_l = cl;
    h->dc_r = cr;
    return filt;
}

/* The renderer works a block at a time and a voice at a time: each voice's
   state lives in registers for its whole block and the oscillator switch is
   taken once per block, not once per sample. Ring and sync need, sample by
   sample, what the previous voice did, so each voice leaves its square and
   its wraps in two small arrays for the next. That is the whole reason the
   voices are rendered in order. The block buffers are on the stack: about
   26 bytes a sample of VOX_BLOCK, 1.7 KB at 64 (and the moving parts of the
   eight voices, 0.5 KB). */
#define BLOCK VOX_BLOCK

uint32_t vox_render(Vox *x, int16_t *left, int16_t *right, int n)
{
    float bl[BLOCK], br[BLOCK], bf[BLOCK], scratch[BLOCK];
    float sq_a[BLOCK], sq_b[BLOCK];
    uint8_t wr_a[BLOCK], wr_b[BLOCK];
    Moving mv[VOX_VOICES];
    unsigned live = 0;              /* the voices copied in: sounding, or a declick still decaying */
    float low = x->low, band = x->band;
    uint8_t declicks = x->declicks;
    uint64_t total = (uint64_t)n * 4194304u + x->frac;
    uint32_t cyc = (uint32_t)(total / x->rate);
    int i;
    x->frac = (uint32_t)(total % x->rate);
    for (i = 0; i < VOX_VOICES; i++) {
        const VoxVoice *v = &x->v[i];
        if (v->on || v->dc_l != 0.0f || v->dc_r != 0.0f) {
            moving_load(&mv[i], v);
            live |= 1u << i;
        }
    }

    while (n > 0) {
        int m = n < BLOCK ? n : BLOCK, k, routed = 0, prev_on = 0, dcs = 0;
        float *prev_sq = sq_a, *cur_sq = sq_b;
        uint8_t *prev_wr = wr_a, *cur_wr = wr_b;
        const float scale = x->gain * x->master * 32767.0f / 15.0f;
        for (k = 0; k < m; k++) bl[k] = br[k] = bf[k] = 0.0f;

        for (i = 0; i < VOX_VOICES; i++) {
            const VoxVoice *v = &x->v[i];
            Moving *h = &mv[i];
            int ring, sync, vol;
            float ph, dt, amp, *dl, *dr;
            if (!((live >> i) & 1)) { prev_on = 0; continue; }
            ring = (v->flags & VOX_RING) && prev_on && v->osc != OSC_NOISE;
            sync = (v->flags & VOX_SYNC) && prev_on;
            ph = h->phase;
            dt = v->inc;
            if (declicks && (h->dc_l != 0.0f || h->dc_r != 0.0f)) {
                routed |= declick(x, v, h, bl, br, bf, scratch, m);
                dcs |= h->dc_l != 0.0f || h->dc_r != 0.0f;
            }
            if (!h->on) { prev_on = 0; continue; }
            vol = h->vol - v->duck;
            amp = (float)(vol > 0 ? vol : 0) * scale;
            /* Most notes end by fading to 0 and are never switched off: skip
               a silent voice that will stay silent -- unless the next voice
               syncs or rings off it, since a silent master is a SID
               technique of its own. */
            if (amp == 0.0f && !(v->env_dir && v->env_pace) &&
                !(i + 1 < VOX_VOICES && ((live >> (i + 1)) & 1) && mv[i + 1].on &&
                  (x->v[i + 1].flags & (VOX_RING | VOX_SYNC)))) {
                prev_on = 0;
                continue;
            }
            amp *= v->level;
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
                h->phase = ph;
                break;
            }
            case OSC_SAW:
                TONAL_LOOP(o = 1.0f - 2.0f * ph + blep(ph, dt))
                h->phase = ph;
                break;
            case OSC_TRIANGLE:
                TONAL_LOOP(o = ph < 0.5f ? 4.0f * ph - 1.0f : 3.0f - 4.0f * ph)
                h->phase = ph;
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
                h->phase = ph;
                break;
            }
#undef TONAL_LOOP
            case OSC_NOISE: {
                uint16_t lfsr = h->lfsr;
                const int short_mode = v->short_mode;
                /* The LFSR's level averaged over the sample, as gbapu does: a
                   bright noise steps the LFSR many times a sample, and taking
                   only the value at the sample instant aliases it all into
                   white hiss up to 22 kHz. */
                const float inv = dt > 0.0f ? 1.0f / dt : 0.0f;
                for (k = 0; k < m; k++) {
                    float o, acc = 0.0f, rem = dt;
                    cur_sq[k] = (lfsr & 1) ? -1.0f : 1.0f;
                    cur_wr[k] = 0;
                    while (ph + rem >= 1.0f) {
                        uint16_t b = (lfsr ^ (lfsr >> 1)) & 1;
                        float seg = 1.0f - ph;
                        acc += (lfsr & 1) ? -seg : seg;
                        rem -= seg;
                        ph = 0.0f;
                        lfsr = (uint16_t)((lfsr >> 1) | (b << 14));
                        if (short_mode) lfsr = (uint16_t)((lfsr & ~0x40) | (b << 6));
                    }
                    acc += (lfsr & 1) ? -rem : rem;
                    ph += rem;
                    o = (dt > 0.0f ? acc * inv : ((lfsr & 1) ? -1.0f : 1.0f)) * amp;
                    dl[k] += o;
                    dr[k] += o;
                }
                h->lfsr = lfsr;
                h->phase = ph;
                break;
            }
            case OSC_SAMPLE: {
                float pos = h->smp_pos;
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
                h->smp_pos = pos;
                if (pos >= end) h->on = 0;
                break;
            }
            case OSC_PCM: {
                /* Resampled with linear interpolation in integers: the 12-bit
                   fraction times the step to the next frame, one conversion
                   to float. The block is cut at the sample's end or loop end,
                   so the inner loop carries no boundary test and the one
                   division is per segment, not per sample. */
                const int8_t *d = v->pcm;
                uint32_t pos = h->pos;
                const int32_t step = v->step;
                const uint32_t lfp = v->loop_len << 12;
                const uint32_t end = (v->loop_len ? v->loop_start + v->loop_len : v->pcm_len) << 12;
                /* envelope x volume x the 8-bit and 12-bit scales, and the pan,
                   ramped from where the last block ended */
                const float g = amp * (1.0f / 524288.0f);
                const int filt = (v->flags & VOX_FILTER) != 0;
                const float tl = filt ? g : g * v->bal_l, tr = filt ? g : g * v->bal_r;
                const float inv = m == BLOCK ? 1.0f / (float)BLOCK : 1.0f / (float)m;
                float gl = h->ramp ? h->gl : tl, gr = h->ramp ? h->gr : tr, o = 0.0f;
                const float sl = (tl - gl) * inv, sr = (tr - gr) * inv;
                k = 0;
                while (k < m) {
                    uint32_t run, j;
                    if (!d) { h->on = 0; break; }
                    if (step > 0) {
                        if (pos >= end) {
                            if (!lfp) { h->on = 0; break; }
                            pos = end - lfp + (pos - (end - lfp)) % lfp;
                        }
                        run = (end - pos + (uint32_t)step - 1) / (uint32_t)step;
                    } else {
                        if (pos & 0x80000000u) { h->on = 0; break; }   /* ran back past frame 0 */
                        run = pos / (uint32_t)-step + 1;
                    }
                    if (run > (uint32_t)(m - k)) run = (uint32_t)(m - k);
                    for (j = 0; j < run; j++, k++) {
                        const int8_t *sp = d + (pos >> 12);
                        const int32_t a = sp[0];
                        o = (float)(a * 4096 + (sp[1] - a) * (int32_t)(pos & 4095u));
                        dl[k] += o * gl;
                        dr[k] += o * gr;
                        gl += sl;
                        gr += sr;
                        pos += (uint32_t)step;
                    }
                }
                h->pos = pos;
                h->gl = tl;
                h->gr = tr;
                h->ramp = 1;
                /* the last output, for a declick if the note is cut next --
                   or now, when the sample ran out */
                h->out_l = o * gl;
                h->out_r = o * gr;
                if (!h->on) {
                    h->dc_l += h->out_l; h->dc_r += h->out_r;
                    h->out_l = h->out_r = 0.0f;
                    dcs = 1;
                }
                /* a ring or sync voice after this one hears a steady square */
                if (i + 1 < VOX_VOICES && (x->v[i + 1].flags & (VOX_RING | VOX_SYNC)))
                    for (k = 0; k < m; k++) { cur_sq[k] = 1.0f; cur_wr[k] = 0; }
                break;
            }
            }
            prev_on = 1;
            { float *t = prev_sq; prev_sq = cur_sq; cur_sq = t; }
            { uint8_t *t = prev_wr; prev_wr = cur_wr; cur_wr = t; }
        }

        /* The filter runs while anything goes through it, and on after, until
           its ringing has died away. */
        if (x->mode && (routed || band > 1.0f || band < -1.0f || low > 1.0f || low < -1.0f)) {
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
        }

        for (k = 0; k < m; k++) {
            float sl = bl[k], sr = br[k];
            /* A soft knee: above 3/4 of full scale the excess is halved, so
               a rare pile-up of voices bends instead of clipping (hard
               clipping now takes 1.25x full scale). Rarely taken. */
            if (sl > 24576.0f) sl = 24576.0f + (sl - 24576.0f) * 0.5f;
            else if (sl < -24576.0f) sl = -24576.0f + (sl + 24576.0f) * 0.5f;
            if (sr > 24576.0f) sr = 24576.0f + (sr - 24576.0f) * 0.5f;
            else if (sr < -24576.0f) sr = -24576.0f + (sr + 24576.0f) * 0.5f;
            if (sl > 32767.0f) sl = 32767.0f; else if (sl < -32768.0f) sl = -32768.0f;
            if (sr > 32767.0f) sr = 32767.0f; else if (sr < -32768.0f) sr = -32768.0f;
            if (left) left[k] = (int16_t)sl;
            if (right) right[k] = (int16_t)sr;
        }
        if (left) left += m;
        if (right) right += m;
        n -= m;
        declicks = (uint8_t)dcs;
        housekeeping(x, mv, live, m);
    }

    for (i = 0; i < VOX_VOICES; i++)
        if ((live >> i) & 1) moving_store(&x->v[i], &mv[i]);
    if (x->low != low) x->low = low;
    if (x->band != band) x->band = band;
    if (x->declicks != declicks) x->declicks = declicks;
    return cyc;
}
