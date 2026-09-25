/* gbapu: the DMG's four sound channels. See gbapu.h.

   Reference: Pan Docs, "Audio" and "Audio Registers"; the behaviours below
   are the ones a sequencer can hear. Deliberately left out: the wave
   channel's trigger delay and DMG wave-RAM corruption (the driver stops CH3
   before touching wave RAM, so it never meets either), and the obscure
   "zombie mode" envelope writes (the driver retriggers instead). */
#include "gbapu.h"
#include <string.h>

enum { NR10 = 0x00, NR11, NR12, NR13, NR14, NR21 = 0x06, NR22, NR23, NR24,
       NR30 = 0x0A, NR31, NR32, NR33, NR34, NR41 = 0x10, NR42, NR43, NR44,
       NR50 = 0x14, NR51, NR52, WAVE = 0x20 };

/* 12.5%, 25%, 50%, 75%: one bit per duty step. */
static const uint8_t DUTY[4] = { 0x01, 0x81, 0x87, 0x7E };

/* Loudness of one channel at full volume: 4 channels x 15 x 8 (NR50) sit
   under full scale, with room for the DC blocker's overshoot on a step. */
#define GAIN 52

static int32_t period(const GbApu *a, int c)
{
    const GbApuChan *ch = &a->ch[c];
    if (c < 2) return (2048 - ch->freq) * 4;
    if (c == 2) return (2048 - ch->freq) * 2;
    {
        uint8_t nr43 = a->reg[NR43], s = nr43 >> 4, r = nr43 & 7;
        if (s >= 14) return 0x7FFFFFFF;          /* the LFSR is not clocked */
        return (r ? r * 16 : 8) << s;
    }
}

static void refresh(GbApu *a, int c)
{
    GbApuChan *ch = &a->ch[c];
    if (!ch->on) { ch->level = 0; return; }
    if (c < 2) {
        uint8_t duty = a->reg[c ? NR21 : NR11] >> 6;
        ch->level = (DUTY[duty] >> ch->pos) & 1 ? ch->vol : 0;
    } else if (c == 2) {
        static const uint8_t SHIFT[4] = { 4, 0, 1, 2 };
        ch->level = ch->buffer >> SHIFT[(a->reg[NR32] >> 5) & 3];
    } else {
        ch->level = (ch->lfsr & 1) ? 0 : ch->vol;
    }
}

static void step(GbApu *a, int c)
{
    GbApuChan *ch = &a->ch[c];
    if (c < 2) {
        ch->pos = (ch->pos + 1) & 7;
    } else if (c == 2) {
        uint8_t b;
        ch->pos = (ch->pos + 1) & 31;
        b = a->reg[WAVE + (ch->pos >> 1)];
        ch->buffer = (ch->pos & 1) ? (b & 15) : (b >> 4);
    } else {
        uint16_t x = (ch->lfsr ^ (ch->lfsr >> 1)) & 1;
        ch->lfsr = (uint16_t)((ch->lfsr >> 1) | (x << 14));
        if (a->reg[NR43] & 8) ch->lfsr = (uint16_t)((ch->lfsr & ~0x40) | (x << 6));
    }
    refresh(a, c);
}

static uint16_t sweep_calc(GbApu *a)
{
    GbApuChan *ch = &a->ch[0];
    uint8_t nr10 = a->reg[NR10];
    uint16_t d = ch->shadow >> (nr10 & 7);
    uint16_t f = (nr10 & 8) ? ch->shadow - d : ch->shadow + d;
    if (f > 2047) { ch->on = 0; refresh(a, 0); }
    return f;
}

static void trigger(GbApu *a, int c)
{
    GbApuChan *ch = &a->ch[c];
    static const uint8_t ENV[4] = { NR12, NR22, 0, NR42 };
    ch->on = ch->dac;
    if (!ch->length) ch->length = c == 2 ? 256 : 64;
    ch->timer = period(a, c);
    if (c == 2) {
        ch->pos = 0;             /* the buffer keeps its nibble: it plays first */
    } else {
        uint8_t e = a->reg[ENV[c]];
        ch->vol = e >> 4; ch->env_dir = (e >> 3) & 1; ch->env_pace = e & 7;
        ch->env_timer = ch->env_pace ? ch->env_pace : 8;
        if (c == 3) ch->lfsr = 0x7FFF;
    }
    if (c == 0) {
        uint8_t nr10 = a->reg[NR10], pace = (nr10 >> 4) & 7;
        ch->shadow = ch->freq;
        ch->sweep_timer = pace ? pace : 8;
        ch->sweep_on = pace || (nr10 & 7);
        if (nr10 & 7) sweep_calc(a);
    }
    refresh(a, c);
}

