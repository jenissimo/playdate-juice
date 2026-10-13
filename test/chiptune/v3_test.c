/* Format 3: FastTracker 2's sampler on vox, and FT2's commands in the
   driver. As with format 2 there is no original to match, so these hold
   the features to what they promise: a sample plays at its rate and follows
   the note, stops or loops, starts at its offset, plays backwards, takes a
   volume and a pan position without clicking; the tempo is a BPM on the
   music's own clock while the effects keep the frame.

     v3_test <probe3.gbm> <sfx.gbm>   (tools/chiptune.py test writes the probe) */
#define _CRT_SECURE_NO_WARNINGS
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../../chiptune/chip.h"

static int checks, fails;
#define CHECK(cond, ...) do { checks++; if (!(cond)) { fails++; printf("  FAIL: " __VA_ARGS__); printf("\n"); } } while (0)

static int16_t L[44100 * 2], R[44100 * 2];

static double upward_rate(const int16_t *x, int n, int rate)
{
    int i, c = 0;
    for (i = 1; i < n; i++) if (x[i - 1] < 0 && x[i] >= 0) c++;
    return (double)c * rate / n;
}

static double rms(const int16_t *x, int n)
{
    double e = 0;
    int i;
    for (i = 0; i < n; i++) e += (double)x[i] * x[i];
    return sqrt(e / n);
}

/* ─── the sampler, on vox directly ─────────────────────────────────────── */

static int8_t SINE[1025], STAIR[4097], FLAT[2049];

static void make_samples(void)
{
    int i;
    for (i = 0; i < 1024; i++) SINE[i] = (int8_t)floor(100.0 * sin(2 * 3.14159265358979 * i / 64) + 0.5);
    SINE[1024] = SINE[0];                                   /* the loop's guard frame */
    for (i = 0; i < 4096; i++) STAIR[i] = (int8_t)(-120 + 16 * (i >> 8));
    STAIR[4096] = STAIR[4095];
    for (i = 0; i <= 2048; i++) FLAT[i] = 100;
}

/* The first output of a note on the staircase: its level says the block. */
static int first_out(uint32_t from, uint8_t rev)
{
    static Vox x;
    vox_init(&x, 44100);
    vox_pcm(&x, 0, STAIR, 4096, 0, 0, 44100);
    vox_pcm_from(&x, 0, from, rev);
    vox_trigger(&x, 0, OSC_PCM, 1798, 0xF0);
    vox_render(&x, L, R, 1);
    return L[0];
}

