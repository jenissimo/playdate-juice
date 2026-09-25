"""The GBM song project (.gbm.json) and its encoding into the blob chiptune/
plays (.gbm).

A line-for-line port of gameboy-lab's shared/gbm/ts/format.ts, so the GBM
tracker's projects and exports are interchangeable with these: the encoder is
tested byte for byte against blobs the original produced
(test/chiptune/golden). Layout reference: chiptune/README.md.

One addition, after the blob where the driver never looks: the SFX names,
so a game can say Chiptune.sfx("coin") instead of an index.
    names   := count:u8 { len:u8 bytes }*
    trailer := names u16(len(names)) "NM"
"""

FX = dict(ARP=0x0, SLIDE_UP=0x1, SLIDE_DOWN=0x2, PORTA=0x3, VIBRATO=0x4, ENVELOPE=0x5,
          DUTY=0x6, DELAY=0x7, PAN=0x8, RETRIG=0x9, CUT=0xA, JUMP=0xB, SWEEP=0xC,
          BREAK=0xD, SYNC=0xE, GROOVE=0xF)
NOTE_OFF = -1
HEADER = 24


def env_byte(volume, direction, pace):
    return ((volume & 15) << 4) | (8 if direction > 0 else 0) | (pace & 7)


def new_instrument(kind, name=None):
    return dict(name=name or kind, kind=kind, volume=3 if kind == 'wave' else 12, envDir=-1,
                envPace=2 if kind == 'noise' else 0, duty=2 if kind == 'pulse' else 0, length=0,
                table=-1, tableSpeed=0, vibSpeed=0, vibDepth=0, vibDelay=0, sweep=0)


WAVES = dict(
    triangle=lambda: [i if i < 16 else 31 - i for i in range(32)],
    saw=lambda: [i >> 1 for i in range(32)],
    square=lambda w: [15 if (i % 32) < w * 2 else 0 for i in range(32)],
    sine=lambda: [int(__import__('math').floor(7.5 + 7.5 * __import__('math').sin(__import__('math').pi * 2 * i / 32) + 0.5)) for i in range(32)],
)


def _is_empty(c):
    return c.get('note') is None and c.get('inst') is None and not c.get('fx')


def _clamp_note(n):
    return max(0, min(0x5F, n))


def encode_stream(cells, end=False):
    """A row stream: each row is [inst][fx..] then a note, 0x60 (off) or
    0x80+n (this row and n more are otherwise empty). `end` appends 0x61."""
    out = []
    inst = -1
    dedup = []
    for c in cells:
        if c.get('inst') is None:
            dedup.append(c)
        elif c['inst'] == inst:
            dedup.append({k: v for k, v in c.items() if k != 'inst'})
        else:
            inst = c['inst']
            dedup.append(c)
    cells = dedup
    i = 0
    while i < len(cells):
        c = cells[i]
        if c.get('inst') is not None:
            out += [0xC0 + c['inst']] if c['inst'] < 32 else [0xF0, c['inst'] & 255]
        for f in c.get('fx') or []:
            out += [0xE0 | (f['cmd'] & 15), f['val'] & 255]
        if c.get('note') is not None:
            out.append(0x60 if c['note'] == NOTE_OFF else _clamp_note(c['note']))
            i += 1
            if i >= len(cells) or not _is_empty(cells[i]):
                continue
            n = 0
            while i + n < len(cells) and _is_empty(cells[i + n]) and n < 64:
                n += 1
            out.append(0x80 + n - 1)
            i += n
        else:
            n = 1
            while i + n < len(cells) and _is_empty(cells[i + n]) and n < 64:
                n += 1
            out.append(0x80 + n - 1)
            i += n
    if end:
        out.append(0x61)
    return out


def pcm_frame(data, at):
    """One 32-sample frame as CH3 wants it: rotated by one (a restarted CH3
    first plays the nibble left in its buffer) and inverted (on the DMG
    nibble 0 is the positive peak)."""
    slot = [0] * 32
    for k in range(32):
        v = data[at + k] if at + k < len(data) else 8
        slot[(k + 1) % 32] = 15 - (v & 15)
    return [slot[j] << 4 | slot[j + 1] for j in range(0, 32, 2)]


def validate(song):
    e = []
    rows = song['rows']
    if rows < 1 or rows > 255:
        e.append(f'rows {rows} out of 1-255')
    orders, sfx = song['orders'], song.get('sfx', [])
    if len(orders) > 255 or (not orders and not sfx):
        e.append('need 1-255 orders')
    for c in range(4):
        if len({o['pat'][c] for o in orders}) > 256:
            e.append(f'channel {c} uses more than 256 patterns')
    if len(sfx) > 255:
        e.append('at most 255 SFX')
    for i, s in enumerate(sfx):
        if any(s['pattern'] in o['pat'] for o in orders):
            e.append(f"SFX {i} pattern {s['pattern']} is also in the song")
    if len(song['instruments']) > 256:
        e.append('at most 256 instruments')
    g = song['grooves']
    if not g or any(not x or len(x) > 16 or any(t < 1 or t > 255 for t in x) for x in g):
        e.append('grooves need 1-16 steps of 1-255 frames')
    for i, o in enumerate(orders):
        for p in o['pat']:
            if p >= len(song['patterns']):
                e.append(f'order {i} names pattern {p}')
    sfx_pats = {s['pattern'] for s in sfx}
    for i, p in enumerate(song['patterns']):
        if i not in sfx_pats and len(p['cells']) != rows:
            e.append(f"pattern {i} has {len(p['cells'])} rows, not {rows}")
        for r, c in enumerate(p['cells']):
            if c.get('inst') is not None and c['inst'] >= len(song['instruments']):
                e.append(f"pattern {i} row {r}: no instrument {c['inst']}")
    for i, t in enumerate(song['tables']):
        if len(t['rows']) > 42:
            e.append(f"table {i}: {len(t['rows'])} rows, at most 42")
    for i, ins in enumerate(song['instruments']):
        if ins.get('table', -1) >= len(song['tables']):
            e.append(f"instrument {i}: no table {ins['table']}")
        smp = ins.get('sample')
        if smp is not None and smp >= 0 and smp >= len(song.get('samples') or []):
            e.append(f'instrument {i}: no sample {smp}')
        if ins['kind'] == 'wave' and ins['duty'] >= len(song['waves']):
            e.append(f"instrument {i}: no wave {ins['duty']}")
    return e


