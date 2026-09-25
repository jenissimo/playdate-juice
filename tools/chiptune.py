#!/usr/bin/env python3
"""chiptune's host-side tools.

    python tools/chiptune.py songs [--json DIR]    build chiptune/music/*.gbm from tools/chiptune_songs.py
    python tools/chiptune.py encode in.gbm.json out.gbm
    python tools/chiptune.py render in.gbm out.wav [renderer options]
    python tools/chiptune.py render-all DIR [--adpcm] [--rate 22050]
    python tools/chiptune.py test                  the C port against the original ROM, and the encoder

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
CORE = ['chiptune/gbapu.c', 'chiptune/gbm.c', 'chiptune/chip.c']


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
        if blob[4]:     # has orders: a song
            subprocess.run([exe, path, os.path.join(out, f[:-4] + '.wav'), '--mono'] + extra, check=True)
        for i, n in enumerate(sfx_names(blob)):
            subprocess.run([exe, path, os.path.join(out, 'sfx_' + n + '.wav'), '--sfx', str(i), '--mono'] + extra,
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
        exe = compile_c(['test/chiptune/trace_test.c', 'chiptune/gbm.c', 'chiptune/gbapu.c'], 'trace_test')
        r = subprocess.run([exe, tmp] + scenarios)
        fails += r.returncode != 0
    # The shipped songs build and every effect has a name.
    import chiptune_songs
    for name, fn in chiptune_songs.SONGS.items():
        blob = encode_song(fn().project())
        want = os.path.join(MUSIC, name + '.gbm')
        if not os.path.isfile(want) or open(want, 'rb').read() != blob:
            print(f'  chiptune/music/{name}.gbm is stale: run `python tools/chiptune.py songs`')
            fails += 1
    print('chiptune: ' + ('all passed' if not fails else f'{fails} failure(s)'))
    sys.exit(1 if fails else 0)


COMMANDS = {'songs': cmd_songs, 'encode': cmd_encode, 'render': cmd_render,
            'render-all': cmd_render_all, 'test': cmd_test}

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(2)
    COMMANDS[sys.argv[1]](sys.argv[2:])
