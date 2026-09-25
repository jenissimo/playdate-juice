/* The GBM port against the original, write for write.

   Each fixture in test/chiptune/golden was captured from gameboy-lab's
   music-box ROM running in binjgb (tools/chiptune.py documents how): the
   song blob, the host commands and the frame each took effect in (.scn),
   every APU register write the ROM made, by frame (.trace), and the
   driver's state at the end of each frame (.state). This replays the same
   commands through the port and demands the same writes in the same order
   on the same frame, and the same state.

   One thing cannot be replayed exactly: when the drum-sample timer fires.
   It runs off the Game Boy's DIV counter, whose phase against the frame is
   a fact about that ROM's boot, not about the driver. So the timer's blocks
   are placed from the recorded state (a block is due when the ROM's sample
   counter says it played), and within a frame they may fall between any two
   of the driver's writes, as an interrupt would. Everything else is exact.

   Wave RAM writes are not compared: binjgb does not log them. The sound
   test (sound_test.c) covers what is in wave RAM through what it plays. */
#define _CRT_SECURE_NO_WARNINGS
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../../chiptune/gbm.h"

typedef struct { uint16_t frame, addr; uint8_t val; int block; } Wr;
typedef struct { Wr *v; int n, cap; } Wrs;

static void push(Wrs *w, Wr x)
{
    if (w->n == w->cap) { w->cap = w->cap ? w->cap * 2 : 4096; w->v = realloc(w->v, w->cap * sizeof *w->v); }
    w->v[w->n++] = x;
}

static Wrs mine, timer;
static int cur_frame, in_isr, ti_used, cur_block;

static void hook(void *user, uint16_t addr, uint8_t v)
{
    Wr w;
    (void)user;
    if (addr >= 0xFF30) return;
    w.frame = (uint16_t)cur_frame; w.addr = addr; w.val = v; w.block = in_isr ? cur_block : -1;
    push(in_isr ? &timer : &mine, w);
}

static uint8_t *slurp(const char *path, long *len)
{
    FILE *f = fopen(path, "rb");
    uint8_t *b;
    if (!f) return NULL;
    fseek(f, 0, SEEK_END); *len = ftell(f); fseek(f, 0, SEEK_SET);
    b = malloc(*len + 1);
    if (fread(b, 1, *len, f) != (size_t)*len) { fclose(f); free(b); return NULL; }
    b[*len] = 0;
    fclose(f);
    return b;
}

typedef struct { int frame; char cmd[16]; int a, b, done; } Cmd;

/* Can E[e..] be matched by all of M[m..] interleaved with the timer's
   writes T[t..]? The timer's stream need not be used up: a block the ROM
   began just before the frame ended finishes in the next one. */
/* t: the whole stream. The frame runs as the ROM does: timer blocks due
   before its VBlank (up to tpre), then the tick with interrupts off (M up to
   mtick, unbroken), then the main loop's commands with the timer free to
   cut in. */
typedef struct { const Wr *e; int ne; const Wr *m; int nm; int mtick; const Wr *t; int nt; int tpre; int used; } Frame;

static int eq(const Wr *x, const Wr *y) { return x->addr == y->addr && x->val == y->val; }

static int fit(Frame *f, int e, int m, int t, int depth)
{
    if (depth > 20000) return 0;
    if (e == f->ne) { if (m != f->nm) return 0; f->used = t; return 1; }
    /* An interrupt handler runs to the end: inside a block only the block
       goes on (a frame may still end in it). */
    if (t > 0 && t < f->nt && f->t[t].block == f->t[t - 1].block)
        return eq(&f->e[e], &f->t[t]) && fit(f, e + 1, m, t + 1, depth + 1);
    if (m < f->nm && t >= f->tpre
        && eq(&f->e[e], &f->m[m]) && fit(f, e + 1, m + 1, t, depth + 1)) return 1;
    if (t < f->nt && (t < f->tpre ? m == 0 : m >= f->mtick)
        && eq(&f->e[e], &f->t[t]) && fit(f, e + 1, m, t + 1, depth + 1)) return 1;
    return 0;
}

static void dump(const char *label, const Wr *w, int n)
{
    int i;
    printf("    %s:", label);
    for (i = 0; i < n; i++) printf(" %02X=%02X", w[i].addr & 0xFF, w[i].val);
    printf("\n");
}

