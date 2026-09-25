/* GBM driver: see gbm.h. Format and command reference: chiptune/README.md.

   This is a port, not a rewrite. The per-frame half follows gameboy-lab's
   gbm_core.s routine by routine, the rest follows its gbm.c, and both keep
   the original's 8-bit arithmetic where it is observable: note numbers wrap
   at 256 and clamp by their top bit, periods are 16-bit and clamp to
   0-2047. test/chiptune holds the port to the original's APU writes. */
#include "gbm.h"
#include <stddef.h>

/* Channel flags: what the frame path has to do. */
#define F_ARP   0x01
#define F_BEND  0x02
#define F_VIB   0x04
#define F_TABLE 0x08
#define F_COUNT 0x10
#define F_HOLD  0x20   /* row parsed a frame early: hands off until its frame */
#define F_DIRTY 0x40   /* registers need writing though nothing moves */
#define F_ON    0x80
#define F_WORK  0x5F

/* Mode bits a row's commands hand to note_on: what the instrument must not
   overwrite, and which kind of note this is. */
#define M_DELAY 0x01
#define M_PORTA 0x02
#define M_VIB   0x04
#define M_CUT   0x08
#define M_ENV   0x10
#define M_DUTY  0x20

#define NO_OWNER 0xFF
#define NOTE_COUNT 108
#define NOISE_COUNT 46

#define NR10 0xFF10
#define NR11 0xFF11
#define NR12 0xFF12
#define NR13 0xFF13
#define NR14 0xFF14
#define NR21 0xFF16
#define NR22 0xFF17
#define NR23 0xFF18
#define NR24 0xFF19
#define NR30 0xFF1A
#define NR32 0xFF1C
#define NR33 0xFF1D
#define NR34 0xFF1E
#define NR42 0xFF21
#define NR43 0xFF22
#define NR44 0xFF23
#define NR50 0xFF24
#define NR51 0xFF25
#define NR52 0xFF26

/* gameboy-lab shared/gbm/ts/tables.ts: note periods from C1, the noise
   shapes sorted by pitch a third of an octave apart, and a 16x16 sine for
   vibrato (depth-major). */
static const uint16_t PERIODS[NOTE_COUNT] = {0,0,0,0,0,0,0,0,0,0,0,0,44,157,263,363,457,547,631,711,786,856,923,986,1046,1102,1155,1205,1253,1297,1339,1379,1417,1452,1486,1517,1547,1575,1602,1627,1650,1673,1694,1714,1732,1750,1767,1783,1798,1812,1825,1837,1849,1860,1871,1881,1890,1899,1907,1915,1923,1930,1936,1943,1949,1954,1959,1964,1969,1974,1978,1982,1985,1989,1992,1995,1998,2001,2004,2006,2009,2011,2013,2015,2017,2018,2020,2022,2023,2025,2026,2027,2028,2029,2030,2031,2032,2033,2034,2035,2036,2036,2037,2038,2038,2039,2039,2040};
static const uint8_t NOISE[NOISE_COUNT] = {0xd7,0xd5,0xd4,0xc6,0xc5,0xc4,0xb6,0xb5,0xb4,0xa6,0xa5,0xa4,0x96,0x95,0x94,0x86,0x85,0x84,0x76,0x75,0x74,0x66,0x65,0x64,0x56,0x55,0x54,0x46,0x45,0x44,0x36,0x35,0x34,0x26,0x25,0x24,0x16,0x15,0x14,0x6,0x5,0x4,0x3,0x2,0x1,0x0};
static const int8_t VIBRATO[256] = {0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,0,0,0,-1,-1,-1,-1,-1,0,0,1,1,2,2,2,1,1,0,-1,-1,-2,-2,-2,-1,-1,0,1,2,3,3,3,2,1,0,-1,-2,-3,-3,-3,-2,-1,0,2,3,4,4,4,3,2,0,-2,-3,-4,-4,-4,-3,-2,0,2,4,5,5,5,4,2,0,-2,-4,-5,-5,-5,-4,-2,0,2,4,6,6,6,4,2,0,-2,-4,-6,-6,-6,-4,-2,0,3,5,6,7,6,5,3,0,-3,-5,-6,-7,-6,-5,-3,0,3,6,7,8,7,6,3,0,-3,-6,-7,-8,-7,-6,-3,0,3,6,8,9,8,6,3,0,-3,-6,-8,-9,-8,-6,-3,0,4,7,9,10,9,7,4,0,-4,-7,-9,-10,-9,-7,-4,0,4,8,10,11,10,8,4,0,-4,-8,-10,-11,-10,-8,-4,0,5,8,11,12,11,8,5,0,-5,-8,-11,-12,-11,-8,-5,0,5,9,12,13,12,9,5,0,-5,-9,-12,-13,-12,-9,-5,0,5,10,13,14,13,10,5,0,-5,-10,-13,-14,-13,-10,-5,0,6,11,14,15,14,11,6,0,-6,-11,-14,-15,-14,-11,-6};
static const uint8_t NR32_LEVELS[4] = {0x00, 0x60, 0x40, 0x20};