static void synth_tests(void)
{
    static Vox x;
    double hz, a, b;
    int i, base, top;
    make_samples();

    /* pitch: a 64-frame cycle at 22050 Hz is 344.5 Hz on C5, an octave up on C6 */
    vox_init(&x, 44100);
    vox_pcm(&x, 0, SINE, 1024, 0, 1024, 22050);
    vox_trigger(&x, 0, OSC_PCM, 1798, 0xF0);
    vox_render(&x, L, R, 44100);
    hz = upward_rate(L, 44100, 44100);
    CHECK(hz > 341 && hz < 348, "a sample at its rate on C5: %.1f Hz, want 344.5", hz);
    CHECK(vox_active(&x), "a looped sample still plays after a second");
    vox_pitch(&x, 0, 1923);
    vox_render(&x, L, R, 44100);
    hz = upward_rate(L, 44100, 44100);
    CHECK(hz > 682 && hz < 696, "and follows the note: C6 at %.1f Hz", hz);

    /* a one-shot plays its frames and stops */
    vox_init(&x, 44100);
    vox_pcm(&x, 0, STAIR, 4096, 0, 0, 44100);
    vox_trigger(&x, 0, OSC_PCM, 1798, 0xF0);
    vox_render(&x, L, R, 4000);
    CHECK(vox_active(&x), "a one-shot of 4096 frames sounds at 4000 samples");
    vox_render(&x, L, R, 200);
    CHECK(!vox_active(&x), "and has stopped by 4200");

    /* offset and direction: the staircase's first level names its block */
    base = first_out(0, 0);                                 /* block 0: -120 */
    CHECK(base < 0, "the staircase starts low (%d)", base);
    a = (double)first_out(1024, 0) / base;                  /* block 4: -56 */
    CHECK(fabs(a - 56.0 / 120) < 0.02, "an offset of 1024 frames starts in block 4 (%.3f)", a);
    top = first_out(0, 1);                                  /* backwards from the end: block 15, +120 */
    CHECK(fabs((double)top / base + 1.0) < 0.02, "backwards starts at the end (%d vs %d)", top, base);
    a = (double)first_out(1024, 1) / base;                  /* backwards from 1024: block 3, -72 */
    CHECK(fabs(a - 72.0 / 120) < 0.02, "backwards from an offset starts just before it (%.3f)", a);
    vox_init(&x, 44100);
    vox_pcm(&x, 0, STAIR, 4096, 0, 0, 44100);
    vox_pcm_from(&x, 0, 0, 1);
    vox_trigger(&x, 0, OSC_PCM, 1798, 0xF0);
    CHECK(x.v[0].step < 0, "backwards steps down (%d)", x.v[0].step);
    vox_render(&x, L, R, 4000);
    CHECK(vox_active(&x), "backwards plays all 4096 frames");
    vox_render(&x, L, R, 200);
    CHECK(!vox_active(&x), "and stops at frame 0");

    /* volume and pan position */
    vox_init(&x, 44100);
    vox_pcm(&x, 0, SINE, 1024, 0, 1024, 22050);
    vox_trigger(&x, 0, OSC_PCM, 1798, 0xF0);
    vox_render(&x, L, R, 4410);
    a = rms(L, 4410);
    vox_volume(&x, 0, 32, 16);
    vox_render(&x, L, R, 64);
    vox_render(&x, L, R, 4410);
    b = rms(L, 4410);
    CHECK(fabs(b / a - 0.5) < 0.02, "volume 32 of 64 is half (%.3f)", b / a);
    CHECK(vox_level(&x, 0) == 8, "and the meter says so (%d)", vox_level(&x, 0));
    vox_volume(&x, 0, 64, 16);
    vox_balance(&x, 0, 0);
    vox_render(&x, L, R, 64);
    vox_render(&x, L, R, 4410);
    CHECK(rms(R, 4410) == 0 && fabs(rms(L, 4410) / a - 1) < 0.02, "pan 0 is all left (L %.0f, R %.0f)",
          rms(L, 4410), rms(R, 4410));
    vox_balance(&x, 0, 192);
    vox_render(&x, L, R, 64);
    vox_render(&x, L, R, 4410);
    CHECK(fabs(rms(L, 4410) / a - 63.0 / 127) < 0.02 && fabs(rms(R, 4410) / a - 1) < 0.02,
          "pan 192 is right of centre (L %.3f, R %.3f)", rms(L, 4410) / a, rms(R, 4410) / a);

    /* a volume change ramps across a block rather than stepping */
    vox_init(&x, 44100);
    vox_pcm(&x, 0, FLAT, 2048, 0, 2048, 44100);
    vox_trigger(&x, 0, OSC_PCM, 1798, 0xF0);
    vox_render(&x, L, R, 256);
    a = L[255];
    vox_volume(&x, 0, 32, 16);
    vox_render(&x, L, R, VOX_BLOCK + 16);
    CHECK(L[0] > 0.95 * a && fabs(L[VOX_BLOCK / 2] / a - 0.75) < 0.03 && fabs(L[VOX_BLOCK + 8] / a - 0.5) < 0.01,
          "volume ramps over a block (%.3f, %.3f, %.3f)", L[0] / a, L[VOX_BLOCK / 2] / a, L[VOX_BLOCK + 8] / a);

    /* a cut note fades in well under a millisecond instead of stopping dead */
    vox_volume(&x, 0, 64, 16);
    vox_render(&x, L, R, 256);
    a = L[255];
    vox_off(&x, 0);
    vox_render(&x, L, R, 512);
    {
        double jump = fabs(L[0] - a), worst = jump;
        for (i = 1; i < 512; i++) if (fabs(L[i] - L[i - 1]) > worst) worst = fabs(L[i] - L[i - 1]);
        CHECK(worst < 0.06 * a, "a cut sampled note does not click (largest step %.3f of its level)", worst / a);
        CHECK(fabs(L[64]) < 0.2 * a && L[400] == 0, "and is gone in ~2 ms (%d, %d)", L[64], L[400]);
    }
    /* so does a retrigger: the old note's tail hands over */
    vox_trigger(&x, 0, OSC_PCM, 1798, 0xF0);
    vox_render(&x, L, R, 256);
    vox_pcm(&x, 0, STAIR, 4096, 0, 0, 44100);
    vox_pcm_from(&x, 0, 2048, 0);                            /* block 8: +8, near silence */
    vox_trigger(&x, 0, OSC_PCM, 1798, 0xF0);
    vox_render(&x, L, R, 4);
    CHECK(L[0] > 0.9 * a, "a retrigger over a loud note starts from where it was (%.3f)", L[0] / a);
}

