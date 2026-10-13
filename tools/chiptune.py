#!/usr/bin/env python3
"""chiptune's host-side tools.

    python tools/chiptune.py songs [--json DIR]    build chiptune/music/*.gbm from tools/chiptune_songs.py
    python tools/chiptune.py encode in.gbm.json out.gbm
    python tools/chiptune.py render in.gbm out.wav [renderer options]
    python tools/chiptune.py render-all DIR [--adpcm] [--rate 22050]
    python tools/chiptune.py test                  the C port against the original ROM, and the encoder
    python tools/chiptune.py studio [--rate HZ]     build the PCM8 bank and rock/jungle/trance demos
    python tools/chiptune.py bank DIR out.gbank [--rate HZ] [--only a,b]

render, render-all and test compile tools/chiptune_render.c or
test/chiptune/trace_test.c with whatever C compiler is at hand: cc, gcc or
clang on PATH, or MSVC found through vswhere. Binaries go to build/ (ignored).

render-all writes every song and effect as WAV, for games that play
pre-rendered audio through Jukebox and a sampleplayer instead of building
the C extension.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from gbm_format import encode_song, sfx_names  # noqa: E402

MUSIC = os.path.join(ROOT, 'chiptune', 'music')
BUILD = os.path.join(ROOT, 'build')
CORE = ['chiptune/gbapu.c', 'chiptune/vox.c', 'chiptune/gbm.c', 'chiptune/chip.c', 'chiptune/bank_codec.c']


# ─── compiling ────────────────────────────────────────────────────────────

def _vcvars():
    vswhere = os.path.join(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'),
                           'Microsoft Visual Studio', 'Installer', 'vswhere.exe')
    roots = []
    if os.path.isfile(vswhere):
        out = subprocess.run([vswhere, '-all', '-products', '*', '-property', 'installationPath'],
                             capture_output=True, text=True).stdout
        roots = [l.strip() for l in out.splitlines() if l.strip()]
    for base in [os.environ.get('ProgramFiles', r'C:\Program Files'), os.environ.get('ProgramFiles(x86)', '')]:
        for ver in ('2022', '2019'):
            for ed in ('Community', 'Professional', 'Enterprise', 'BuildTools'):
                roots.append(os.path.join(base, 'Microsoft Visual Studio', ver, ed))
    for r in roots:
        bat = os.path.join(r, 'VC', 'Auxiliary', 'Build', 'vcvars64.bat')
        if os.path.isfile(bat):
            return bat
    return None


def compile_c(sources, out):
    """Builds `sources` (repo-relative) into build/`out`; returns its path."""
    os.makedirs(BUILD, exist_ok=True)
    exe = os.path.join(BUILD, out + ('.exe' if os.name == 'nt' else ''))
    srcs = [os.path.join(ROOT, s) for s in sources]
    for cc in ('cc', 'gcc', 'clang'):
        if shutil.which(cc):
            cmd = [cc, '-std=c99', '-O2', '-Wall', '-Wextra', '-o', exe] + srcs
            if subprocess.run(cmd).returncode:
                sys.exit(f'{cc} failed')
            return exe
    bat = _vcvars()
    if bat:
        with tempfile.TemporaryDirectory() as tmp:
            script = os.path.join(tmp, 'build.bat')
            with open(script, 'w') as f:
                f.write(f'@echo off\ncall "{bat}" >nul 2>nul\n')
                f.write(f'cl /nologo /O2 /W3 /Fe:"{exe}" /Fo:"{tmp}/" ' + ' '.join(f'"{s}"' for s in srcs) + '\n')
            r = subprocess.run(['cmd', '/c', script], capture_output=True, text=True)
            if r.returncode:
                sys.exit('cl failed:\n' + r.stdout + r.stderr)
        return exe
    sys.exit('no C compiler found (cc, gcc, clang, or MSVC through vswhere)')


def renderer():
    return compile_c(['tools/chiptune_render.c'] + CORE, 'chiptune_render')


def probe_song():
    """Every format-2 feature in one bar, for test/chiptune/v2_test.c."""
    from gbm_compose import Song, sid_kick, sid_snare, sid_hat, sample_voice, synth_kit
    s = Song('v2 probe', groove=(6, 6), version=2, voices=6, filter=dict(cutoff=120, resonance=10, mode=1))
    s.voice('pulse', 'lead', volume=12, width=128, pwm=3)
    s.voice('saw', 'bass', volume=12, filter=True)
    s.voice('triangle', 'tri', volume=10)
    sid_kick(s); sid_snare(s); sid_hat(s)
    sample_voice(s, synth_kit()[0], 'kick808')
    s.bar(['C5@lead . E5 . G5 . . . C6 . . . G5 . . .',
           'C2@bass+G1220 . . . C3 . . . G2 . . . C3 . . .',
           'E4@tri+047 . . . . . . . . . . . . . . .',
           'C4@skick . . . A3@ssnare . . . C4@skick . C4 . A3@ssnare . . .',
           'C6@shat . C6 . C6 . C6 . C6 . C6 . C6 . C6 .',
           'C5@kick808 . . . . . . . C5 . . . . . . .'])
    s.sfx('blip', 'C6@lead E6 G6 . . . . . -', 7, 1, 2)
    return s.project()


# ─── commands ─────────────────────────────────────────────────────────────

def cmd_songs(args):
    import chiptune_songs
    json_dir = args[args.index('--json') + 1] if '--json' in args else None
    os.makedirs(MUSIC, exist_ok=True)
    built = [(name, fn().project()) for name, fn in chiptune_songs.SONGS.items()]
    built.append(('sfx', chiptune_songs.sfx_library().project()))
    for name, song in built:
        blob = encode_song(song, names=name == 'sfx')
        with open(os.path.join(MUSIC, name + '.gbm'), 'wb') as f:
            f.write(blob)
        if json_dir:
            os.makedirs(json_dir, exist_ok=True)
            with open(os.path.join(json_dir, name + '.gbm.json'), 'w') as f:
                json.dump(song, f)
        what = f"{len(song['sfx'])} effects" if name == 'sfx' else f"{len(song['orders'])} orders"
        print(f'  {name}.gbm: {len(blob)} bytes, {what}')


def cmd_encode(args):
    src, dst = args[0], args[1]
    with open(src) as f:
        song = json.load(f)
    blob = encode_song(song, names=bool(song.get('sfx')))
    with open(dst, 'wb') as f:
        f.write(blob)
    print(f'{dst}: {len(blob)} bytes')


def cmd_render(args):
    sys.exit(subprocess.run([renderer()] + args).returncode)


def cmd_render_all(args):
    out = args[0]
    extra = args[1:]
    exe = renderer()
    os.makedirs(out, exist_ok=True)
    for f in sorted(os.listdir(MUSIC)):
        if not f.endswith('.gbm'):
            continue
        path = os.path.join(MUSIC, f)
        blob = open(path, 'rb').read()
        bank_args = ['--bank', sample_bank_path(blob, MUSIC)] if blob[2] == 3 and blob[26] else []
        if blob[4]:     # has orders: a song
            subprocess.run([exe, path, os.path.join(out, f[:-4] + '.wav'), '--mono'] + bank_args + extra, check=True)
        for i, n in enumerate(sfx_names(blob)):
            subprocess.run([exe, path, os.path.join(out, 'sfx_' + n + '.wav'), '--sfx', str(i), '--mono'] + bank_args + extra,
                           check=True, stdout=subprocess.DEVNULL)
        if blob[6]:
            print(f'  {blob[6]} effects from {f}')


def cmd_test(args):
    golden = os.path.join(ROOT, 'test', 'chiptune', 'golden.zip')
    fails = 0
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(golden) as z:
            z.extractall(tmp)
        # The encoder, byte for byte against blobs the original encoder made.
        for f in sorted(os.listdir(tmp)):
            if f.endswith('.gbm.json'):
                with open(os.path.join(tmp, f)) as j:
                    song = json.load(j)
                want = open(os.path.join(tmp, f[:-5]), 'rb').read()
                ok = encode_song(song) == want
                fails += not ok
                print(f"  encode {f}: {'matches the original encoder' if ok else 'DIFFERS'}")
        scenarios = sorted(f[:-4] for f in os.listdir(tmp) if f.endswith('.scn'))
        exe = compile_c(['test/chiptune/trace_test.c', 'chiptune/gbm.c', 'chiptune/gbapu.c', 'chiptune/vox.c'], 'trace_test')
        r = subprocess.run([exe, tmp] + scenarios)
        fails += r.returncode != 0
        # Format 2 and vox: there is no original to match, so the promises.
        probe = os.path.join(tmp, 'probe.gbm')
        with open(probe, 'wb') as f:
            f.write(encode_song(probe_song()))
        exe = compile_c(['test/chiptune/v2_test.c'] + CORE, 'v2_test')
        fails += subprocess.run([exe, probe]).returncode != 0
        # PCM8 and a >64 KiB external bank, independent of studio's DSP.
        from gbm_bank import encode_bank
        from gbm_compose import Song, sample_voice
        import struct
        data = encode_bank([dict(name='bass', pcm8=bytes([0, 80, 0, 176]) * 17500,
                                 rate=16384, root=33, loop=[0, 4]),
                            dict(name='hit', pcm8=bytes([64, 0, 192, 0]) * 4096,
                                 rate=22050, root=72, loop=None)])
        s = Song('PCM probe', version=3, voices=2, groove=(255,))
        s.s['sampleBank'] = dict(count=2, hash=struct.unpack_from('<I', data, 8)[0])
        s.voice('sample', 'bass', sample=0, volume=12, envPace=0)
        s.voice('sample', 'hit', sample=1, volume=10, envPace=0)
        s.bar(['A1@bass+E2A', '.'])
        s.sfx('hit', 'C5@hit . . -', 7, 3, 3)
        pcm_probe = os.path.join(tmp, 'pcm.gbm')
        pcm_bank = os.path.join(tmp, 'pcm.gbank')
        legacy_sfx = os.path.join(tmp, 'legacy.gbm')
        packed_bank = os.path.join(tmp, 'packed.gbank')
        extended_probe = os.path.join(tmp, 'extended.gbm')
        legacy = Song('legacy SFX', version=2)
        sample_voice(legacy, dict(name='drum', data=[15, 0] * 8192), 'drum')
        legacy.sfx('hit', 'C5@drum . . -', 0, 3, 3)
        for path, payload in ((pcm_probe, encode_song(s.project())), (pcm_bank, data),
                              (legacy_sfx, encode_song(legacy.project()))):
            with open(path, 'wb') as f:
                f.write(payload)
        from gbm_bank_codec import pack_bank
        with open(packed_bank, 'wb') as f:
            f.write(pack_bank(data))
        s.s.update(tickRate=56, mixGain=1)
        s.s['instruments'][0].update(release=30, mixGain=1)
        with open(extended_probe, 'wb') as f:
            f.write(encode_song(s.project()))
        exe = compile_c(['test/chiptune/v3_test.c'] + CORE, 'v3_test')
        fails += subprocess.run([exe, pcm_probe, pcm_bank, legacy_sfx, packed_bank, extended_probe]).returncode != 0
        fails += subprocess.run([sys.executable, os.path.join(ROOT, 'test', 'chiptune', 'bank_test.py')]).returncode != 0
    # The shipped songs build and every effect has a name.
    import chiptune_songs
    for name, fn in chiptune_songs.SONGS.items():
        blob = encode_song(fn().project())
        want = os.path.join(MUSIC, name + '.gbm')
        if not os.path.isfile(want) or open(want, 'rb').read() != blob:
            print(f'  chiptune/music/{name}.gbm is stale: run `python tools/chiptune.py songs`')
            fails += 1
    with tempfile.TemporaryDirectory(prefix='studio-check-') as directory:
        built = studio_projects(directory, 16384)
        for name, (song, bank) in built:
            for filename, payload in ((name + '.gbm', encode_song(song.project())), ('rock.gbank', bank)):
                path = os.path.join(MUSIC, filename)
                if not os.path.isfile(path) or open(path, 'rb').read() != payload:
                    print(f'  chiptune/music/{filename} is stale: run `python tools/chiptune.py studio`')
                    fails += 1
    print('chiptune: ' + ('all passed' if not fails else f'{fails} failure(s)'))
    sys.exit(1 if fails else 0)


def cmd_bank(args):
    from gbm_bank import import_bank, encode_bank
    rate = int(args[args.index('--rate') + 1]) if '--rate' in args else 16384
    only = args[args.index('--only') + 1].split(',') if '--only' in args else None
    samples = import_bank(args[0], rate=rate, only=only)
    blob = encode_bank(samples)
    with open(args[1], 'wb') as f:
        f.write(blob)
    print(f'{args[1]}: {len(samples)} PCM8 samples, {len(blob)} bytes')


def sample_bank_path(song, directory):
    for name in sorted(os.listdir(directory)):
        if name.endswith('.gbank'):
            path = os.path.join(directory, name)
            with open(path, 'rb') as f:
                h = f.read(12)
            if h[:4] == b'GBK\x01' and h[4] == song[26] and h[5] == 0 and h[8:12] == song[28:32]:
                return path
            if h[:4] == b'GBZ\x01' and h[8:12] == song[28:32]:
                return path
    raise ValueError('no matching sample bank in ' + directory)


def studio_projects(directory, rate):
    from studio_theme import THEMES, SAMPLES
    node = shutil.which('node')
    if not node:
        sys.exit('node is required to render the studio instruments')
    subprocess.run([node, os.path.join(ROOT, 'chiptune', 'studio', 'samples.cjs'),
                    os.path.join(ROOT, 'chiptune', 'studio', 'banks', 'tracker.cjs'), directory,
                    '--only', ','.join(SAMPLES)], check=True)
    built = [(name, fn(directory, rate=rate)) for name, fn in THEMES.items()]
    bank = built[0][1][1]
    if any(pair[1] != bank for _, pair in built):
        sys.exit('the studio themes must share one bank')
    return built


def cmd_studio(args):
    rate = int(args[args.index('--rate') + 1]) if '--rate' in args else 16384
    directory = os.path.join(BUILD, 'studio-rock')
    built = studio_projects(directory, rate)
    bank = built[0][1][1]
    if len(bank) > 256 * 1024:
        sys.exit(f'rock bank is {len(bank)} bytes; budget is 256 KiB')
    os.makedirs(MUSIC, exist_ok=True)
    for name, data in [(name + '.gbm', encode_song(pair[0].project())) for name, pair in built] + [('rock.gbank', bank)]:
        with open(os.path.join(MUSIC, name), 'wb') as f:
            f.write(data)
        print(f'  {name}: {len(data)} bytes')
    for name, (song, _) in built:
        with open(os.path.join(directory, name + '.gbm.json'), 'w') as f:
            json.dump(song.project(), f, indent=1)


COMMANDS = {'songs': cmd_songs, 'encode': cmd_encode, 'render': cmd_render,
            'render-all': cmd_render_all, 'test': cmd_test, 'bank': cmd_bank, 'studio': cmd_studio}

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(2)
    COMMANDS[sys.argv[1]](sys.argv[2:])
