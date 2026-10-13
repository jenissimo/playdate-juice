"""Compile the recorded studio arrangement, then check encoded note starts.

The JSON owns the arrangement. GBM rows are generated, never rewritten by
hand. Simultaneous percussion can be baked as layers; optional melodic
collisions are listed explicitly in the audit beside the generated project.
"""
import json
import math
import os
import struct

from gbm_bank import import_bank, encode_bank
from gbm_bank_codec import pack_bank
from gbm_compose import Song
from gbm_format import encode_song


def decoded_notes(blob):
    u16 = lambda at: struct.unpack_from('<H', blob, at)[0]
    voices, rows, orders = blob[7], blob[3], blob[4]
    directory, order_at = u16(10), u16(8)
    notes = []
    for order in range(orders):
        for lane in range(voices):
            pattern = blob[order_at + order * voices * 2 + lane]
            transpose = blob[order_at + order * voices * 2 + voices + lane]
            if transpose >= 128:
                transpose -= 256
            at, row, inst = u16(u16(directory + lane * 2) + pattern * 2), 0, None
            while row < rows:
                b = blob[at]; at += 1
                if 0xC0 <= b < 0xE0:
                    inst = b - 0xC0; b = blob[at]; at += 1
                elif b == 0xF0:
                    inst = blob[at]; b = blob[at + 1]; at += 2
                fx = []
                while 0xE0 <= b <= 0xEF or b == 0xF1:
                    cmd = blob[at] if b == 0xF1 else b & 15
                    if b == 0xF1:
                        at += 1
                    fx.append((cmd, blob[at])); at += 1
                    b = blob[at]; at += 1
                if b < 0x60:
                    notes.append(dict(step=order * rows + row, lane=lane,
                                      midi=b + 24 + transpose, inst=inst, fx=fx))
                row += 1 + (b & 63) if 0x80 <= b < 0xC0 else 1
    return sorted(notes, key=lambda n: (n['step'], n['lane']))


def build(directory, outdir, mix_gain=1.0, lane_gains=None, packed=True, quiet=False):
    with open(os.path.join(directory, 'port.json'), encoding='utf-8') as f:
        port = json.load(f)
    samples = import_bank(directory, rate=0)
    metas = {s['name']: s for s in port['bank']}
    for sample in samples:
        meta = metas[sample['name']]
        if not meta['sustain']:
            # No caller can read past its next retrigger plus the bounded
            # release overlap. Keep two guard samples for interpolation.
            limit = math.ceil(meta['maxLife'] * sample['rate']) + 2
            sample['pcm8'] = sample['pcm8'][:limit]
    bank = encode_bank(samples)
    raw_size = len(bank)
    file_bank = pack_bank(bank) if packed else bank
    names = [s['name'] for s in samples]
    identity = struct.unpack_from('<I', bank, 8)[0]
    os.makedirs(outdir, exist_ok=True)
    results = {}
    for name, source in port['songs'].items():
        s = Song('Studio ' + name, groove=(6,), version=4, voices=8)
        s.s['tickRate'] = source['bpm'] * 4 * 6 / 60
        s.s['mixGain'] = mix_gain
        s.s['sampleBank'] = dict(count=len(samples), hash=identity)
        rows = [[{} for _ in range(source['steps'])] for _ in range(8)]
        instruments = {}
        for e in source['selected']:
            sample = e['sample']
            if sample not in instruments:
                m = metas[sample]
                # PCM is peak-normalised to -1 dB. Recover the studio's
                # pre-normalisation level and its measured stem mix gain.
                gain = m['rawPeak'] / (10 ** (-1 / 20)) * source['stemGains'][e['stem']] * e['velocityMax'] / (0.23 * 2 * 0.3536)
                if lane_gains:
                    gain *= lane_gains.get(name, [1] * 8)[e['lane']]
                instruments[sample] = s.voice('sample', sample, sample=names.index(sample), volume=15,
                                             release=m['release'], mixGain=gain, envPace=0)
            volume = max(1, min(15, round(15 * e['gain'] / e['velocityMax'])))
            cell = dict(note=round(e['note']) - 24, inst=instruments[sample],
                        fx=[dict(cmd=5, val=volume << 4)])
            duration = e.get('d')
            if duration and (e['sustain'] or e['inst'] in ('G.chug', 'G.scrape')):
                ticks = max(1, round(duration * s.s['tickRate']))
                if ticks < 255:
                    cell['fx'].append(dict(cmd=10, val=ticks + 1))
            rows[e['lane']][e['step']] = cell
        for bar in range(source['bars']):
            patterns = []
            for lane in rows:
                cells = lane[bar * 16:(bar + 1) * 16]
                s.s['patterns'].append(dict(cells=cells))
                patterns.append(len(s.s['patterns']) - 1)
            s.s['orders'].append(dict(pat=patterns, tr=[0] * 8))
        blob = encode_song(s.project())
        decoded = decoded_notes(blob)
        expected = [(e['step'], e['lane'], round(e['note'])) for e in source['selected']]
        actual = [(e['step'], e['lane'], e['midi']) for e in decoded]
        if expected != actual:
            raise ValueError(name + ': encoded notes differ from the recorded arrangement')
        length_checks = 0
        for e, decoded_event in zip(source['selected'], decoded):
            if e['sustain'] and e.get('d') and e['d'] * s.s['tickRate'] < 254:
                cut = next(v for c, v in decoded_event['fx'] if c == 10)
                if abs((cut - 1) / s.s['tickRate'] - e['d']) > 60 / source['bpm'] / 4:
                    raise ValueError(name + ': gate differs by more than a row')
                length_checks += 1
        audit = dict(name=name, bpm=source['bpm'], tickRate=s.s['tickRate'], rows=source['steps'],
                     notes_checked=len(actual), lengths_checked=length_checks,
                     layered_events=sum(len(e.get('layers', [])) for e in source['selected']),
                     dropped=source['dropped'], bank_bytes=len(file_bank), bank_ram_bytes=raw_size, mix_gain=mix_gain,
                     lane_gains=lane_gains.get(name) if lane_gains else None)
        for filename, data in ((f'studio_{name}.gbm', blob), ('overturn.gbank', file_bank)):
            with open(os.path.join(outdir, filename), 'wb') as f:
                f.write(data)
        for suffix, data in (('gbm.json', s.project()), ('audit.json', audit)):
            with open(os.path.join(directory, f'studio_{name}.{suffix}'), 'w') as f:
                json.dump(data, f, indent=1)
        results[name] = audit
        if not quiet:
            print(f'{name}: {len(blob)} pattern bytes, {len(actual)} notes checked, {length_checks} gates checked, bank {len(file_bank)} bytes / {raw_size} RAM')
    return results


if __name__ == '__main__':
    import sys
    build(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 1.0)