/* ─── the driver, on the probe ─────────────────────────────────────────── */

static uint8_t *slurp(const char *path, long *len)
{
    FILE *f = fopen(path, "rb");
    uint8_t *b;
    if (!f) return NULL;
    fseek(f, 0, SEEK_END); *len = ftell(f); fseek(f, 0, SEEK_SET);
    b = malloc(*len);
    if (fread(b, 1, *len, f) != (size_t)*len) { fclose(f); free(b); return NULL; }
    fclose(f);
    return b;
}

#define U16(p) ((uint16_t)((p)[0] | ((p)[1] << 8)))

static void put32(uint8_t *p, uint32_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24); }

static long clock_;                       /* samples rendered since play */

/* The driver publishes the next row to play: row n sounds while it says n + 1. */
static int playing(const Chip *c, int order, int row) { return c->gbm.order == order && c->gbm.row == row + 1; }

/* Renders until `order`/`row` is the row sounding: returns the sample count
   then, or -1 if it never is. */
static long until(Chip *c, int order, int row)
{
    long limit = clock_ + 44100 * 4;
    while (clock_ < limit) {
        if (playing(c, order, row)) return clock_;
        chip_render(c, L, R, 32);
        clock_ += 32;
    }
    return -1;
}

/* A voice's channel volume, less the song's amplification. */
static float lvl(const Chip *c, int i) { return c->vox.v[i].level * 16.0f / (float)c->gbm.mix; }