/* Blob offsets are u16 little-endian from its start: read them bytewise, a
   blob loaded from a file need not be aligned. */
#define U16(p) ((uint16_t)((p)[0] | ((p)[1] << 8)))

static void W(Gbm *g, uint16_t reg, uint8_t v) { gbapu_write(g->apu, reg, v); }

static void command(Gbm *g, GbmChan *c, uint8_t cmd, uint8_t val, uint8_t *mode);
static void enter_order(Gbm *g, uint8_t order);
static void rows4(Gbm *g);

/* ─── registers ────────────────────────────────────────────────────────── */

static void silence_hw(Gbm *g, uint8_t hw)
{
    switch (hw) {
    case 0: W(g, NR12, 0); W(g, NR14, 0x80); break;
    case 1: W(g, NR22, 0); W(g, NR24, 0x80); break;
    case 2: W(g, NR30, 0); break;
    default: W(g, NR42, 0); W(g, NR44, 0x80); break;
    }
}

/* NR51 from each hardware channel's owner's pan. */
static void set_pan(Gbm *g)
{
    uint8_t v = 0, n;
    for (n = 0; n < 4; n++) {
        uint8_t o = g->owner[n];
        uint8_t pan = o == NO_OWNER ? g->ch[n].pan : o == 4 ? g->ch[4].pan : g->ch[5].pan;
        if (pan & 1) v |= 1 << n;           /* bit 0: right */
        if (pan & 2) v |= 1 << (n + 4);     /* bit 1: left */
    }
    if (v != g->nr51) { g->nr51 = v; W(g, NR51, v); }
}

static const GbmBank *bank_of(const Gbm *g, const GbmChan *c) { return &g->banks[c->bank ? 1 : 0]; }

/* The envelope, less the duck level on a music channel. */
static uint8_t duck_env(const Gbm *g, const GbmChan *c)
{
    int v;
    if (!g->duck_level || c->bank) return c->env;
    v = (c->env >> 4) - g->duck_level;
    if (v < 0) v = 0;
    return (uint8_t)((v << 4) | (c->env & 0x0F));
}

/* Level 0-3 -> NR32, one step down per 4 of duck on music. */
static uint8_t wave_level(const Gbm *g, const GbmChan *c, uint8_t env)
{
    int a = env & 3;
    if (g->duck_level && !c->bank) {
        a -= (g->duck_level >> 2) & 3;
        if (a < 0) a = 0;
    }
    return NR32_LEVELS[a];
}

static uint8_t duty_bits(const GbmChan *c) { return (uint8_t)((c->duty & 3) << 6); }

/* ─── drum samples ─────────────────────────────────────────────────────── */

/* The 256 Hz handler: each call plays the next 32 samples (16 bytes) through
   CH3 at 8192 Hz; after the last it stops CH3 and flags gbm_tick to give the
   channel back to the music. */
void gbm_pcm_isr(Gbm *g)
{
    int i;
    if (!g->pcm_left) {
        if (!g->pcm_active) return;
        W(g, NR30, 0);
        g->pcm_done = 1;
        g->timer_irq = 0;
        return;
    }
    g->pcm_left--;
    W(g, NR30, 0);
    for (i = 0; i < 16; i++) W(g, (uint16_t)(0xFF30 + i), g->pcm_ptr[i]);
    W(g, NR30, 0x80);
    W(g, NR32, 0x20);
    W(g, NR33, 0);
    W(g, NR34, 0x87);                     /* period 0x700: 32 samples in 1/256 s */
    g->pcm_ptr += 16;
}

/* Sample `n` of bank `b` takes CH3 from the music; its first block plays now,
   the timer feeds the rest. */
static void pcm_start(Gbm *g, uint8_t n, uint8_t b)
{
    const uint8_t *blob, *tab, *s;
    if (!g->pcm_timer_on || g->owner[2] != NO_OWNER) return;
    blob = g->banks[b].base;
    tab = blob + U16(blob + 22);
    s = blob + U16(tab + (uint8_t)(n << 1));
    g->pcm_left = s[0];
    g->pcm_ptr = s + 1;
    g->pcm_active = 1;
    g->ch[2].block = 1;
    g->pcm_done = 0;
    gbm_pcm_isr(g);                         /* the first block now, not 4 ms later */
    g->timer_restart = 1;
    g->timer_irq = 1;
}

/* The sample ran out: CH3 goes back to the music, which restarts its note. */
static void pcm_end(Gbm *g)
{
    GbmChan *c = &g->ch[2];
    g->pcm_active = 0;
    g->pcm_done = 0;
    g->wave_ptr = NULL;
    c->block = g->owner[2] != NO_OWNER || (g->muted & 4) ? 1 : 0;
    c->out = 0xFFFF;
    c->trig |= 1;
    if (c->flags & F_ON) c->flags |= F_DIRTY;
    else silence_hw(g, 2);
}

