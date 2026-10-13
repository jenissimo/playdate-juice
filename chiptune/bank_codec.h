#ifndef BANK_CODEC_H
#define BANK_CODEC_H
#include <stdint.h>
/* GBK1 raw or GBZ1 lossless wrapper. Zero means an invalid size/header. */
uint32_t bank_raw_size(const uint8_t *data, uint32_t bytes);
uint32_t bank_workspace_size(void);
/* Caller owns output and workspace. Runs before the bank reaches audio. */
int bank_unpack(const uint8_t *data, uint32_t bytes, uint8_t *out,
                uint32_t out_bytes, void *workspace);
#endif
