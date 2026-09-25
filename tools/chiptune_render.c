/* chiptune_render: a GBM song or sound effect to a WAV file, on the host.

     chiptune_render song.gbm out.wav [--loops N | --seconds S] [--rate R]
                                      [--mono] [--adpcm] [--from ORDER]
     chiptune_render bank.gbm out.wav --sfx ID [--rate R] [--mono] [--adpcm]

   It runs the same chiptune/ sources the game does, so what it writes is
   what the device plays. Two uses: listening without a Playdate, and games
   that do not want the C extension -- render the music once, play it with
   Jukebox (a looping song prints where its loop starts, for
   fileplayer:setLoopRange), and effects with a sampleplayer.

   --adpcm writes 4-bit IMA ADPCM, which pdc keeps as it is: a quarter of the
   size of 16-bit PCM, and what the Playdate decodes natively. */
#define _CRT_SECURE_NO_WARNINGS
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "../chiptune/chip.h"

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

static void put16(FILE *f, int v) { fputc(v & 255, f); fputc((v >> 8) & 255, f); }
static void put32(FILE *f, uint32_t v) { put16(f, v & 0xFFFF); put16(f, (int)(v >> 16)); }

/* ─── IMA ADPCM (the Microsoft WAV flavour: blocks with a header each) ─── */

static const int STEPS[89] = {7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,34,37,41,45,50,55,60,66,73,80,88,97,107,118,130,143,157,173,190,209,230,253,279,307,337,371,408,449,494,544,598,658,724,796,876,963,1060,1166,1282,1411,1552,1707,1878,2066,2272,2499,2749,3024,3327,3660,4026,4428,4871,5358,5894,6484,7132,7845,8630,9493,10442,11487,12635,13899,15289,16818,18500,20350,22385,24623,27086,29794,32767};
static const int INDEX[16] = {-1,-1,-1,-1,2,4,6,8,-1,-1,-1,-1,2,4,6,8};

typedef struct { int pred, index; } Ima;

static int ima_nibble(Ima *s, int x)
{
    int step = STEPS[s->index], diff = x - s->pred, code = 0, d = step >> 3;
    if (diff < 0) { code = 8; diff = -diff; }
    if (diff >= step) { code |= 4; diff -= step; d += step; }
    step >>= 1;
    if (diff >= step) { code |= 2; diff -= step; d += step; }
    step >>= 1;
    if (diff >= step) { code |= 1; d += step; }
    s->pred += (code & 8) ? -d : d;
    if (s->pred > 32767) s->pred = 32767;
    if (s->pred < -32768) s->pred = -32768;
    s->index += INDEX[code];
    if (s->index < 0) s->index = 0;
    if (s->index > 88) s->index = 88;
    return code;
}

#define BLOCK 1024                 /* bytes per block per channel group */

static void write_wav(const char *path, const int16_t *pcm, uint32_t frames, int chans, uint32_t rate, int adpcm)
{
    FILE *f = fopen(path, "wb");
    uint32_t data;
    if (!f) { fprintf(stderr, "cannot write %s\n", path); exit(1); }
    if (!adpcm) {
        data = frames * chans * 2;
        fwrite("RIFF", 1, 4, f); put32(f, 36 + data); fwrite("WAVEfmt ", 1, 8, f);
        put32(f, 16); put16(f, 1); put16(f, chans); put32(f, rate); put32(f, rate * chans * 2);
        put16(f, chans * 2); put16(f, 16);
        fwrite("data", 1, 4, f); put32(f, data);
        fwrite(pcm, 2, (size_t)frames * chans, f);
    } else {
        /* Each block: per channel a 4-byte header (first sample, index), then
           groups of 8 samples as 4 bytes per channel, interleaved. */
        int per_block = (BLOCK - 4 * chans) * 8 / (4 * chans) + 1;
        uint32_t blocks = (frames + per_block - 1) / per_block, b;
        Ima st[2] = {{0, 0}, {0, 0}};
        data = blocks * BLOCK;
        fwrite("RIFF", 1, 4, f); put32(f, 4 + 28 + 12 + 8 + data); fwrite("WAVEfmt ", 1, 8, f);
        put32(f, 20); put16(f, 0x11); put16(f, chans); put32(f, rate);
        put32(f, (uint32_t)((uint64_t)rate * BLOCK / per_block)); put16(f, BLOCK); put16(f, 4);
        put16(f, 2); put16(f, per_block);
        fwrite("fact", 1, 4, f); put32(f, 4); put32(f, frames);
        fwrite("data", 1, 4, f); put32(f, data);
        for (b = 0; b < blocks; b++) {
            uint8_t out[BLOCK];
            int c, n = 4 * chans, i;
            uint32_t base = b * per_block;
            memset(out, 0, sizeof out);
            for (c = 0; c < chans; c++) {
                int16_t first = base < frames ? pcm[base * chans + c] : 0;
                st[c].pred = first;
                out[c * 4] = (uint8_t)(first & 255); out[c * 4 + 1] = (uint8_t)((first >> 8) & 255);
                out[c * 4 + 2] = (uint8_t)st[c].index; out[c * 4 + 3] = 0;
            }
            for (i = 1; i < per_block; i += 8) {
                for (c = 0; c < chans; c++) {
                    int k;
                    for (k = 0; k < 8; k++) {
                        uint32_t at = base + i + k;
                        int x = at < frames ? pcm[at * chans + c] : 0;
                        int code = ima_nibble(&st[c], x);
                        out[n + k / 2] |= (uint8_t)(k & 1 ? code << 4 : code);
                    }
                    n += 4;
                }
            }
            fwrite(out, 1, BLOCK, f);
        }
    }
    fclose(f);
}