/* ─── register writers: `e` = trigger bits, `v` = period or NR43 ────────── */

static void w_pu(Gbm *g, GbmChan *c, uint8_t e, uint16_t v, int two)
{
    if (e & 1) {
        if (!two) W(g, NR10, c->sweep);
        W(g, two ? NR21 : NR11, duty_bits(c));
        W(g, two ? NR22 : NR12, duck_env(g, c));
        W(g, two ? NR23 : NR13, (uint8_t)v);
        W(g, two ? NR24 : NR14, (uint8_t)((v >> 8) | 0x80));
        return;
    }
    if (e & 2) W(g, two ? NR21 : NR11, duty_bits(c));
    W(g, two ? NR23 : NR13, (uint8_t)v);
    W(g, two ? NR24 : NR14, (uint8_t)(v >> 8));
}

/* CH3: stopping it before a restart sidesteps the DMG wave-RAM corruption,
   and the wave is copied only when it differs from what is loaded. */
static void w_wav(Gbm *g, GbmChan *c, uint8_t e, uint16_t v)
{
    if (e & 1) {
        const uint8_t *w = bank_of(g, c)->wave + (uint16_t)(c->duty << 4);
        W(g, NR30, 0);
        if (w != g->wave_ptr) {
            int i;
            g->wave_ptr = w;
            for (i = 0; i < 16; i++) W(g, (uint16_t)(0xFF30 + i), w[i]);
        }
        W(g, NR30, 0x80);
        W(g, NR32, wave_level(g, c, c->env));
        W(g, NR33, (uint8_t)v);
        W(g, NR34, (uint8_t)((v >> 8) | 0x80));
        return;
    }
    W(g, NR33, (uint8_t)v);
    W(g, NR34, (uint8_t)(v >> 8));
}

/* Noise: the sweep byte names a drum sample (index + 1). */
static void w_noi(Gbm *g, GbmChan *c, uint8_t e, uint16_t v)
{
    if (e & 1) {
        if (c->sweep) pcm_start(g, (uint8_t)(c->sweep - 1), c->bank);
        W(g, NR42, duck_env(g, c));
        W(g, NR43, (uint8_t)v);
        W(g, NR44, 0x80);
        return;
    }
    W(g, NR43, (uint8_t)v);
}

/* ─── notes ────────────────────────────────────────────────────────────── */

/* Flag a sounding channel for output this frame. */
static void mark(GbmChan *c) { if (c->flags & F_ON) c->flags |= F_DIRTY; }
/* Restart the note on the next output. */
static void restart(GbmChan *c) { c->trig |= 1; mark(c); }

static void note_on(Gbm *g, GbmChan *c, uint8_t note, uint8_t mode)
{
    const uint8_t *rec = c->insp;
    uint16_t tbl;
    c->trig = 1;
    c->flags = (uint8_t)((c->flags & F_ARP) | F_ON | F_DIRTY);
    c->note = note;
    c->t_tr = 0;
    c->arp_ph = 0;
    if (!(mode & M_DUTY)) c->duty = rec[0];
    c->bend = 0;
    c->t_pitch = 0;
    if (!(mode & M_VIB)) { c->vib = rec[1]; c->vib_wait = rec[2]; c->vib_pos = 0; }
    if (!(mode & M_ENV)) c->env = rec[3];
    c->sweep = rec[4];
    if (!(mode & M_CUT)) c->cut = rec[5];
    if (c->cut | c->retrig) c->flags |= F_COUNT;
    /* The retrigger count restarts, one up: it counts down in this frame too. */
    c->retrig_n = c->retrig ? (uint8_t)((c->retrig & 0x0F) + 1) : 0;
    tbl = U16(rec + 6);
    if (tbl) {
        c->t = bank_of(g, c)->base + tbl;
        c->t_pos = 0;
        c->t_speed = rec[8];
        c->t_n = 0;
        c->flags |= F_TABLE;
    }
    if (c->vib) c->flags |= F_VIB;
}

/* A note's period on this channel (the wave channel sounds an octave down). */
static uint16_t period_of(const GbmChan *c, uint8_t n)
{
    if (c->hw == 2) n = (uint8_t)(n + 12);
    if (n >= NOTE_COUNT) n = NOTE_COUNT - 1;
    return PERIODS[n];
}

/* Portamento: keep sounding and bend from the current pitch to `note`. */
static void porta_to(GbmChan *c, uint8_t note)
{
    uint16_t now = (uint16_t)(period_of(c, c->note) + c->bend);
    c->note = note;
    c->bend = (uint16_t)(now - period_of(c, note));
    c->mode |= 2;
    c->flags |= F_BEND;
}

static void note_off(Gbm *g, GbmChan *c)
{
    c->flags = 0;
    c->delay = 0;
    if (g->look) return;              /* parsed ahead: release silences it on time */
    if (c->block) return;             /* lent to an SFX (or muted): leave it be */
    silence_hw(g, c->hw);
}

