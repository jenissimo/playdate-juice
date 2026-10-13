"""Studio bank.json + PCM WAV -> shared, immutable PCM8 .gbank.

GBK1: 12-byte header (magic, u16 count, u16 reserved, u32 FNV-1a identity),
then count records of six u32s: data offset, sample count, rate, root mHz,
loop start, exclusive loop end (both zero for a one-shot). PCM is signed
8-bit, mono. All integers are little-endian; offsets may exceed 64 KiB.
"""
import json
import math
import os
import random
import shutil
import struct
import subprocess
import tempfile
import wave


def bank_hash(data):
    h = 2166136261
    for i, b in enumerate(data):
        h = ((h ^ (0 if 8 <= i < 12 else b)) * 16777619) & 0xFFFFFFFF
    return h


def encode_bank(samples):
    if not 1 <= len(samples) <= 255:
        raise ValueError('a bank needs 1-255 samples')
    header = 12 + 24 * len(samples)
    records, pcm = bytearray(), bytearray()
    for s in samples:
        data = bytes(s['pcm8'])
        rate, root = s['rate'], s['root']
        if not data or len(data) > 0xFFFFFF or not 1000 <= rate <= 192000 or not 0 <= root <= 127:
            raise ValueError(f"invalid sample: {s.get('name')}")
        a, b = s.get('loop') or (0, 0)
        if (b and not 0 <= a < b <= len(data)) or (not b and a):
            raise ValueError(f"invalid loop: {s.get('name')}")
        mhz = round(440000 * 2 ** ((root - 69) / 12))
        records += struct.pack('<6I', header + len(pcm), len(data), rate, mhz, a, b)
        pcm += data
    blob = bytearray(struct.pack('<4sHHI', b'GBK\x01', len(samples), 0, 0)) + records + pcm
    struct.pack_into('<I', blob, 8, bank_hash(blob))
    return bytes(blob)


def read_wav(path):
    with wave.open(path, 'rb') as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2 or w.getcomptype() != 'NONE':
            raise ValueError(f'{path}: expected PCM16 mono')
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())
    return rate, [v[0] for v in struct.iter_unpack('<h', raw)]


def import_bank(directory, rate=16384, only=None):
    """Downsample before quantising, preserving roots and exclusive loop ends.

    ffmpeg supplies the anti-alias filter when the rate changes. A fixed
    TPDF dither seed makes repeat builds byte-identical, including identity.
    """
    with open(os.path.join(directory, 'bank.json'), encoding='utf-8') as f:
        meta = json.load(f)
    if only:
        missing = set(only) - {s['name'] for s in meta}
        if missing:
            raise ValueError('no studio sample: ' + ', '.join(sorted(missing)))
    out, seen = [], set()
    with tempfile.TemporaryDirectory(prefix='gbm-bank-') as tmp:
        for m in meta:
            name = m['name']
            if only and name not in only:
                continue
            if name in seen:
                raise ValueError(f'duplicate sample: {name}')
            seen.add(name)
            path = os.path.join(directory, m['file'])
            original_rate, data = read_wav(path)
            if original_rate != m['rate'] or len(data) != m['length']:
                raise ValueError(f'{name}: WAV and bank.json disagree on rate or length')
            if m.get('loop') and not 0 <= m['loop'][0] < m['loop'][1] <= len(data):
                raise ValueError(f'{name}: loop outside sample')
            target = rate or original_rate
            if not 1000 <= target <= 192000:
                raise ValueError('sample rate must be 1000-192000 Hz')
            if target != original_rate:
                ffmpeg = os.environ.get('FFMPEG') or shutil.which('ffmpeg')
                if not ffmpeg:
                    raise ValueError('ffmpeg is required for bank resampling (or set FFMPEG)')
                dest = os.path.join(tmp, 'resampled.wav')
                subprocess.run([ffmpeg, '-v', 'error', '-y', '-i', path, '-ar', str(target),
                                '-ac', '1', '-c:a', 'pcm_s16le', dest], check=True)
                _, data = read_wav(dest)
            loop = None
            if m.get('loop'):
                a, b = m['loop']
                a = round(a * target / original_rate)
                b = len(data) if b == m['length'] else round(b * target / original_rate)
                loop = [a, b]
                if not 0 <= a < b <= len(data):
                    raise ValueError(f'{name}: loop collapsed after resampling')
                # The resampler sees an ending, rather than the loop's next lap.
                # Rejoin its final few milliseconds before PCM8 quantisation.
                c = min(round(0.005 * target), a, (b - a) // 2)
                for j in range(c):
                    t = (j + 1) / c
                    data[b - c + j] = round(data[b - c + j] * (1 - t) + data[a - c + j] * t)
            rng = random.Random(1)
            pcm = bytes(max(-128, min(127, math.floor(v / 256 + rng.random() - rng.random() + 0.5))) & 255
                        for v in data)
            out.append(dict(name=name, rate=target, root=m['root'], loop=loop, pcm8=pcm))
    return out