static void frame_sequencer(GbApu *a)
{
    int c;
    uint8_t s = a->fs_step;
    a->fs_step = (s + 1) & 7;
    if (!(s & 1)) {
        for (c = 0; c < 4; c++) {
            GbApuChan *ch = &a->ch[c];
            if (ch->length_on && ch->length && !--ch->length) { ch->on = 0; refresh(a, c); }
        }
    }
    if (s == 2 || s == 6) {
        GbApuChan *ch = &a->ch[0];
        uint8_t nr10 = a->reg[NR10], pace = (nr10 >> 4) & 7;
        if (!--ch->sweep_timer) {
            ch->sweep_timer = pace ? pace : 8;
            if (ch->on && ch->sweep_on && pace) {
                uint16_t f = sweep_calc(a);
                if (f <= 2047 && (nr10 & 7)) {
                    ch->shadow = ch->freq = f;
                    a->reg[NR13] = f & 0xFF;
                    a->reg[NR14] = (uint8_t)((a->reg[NR14] & 0xF8) | (f >> 8));
                    sweep_calc(a);
                }
            }
        }
    }
    if (s == 7) {
        for (c = 0; c < 4; c++) {
            GbApuChan *ch = &a->ch[c];
            if (c == 2 || !ch->env_pace) continue;
            if (!--ch->env_timer) {
                ch->env_timer = ch->env_pace;
                if (ch->env_dir && ch->vol < 15) ch->vol++;
                else if (!ch->env_dir && ch->vol > 0) ch->vol--;
                refresh(a, c);
            }
        }
    }
}

void gbapu_init(GbApu *a, uint32_t sample_rate)
{
    memset(a, 0, sizeof *a);
    a->rate = sample_rate;
    a->fs_timer = 8192;
    a->ch[3].lfsr = 0x7FFF;
    /* The DMG's output capacitor: 0.999958 per CPU cycle (Pan Docs), so
       0.999958^(cycles per sample) -- by multiplication: no libm on the
       device for one number. */
    {
        uint32_t i, q = GBAPU_CLOCK / sample_rate;
        double k = 1.0;
        for (i = 0; i < q; i++) k *= 0.999958;
        k *= 1.0 - 0.000042 * (double)(GBAPU_CLOCK % sample_rate) / sample_rate;
        a->hp_k = (int32_t)(65536.0 * k);
    }
    a->reg[NR52] = 0x80;
}

uint8_t gbapu_read(const GbApu *a, uint16_t addr)
{
    if (addr < 0xFF10 || addr >= 0xFF40) return 0xFF;
    if (addr == 0xFF26) {
        uint8_t v = a->reg[NR52] & 0x80;
        int c;
        for (c = 0; c < 4; c++) if (a->ch[c].on) v |= 1 << c;
        return v;
    }
    return a->reg[addr - 0xFF10];
}

void gbapu_write(GbApu *a, uint16_t addr, uint8_t v)
{
    uint8_t r;
    if (addr < 0xFF10 || addr >= 0xFF40) return;
    r = (uint8_t)(addr - 0xFF10);
    if (a->hook) a->hook(a->hook_user, addr, v);
    if (r >= WAVE) { a->reg[r] = v; return; }
    if (!(a->reg[NR52] & 0x80) && r != NR52) return;     /* powered off */
    a->reg[r] = v;
    switch (r) {
    case NR11: case NR21: {
        int c = r == NR11 ? 0 : 1;
        a->ch[c].length = 64 - (v & 63);
        refresh(a, c);
        break;
    }
    case NR12: case NR22: case NR42: {
        int c = r == NR12 ? 0 : r == NR22 ? 1 : 3;
        a->ch[c].dac = (v & 0xF8) != 0;
        if (!a->ch[c].dac) { a->ch[c].on = 0; refresh(a, c); }
        break;
    }
    case NR13: case NR23: case NR33: {
        int c = r == NR13 ? 0 : r == NR23 ? 1 : 2;
        a->ch[c].freq = (uint16_t)((a->ch[c].freq & 0x700) | v);
        break;
    }
    case NR14: case NR24: case NR34: case NR44: {
        int c = r == NR14 ? 0 : r == NR24 ? 1 : r == NR34 ? 2 : 3;
        if (c < 3) a->ch[c].freq = (uint16_t)((a->ch[c].freq & 0xFF) | ((v & 7) << 8));
        a->ch[c].length_on = (v >> 6) & 1;
        if (v & 0x80) trigger(a, c);
        break;
    }
    case NR30:
        a->ch[2].dac = v >> 7;
        if (!a->ch[2].dac) { a->ch[2].on = 0; refresh(a, 2); }
        break;
    case NR31: a->ch[2].length = 256 - v; break;
    case NR32: refresh(a, 2); break;
    case NR41: a->ch[3].length = 64 - (v & 63); break;
    case NR52:
        if (!(v & 0x80)) {
            int c;
            memset(a->reg, 0, WAVE);
            for (c = 0; c < 4; c++) { a->ch[c].on = 0; a->ch[c].dac = 0; refresh(a, c); }
        }
        a->reg[NR52] = v & 0x80;
        break;
    default: break;
    }
}