static void set_inst(Gbm *g, GbmChan *c, uint8_t i)
{
    c->inst = i;
    c->insp = bank_of(g, c)->ins + i * 10;
}

/* One row of one stream: [instrument] [command...] then a note, 0x60 note
   off, 0x61 end (SFX) or 0x80+n (this and n more rows are empty).
   Returns 0 at the end of an SFX stream, 2 if the row did something. */
static uint8_t row(Gbm *g, GbmChan *c)
{
    const uint8_t *p;
    uint8_t mode = 0, a;
    if (c->wait) { c->wait--; return 1; }
    p = c->p;
    a = *p++;
    if (a >= 0xC0) {
        if (a < 0xE0 || a == 0xF0) {
            uint8_t i = a < 0xE0 ? (uint8_t)(a - 0xC0) : *p++;
            if (c->inst != i) set_inst(g, c, i);
            a = *p++;
        }
        while ((a & 0xF0) == 0xE0) {
            uint8_t val = *p++;
            command(g, c, a & 0x0F, val, &mode);
            mode |= 0x80;               /* the row did something */
            a = *p++;
        }
    }
    c->p = p;
    if (a >= 0x60) {
        if (a == 0x60) { note_off(g, c); return 2; }
        if (a == 0x61) return 0;
        c->wait = a & 0x3F;
        return (mode & 0x80) ? 2 : 1;
    }
    a = (uint8_t)(a + c->transpose);
    if ((mode & M_PORTA) && (c->flags & F_ON)) { porta_to(c, a); return 2; }
    if (mode & M_DELAY) {               /* frame_ch starts it later */
        c->dnote = a;
        c->note = 0xFF;
        c->flags |= F_ON | F_COUNT;
        return 2;
    }
    note_on(g, c, a, mode);
    return 2;
}

/* ─── commands ─────────────────────────────────────────────────────────── */

/* A = x << 4 of a 9xy: x 1-7 takes x off the envelope's volume, 9-F adds x-8. */
static void retrig_volume(GbmChan *c, uint8_t x)
{
    int v = c->env >> 4;
    if (!(x & 8)) { v -= x; if (v < 0) v = 0; }
    else { v += x & 7; if (v > 15) v = 15; }
    c->env = (uint8_t)((v << 4) | (c->env & 0x0F));
}

static void command(Gbm *g, GbmChan *c, uint8_t cmd, uint8_t val, uint8_t *mode)
{
    uint8_t m = 0;
    switch (cmd) {
    case 0x0:                                   /* arpeggio */
        c->arp = val; c->arp_ph = 0;
        c->flags = val ? c->flags | F_ARP : c->flags & ~F_ARP;
        break;
    case 0x1: case 0x2:                         /* slide up / down */
        c->slide = val; c->mode = cmd == 1;
        c->flags = val ? c->flags | F_BEND : c->flags & ~F_BEND;
        break;
    case 0x3: c->slide = val; m = M_PORTA; break;
    case 0x4:                                   /* vibrato */
        c->vib = val; c->vib_wait = 0;
        c->flags = val ? c->flags | F_VIB : c->flags & ~F_VIB;
        m = M_VIB;
        break;
    case 0x5: c->env = val; restart(c); m = M_ENV; break;
    case 0x6:                                   /* duty / wave / noise mode */
        c->duty = val;
        if (c->hw == 2) restart(c);             /* a new wave needs a restart */
        else { c->trig |= 2; mark(c); }
        m = M_DUTY;
        break;
    case 0x7: c->delay = val; c->flags |= F_COUNT; m = M_DELAY; break;
    case 0x8: c->pan = val; set_pan(g); break;
    case 0x9: {                                 /* retrigger */
        uint8_t rate = val & 0x0F;
        if (!rate) val = 0;                     /* a rate of 0 turns it off */
        c->retrig = val;
        c->retrig_n = (uint8_t)(rate + 1);      /* counts down in this frame too */
        if (val) c->flags |= F_COUNT;
        break;
    }
    case 0xA: c->cut = val; c->flags |= F_COUNT; m = M_CUT; break;
    case 0xB: g->jump = val; break;
    case 0xC: c->sweep = val; restart(c); break;
    case 0xD: g->brk = val; break;
    case 0xE: g->sync = val; break;
    case 0xF:                                   /* groove: an SFX may not */
        if (!c->bank) {
            g->groove = g->banks[0].base + U16(g->groovetab + val * 2);
            g->groove_pos = 0;
        }
        break;
    }
    *mode = (uint8_t)(*mode | m);
}

/* ─── per frame ────────────────────────────────────────────────────────── */

/* One step of the instrument table, every t_speed + 1 frames. Returns 1 if
   the table only waited. */