int main(int argc, char **argv)
{
    const char *in = NULL, *out = NULL;
    int loops = 1, sfx = -1, mono = 0, adpcm = 0, from = 0, mute = 0, bench = 0, i;
    const char *with = NULL;
    uint8_t *bank = NULL;
    double seconds = 0;
    uint32_t rate = 44100, cap, n = 0;
    long len;
    uint8_t *blob;
    int16_t *l, *r;
    static Chip chip;
    for (i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--loops") && i + 1 < argc) loops = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--seconds") && i + 1 < argc) seconds = atof(argv[++i]);
        else if (!strcmp(argv[i], "--rate") && i + 1 < argc) rate = (uint32_t)atoi(argv[++i]);
        else if (!strcmp(argv[i], "--sfx") && i + 1 < argc) sfx = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--from") && i + 1 < argc) from = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--mute") && i + 1 < argc) mute = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--mono")) mono = 1;
        else if (!strcmp(argv[i], "--bench")) bench = 1;
        else if (!strcmp(argv[i], "--with") && i + 1 < argc) with = argv[++i];
        else if (!strcmp(argv[i], "--adpcm")) adpcm = 1;
        else if (!in) in = argv[i];
        else if (!out) out = argv[i];
    }
    if (!in || !out) {
        fprintf(stderr, "usage: chiptune_render in.gbm out.wav [--loops N|--seconds S] [--sfx ID] [--rate R] [--mono] [--adpcm] [--from ORDER]\n");
        return 2;
    }
    if (!(blob = slurp(in, &len)) || gbm_check(blob, (uint32_t)len)) { fprintf(stderr, "%s: not a GBM blob\n", in); return 1; }
    chip_init(&chip, rate);
    /* --with BANK: load an SFX bank first, as a game would -- a format-2
       bank moves a format-1 song onto vox, and this hears it there. */
    if (with) {
        long blen;
        if (!(bank = slurp(with, &blen)) || gbm_check(bank, (uint32_t)blen)) { fprintf(stderr, "%s: not a GBM blob\n", with); return 1; }
        chip_post(&chip, CHIP_SFX_BANK, 0, 0, bank);
    }
    if (sfx >= 0) {
        if (sfx >= blob[6]) { fprintf(stderr, "%s has %d effects\n", in, blob[6]); return 1; }
        chip_post(&chip, CHIP_SFX_BANK, 0, 0, blob);
        chip_post(&chip, CHIP_SFX, (uint8_t)sfx, 0, NULL);
    } else {
        if (!blob[4]) { fprintf(stderr, "%s has no song, only effects: use --sfx\n", in); return 1; }
        chip_post(&chip, CHIP_PLAY, (uint8_t)from, 0, blob);
        if (mute) chip_post(&chip, CHIP_MUTE, (uint8_t)mute, 0, NULL);
    }
    if (bench) {
        /* The cost of the callback: 60 s of song in 256-sample buffers, as the
           Playdate asks for them, timed; nothing written. */
        static int16_t bl[256], br[256];
        uint32_t k, total = rate * 60;
        clock_t t0 = clock();
        for (k = 0; k < total; k += 256) chip_render(&chip, bl, br, 256);
        {
            double s = (double)(clock() - t0) / CLOCKS_PER_SEC;
            printf("%s: %s, %.1f ns a sample, %.0fx real time on this machine\n", in,
                   chip.gbm.v2 ? "vox" : "gbapu", s * 1e9 / total, 60.0 / s);
        }
        return 0;
    }
    cap = (uint32_t)(rate * (seconds > 0 ? seconds : 600));
    l = malloc(cap * sizeof *l); r = malloc(cap * sizeof *r);
    {
        /* Tick by tick, watching the song: a loop is the driver entering the
           loop order from a later one. */
        int wraps = 0, last_order = -1, silent = 0, entered = 0;
        uint32_t loop_at = 0, step = rate / 60;
        const Gbm *g = &chip.gbm;
        while (n + step <= cap) {
            int played = chip_render(&chip, l + n, r + n, (int)step);
            if (!played) { memset(l + n, 0, step * 2); memset(r + n, 0, step * 2); }
            n += step;
            if (seconds > 0) continue;
            if (sfx < 0 && g->playing) {
                if (last_order >= 0 && g->order < last_order && ++wraps >= loops) {
                    n -= step;             /* the tick that wrapped belongs to the next pass */
                    break;
                }
                /* where the loop begins: the first time its order plays */
                if (!entered && g->order == g->loop_order) { entered = 1; loop_at = n - step; }
                last_order = g->order;
            } else if (!played || (!g->playing && !g->ch[4].prio && !g->ch[5].prio && !gbapu_active(&chip.apu))) {
                /* the end: let the DC blocker settle for a moment */
                if (++silent > 6) break;
            }
        }
        if (sfx < 0 && entered && wraps)
            printf("%s: %.3f s, loop starts at %.3f s (sample %u)\n", out, (double)n / rate, (double)loop_at / rate, loop_at);
        else
            printf("%s: %.3f s\n", out, (double)n / rate);
    }
    {
        int chans = mono ? 1 : 2;
        int16_t *pcm = malloc((size_t)n * chans * sizeof *pcm);
        uint32_t k;
        for (k = 0; k < n; k++) {
            if (mono) pcm[k] = (int16_t)(((int32_t)l[k] + r[k]) / 2);
            else { pcm[k * 2] = l[k]; pcm[k * 2 + 1] = r[k]; }
        }
        write_wav(out, pcm, n, chans, rate, adpcm);
    }
    return 0;
}
