/* Check the composed envelope macros as the real driver executes them. */
#define _CRT_SECURE_NO_WARNINGS
#include <stdio.h>
#include <stdlib.h>
#include "../../chiptune/chip.h"

static int fails;
#define REQUIRE(c) do { if (!(c)) { printf("frame %d: %s\n", frame, #c); fails++; } } while (0)

static void check(const char *path, int solo)
{
    FILE *f = fopen(path, "rb");
    long n;
    unsigned char *blob;
    static Chip chip;
    int frame;
    if (!f) { fails++; return; }
    fseek(f, 0, SEEK_END); n = ftell(f); rewind(f);
    blob = malloc((size_t)n);
    if (!blob || fread(blob, 1, (size_t)n, f) != (size_t)n) { fclose(f); free(blob); fails++; return; }
    fclose(f);
    chip_init(&chip, 44100);
    chip_post(&chip, CHIP_PLAY, 0, 0, blob);
    chip_drain(&chip);
    for (frame = 0; frame < 64; frame++) {
        gbm_tick(&chip.gbm);
        if (!solo) {
            REQUIRE(chip.vox.v[0].vol == 14 - frame / 16);
            REQUIRE(chip.vox.v[1].vol == 10 - frame / 18);
            REQUIRE(chip.vox.v[2].vol == 15);
            REQUIRE(chip.vox.v[3].vol == (frame == 0 ? 15 : frame == 1 ? 5 : 0));
        } else {
            int riff = 14 - frame / 4, snare = frame / 2 < 4 ? 15 - 4 * (frame / 2) : 0;
            REQUIRE(chip.vox.v[0].vol == (riff > 0 ? riff : 0));
            REQUIRE(chip.vox.v[1].vol == 15 - 3 * (frame / 21));
            REQUIRE(chip.vox.v[3].vol == snare);
        }
    }
    free(blob);
}

int main(int argc, char **argv)
{
    if (argc != 3) return 2;
    check(argv[1], 0);
    check(argv[2], 1);
    printf("NES envelope timing: %s\n", fails ? "FAILED" : "passed");
    return fails ? 1 : 0;
}