static int table_step(Gbm *g, GbmChan *c)
{
    const uint8_t *r;
    uint8_t cmd, val, dummy = 0;
    if (c->t_n) { c->t_n--; return 1; }
    r = c->t + 2 + c->t_pos * 6;
    c->t_tr = (int8_t)r[0];
    if (r[1] != 0xFF) { c->env = r[1]; restart(c); }
    if (r[2] != 0xFF && c->duty != r[2]) {
        c->duty = r[2];
        if (c->hw == 2) restart(c);
        else c->trig |= 2;
    }
    c->t_pitch = (int8_t)r[3];
    cmd = r[4]; val = r[5];
    if (++c->t_pos >= c->t[0]) {
        if (c->t[1] == 0xFF) c->flags &= ~F_TABLE;
        else c->t_pos = c->t[1];
    }
    c->t_n = c->t_speed;
    /* The command column: any pattern command, except B, which hops within
       the table (LSDj's H). */
    if (cmd != 0xFF) {
        if (cmd == 0x0B) { c->t_pos = val; c->flags |= F_TABLE; }
        else command(g, c, cmd, val, &dummy);
    }
    return 0;
}

/* Slides move the bend every frame; portamento walks it back to zero. */
static void bend_step(GbmChan *c)
{
    uint16_t b = c->bend, s = c->slide;
    if (c->mode & 2) {
        if (!(b & 0x8000)) b = b < s ? 0 : (uint16_t)(b - s);
        else b = (uint32_t)b + s > 0xFFFF ? 0 : (uint16_t)(b + s);
        if (!b) c->flags &= ~F_BEND;
    } else if (c->mode & 1) b = (uint16_t)(b + s);
    else b = (uint16_t)(b - s);
    c->bend = b;
}

/* Countdowns, table and bends, then the pitch, then the registers that
   changed. */
static void frame_ch(Gbm *g, GbmChan *c)
{
    uint8_t trig, block, n;
    uint16_t v;
    if (c->flags & F_COUNT) {
        if (c->delay) {
            if (--c->delay) return;
            note_on(g, c, c->dnote, 0);
        }
        if (c->cut && !--c->cut) { note_off(g, c); return; }
        if (c->retrig && !--c->retrig_n) {      /* 9xy: every y frames, volume +-x */
            c->retrig_n = c->retrig & 0x0F;
            c->trig |= 1;
            if (c->retrig & 0xF0) retrig_volume(c, c->retrig >> 4);
        }
        if (!(c->cut | c->delay | c->retrig)) c->flags &= ~F_COUNT;
    }
    if ((c->flags & F_TABLE) && table_step(g, c)) {
        /* nothing else moving: nothing to write */
        if (!(c->flags & (F_ARP | F_BEND | F_VIB | F_DIRTY))) return;
    }
    if (c->flags & F_BEND) bend_step(c);

    if (!(c->flags & F_ON)) return;
    c->flags &= ~F_DIRTY;
    trig = c->trig; c->trig = 0;
    block = c->block;
    if (c->note == 0xFF) return;
    n = (uint8_t)(c->note + c->t_tr);
    if (c->arp) {
        uint8_t ph = (uint8_t)(c->arp_ph + 1);
        if (ph >= 3) ph = 0;
        c->arp_ph = ph;
        if (ph == 2) n = (uint8_t)(n + (c->arp >> 4));
        else if (ph == 0) n = (uint8_t)(n + (c->arp & 0x0F));
    }
    if (c->hw == 3) {
        if (n >= NOISE_COUNT) n = (n & 0x80) ? 0 : NOISE_COUNT - 1;
        v = NOISE[n] | (c->duty & 8);
    } else {
        if (c->hw == 2) n = (uint8_t)(n + 12);
        if (n >= NOTE_COUNT) n = (n & 0x80) ? 0 : NOTE_COUNT - 1;
        v = (uint16_t)(PERIODS[n] + c->bend + c->t_pitch);
        if (c->vib) {
            if (c->vib_wait) c->vib_wait--;
            else {
                c->vib_pos = (uint8_t)(c->vib_pos + (c->vib >> 4));
                v = (uint16_t)(v + VIBRATO[((c->vib_pos >> 2) & 0x0F) | ((c->vib & 0x0F) << 4)]);
            }
        }
        if (v & 0x8000) v = 0;
        else if (v > 2047) v = 2047;
    }
    if (!trig) {
        if (c->out == v) return;           /* nothing changed: no writes */
    }
    c->out = v;
    if (block) return;
    switch (c->hw) {
    case 0: w_pu(g, c, trig, v, 0); break;
    case 1: w_pu(g, c, trig, v, 1); break;
    case 2: w_wav(g, c, trig, v); break;
    default: w_noi(g, c, trig, v); break;
    }
}

/* ─── rows and orders ──────────────────────────────────────────────────── */

/* row(), then, when parsing ahead, hold the channel if its row did anything. */
static void row_held(Gbm *g, GbmChan *c)
{
    if (row(g, c) == 2 && g->look) c->flags |= F_HOLD;
}

static void rows4(Gbm *g)
{
    int i;
    for (i = 0; i < 4; i++) row_held(g, &g->ch[i]);
}

