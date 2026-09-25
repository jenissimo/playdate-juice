/* Format 2 and vox. There is no original to hold these to, so they test
   what the features promise: a note sounds at its pitch, a width is a
   width, the filter filters, a table switches the oscillator, PWM moves,
   an effect on a spare voice takes nothing from the music.

     v2_test <probe.gbm>     (tools/chiptune.py test writes the probe) */
#define _CRT_SECURE_NO_WARNINGS
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../../chiptune/chip.h"

static int checks, fails;
#define CHECK(cond, ...) do { checks++; if (!(cond)) { fails++; printf("  FAIL: " __VA_ARGS__); printf("\n"); } } while (0)

static int16_t L[44100 * 2], R[44100 * 2];

/* Zero crossings (upward) a second: the pitch of a clean tone. */
static double upward_rate(const int16_t *x, int n, int rate)
{
    int i, c = 0;
    double mean = 0;
    for (i = 0; i < n; i++) mean += x[i];
    mean /= n;
    for (i = 1; i < n; i++) if (x[i - 1] < mean && x[i] >= mean) c++;
    return (double)c * rate / n;
}

/* The period by autocorrelation: for waves with more than one crossing a cycle. */
static double acf_pitch(const int16_t *x, int n, int rate)
{
    /* the first lag within 5% of the best: every multiple of the period
       correlates about as well as the period itself */
    static double sums[400];
    int lag, i;
    double top = -1e300;
    (void)n;
    for (lag = 40; lag < 400; lag++) {
        double sum = 0;
        for (i = 0; i < 8192; i++) sum += (double)x[i] * x[i + lag];
        sums[lag] = sum;
        if (sum > top) top = sum;
    }
    for (lag = 41; lag < 399; lag++)
        if (sums[lag] >= 0.95 * top && sums[lag] >= sums[lag - 1] && sums[lag] >= sums[lag + 1]) break;
    return (double)rate / lag;
}

static double energy(const int16_t *x, int n)
{
    double e = 0;
    int i;
    for (i = 1; i < n; i++) { double d = (double)x[i] - x[i - 1]; e += d * d; }
    return e / n;
}

static void synth_tests(void)
{
    static Vox x;
    int n = 44100;
    double hz, pos, e_open, e_closed;
    int i;
    /* A4 is period 1750: 131072 / 298 = 439.8 Hz */
    vox_init(&x, 44100);
    vox_trigger(&x, 0, OSC_PULSE, 1750, 0xF0);
    vox_render(&x, L, R, n);
    hz = upward_rate(L, n, 44100);
    CHECK(hz > 435 && hz < 445, "pulse A4 at %.1f Hz", hz);
    /* the wave oscillator runs an octave lower for the same period */
    vox_init(&x, 44100);
    {
        static const uint8_t tri[16] = {0x01,0x23,0x45,0x67,0x89,0xAB,0xCD,0xEF,0xFE,0xDC,0xBA,0x98,0x76,0x54,0x32,0x10};
        vox_wave(&x, 0, tri);
    }
    vox_trigger(&x, 0, OSC_WAVE, 1750, 0xF0);
    vox_render(&x, L, R, n);
    hz = upward_rate(L, n, 44100);
    CHECK(hz > 217 && hz < 223, "wave at %.1f Hz, half the pulse's", hz);
    for (i = OSC_TRIANGLE; i <= OSC_SAW; i++) {
        vox_init(&x, 44100);
        vox_trigger(&x, 0, (uint8_t)i, 1750, 0xF0);
        vox_render(&x, L, R, n);
        hz = upward_rate(L, n, 44100);
        CHECK(hz > 435 && hz < 445, "oscillator %d at %.1f Hz", i, hz);
    }
    /* width: the share of time the pulse is high */
    vox_init(&x, 44100);
    vox_width(&x, 0, 64);
    vox_trigger(&x, 0, OSC_PULSE, 1024, 0xF0);
    vox_render(&x, L, R, n);
    for (i = 0, pos = 0; i < n; i++) if (L[i] > 0) pos++;
    CHECK(pos / n > 0.21 && pos / n < 0.29, "width 64/256 is high %.0f%% of the time", 100 * pos / n);
    /* the filter: a closed low-pass takes the edge off a saw */
    vox_init(&x, 44100);
    vox_trigger(&x, 0, OSC_SAW, 1750, 0xF0);
    vox_render(&x, L, R, n);
    e_open = energy(L, n);
    vox_init(&x, 44100);
    vox_filter(&x, 60, 2, VOX_LP);
    vox_flags(&x, 0, VOX_FILTER);
    vox_trigger(&x, 0, OSC_SAW, 1750, 0xF0);
    vox_render(&x, L, R, n);
    e_closed = energy(L, n);
    CHECK(e_closed < e_open * 0.1, "low-pass at 60 leaves %.3f of the saw's edge", e_closed / e_open);
    /* envelope: a decaying note is quieter a second later */
    vox_init(&x, 44100);
    vox_trigger(&x, 0, OSC_PULSE, 1750, 0xF2);
    vox_render(&x, L, R, 500);        /* the first step is 2/64 s away */
    CHECK(vox_level(&x, 0) == 15, "full at the start (%d)", vox_level(&x, 0));
    vox_render(&x, L, R, 44100);
    CHECK(vox_level(&x, 0) == 0, "faded after a second (%d)", vox_level(&x, 0));
    /* volume 0 decreasing is the DAC off: no sound at all */
    vox_init(&x, 44100);
    vox_trigger(&x, 0, OSC_PULSE, 1750, 0x00);
    CHECK(!vox_active(&x), "an envelope of 0 does not sound");
    /* sync: voice 1 restarts with voice 0, so its pitch is voice 0's */
    vox_init(&x, 44100);
    vox_trigger(&x, 0, OSC_PULSE, 1750, 0x10);
    x.v[0].vol = 0;                                    /* the master runs, inaudible */
    vox_flags(&x, 1, VOX_SYNC);
    vox_trigger(&x, 1, OSC_SAW, 1850, 0xF0);           /* 662 Hz: 1.5x, so sync shows */
    vox_render(&x, L, R, n);
    hz = acf_pitch(L, n, 44100);
    CHECK(hz > 430 && hz < 450, "hard sync pulls the saw to the master's %.1f Hz", hz);
    /* render reports cycles like gbapu: a second is 4194304 of them */
    vox_init(&x, 44100);
    {
        uint32_t c = 0;
        for (i = 0; i < 100; i++) c += vox_render(&x, L, R, 441);
        CHECK(c == 4194304u, "a second of render is %u cycles", c);
    }
}

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