int gbapu_active(const GbApu *a)
{
    int c;
    for (c = 0; c < 4; c++) if (a->ch[c].on) return 1;
    return 0;
}

int gbapu_samples_for(const GbApu *a, uint32_t cycles)
{
    uint64_t n = ((uint64_t)cycles * a->rate + GBAPU_CLOCK - 1) / GBAPU_CLOCK;
    return n ? (int)n : 1;
}

/* The integral of one channel's level over the next `cyc` cycles. */
static int32_t integrate(GbApu *a, int c, int32_t cyc)
{
    GbApuChan *ch = &a->ch[c];
    int32_t acc = 0, t = cyc;
    if (!ch->on) return 0;
    /* A pulse or noise note that has faded to 0 and is not coming back
       outputs 0 whatever its timer does: stop stepping it. (Most notes end
       this way rather than being switched off.) */
    if (c != 2 && !ch->vol && !(ch->env_dir && ch->env_pace)) return 0;
    while (ch->timer <= t) {
        acc += ch->level * ch->timer;
        t -= ch->timer;
        step(a, c);
        ch->timer = period(a, c);
    }
    acc += ch->level * t;
    ch->timer -= t;
    return acc;
}

uint32_t gbapu_render(GbApu *a, int16_t *left, int16_t *right, int n)
{
    uint32_t total = 0;
    uint32_t q = GBAPU_CLOCK / a->rate, r = GBAPU_CLOCK % a->rate;
    const int32_t inv_q = (int32_t)(65536u / q), inv_q1 = (int32_t)(65536u / (q + 1));
    int i, c;
    for (i = 0; i < n; i++) {
        int32_t cyc = (int32_t)q, l = 0, rr = 0, xl, xr;
        uint8_t nr51 = a->reg[NR51], nr50 = a->reg[NR50];
        a->frac += r;
        if (a->frac >= a->rate) { a->frac -= a->rate; cyc++; }
        total += (uint32_t)cyc;
        for (c = 0; c < 4; c++) {
            int32_t acc = integrate(a, c, cyc), v;
            if (!a->ch[c].dac) continue;
            v = 15 * cyc - 2 * acc;          /* the DAC: 0 -> +1, 15 -> -1 */
            if (nr51 & (0x10 << c)) l += v;
            if (nr51 & (1 << c)) rr += v;
        }
        /* cyc is q or q+1: its reciprocal (Q16) is precomputed, so no
           division per sample */
        {
            int32_t inv = cyc == (int32_t)q ? inv_q : inv_q1;
            xl = (int32_t)(((int64_t)l * ((((nr50 >> 4) & 7) + 1) * GAIN) * inv) >> 16);
            xr = (int32_t)(((int64_t)rr * (((nr50 & 7) + 1) * GAIN) * inv) >> 16);
        }
        /* DC blocker: the DAC's idle level is not silence. */
        a->hp_l = xl - a->hp_xl + (int32_t)(((int64_t)a->hp_k * a->hp_l) >> 16);
        a->hp_r = xr - a->hp_xr + (int32_t)(((int64_t)a->hp_k * a->hp_r) >> 16);
        a->hp_xl = xl; a->hp_xr = xr;
        if (left) left[i] = (int16_t)(a->hp_l > 32767 ? 32767 : a->hp_l < -32768 ? -32768 : a->hp_l);
        if (right) right[i] = (int16_t)(a->hp_r > 32767 ? 32767 : a->hp_r < -32768 ? -32768 : a->hp_r);
        a->fs_timer -= cyc;
        while (a->fs_timer <= 0) { a->fs_timer += 8192; frame_sequencer(a); }
    }
    return total;
}