static void enter_order(Gbm *g, uint8_t order)
{
    const uint8_t *o;
    int i;
    if (g->hold != 0xFF) order = g->hold;
    if (order >= g->order_count) {
        if (g->loop_order == 0xFF) { gbm_stop(g); return; }
        order = g->loop_order;
    }
    g->porder = order;
    g->prow = 0;
    o = g->orders + order * 8;
    for (i = 0; i < 4; i++) {
        GbmChan *c = &g->ch[i];
        c->p = g->banks[0].base + U16(g->patdir[i] + o[i] * 2);
        c->wait = 0;
        c->transpose = o[4 + i];
    }
}

static void music_row(Gbm *g)
{
    uint8_t order, r;
    g->jump = 0xFF;
    g->brk = 0xFF;
    rows4(g);
    if (g->jump != 0xFF) { order = g->jump; r = 0; }                     /* Bxx */
    else if (g->brk != 0xFF) { order = (uint8_t)(g->porder + 1); r = g->brk; }   /* Dxx */
    else {
        /* at the end it reads rows: "the next order" */
        if (++g->prow < g->rows) return;
        order = (uint8_t)(g->porder + 1); r = 0;
    }
    /* The order is entered later, in a lighter frame (pending_order). */
    g->next_order = order;
    g->next_row = r;
    g->pending = 1;
}

/* Enters the order music_row left pending, and skips to its row. */
static void pending_order(Gbm *g)
{
    uint8_t r;
    g->pending = 0;
    enter_order(g, g->next_order);
    r = g->next_row;
    while (g->playing && g->prow < r) { rows4(g); g->prow++; }
}

/* The frame before a row: parse it now, hold what it touches. */
static void parse_ahead(Gbm *g)
{
    if (g->pending) pending_order(g);
    if (!g->playing) return;
    g->look = 1;
    music_row(g);
    g->look = 0;
    g->parsed = 1;
}

/* The row's frame: the held channels go, and a note-off parsed ahead
   silences its channel now. */
static void release_held(Gbm *g)
{
    int i;
    for (i = 0; i < 4; i++) {
        GbmChan *c = &g->ch[i];
        if (!(c->flags & F_HOLD)) continue;
        c->flags &= ~F_HOLD;
        if (!(c->flags & F_ON) && !c->block) silence_hw(g, (uint8_t)i);
    }
}

/* The effect is over; its hardware channel goes back to the music, which
   restarts whatever note it is holding. */
static void sfx_end(Gbm *g, uint8_t slot)
{
    GbmChan *s = &g->ch[slot], *m;
    uint8_t hw = s->hw, block;
    s->prio = 0;
    s->flags = 0;
    silence_hw(g, hw);
    g->owner[hw] = NO_OWNER;
    m = &g->ch[hw];
    /* blocked still if muted, or CH3 while a drum sample plays */
    block = (g->muted >> hw) & 1;
    if (hw == 2) { g->wave_ptr = NULL; block |= g->pcm_active; }
    m->block = block;
    if (hw == 0) W(g, NR10, 0);            /* PU1: the effect's sweep goes */
    m->out = 0xFFFF;
    restart(m);
    if (!(m->flags & F_ON)) silence_hw(g, hw);
    set_pan(g);
}

/* An SFX slot's frame: its own row clock, then the channel. */
static void sfx_slot(Gbm *g, uint8_t slot)
{
    GbmChan *c = &g->ch[slot];
    g->active = 1;
    if (!--c->speed_n) {
        c->speed_n = c->speed;
        if (!row(g, c)) { sfx_end(g, slot); return; }
    }
    if (c->flags & F_WORK) frame_ch(g, c);
}

static void duck_step(Gbm *g)
{
    uint8_t target = g->active ? g->duck_amount : 0;
    GbmChan *c = &g->ch[2];
    if (g->duck_level == target) return;
    if (--g->duck_n) return;
    g->duck_n = g->duck_speed;
    if (g->duck_level < target) g->duck_level++;
    else g->duck_level--;
    /* pulse and noise pick the level up at their next note; CH3 now */
    if (c->block || !(c->flags & F_ON)) return;
    W(g, NR32, wave_level(g, c, c->env));
}

