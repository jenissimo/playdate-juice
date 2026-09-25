/* GBM: a tracker music and sound-effect driver, ported from the DMG.

   The original (gameboy-lab, shared/gbm) is SDCC C plus SM83 assembly that
   owns a real Game Boy's APU. This is the same driver in portable C, driving
   gbapu instead of the hardware: every register write it makes, in order and
   on the same frame, matches the original running in an emulator. The song
   format is unchanged, so anything the GBM tracker exports plays here.

   Four music channels and two SFX slots run on the same machinery. An SFX
   takes its hardware channel from the music, which keeps running silently
   and gets the channel back, retriggered, when the effect ends. While any
   SFX plays the other music channels are ducked.

   Two formats. Format 1 is the original's, played on gbapu and held to the
   original write for write. Format 2 (chiptune/README.md) is this port's
   own: up to 8 voices, each instrument picking its oscillator (and a table
   switching it frame by frame, as SID drums do), continuous pulse width and
   PWM, triangle and saw, ring modulation, hard sync and a resonant filter;
   it plays on vox. Everything else -- rows, commands, tables, SFX, ducking
   -- is the same machinery.

   Not thread-safe: one thread owns a Gbm. chip.h wraps it for an audio
   callback. */
#ifndef GBM_H
#define GBM_H
#include <stdint.h>
#include "gbapu.h"
#include "vox.h"

typedef struct {
    uint8_t flags, trig, block, hw;
    uint8_t note; int8_t t_tr; uint8_t arp, arp_ph, duty;
    uint16_t bend;
    int8_t t_pitch;
    uint8_t vib, vib_wait, vib_pos;
    uint16_t out;
    uint8_t env, sweep, cut, delay, retrig, retrig_n;
    const uint8_t *t;
    uint8_t t_pos, t_speed, t_n, slide, mode;
    uint8_t wait;
    const uint8_t *p;
    uint8_t inst;
    uint8_t transpose;
    const uint8_t *insp;
    uint8_t dnote, pan, prio, speed, speed_n, bank;
    /* format 2 */
    uint8_t osc, xflags, sample;
    int8_t pwm;
} GbmChan;

typedef struct {
    const uint8_t *base, *ins, *tbl, *wave;
    uint8_t version, rec, trow;        /* format; instrument and table-row sizes */
} GbmBank;

#define GBM_VOICES 8                    /* music channels, at most */
#define GBM_SLOT0 GBM_VOICES            /* the two SFX slots follow them */
#define GBM_SLOT1 (GBM_VOICES + 1)

typedef struct Gbm {
    GbApu *apu;
    Vox *vox;
    GbmChan ch[GBM_VOICES + 2];
    GbmBank banks[2];
    const uint8_t *patdir[GBM_VOICES];
    const uint8_t *sfxdir;
    uint8_t nv, v2;                     /* music channels; playing on vox */
    const uint8_t *orders, *groove, *groovetab;
    uint8_t rows, order_count, loop_order, tick_n, groove_pos;
    uint8_t jump, brk, paused, muted;
    uint8_t owner[GBM_VOICES];
    const uint8_t *wave_ptr;
    uint8_t duck_amount, duck_speed, duck_level, duck_n;
    /* Where the song is: order/row name the next row to play; sync holds the
       last Exx value, so gameplay can hang events on the music. */
    volatile uint8_t playing, order, row, sync, hold;
    uint8_t look, parsed, pending, next_order, next_row;
    uint8_t porder, prow;
    uint8_t nr51;
    uint8_t active;
    /* A drum sample borrowing CH3, fed 16 bytes at a time by gbm_pcm_isr at
       256 Hz. The host owns that timer: it calls gbm_pcm_isr while
       timer_irq is set, restarting its count when timer_restart is. */
    const uint8_t *pcm_ptr;
    uint8_t pcm_left, pcm_active, pcm_done, pcm_timer_on;
    uint8_t timer_irq, timer_restart;
} Gbm;

/* `vox` may be NULL: format-2 blobs then play silent. */
void gbm_init(Gbm *g, GbApu *apu, Vox *vox);
void gbm_play(Gbm *g, const uint8_t *song);
void gbm_seek(Gbm *g, uint8_t order, uint8_t row);
void gbm_stop(Gbm *g);
void gbm_pause(Gbm *g, uint8_t paused);
/* Once per DMG frame: 4194304 / 70224 = 59.73 times a second. */
void gbm_tick(Gbm *g);

void gbm_sfx_bank(Gbm *g, const uint8_t *bank);
/* Starts effect `id` from the SFX bank. Returns 0 if a higher-priority effect
   holds every slot it could use, or there is no such effect. */
uint8_t gbm_sfx(Gbm *g, uint8_t id);
void gbm_sfx_stop(Gbm *g);
/* While an SFX plays, music volume drops by `amount` (0-15 envelope steps),
   moving one step every `speed` frames each way. */
void gbm_duck(Gbm *g, uint8_t amount, uint8_t speed);
/* Music channels muted from the game side (a bit per channel); the song
   keeps time. */
void gbm_mute(Gbm *g, uint8_t mask);
/* Drum samples play only once this has been called: it stands for the
   original's installing a timer interrupt. */
void gbm_pcm_timer(Gbm *g);
void gbm_pcm_isr(Gbm *g);
/* NR50 master volume 0-7; affects SFX too. */
void gbm_volume(Gbm *g, uint8_t level);

/* Frames per second of the original: the host ticks at this rate. */
#define GBM_FRAME_CYCLES 70224u
/* The drum-sample timer: 4096 Hz / 16. */
#define GBM_TIMER_CYCLES 16384u

/* The blob's own checks: 0 if `bytes` can be played. */
int gbm_check(const uint8_t *bytes, uint32_t len);
#endif
