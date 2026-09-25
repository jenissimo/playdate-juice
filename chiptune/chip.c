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
    memset(c, 0, sizeof *c);
    gbapu_init(&c->apu, sample_rate);
    gbm_init(&c->gbm, &c->apu);
    gbm_pcm_timer(&c->gbm);
    c->idle = 1;
}

int chip_post(Chip *c, uint8_t op, uint8_t a, uint8_t b, const uint8_t *blob)
{
    uint32_t h = c->head;
    ChipCmd *q;
    if (h - c->tail >= CHIP_QUEUE) return 0;
    q = &c->queue[h % CHIP_QUEUE];
    q->op = op; q->a = a; q->b = b; q->blob = blob;
    BARRIER();
    c->head = h + 1;
    return 1;
}

static void run(Chip *c, const ChipCmd *q)
{
    Gbm *g = &c->gbm;
    switch (q->op) {
    case CHIP_PLAY: gbm_play(g, q->blob); if (q->a || q->b) gbm_seek(g, q->a, q->b); break;
    case CHIP_STOP: gbm_stop(g); break;
    case CHIP_PAUSE: gbm_pause(g, q->a); break;
    case CHIP_SFX_BANK: gbm_sfx_bank(g, q->blob); break;
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
    return !g->playing && !g->ch[4].prio && !g->ch[5].prio && !g->pcm_active &&
           !gbapu_active(&c->apu) &&
           c->apu.hp_l < 8 && c->apu.hp_l > -8 && c->apu.hp_r < 8 && c->apu.hp_r > -8;
}

int chip_render(Chip *c, int16_t *left, int16_t *right, int n)
{
    Gbm *g = &c->gbm;
    chip_drain(c);
    if (quiet(c)) {
        c->idle = 1;
        return 0;
    }
    c->idle = 0;
    while (n > 0) {
        int32_t next;
        int k;
        uint32_t cyc;
        while (c->tick_cd <= 0) {
            gbm_tick(g);
            c->ticks++;
            c->tick_cd += GBM_FRAME_CYCLES;
            /* a drum sample started: its first block played inside the tick */
            if (g->timer_restart) { g->timer_restart = 0; c->timer_cd = GBM_TIMER_CYCLES; }
        }
        while (g->timer_irq && c->timer_cd <= 0) {
            gbm_pcm_isr(g);
            c->timer_cd += GBM_TIMER_CYCLES;
        }
        next = c->tick_cd;
        if (g->timer_irq && c->timer_cd < next) next = c->timer_cd;
        k = gbapu_samples_for(&c->apu, (uint32_t)next);
        if (k > n) k = n;
        cyc = gbapu_render(&c->apu, left, right, k);
        if (left) left += k;
        if (right) right += k;
        c->tick_cd -= (int32_t)cyc;
        c->timer_cd -= (int32_t)cyc;
        n -= k;
    }
    return 1;
}
