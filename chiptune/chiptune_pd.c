/* The Playdate side of chiptune: one sound source, and the Lua functions
   chiptune.lua calls (the static class `chiptune_native`).

   Call chiptune_register(pd) from your eventHandler on kEventInitLua, or
   build chiptune_main.c in if the game has no C of its own. */
#include <string.h>
#include "pd_api.h"
#include "chip.h"
#include "chiptune_pd.h"

#define MAX_BLOBS 64

static PlaydateAPI *pd;
static Chip *chip;
static SoundSource *source;
static uint8_t *blobs[MAX_BLOBS];
static int nblobs;

static int render(void *ctx, int16_t *left, int16_t *right, int len)
{
    return chip_render((Chip *)ctx, left, right, len);
}

static int ensure(void)
{
    if (chip) return 1;
    chip = pd->system->realloc(NULL, sizeof *chip);
    if (!chip) return 0;
    chip_init(chip, 44100);
    source = pd->sound->addSource(render, chip, 1);
    return source != NULL;
}

static int arg_u8(int i, int def)
{
    int v;
    if (pd->lua->getArgCount() < i || pd->lua->getArgType(i, NULL) == kTypeNil) return def;
    v = pd->lua->getArgInt(i);
    return v < 0 ? 0 : v > 255 ? 255 : v;
}

static const uint8_t *blob_arg(int i)
{
    int id = pd->lua->getArgInt(i);
    return id >= 1 && id <= nblobs ? blobs[id - 1] : NULL;
}

static int post(uint8_t op, uint8_t a, uint8_t b, const uint8_t *blob)
{
    if (!ensure()) { pd->lua->pushBool(0); return 1; }
    pd->lua->pushBool(chip_post(chip, op, a, b, blob));
    return 1;
}

/* load(bytes) -> id | nil, error. The blob is copied and kept: songs are
   small (a few KB) and the audio thread may be reading one at any moment,
   so nothing is ever freed from under it. */
static int l_load(lua_State *L)
{
    size_t len = 0;
    const char *bytes = pd->lua->getArgBytes(1, &len);
    uint8_t *copy;
    int err;
    (void)L;
    if (!bytes) { pd->lua->pushNil(); pd->lua->pushString("expected the blob's bytes"); return 2; }
    if ((err = gbm_check((const uint8_t *)bytes, (uint32_t)len)) != 0) {
        pd->lua->pushNil(); pd->lua->pushString("not a GBM blob (or damaged)"); return 2;
    }
    if (nblobs >= MAX_BLOBS) { pd->lua->pushNil(); pd->lua->pushString("too many songs loaded"); return 2; }
    copy = pd->system->realloc(NULL, len);
    if (!copy) { pd->lua->pushNil(); pd->lua->pushString("out of memory"); return 2; }
    memcpy(copy, bytes, len);
    blobs[nblobs++] = copy;
    ensure();
    pd->lua->pushInt(nblobs);
    return 1;
}

static int l_play(lua_State *L)
{
    const uint8_t *b = blob_arg(1);
    (void)L;
    if (!b) { pd->lua->pushBool(0); return 1; }
    return post(CHIP_PLAY, (uint8_t)arg_u8(2, 0), (uint8_t)arg_u8(3, 0), b);
}

static int l_sfxbank(lua_State *L)
{
    const uint8_t *b = blob_arg(1);
    (void)L;
    if (!b) { pd->lua->pushBool(0); return 1; }
    return post(CHIP_SFX_BANK, 0, 0, b);
}

static int l_stop(lua_State *L) { (void)L; return post(CHIP_STOP, 0, 0, NULL); }
static int l_pause(lua_State *L) { (void)L; return post(CHIP_PAUSE, (uint8_t)pd->lua->getArgBool(1), 0, NULL); }
static int l_sfx(lua_State *L) { (void)L; return post(CHIP_SFX, (uint8_t)arg_u8(1, 0), 0, NULL); }
static int l_sfxstop(lua_State *L) { (void)L; return post(CHIP_SFX_STOP, 0, 0, NULL); }
static int l_duck(lua_State *L) { (void)L; return post(CHIP_DUCK, (uint8_t)arg_u8(1, 0), (uint8_t)arg_u8(2, 1), NULL); }
static int l_mute(lua_State *L) { (void)L; return post(CHIP_MUTE, (uint8_t)arg_u8(1, 0), 0, NULL); }
static int l_hold(lua_State *L) { (void)L; return post(CHIP_HOLD, (uint8_t)arg_u8(1, 255), 0, NULL); }
static int l_master(lua_State *L) { (void)L; return post(CHIP_VOLUME, (uint8_t)(arg_u8(1, 7) & 7), 0, NULL); }

static int l_volume(lua_State *L)
{
    float l = pd->lua->getArgFloat(1), r = pd->lua->getArgCount() >= 2 ? pd->lua->getArgFloat(2) : l;
    (void)L;
    if (ensure()) pd->sound->source->setVolume(source, l, r);
    return 0;
}

/* status() -> playing, order, row, sync, sfx (a bit per busy slot), ticks */
static int l_status(lua_State *L)
{
    const Gbm *g;
    (void)L;
    if (!chip) {
        pd->lua->pushBool(0); pd->lua->pushInt(0); pd->lua->pushInt(0); pd->lua->pushInt(0);
        pd->lua->pushInt(0); pd->lua->pushInt(0);
        return 6;
    }
    g = &chip->gbm;
    pd->lua->pushBool(g->playing);
    pd->lua->pushInt(g->order);
    pd->lua->pushInt(g->row);
    pd->lua->pushInt(g->sync);
    pd->lua->pushInt((g->ch[GBM_SLOT0].prio ? 1 : 0) | (g->ch[GBM_SLOT1].prio ? 2 : 0));
    pd->lua->pushInt((int)chip->ticks);
    return 6;
}

/* levels() -> a level 0-15 per music channel (4, or a format-2 song's
   voices), as they sound right now: for meters. Racy by design (the audio
   thread moves them), and harmless: each is one byte. */
static int l_levels(lua_State *L)
{
    int c;
    (void)L;
    if (chip && chip->gbm.v2) {
        for (c = 0; c < chip->gbm.nv; c++) pd->lua->pushInt(vox_level(&chip->vox, c));
        return chip->gbm.nv;
    }
    for (c = 0; c < 4; c++) {
        const GbApuChan *ch = chip ? &chip->apu.ch[c] : NULL;
        int v = 0;
        if (ch && ch->on && ch->dac) {
            if (c == 2) {
                static const int WAVE[4] = {0, 15, 8, 4};
                v = WAVE[(chip->apu.reg[0x0C] >> 5) & 3];
            } else v = ch->vol;
        }
        pd->lua->pushInt(v);
    }
    return 4;
}

static const lua_reg REG[] = {
    {"load", l_load}, {"play", l_play}, {"stop", l_stop}, {"pause", l_pause},
    {"sfxbank", l_sfxbank}, {"sfx", l_sfx}, {"sfxstop", l_sfxstop},
    {"duck", l_duck}, {"mute", l_mute}, {"hold", l_hold}, {"master", l_master},
    {"volume", l_volume}, {"status", l_status}, {"levels", l_levels},
    {NULL, NULL}
};

int chiptune_register(PlaydateAPI *api)
{
    const char *err = NULL;
    pd = api;
    if (!pd->lua->registerClass("chiptune_native", REG, NULL, 1, &err)) {
        pd->system->logToConsole("chiptune: %s", err ? err : "registerClass failed");
        return 0;
    }
    return 1;
}