/* The probe song (tools/chiptune.py): 6 voices -- a PWM pulse, a filtered saw
   with a cutoff slide, a triangle arpeggio, SID drums, hats, a sampled kick
   -- and an effect on voice 7. */
static void driver_tests(const char *probe)
{
    static Chip c;
    long len = 0;
    uint8_t *blob = slurp(probe, &len);
    int f, seen[8] = {0}, noise_frames = 0, tri_frames = 0, w0, wmoved = 0, cut0;
    Gbm *g = &c.gbm;
    CHECK(blob != NULL, "the probe song");
    if (!blob) return;
    CHECK(gbm_check(blob, (uint32_t)len) == 0, "the probe passes gbm_check");
    chip_init(&c, 44100);
    chip_post(&c, CHIP_PLAY, 0, 0, blob);
    chip_post(&c, CHIP_SFX_BANK, 0, 0, blob);
    chip_render(&c, L, R, 10);
    CHECK(g->v2 && g->nv == 6, "a format-2 song runs on vox with its 6 voices (v2 %d, nv %d)", g->v2, g->nv);
    w0 = g->ch[0].duty;
    cut0 = c.vox.cutoff;
    for (f = 0; f < 120; f++) {
        int i;
        chip_render(&c, L, R, 735);
        for (i = 0; i < 8; i++) if (vox_level(&c.vox, i)) seen[i] = 1;
        if (g->ch[3].flags & 0x80) {
            if (g->ch[3].osc == OSC_NOISE) noise_frames++;
            if (g->ch[3].osc == OSC_TRIANGLE) tri_frames++;
        }
        if (g->ch[0].duty != w0) wmoved = 1;
    }
    CHECK(seen[0] && seen[1] && seen[2] && seen[3] && seen[4] && seen[5], "all six voices sound (%d%d%d%d%d%d)",
          seen[0], seen[1], seen[2], seen[3], seen[4], seen[5]);
    CHECK(!seen[6] && !seen[7], "and the two spare voices stay quiet");
    CHECK(noise_frames > 0 && tri_frames > 0, "the SID kick's table switches noise -> triangle (%d, %d frames)",
          noise_frames, tri_frames);
    CHECK(wmoved, "PWM moves the lead's width");
    CHECK(c.vox.cutoff != cut0, "the cutoff slide moved the filter (%d -> %d)", cut0, c.vox.cutoff);
    /* an effect on voice 7, which the song does not use: nothing is stolen */
    chip_post(&c, CHIP_SFX, 0, 0, NULL);
    chip_render(&c, L, R, 735 * 2);
    CHECK(g->owner[7] != 0xFF, "the effect holds voice 7");
    {
        int i, blocked = 0;
        for (i = 0; i < 6; i++) blocked |= g->ch[i].block;
        CHECK(!blocked, "and no music voice is blocked");
    }
    CHECK(vox_level(&c.vox, 7) > 0, "voice 7 sounds");
    chip_render(&c, L, R, 735 * 30);
    CHECK(g->owner[7] == 0xFF, "the effect ends and lets voice 7 go");
    /* mute: a format-2 song's fifth voice is mutable too */
    chip_post(&c, CHIP_MUTE, 0x10, 0, NULL);
    chip_render(&c, L, R, 735 * 20);
    CHECK(vox_level(&c.vox, 4) == 0 && g->ch[4].block, "mute silences voice 5");
    free(blob);
}

int main(int argc, char **argv)
{
    synth_tests();
    if (argc > 1) driver_tests(argv[1]);
    printf("  v2: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
