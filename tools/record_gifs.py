#!/usr/bin/env python3
"""Film the README's GIFs in the Zoo.

    python tools/record_gifs.py [--encode-only] [--scale N] [--out DIR] [clip ...]

Builds demo/Juice-Record.pdx (build_demo.py --record), runs it in the
simulator -- demo/record.lua.in plays the Zoo with scripted presses and crank
turns and writes every frame of each clip -- then turns the frames into GIFs
in the Playdate's own two colours, scaled up with hard pixel edges.

The simulator plays the music out loud while it films. --encode-only skips
the build and the run and re-encodes the frames already in build/gif-frames.
Needs Pillow.
"""
import os
import re
import shutil
import subprocess
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES = os.path.join(ROOT, "build", "gif-frames")
PDX = os.path.join(ROOT, "demo", "Juice-Record.pdx")

# The Memory LCD is not black on white: dark ink on a grey-green panel.
INK = (49, 47, 40)
PAPER = (177, 175, 168)

CUT = re.compile(r"record: cut (\S+) (\d+) (\d+)")


def run_simulator():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import build_demo
    sdk = build_demo.find_sdk()
    exe = os.path.join(sdk, "bin", "PlaydateSimulator.exe" if os.name == "nt" else "PlaydateSimulator")
    if not os.path.isfile(exe):
        sys.exit("simulator not found: " + exe)
    shutil.rmtree(FRAMES, ignore_errors=True)
    os.makedirs(FRAMES)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_demo.py"), "--record", FRAMES], check=True)
    log = os.path.join(FRAMES, "sim.log")
    with open(log, "w", encoding="utf-8") as f:
        subprocess.run([exe, PDX], stdout=f, stderr=subprocess.STDOUT, timeout=900)
    return log


def read_clips(log):
    with open(log, encoding="utf-8", errors="replace") as f:
        clips = [(m[0], int(m[1]), int(m[2])) for m in CUT.findall(f.read())]
    if not clips:
        sys.exit("no clips in " + log + " -- did the script run to the end?")
    return clips


def durations(frames, every):
    """GIF delays are whole centiseconds: round a running 30 fps clock instead
    of each frame, so 33.3 ms averages out to 30, 30, 40 rather than 30."""
    out, last = [], 0
    for i in range(1, frames + 1):
        t = round(i * every * 100 / 30) * 10
        out.append(t - last)
        last = t
    return out


def encode(name, frames, every, scale, out_dir):
    palette = list(INK) + list(PAPER) + [0] * (254 * 3)
    images = []
    for i in range(1, frames + 1):
        src = Image.open(os.path.join(FRAMES, "%s-%04d.png" % (name, i))).convert("L")
        img = src.point(lambda v: 1 if v >= 128 else 0).convert("P")
        img.putpalette(palette)
        if scale != 1:
            img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
        images.append(img)
    path = os.path.join(out_dir, name + ".gif")
    images[0].save(path, save_all=True, append_images=images[1:], duration=durations(frames, every),
                   loop=0, optimize=False, disposal=1)
    print("%-12s %4d frames  %6.0f KiB  %s" % (name, frames, os.path.getsize(path) / 1024, path))


def main():
    args = sys.argv[1:]
    encode_only = "--encode-only" in args
    scale, out_dir = 2, os.path.join(ROOT, "build", "gifs")
    if "--scale" in args:
        scale = int(args[args.index("--scale") + 1])
    if "--out" in args:
        out_dir = os.path.abspath(args[args.index("--out") + 1])
    only = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] not in ("--scale", "--out"))]
    log = os.path.join(FRAMES, "sim.log") if encode_only else run_simulator()
    os.makedirs(out_dir, exist_ok=True)
    for name, frames, every in read_clips(log):
        if not only or name in only:
            encode(name, frames, every, scale, out_dir)


if __name__ == "__main__":
    main()