void gbm_tick(Gbm *g)
{
    int i;
    if (g->paused) return;
    g->active = 0;
    if (g->playing) {
        /* A row's work is spread over three frames so no frame carries it all:
             tick_n 2 -> (a light frame) enter the order the last row left pending;
             tick_n 1 -> parse the row, holding the channels it touches;
             tick_n 0 -> release them: their registers are written this frame.
           A groove step of 1 frame leaves no room, and the row is done at 0. */
        uint8_t n = --g->tick_n;
        int channels = 1;
        if (n == 0) {
            int row_ok = 1;
            if (g->parsed) { g->parsed = 0; release_held(g); }
            else {
                if (g->pending) pending_order(g);
                if (g->playing) music_row(g);
                else row_ok = 0;             /* the song ended entering the order */
            }
            if (row_ok) {
                /* publish the position on the row's frame */
                g->order = g->porder;
                g->row = g->prow;
            }
            if (row_ok && g->playing) {
                uint8_t pos = (uint8_t)(g->groove_pos + 1);
                g->tick_n = g->groove[pos];
                g->groove_pos = pos < g->groove[0] ? pos : 0;
            } else channels = 0;
        } else if (n == 1) parse_ahead(g);
        else if (n == 2) { if (g->pending) pending_order(g); }
        if (channels)
            for (i = 0; i < 4; i++) {
                GbmChan *c = &g->ch[i];
                if (!(c->flags & F_HOLD) && (c->flags & F_WORK)) frame_ch(g, c);
            }
    }
    for (i = 4; i < 6; i++) if (g->ch[i].prio) sfx_slot(g, (uint8_t)i);
    if (g->duck_amount) duck_step(g);
    if (g->pcm_done) pcm_end(g);
}

/* ─── the rarely called API (gameboy-lab gbm.c) ────────────────────────── */

/* Restart the channel's note on the next frame. */
static void dirty(GbmChan *c) { c->trig = 1; c->out = 0xFFFF; mark(c); }

static void update_block(Gbm *g, uint8_t hw)
{
    g->ch[hw].block = g->owner[hw] != NO_OWNER || ((g->muted >> hw) & 1) || (hw == 2 && g->pcm_active);
}

static void bind(Gbm *g, int b, const uint8_t *blob)
{
    GbmBank *k = &g->banks[b];
    k->base = blob;
    k->ins = blob + U16(blob + 12);
    k->tbl = blob + U16(blob + 14);
    k->wave = blob + U16(blob + 16);
}

/* A hardware channel coming back to the music: the next frame retriggers
   whatever note the song is holding there. */
static void release_hw(Gbm *g, uint8_t hw)
{
    GbmChan *c = &g->ch[hw];
    g->owner[hw] = NO_OWNER;
    update_block(g, hw);
    dirty(c);
    if (hw == 2) g->wave_ptr = NULL;
    if (hw == 0) W(g, NR10, 0);
    if (!(c->flags & F_ON)) silence_hw(g, hw);
    set_pan(g);
}

static void pcm_release(Gbm *g)
{
    g->pcm_active = 0;
    g->pcm_done = 0;
    update_block(g, 2);
    dirty(&g->ch[2]);
    g->wave_ptr = NULL;
    if (!(g->ch[2].flags & F_ON)) silence_hw(g, 2);
}

static void pcm_stop(Gbm *g)
{
    g->timer_irq = 0;
    g->pcm_left = 0;
    if (g->pcm_active) { W(g, NR30, 0); pcm_release(g); }
}

void gbm_pcm_timer(Gbm *g) { g->pcm_timer_on = 1; }

void gbm_init(Gbm *g, GbApu *apu)
{
    int i;
    for (i = 0; i < (int)sizeof *g; i++) ((uint8_t *)g)[i] = 0;
    g->apu = apu;
    g->hold = 0xFF;
    W(g, NR52, 0x80);
    W(g, NR50, 0x77);
    W(g, NR51, g->nr51 = 0xFF);
    W(g, NR10, 0);
    for (i = 0; i < 6; i++) {
        GbmChan *c = &g->ch[i];
        c->hw = (uint8_t)(i < 4 ? i : 0);
        c->pan = 3;
        c->bank = (uint8_t)(i < 4 ? 0 : 1);
    }
    for (i = 0; i < 4; i++) { g->owner[i] = NO_OWNER; silence_hw(g, (uint8_t)i); }
}

void gbm_play(Gbm *g, const uint8_t *s)
{
    int i;
    g->playing = 0;
    g->paused = 0;
    bind(g, 0, s);
    g->rows = s[3];
    g->order_count = s[4];
    g->loop_order = s[5];
    g->orders = s + U16(s + 8);
    for (i = 0; i < 4; i++) g->patdir[i] = s + U16(s + U16(s + 10) + i * 2);
    g->groovetab = s + U16(s + 18);
    gbm_seek(g, 0, 0);
}

void gbm_seek(Gbm *g, uint8_t order, uint8_t r)
{
    int i;
    if (!g->banks[0].base) return;
    g->playing = 0;
    pcm_stop(g);
    for (i = 0; i < 4; i++) {
        GbmChan *c = &g->ch[i];
        c->flags = 0; c->inst = 0; c->insp = g->banks[0].ins; c->arp = 0; c->retrig = 0;
        c->cut = 0; c->delay = 0; c->pan = 3; c->out = 0xFFFF; c->mode = 0; c->bend = 0;
        if (g->owner[i] == NO_OWNER) silence_hw(g, (uint8_t)i);
    }
    g->wave_ptr = NULL;
    set_pan(g);
    g->groove = g->banks[0].base + U16(g->groovetab);
    g->groove_pos = 0;
    g->look = 0; g->parsed = 0; g->pending = 0;
    g->playing = 1;
    enter_order(g, order);
    /* Fast-forward whole rows in silence: instruments and running effects end
       up as the row would have inherited them. */
    while (g->playing && g->prow < r) { rows4(g); g->prow++; }
    g->order = g->porder;
    g->row = g->prow;
    for (i = 0; i < 4; i++) dirty(&g->ch[i]);
    g->tick_n = 1;
}