static void driver_tests(const char *probe, const char *bankpath)
{
    static Chip c;
    long len = 0, blen = 0, t0, t8, t;
    uint8_t *blob = slurp(probe, &len), *bank = slurp(bankpath, &blen), *bad;
    const Gbm *g = &c.gbm;
    const Vox *x = &c.vox;
    uint32_t lo = 0xFFFFFFFF, hi = 0, f0;
    CHECK(blob && bank, "the probe song and the SFX bank");
    if (!blob || !bank) return;

    /* the blob's own checks reach into the samples */
    CHECK(blob[2] == 3 && gbm_check(blob, (uint32_t)len) == 0, "the probe is format 3 and passes gbm_check");
    bad = malloc(len);
    {
        const uint8_t *h = blob + U16(blob + U16(blob + 22));
        long at = h - blob;
        memcpy(bad, blob, len); put32(bad + at + 8, (uint32_t)len - 100);
        CHECK(gbm_check(bad, (uint32_t)len) != 0, "a sample running past the blob is refused");
        memcpy(bad, blob, len); put32(bad + at + 12, 0);
        CHECK(gbm_check(bad, (uint32_t)len) != 0, "an empty sample is refused");
        memcpy(bad, blob, len); bad[at] = 1; put32(bad + at + 16, 4000); put32(bad + at + 20, 200);
        CHECK(gbm_check(bad, (uint32_t)len) != 0, "a loop past the sample's end is refused");
        memcpy(bad, blob, len); bad[26] = 40;
        CHECK(gbm_check(bad, (uint32_t)len) != 0, "a sample table past the blob is refused");
    }
    free(bad);

    chip_init(&c, 44100);
    chip_post(&c, CHIP_SFX_BANK, 0, 0, bank);
    chip_post(&c, CHIP_PLAY, 0, 0, blob);
    chip_render(&c, L, R, 32);
    clock_ = 32;
    CHECK(g->v2 && g->nv == 4, "a format-3 song plays on vox with its 4 voices");
    CHECK(g->tick_cycles == 10485760u / 125, "125 BPM: a tick every %u cycles", g->tick_cycles);
    CHECK(g->mix == 24, "the song's amplification is 24/16 (%d)", g->mix);

    /* row 0 */
    t0 = until(&c, 0, 0);
    CHECK(x->v[0].osc == OSC_PCM && x->v[0].on && x->v[0].from == 4 * 256 && !x->v[0].rev,
          "G1904 starts the note at frame 1024 (%u)", x->v[0].from);
    CHECK(fabs(lvl(&c, 1) - 48.0 / 64) < 1e-6, "a note takes its instrument's volume (48): %.3f", lvl(&c, 1) * 64);
    CHECK(fabs(x->v[1].level - 48.0 / 64 * 1.5) < 1e-6, "amplified by the song's 24/16 (%.3f)", x->v[1].level);
    CHECK(x->v[2].from == 8 * 256, "G1908 on the retriggered voice (%u)", x->v[2].from);
    f0 = c.ticks;
    /* rows 1-7: 902 restarts voice 2 at its offset every 2 ticks */
    {
        int seen = 0;
        while (!playing(&c, 0, 8) && clock_ < t0 + 44100 * 2) {
            uint32_t p = x->v[2].pos >> 12;
            if (p < lo) lo = p;
            if (p > hi) hi = p;
            if (playing(&c, 0, 2) && !(seen & 1)) {
                seen |= 1;
                CHECK(fabs(lvl(&c, 1) - 16.0 / 64) < 1e-6 && x->v[1].on, "G1C10 turns a sounding note down to 16 (%.1f)", lvl(&c, 1) * 64);
            }
            if (playing(&c, 0, 4) && !(seen & 2)) {
                seen |= 2;
                CHECK(x->v[0].rev && x->v[0].step < 0 && x->v[0].from == 0, "G1B01 plays the next note backwards, from the end");
                CHECK(fabs(lvl(&c, 1) - 24.0 / 64) < 1e-6, "a ghost note at G1C18 (%.1f)", lvl(&c, 1) * 64);
            }
            if (playing(&c, 0, 6) && !(seen & 4)) {
                seen |= 4;
                CHECK(fabs(lvl(&c, 1) - 48.0 / 64) < 1e-6, "the next note is back at its instrument's volume (%.1f)", lvl(&c, 1) * 64);
            }
            chip_render(&c, L, R, 32);
            clock_ += 32;
        }
        CHECK(seen == 7, "rows 2, 4 and 6 were seen (%d)", seen);
    }
    t8 = until(&c, 0, 8);
    CHECK(lo >= 2048 && hi < 2048 + 400, "retriggering restarts at the offset, not the start (frames %u-%u)", lo, hi);
    CHECK(labs(t8 - t0 - 35280) <= 64, "8 rows of 5 ticks at 125 BPM take 0.8 s (%ld samples)", t8 - t0);
    CHECK(abs((int)(c.ticks - f0) - 48) <= 1, "while the effects' frame clock keeps 59.73 Hz (%u frames)", c.ticks - f0);
    CHECK(x->v[0].rev && x->v[0].from == 1024 && (x->v[0].pos >> 12) < 1024, "backwards from an offset (frame %u)", x->v[0].pos >> 12);

    /* row 9: the slide has run five ticks; the delayed note took its offset */
    until(&c, 0, 9);
    CHECK(fabs(lvl(&c, 1) * 64 - (48 - 4 * 6)) < 1e-4, "G1A04 slides the volume down 4 a tick, from the note's own (%.1f)", lvl(&c, 1) * 64);
    CHECK(x->v[2].from == 6 * 256, "a delayed note (704) keeps its row's offset (%u)", x->v[2].from);

    /* row 12: pan position */
    until(&c, 0, 12);
    CHECK(x->v[1].bal_l == 1.0f && x->v[1].bal_r == 0.0f, "G1E00 pans hard left (%.2f, %.2f)", x->v[1].bal_l, x->v[1].bal_r);
    CHECK(!x->v[0].rev && x->v[0].from == 0, "a plain note plays forwards from the start");

    /* order 1: G1FFA doubles the tempo */
    until(&c, 1, 1);
    t = clock_;
    until(&c, 1, 9);
    CHECK(g->tick_cycles == 10485760u / 250, "G1FFA: 250 BPM");
    CHECK(labs(clock_ - t - 17640) <= 64, "8 rows now take 0.4 s (%ld samples)", clock_ - t);

    /* an effect from the format-2 bank on a voice the song does not use */
    {
        uint32_t start;
        int frames_song, frames_alone;
        chip_post(&c, CHIP_SFX, 0, 0, NULL);          /* cursor: voice 7 */
        chip_render(&c, L, R, 1000);                  /* its first row is on the next frame */
        CHECK(g->owner[7] != 0xFF && x->v[7].level == 1.0f && vox_level(x, 7) > 0,
              "an effect plays on voice 7 at full volume (%.2f)", x->v[7].level);
        start = c.ticks;
        while (g->owner[7] != 0xFF && c.ticks - start < 600) chip_render(&c, L, R, 64);
        frames_song = (int)(c.ticks - start);
        chip_init(&c, 44100);
        chip_post(&c, CHIP_SFX_BANK, 0, 0, bank);
        chip_post(&c, CHIP_SFX, 0, 0, NULL);
        chip_render(&c, L, R, 64);
        start = c.ticks;
        while (g->owner[7] != 0xFF && c.ticks - start < 600) chip_render(&c, L, R, 64);
        frames_alone = (int)(c.ticks - start);
        CHECK(abs(frames_song - frames_alone) <= 1, "and lasts as long as it does alone: the song's tempo is not its (%d, %d frames)",
              frames_song, frames_alone);
    }

    /* an effect takes a voice the song plays (the probe's own, on voice 3):
       after it the song's sample is not replayed from its start mid-row --
       the voice waits for its next note */
    chip_init(&c, 44100);
    chip_post(&c, CHIP_SFX_BANK, 0, 0, blob);
    chip_post(&c, CHIP_PLAY, 0, 0, blob);
    clock_ = 0;
    until(&c, 0, 1);
    CHECK(x->v[2].on, "voice 3 plays the song's retriggered note");
    chip_post(&c, CHIP_SFX, 0, 0, NULL);
    chip_render(&c, L, R, 1000);
    CHECK(g->owner[2] != 0xFF, "the effect takes voice 3");
    t = clock_;
    while (g->owner[2] != 0xFF && clock_ < t + 44100) { chip_render(&c, L, R, 32); clock_ += 32; }
    chip_render(&c, L, R, 32);
    clock_ += 32;
    CHECK(g->owner[2] == 0xFF && !x->v[2].on, "and gives it back silent: no replay of the song's note");
    until(&c, 0, 6);
    CHECK(!x->v[2].on, "the voice stays silent until its next note");
    until(&c, 0, 9);
    CHECK(x->v[2].on && x->v[2].from == 6 * 256, "which plays as written (row 8, delayed, offset 6)");
    /* a looped sample (voice 2's sine) comes back at once, as a held note does */
    chip_post(&c, CHIP_SFX, 1, 0, NULL);
    chip_render(&c, L, R, 1000);
    CHECK(g->owner[1] != 0xFF, "an effect takes voice 2");
    t = clock_;
    while (g->owner[1] != 0xFF && clock_ < t + 44100) { chip_render(&c, L, R, 32); clock_ += 32; }
    chip_render(&c, L, R, 32 * 30);
    CHECK(x->v[1].on && x->v[1].osc == OSC_PCM && x->v[1].loop_len == 1024,
          "a looped sample is back at once when it ends");

    /* mute: a sampler voice goes quiet and the song keeps time */
    chip_init(&c, 44100);
    chip_post(&c, CHIP_PLAY, 0, 0, blob);
    chip_post(&c, CHIP_MUTE, 0x02, 0, NULL);
    chip_render(&c, L, R, 44100 / 10);
    CHECK(vox_level(x, 1) == 0 && g->ch[1].block && vox_level(x, 0) > 0, "mute silences sampler voice 2, not voice 1");
    chip_post(&c, CHIP_MUTE, 0, 0, NULL);
    chip_render(&c, L, R, 44100 / 20);
    CHECK(vox_level(x, 1) > 0, "and unmuted, its looped sample is back at once");
    /* pause and resume: the loop comes back, the one-shot waits for its note */
    chip_init(&c, 44100);
    chip_post(&c, CHIP_PLAY, 0, 0, blob);
    clock_ = 0;
    until(&c, 0, 1);
    chip_post(&c, CHIP_PAUSE, 1, 0, NULL);
    chip_render(&c, L, R, 4410);
    CHECK(!vox_active(x), "pause silences the song");
    chip_post(&c, CHIP_PAUSE, 0, 0, NULL);
    chip_render(&c, L, R, 1470);
    CHECK(x->v[1].on && !x->v[2].on, "resumed, the looped sine is back, the retriggered one-shot waits (%d, %d)",
          x->v[1].on, x->v[2].on);
    chip_post(&c, CHIP_STOP, 0, 0, NULL);
    chip_render(&c, L, R, 64);
    CHECK(!g->playing && g->tick_cycles == 0, "stop hands the clock back to the frame");
    free(blob);
    free(bank);
}

int main(int argc, char **argv)
{
    synth_tests();
    if (argc > 2) driver_tests(argv[1], argv[2]);
    printf("  v3: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
