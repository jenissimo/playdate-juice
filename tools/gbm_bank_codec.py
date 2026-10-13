"""Lossless GBZ1 wrapper: byte deltas, adaptive contextual arithmetic coding.

Decoded output is the exact GBK1 bank. Models use integer counts and rescale
at 16384; the C loader decodes once before publishing immutable PCM.
"""
import struct


def pack_bank(data):
    trees = [[i & -i for i in range(257)] for _ in range(256)]
    frequencies = [[1] * 256 for _ in range(256)]
    totals = [256] * 256
    low, high, pending, context, previous = 0, 0xFFFFFFFF, 0, 0, 0
    output, byte, used = bytearray(), 0, 0

    def bit(value):
        nonlocal byte, used
        byte = (byte << 1) | value
        used += 1
        if used == 8:
            output.append(byte); byte = used = 0

    def follow(value):
        nonlocal pending
        bit(value)
        for _ in range(pending):
            bit(1 - value)
        pending = 0

    for value in data:
        symbol = (value - previous) & 255
        previous = value
        tree, freq, total = trees[context], frequencies[context], totals[context]
        cumulative, at = 0, symbol
        while at:
            cumulative += tree[at]; at -= at & -at
        span = high - low + 1
        high = low + span * (cumulative + freq[symbol]) // total - 1
        low += span * cumulative // total
        while True:
            if high < 0x80000000:
                follow(0)
            elif low >= 0x80000000:
                follow(1); low -= 0x80000000; high -= 0x80000000
            elif low >= 0x40000000 and high < 0xC0000000:
                pending += 1; low -= 0x40000000; high -= 0x40000000
            else:
                break
            low <<= 1; high = (high << 1) | 1
        freq[symbol] += 1
        at = symbol + 1
        while at <= 256:
            tree[at] += 1; at += at & -at
        total += 1
        if total >= 16384:
            total = 0
            tree[:] = [0] * 257
            for i in range(256):
                freq[i] = (freq[i] + 1) // 2
                total += freq[i]
                at = i + 1
                while at <= 256:
                    tree[at] += freq[i]; at += at & -at
        totals[context] = total
        context = symbol
    pending += 1
    follow(0 if low < 0x40000000 else 1)
    for _ in range(32):
        bit(0)
    if used:
        output.append(byte << (8 - used))
    packed = struct.pack('<4sIIHH', b'GBZ\x01', len(data), struct.unpack_from('<I', data, 8)[0],
                         struct.unpack_from('<H', data, 4)[0], 0) + output
    return packed if len(packed) < len(data) else data