static int run(const char *dir, const char *name)
{
    char path[512], line[256];
    long slen = 0, tlen = 0, blen = 0, stlen = 0, sfxlen = 0;
    uint8_t *scn, *trace, *blob = NULL, *sfx = NULL, *state;
    Cmd cmds[256];
    int ncmd = 0, frames = 0, duck_a = 0, duck_s = 1, nr51 = 0xFF, f, ti = 0, failed = 0;
    GbApu apu;
    Gbm g;
    char *p;

    snprintf(path, sizeof path, "%s/%s.scn", dir, name);
    if (!(scn = slurp(path, &slen))) { printf("  %s: no %s\n", name, path); return 1; }
    for (p = (char *)scn; *p;) {
        char *nl = strchr(p, '\n'), word[64], arg[256];
        int len = nl ? (int)(nl - p) : (int)strlen(p);
        if (len >= (int)sizeof line) len = sizeof line - 1;
        memcpy(line, p, len); line[len] = 0;
        p = nl ? nl + 1 : p + len;
        if (line[0] == '#' || !line[0]) continue;
        if (sscanf(line, "%63s %255s", word, arg) < 1) continue;
        if (!strcmp(word, "song")) { snprintf(path, sizeof path, "%s/%s", dir, arg); blob = slurp(path, &blen); }
        else if (!strcmp(word, "sfxbank")) { snprintf(path, sizeof path, "%s/%s", dir, arg); sfx = slurp(path, &sfxlen); }
        else if (!strcmp(word, "duck")) sscanf(line, "duck %d %d", &duck_a, &duck_s);
        else if (!strcmp(word, "nr51")) nr51 = atoi(arg);
        else if (!strcmp(word, "frames")) frames = atoi(arg);
        else {
            Cmd *c = &cmds[ncmd++];
            c->a = c->b = c->done = 0;
            sscanf(line, "%d %15s %d %d", &c->frame, c->cmd, &c->a, &c->b);
        }
    }
    snprintf(path, sizeof path, "%s/%s.trace", dir, name);
    trace = slurp(path, &tlen);
    snprintf(path, sizeof path, "%s/%s.state", dir, name);
    state = slurp(path, &stlen);
    if (!blob || !sfx || !trace || !state) { printf("  %s: missing fixture files\n", name); return 1; }
    if (gbm_check(blob, (uint32_t)blen) || gbm_check(sfx, (uint32_t)sfxlen)) { printf("  %s: blob fails gbm_check\n", name); return 1; }

    mine.n = 0; timer.n = 0; cur_block = 0;
    cur_frame = 0; in_isr = 0; ti_used = 0;
    gbapu_init(&apu, 44100);
    gbm_init(&g, &apu, NULL);
    gbm_duck(&g, (uint8_t)duck_a, (uint8_t)duck_s);
    gbm_sfx_bank(&g, sfx);
    gbm_pcm_timer(&g);
    g.nr51 = (uint8_t)nr51;          /* the boot song's last pan, as the ROM left it */
    apu.hook = hook;

    for (f = 0; f < frames && !failed; f++) {
        const uint8_t *st = state + f * 8;
        static Wr e[4096];
        int ne = 0, k, pre = 0, ok = 0, tpre = 0, mtick = 0, variant;
        Gbm g0 = g;
        GbApu a0 = apu;
        int mn0 = mine.n, tn0 = timer.n, cb0 = cur_block;
        Frame fr;
        cur_frame = f;
        while (ti < tlen && (trace[ti] | trace[ti + 1] << 8) == f) {
            e[ne].addr = (uint16_t)(0xFF10 + trace[ti + 2]); e[ne].val = trace[ti + 3]; e[ne].frame = (uint16_t)f; e[ne].block = -1;
            ne++; ti += 4;
        }
        /* How many of the frame's timer interrupts came before its VBlank
           tick? It matters only when the tick starts or ends a sample, and
           the log cannot say (the tick's own first block looks the same), so
           try each count and keep the one that reproduces the frame. */
        for (variant = 0; variant < 18 && !ok; variant++) {
            /* The ROM acknowledges a command after running it, so one run at
               the very end of a frame is logged against the next: let the
               next frame's commands run in this one too. */
            int early = variant >= 9;
            pre = variant % 9;
            g = g0; apu = a0; mine.n = mn0; timer.n = tn0; cur_block = cb0;
            in_isr = 1;
            for (k = 0; k < pre && g.timer_irq; k++) { cur_block++; gbm_pcm_isr(&g); }
            in_isr = 0;
            if (k < pre) break;
            tpre = timer.n;
            gbm_tick(&g);
            mtick = mine.n - mn0;
            for (k = 0; k < ncmd; k++) {
                Cmd *c = &cmds[k];
                if (c->done || (c->frame != f && !(early && c->frame == f + 1))) continue;
                if (!strcmp(c->cmd, "play")) { gbm_play(&g, blob); gbm_seek(&g, (uint8_t)c->a, (uint8_t)c->b); }
                else if (!strcmp(c->cmd, "stop")) gbm_stop(&g);
                else if (!strcmp(c->cmd, "pause")) gbm_pause(&g, 1);
                else if (!strcmp(c->cmd, "resume")) gbm_pause(&g, 0);
                else if (!strcmp(c->cmd, "sfx")) gbm_sfx(&g, (uint8_t)c->a);
                else if (!strcmp(c->cmd, "sfxsong")) { gbm_sfx_bank(&g, blob); gbm_sfx(&g, (uint8_t)c->a); }
                else if (!strcmp(c->cmd, "mute")) gbm_mute(&g, (uint8_t)c->a);
                else if (!strcmp(c->cmd, "hold")) g.hold = (uint8_t)c->a;
            }
            /* The rest of the frame's blocks: as many as the ROM's sample
               counter says it played. */
            in_isr = 1;
            while (g.timer_irq && g.pcm_left > st[4]) { cur_block++; gbm_pcm_isr(&g); }
            if (g.timer_irq && st[6] && !g.pcm_done && !g.pcm_left) { cur_block++; gbm_pcm_isr(&g); }
            in_isr = 0;
            g.timer_restart = 0;
            fr.e = e; fr.ne = ne; fr.m = mine.v + mn0; fr.nm = mine.n - mn0; fr.t = timer.v; fr.nt = timer.n; fr.used = ti_used; fr.tpre = tpre; fr.mtick = mtick;
            ok = fit(&fr, 0, 0, ti_used, 0) && g.pcm_left == st[4] && g.pcm_active == st[5] && g.pcm_done == st[6];
        }
        for (k = 0; ok && k < ncmd; k++)
            if (cmds[k].frame == f || (variant > 9 && cmds[k].frame == f + 1)) cmds[k].done = 1;
        if (!ok) {
            printf("  %s: frame %d: writes differ (shown: no interrupt before the tick)\n", name, f);
            g = g0; apu = a0; mine.n = mn0; timer.n = tn0; cur_block = cb0;
            gbm_tick(&g);
            dump("rom  ", e, ne);
            dump("port ", mine.v + mn0, mine.n - mn0);
            dump("timer", timer.v + ti_used, timer.n - ti_used < 40 ? timer.n - ti_used : 40);
            failed = 1;
            break;
        }
        if (getenv("TRACE_AT") && f >= atoi(getenv("TRACE_AT")) - 3 && f <= atoi(getenv("TRACE_AT"))) {
            printf("  frame %d: %d interrupt(s) before the tick, pcm_left %d\n", f, pre - 1, g.pcm_left);
            dump("rom  ", e, ne);
            dump("port ", mine.v + mn0, mine.n - mn0);
            dump("timer", timer.v + ti_used, timer.n - ti_used < 40 ? timer.n - ti_used : 40);
        }
        ti_used = fr.used;
        {
            uint8_t got[8] = {g.order, g.row, g.sync, g.playing, g.pcm_left, g.pcm_active, g.pcm_done, g.duck_level};
            static const char *what[8] = {"order", "row", "sync", "playing", "pcm_left", "pcm_active", "pcm_done", "duck_level"};
            /* A command split across the frame line was mid-way when the ROM
               was read: its state is compared from the next frame on. */
            for (k = 0; k < 8 && !failed && variant <= 9; k++)
                if (got[k] != st[k]) {
                    printf("  %s: frame %d: %s is %d, the ROM had %d\n", name, f, what[k], got[k], st[k]);
                    failed = 1;
                }
        }
    }
    if (!failed && timer.n - ti_used > 5) { printf("  %s: %d timer writes the ROM never made\n", name, timer.n - ti_used); failed = 1; }
    if (!failed && ti != tlen) { printf("  %s: the ROM made writes past frame %d\n", name, frames); failed = 1; }
    if (!failed) printf("  %s: %ld writes over %d frames match the ROM\n", name, tlen / 4, frames);
    free(scn); free(trace); free(blob); free(sfx); free(state);
    return failed;
}

int main(int argc, char **argv)
{
    int i, fails = 0;
    if (argc < 3) { printf("usage: trace_test <golden dir> <scenario>...\n"); return 2; }
    for (i = 2; i < argc; i++) fails += run(argv[1], argv[i]);
    printf("%d scenario(s), %d failed\n", argc - 2, fails);
    return fails ? 1 : 0;
}
