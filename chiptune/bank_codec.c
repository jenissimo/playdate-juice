/* GBZ1's bounded, lossless loader. No codec work runs in the audio callback.
   The encoder is tools/gbm_bank_codec.py; integer counts are the ABI. */
#include "bank_codec.h"
#include <string.h>

typedef struct {
    uint16_t freq[256][256], tree[256][257], total[256];
} Model;
typedef struct { const uint8_t *data; uint32_t bytes, bit; int error; } Bits;
static uint32_t u32(const uint8_t *p) { return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24); }
static unsigned read_bit(Bits *b)
{
    unsigned value;
    if (b->bit / 8 >= b->bytes) { b->error = 1; return 0; }
    value = (b->data[b->bit / 8] >> (7 - (b->bit & 7))) & 1;
    b->bit++; return value;
}
uint32_t bank_workspace_size(void) { return (uint32_t)sizeof(Model); }
uint32_t bank_raw_size(const uint8_t *s, uint32_t n)
{
    uint32_t size;
    if (!s || n < 12 || s[0] != 'G' || s[1] != 'B') return 0;
    if (s[2] == 'K' && s[3] == 1) return n;
    if (s[2] != 'Z' || s[3] != 1 || n < 16 || s[14] || s[15]) return 0;
    size = u32(s + 4);
    return size >= 12 && size <= 16u * 1024u * 1024u ? size : 0;
}
int bank_unpack(const uint8_t *s, uint32_t n, uint8_t *out, uint32_t size, void *workspace)
{
    uint32_t low = 0, high = 0xFFFFFFFFu, code = 0, i;
    unsigned context = 0, previous = 0, j;
    Model *m = (Model *)workspace;
    Bits bits;
    if (!out || !size || bank_raw_size(s, n) != size) return 1;
    if (s[2] == 'K') { memmove(out, s, size); return 0; }
    if (!m) return 1;
    bits.data = s + 16; bits.bytes = n - 16; bits.bit = 0; bits.error = 0;
    for (i = 0; i < 256; i++) {
        m->total[i] = 256; m->tree[i][0] = 0;
        for (j = 0; j < 256; j++) m->freq[i][j] = 1;
        for (j = 1; j <= 256; j++) m->tree[i][j] = (uint16_t)(j & (0u - j));
    }
    for (j = 0; j < 32; j++) code = (code << 1) | read_bit(&bits);
    for (i = 0; i < size; i++) {
        uint16_t *tree = m->tree[context], *freq = m->freq[context];
        uint32_t total = m->total[context], cumulative = 0, symbol = 0, step;
        uint64_t span = (uint64_t)high - low + 1;
        uint32_t scaled;
        if (bits.error || code < low || code > high) return 2;
        scaled = (uint32_t)((((uint64_t)(code - low) + 1) * total - 1) / span);
        for (step = 256; step; step >>= 1) {
            uint32_t at = symbol + step;
            if (at <= 256 && cumulative + tree[at] <= scaled) { cumulative += tree[at]; symbol = at; }
        }
        if (symbol >= 256) return 3;
        high = low + (uint32_t)(span * (cumulative + freq[symbol]) / total) - 1;
        low += (uint32_t)(span * cumulative / total);
        for (;;) {
            if (high < 0x80000000u) { /* the high bit is zero */ }
            else if (low >= 0x80000000u) { low -= 0x80000000u; high -= 0x80000000u; code -= 0x80000000u; }
            else if (low >= 0x40000000u && high < 0xC0000000u) { low -= 0x40000000u; high -= 0x40000000u; code -= 0x40000000u; }
            else break;
            low <<= 1; high = (high << 1) | 1; code = (code << 1) | read_bit(&bits);
        }
        previous = (previous + symbol) & 255; out[i] = (uint8_t)previous;
        freq[symbol]++;
        for (j = symbol + 1; j <= 256; j += j & (0u - j)) tree[j]++;
        if (++total >= 16384) {
            memset(tree, 0, 257 * sizeof *tree); total = 0;
            for (j = 0; j < 256; j++) {
                unsigned at;
                freq[j] = (uint16_t)((freq[j] + 1) / 2); total += freq[j];
                for (at = j + 1; at <= 256; at += at & (0u - at)) tree[at] = (uint16_t)(tree[at] + freq[j]);
            }
        }
        m->total[context] = (uint16_t)total; context = symbol;
    }
    if (bits.error || out[0] != 'G' || out[1] != 'B' || out[2] != 'K' || out[3] != 1 ||
        out[4] != s[12] || out[5] != s[13] || u32(out + 8) != u32(s + 8)) return 4;
    return 0;
}
