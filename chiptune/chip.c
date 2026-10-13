/* chip: see chip.h. */
#include "chip.h"
#include <string.h>

/* The queue's two indexes are written from different contexts; what must not
   happen is the compiler moving the slot's contents past the index write.
   Both targets (Cortex-M7, x86-64 for the simulator) keep stores in order in
   hardware, so a compiler barrier is enough. */
#if defined(_MSC_VER)
#include <intrin.h>
#define BARRIER() _ReadWriteBarrier()
#else
#define BARRIER() __asm__ __volatile__("" ::: "memory")
#endif

void chip_init(Chip *c, uint32_t sample_rate)
{
    uint32_t late = (uint32_t)((uint64_t)sample_rate * CHIP_TICK_LATE_US / 1000000u);
    memset(c, 0, sizeof *c);
    gbapu_init(&c->apu, sample_rate);
    vox_init(&c->vox, sample_rate);
    gbm_init(&c->gbm, &c->apu, &c->vox);
    gbm_pcm_timer(&c->gbm);
    c->quantum = 1;
    while ((uint32_t)c->quantum * 2 <= late) c->quantum *= 2;
    c->idle = 1;
}

int chip_post(Chip *c, uint8_t op, uint8_t a, uint8_t b, const uint8_t *blob)
{
    return chip_post_bank(c, op, a, b, blob, NULL);
}

int chip_post_bank(Chip *c, uint8_t op, uint8_t a, uint8_t b,
                   const uint8_t *blob, const uint8_t *samples)
{
    uint32_t h = c->head;
    ChipCmd *q;
    if ((op == CHIP_PLAY || op == CHIP_SFX_BANK) && !gbm_sample_bank_match(blob, samples)) return 0;
    if (h - c->tail >= CHIP_QUEUE) return 0;
    q = &c->queue[h % CHIP_QUEUE];
    q->op = op; q->a = a; q->b = b; q->blob = blob;
    q->samples = samples;
    BARRIER();
    c->head = h + 1;
    return 1;
}

static void run(Chip *c, const ChipCmd *q)
{
    Gbm *g = &c->gbm;
    switch (q->op) {
    case CHIP_PLAY:
        gbm_play_bank(g, q->blob, q->samples);
        if (q->a || q->b) gbm_seek(g, q->a, q->b);
        c->music_cd = 0;
        break;
    case CHIP_STOP: gbm_stop(g); break;
    case CHIP_PAUSE: gbm_pause(g, q->a); break;
    case CHIP_SFX_BANK: gbm_sfx_bank_samples(g, q->blob, q->samples); break;
    case CHIP_SFX: gbm_sfx(g, q->a); break;
    case CHIP_SFX_STOP: gbm_sfx_stop(g); break;
    case CHIP_DUCK: gbm_duck(g, q->a, q->b); break;
    case CHIP_MUTE: gbm_mute(g, q->a); break;
    case CHIP_HOLD: g->hold = q->a; break;
    case CHIP_VOLUME: gbm_volume(g, q->a); break;
    }
}

void chip_drain(Chip *c)
{
    while (c->tail != c->head) {
        BARRIER();
        run(c, &c->queue[c->tail % CHIP_QUEUE]);
        BARRIER();
        c->tail++;
    }
}

/* Nothing will sound until the game asks: no song, no effect, no channel on,
   and the DC blocker has settled. Rendering can stop there -- the music has
   no clock to keep while it is not playing. */
static int quiet(const Chip *c)
{
    const Gbm *g = &c->gbm;
    return !g->playing && !g->ch[GBM_SLOT0].prio && !g->ch[GBM_SLOT1].prio && !g->pcm_active &&
           !gbapu_active(&c->apu) && !vox_active(&c->vox) &&
           c->apu.hp_l < 8 && c->apu.hp_l > -8 && c->apu.hp_r < 8 && c->apu.hp_r > -8;
}

int chip_render(Chip *c, int16_t *left, int16_t *right, int n)
{
    Gbm *g = &c->gbm;
    int q;
    int32_t tick_cd, timer_cd, music_cd;
    chip_drain(c);
    /* Calibrated studio arrangements keep ticks to the sample; embedded FT2
       and chip songs retain the master's bounded-lateness optimization. */
    q = g->banks[0].version == 4 ? 1 : c->quantum;
    if (quiet(c)) {
        c->idle = 1;
        return 0;
    }
    if (c->idle) c->idle = 0;
    /* the countdowns in locals for the call, stored once at the end */
    tick_cd = c->tick_cd;
    timer_cd = c->timer_cd;
    music_cd = c->music_cd;
    while (n > 0) {
        int32_t next;
        int k;
        uint32_t cyc;
        while (tick_cd <= 0) {
            gbm_tick(g);
            c->ticks++;
            tick_cd += GBM_FRAME_CYCLES;
            /* a drum sample started: its first block played inside the tick */
            if (g->timer_restart) { g->timer_restart = 0; timer_cd = GBM_TIMER_CYCLES; }
        }
        /* a format-3 tempo: the music's own clock (it may change, or stop,
           inside a tick: tick_cycles is read afresh each time) */
        while (g->tick_cycles && music_cd <= 0) {
            gbm_tick_music(g);
            music_cd += (int32_t)g->tick_cycles;
        }
        if (!g->tick_cycles) music_cd = 0;
        while (g->timer_irq && timer_cd <= 0) {
            gbm_pcm_isr(g);
            timer_cd += GBM_TIMER_CYCLES;
        }
        /* up to the next tick, rounded up to whole quanta (chip.h); up to
           the drum-sample timer exactly */
        next = tick_cd;
        if (g->tick_cycles && music_cd < next) next = music_cd;
        k = gbapu_samples_for(&c->apu, (uint32_t)next);
        k = (k + q - 1) & ~(q - 1);
        if (g->timer_irq) {
            int kt = gbapu_samples_for(&c->apu, (uint32_t)timer_cd);
            if (kt < k) k = kt;
        }
        if (k > n) k = n;
        cyc = g->v2 ? vox_render(&c->vox, left, right, k) : gbapu_render(&c->apu, left, right, k);
        if (left) left += k;
        if (right) right += k;
        tick_cd -= (int32_t)cyc;
        /* the drum timer only counts while it runs (starting it reloads it),
           so an idle one never wraps */
        if (g->timer_irq) timer_cd -= (int32_t)cyc;
        if (g->tick_cycles) music_cd -= (int32_t)cyc;
        n -= k;
    }
    c->tick_cd = tick_cd;
    c->timer_cd = timer_cd;
    c->music_cd = music_cd;
    return 1;
}