void gbm_stop(Gbm *g)
{
    int i;
    g->playing = 0;
    pcm_stop(g);
    for (i = 0; i < 4; i++) {
        g->ch[i].flags = 0;
        if (g->owner[i] == NO_OWNER) silence_hw(g, (uint8_t)i);
    }
}

void gbm_pause(Gbm *g, uint8_t p)
{
    int i;
    g->paused = p;
    if (p) { pcm_stop(g); for (i = 0; i < 4; i++) silence_hw(g, (uint8_t)i); }
    else { for (i = 0; i < 6; i++) dirty(&g->ch[i]); g->wave_ptr = NULL; }
}

void gbm_sfx_bank(Gbm *g, const uint8_t *b)
{
    bind(g, 1, b);
    g->patdir[4] = b + U16(b + U16(b + 10) + 8);
}

uint8_t gbm_sfx(Gbm *g, uint8_t id)
{
    const uint8_t *b = g->banks[1].base, *e;
    uint8_t slot, hw, prio, pat, speed;
    GbmChan *c;
    if (!b || id >= b[6]) return 0;
    e = b + U16(b + 20) + id * 4;
    pat = e[0]; hw = e[1] & 3; prio = e[2] ? e[2] : 1; speed = e[3] ? e[3] : 1;
    /* The slot already on this channel if any, else a free one, else the
       weaker of the two. */
    if (g->owner[hw] != NO_OWNER) slot = g->owner[hw];
    else if (!g->ch[4].prio) slot = 4;
    else if (!g->ch[5].prio) slot = 5;
    else slot = g->ch[4].prio <= g->ch[5].prio ? 4 : 5;
    c = &g->ch[slot];
    if (c->prio > prio) return 0;
    if (hw == 2) pcm_stop(g);
    if (c->prio && c->hw != hw) release_hw(g, c->hw);
    c->hw = hw; c->prio = prio; c->speed = speed; c->speed_n = 1;
    c->p = b + U16(g->patdir[4] + pat * 2); c->wait = 0; c->transpose = 0;
    c->flags = 0; c->inst = 0; c->insp = g->banks[1].ins; c->arp = 0; c->retrig = 0; c->cut = 0;
    c->delay = 0; c->mode = 0; c->bend = 0; c->pan = 3; c->out = 0xFFFF;
    g->owner[hw] = slot;
    update_block(g, hw);
    if (hw == 2) g->wave_ptr = NULL;
    set_pan(g);
    return 1;
}

void gbm_sfx_stop(Gbm *g)
{
    uint8_t i;
    for (i = 4; i < 6; i++) if (g->ch[i].prio) sfx_end(g, i);
}

void gbm_duck(Gbm *g, uint8_t amount, uint8_t speed)
{
    g->duck_amount = amount;
    g->duck_speed = speed ? speed : 1;
    g->duck_n = g->duck_speed;
    if (!amount) g->duck_level = 0;
}

void gbm_mute(Gbm *g, uint8_t mask)
{
    uint8_t i, bit;
    for (i = 0, bit = 1; i < 4; i++, bit <<= 1) {
        if ((mask & bit) && !(g->muted & bit) && g->owner[i] == NO_OWNER) silence_hw(g, i);
        else if (!(mask & bit) && (g->muted & bit)) { dirty(&g->ch[i]); if (i == 2) g->wave_ptr = NULL; }
    }
    g->muted = mask;
    for (i = 0; i < 4; i++) update_block(g, i);
}

void gbm_volume(Gbm *g, uint8_t level) { W(g, NR50, (uint8_t)((level & 7) * 0x11)); }

/* ─── blob checks ──────────────────────────────────────────────────────── */

/* Everything the driver indexes from the header lies inside the blob. The
   streams themselves are trusted, as the original trusts its ROM: a blob
   from the encoder always ends each one. */
int gbm_check(const uint8_t *s, uint32_t len)
{
    uint32_t i, dir;
    if (len < 24 || s[0] != 'G' || s[1] != 'B' || s[2] != 1) return 1;
    for (i = 8; i < 24; i += 2) if ((uint32_t)U16(s + i) > len) return 2;
    if (U16(s + 8) + (uint32_t)s[4] * 8 > len) return 3;
    dir = U16(s + 10);
    if (dir + 10 > len) return 4;
    for (i = 0; i < 5; i++) if ((uint32_t)U16(s + dir + i * 2) >= len) return 4;
    if ((uint32_t)U16(s + 18) + 2 > len || (uint32_t)U16(s + U16(s + 18)) + 2 > len) return 5;
    if (U16(s + 20) + (uint32_t)s[6] * 4 > len) return 6;
    return 0;
}