def encode_song(song, names=False):
    errors = validate(song)
    if errors:
        raise ValueError('Song is invalid:\n' + '\n'.join(errors))
    out = [0] * HEADER

    def w16(at, v):
        out[at] = v & 255
        out[at + 1] = v >> 8

    here = lambda: len(out)
    out[0], out[1], out[2] = 0x47, 0x42, 1
    orders, sfx = song['orders'], song.get('sfx', [])

    def uniq(seq):
        seen, r = set(), []
        for x in seq:
            if x not in seen:
                seen.add(x)
                r.append(x)
        return r

    locals_ = [uniq(o['pat'][c] for o in orders) for c in range(4)] + [uniq(s['pattern'] for s in sfx)]
    out[3] = song['rows']
    out[4] = len(orders)
    out[5] = 0xFF if song.get('loop') is None else song['loop']
    out[6] = len(sfx)

    w16(8, here())
    for o in orders:
        out += [locals_[c].index(p) for c, p in enumerate(o['pat'])] + [t & 255 for t in o['tr']]

    w16(10, here())
    d = here()
    out += [0] * 10
    dirs = []
    for c, lst in enumerate(locals_):
        w16(d + c * 2, here())
        dirs.append(here())
        out += [0] * (len(lst) * 2)

    w16(12, here())
    table_refs = []
    for ins in song['instruments']:
        kind = ins['kind']
        env = ins['volume'] & 3 if kind == 'wave' else env_byte(ins['volume'], ins['envDir'], ins['envPace'])
        duty = (8 if ins['duty'] else 0) if kind == 'noise' else ins['duty']
        vib = ((ins.get('vibSpeed', 0) & 15) << 4) | (ins.get('vibDepth', 0) & 15)
        smp = ins.get('sample')
        sweep = (smp + 1 if smp is not None and smp >= 0 else 0) if kind == 'noise' else ins.get('sweep', 0) & 255
        if ins.get('table', -1) >= 0:
            table_refs.append((here() + 6, ins['table']))
        out += [duty, vib, ins.get('vibDelay', 0) & 255, env, sweep, ins.get('length', 0) & 255, 0, 0,
                ins.get('tableSpeed', 0) & 255, 0]

    w16(14, here())
    tbl_table = here()
    out += [0] * (len(song['tables']) * 2)
    table_at = []
    for i, t in enumerate(song['tables']):
        w16(tbl_table + i * 2, here())
        table_at.append(here())
        out += [len(t['rows']), 0xFF if t.get('loop') is None else t['loop']]
        for r in t['rows']:
            fx = r.get('fx')
            out += [r.get('transpose', 0) & 255, 0xFF if r.get('env') is None else r['env'],
                    0xFF if r.get('duty') is None else r['duty'], r.get('pitch', 0) & 255,
                    fx['cmd'] & 15 if fx else 0xFF, fx['val'] & 255 if fx else 0]
    for at, t in table_refs:
        w16(at, table_at[t])

    w16(16, here())
    for w in song['waves']:
        for i in range(16):
            out.append(((w[i * 2] & 15) << 4) | (w[i * 2 + 1] & 15))

    w16(18, here())
    grv = here()
    out += [0] * (len(song['grooves']) * 2)
    for i, g in enumerate(song['grooves']):
        w16(grv + i * 2, here())
        out += [len(g)] + list(g)

    w16(20, here())
    for s in sfx:
        out += [locals_[4].index(s['pattern']), s['channel'], s['priority'], s['speed']]

    samples = song.get('samples') or []
    w16(22, here())
    smp_table = here()
    out += [0] * (len(samples) * 2)
    for i, s in enumerate(samples):
        w16(smp_table + i * 2, here())
        blocks = min(255, -(-len(s['data']) // 32))
        out.append(blocks)
        for b in range(blocks):
            out += pcm_frame(s['data'], b * 32)

    seen = {}
    for c, lst in enumerate(locals_):
        for i, p in enumerate(lst):
            s = encode_stream(song['patterns'][p]['cells'], c == 4)
            key = bytes(s)
            at = seen.get(key)
            if at is None:
                at = here()
                seen[key] = at
                out += s
            w16(dirs[c] + i * 2, at)
    if len(out) > 0xFFFF:
        raise ValueError(f'Song is {len(out)} bytes; the limit is 64 KB')
    blob = bytes(out)
    if names:
        nm = [len(sfx)]
        for s in sfx:
            b = s.get('name', '').encode('utf8')[:255]
            nm += [len(b)] + list(b)
        blob += bytes(nm) + bytes([len(nm) & 255, len(nm) >> 8]) + b'NM'
    return blob


def sfx_names(blob):
    """The names trailer, if the blob has one."""
    if len(blob) < 4 or blob[-2:] != b'NM':
        return []
    n = blob[-4] | blob[-3] << 8
    t = blob[-4 - n:-4]
    out, p = [], 1
    for _ in range(t[0]):
        out.append(t[p + 1:p + 1 + t[p]].decode('utf8'))
        p += 1 + t[p]
    return out
