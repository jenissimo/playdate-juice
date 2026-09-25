#!/usr/bin/env python3
"""Build the demo (the Zoo) .pdx.

    python tools/build_demo.py [--lua-only] [--no-device]

The library modules live at the repo ROOT so that a consumer can add this repo
as a submodule straight inside their Source/ and `import "juice/sfxkit"`. pdc,
though, only compiles what is under the source folder it is given -- and
`import "../sfxkit"` does not resolve outside it. So the demo build copies the
modules in, compiles, and cleans up. The copies are gitignored.

The demo's OWN sources are kept as .lua.in for the same reason in reverse: pdc
compiles every .lua in the tree it is pointed at, so a consumer who submodules
this repo into their Source/ would otherwise have the demo's main.lua compiled
as part of THEIR game -- and it would fail, because the modules it imports are
only copied in at demo-build time.

On top of the Lua, the Zoo stages:
  music/     chiptune/music/*.gbm, the songs and the SFX bank;
  jukebox/   two songs pre-rendered to ADPCM WAV, for the Jukebox exhibit
             (needs a host C compiler; skipped without one);
  pdex.*     the chiptune C extension, built with CMake: for the simulator
             with the host compiler, and for the device when arm-none-eabi-gcc
             is on PATH (or ARM_GCC_BIN points at its bin/). --lua-only skips
             it: the Zoo then runs without chiptune, and says so.
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_DIR = os.path.join(ROOT, "demo")
DEMO = os.path.join(DEMO_DIR, "Source")
OUT = os.path.join(DEMO_DIR, "Juice.pdx")
BUILD = os.path.join(ROOT, "build")

MODULES = [
    "transitions.lua", "sfxkit.lua", "jukebox.lua", "chiptune.lua",
    "tween.lua", "shake.lua", "particles.lua", "backgrounds.lua",
]
JUKEBOX_SONGS = ["tidal_twang", "willow_lane"]


def find_sdk():
    sdk = os.environ.get("PLAYDATE_SDK_PATH")
    if sdk and os.path.isdir(sdk):
        return sdk
    for c in ("~/Documents/PlaydateSDK", "~/Developer/PlaydateSDK"):
        c = os.path.expanduser(c)
        if os.path.isdir(c):
            return c
    sys.exit("Playdate SDK not found -- set PLAYDATE_SDK_PATH")


def find_pdc(sdk):
    for c in (os.path.join(sdk, "bin", "pdc.exe"), os.path.join(sdk, "bin", "pdc")):
        if os.path.isfile(c):
            return c
    found = shutil.which("pdc")
    if found:
        return found
    sys.exit("pdc not found -- set PLAYDATE_SDK_PATH")


def cmake(args, env=None):
    r = subprocess.run(["cmake"] + args, env=env, capture_output=True, text=True)
    if r.returncode:
        print(r.stdout[-3000:], r.stderr[-3000:])
        sys.exit("cmake " + " ".join(args[:2]) + " failed")


def build_native(sdk, device):
    """pdex.dll / .dylib / .so for the simulator, and pdex.elf for the device."""
    env = dict(os.environ, PLAYDATE_SDK_PATH=sdk)
    if not shutil.which("cmake"):
        print("no cmake: building without the chiptune extension")
        return False
    sim = os.path.join(BUILD, "demo-sim")
    gen = ["-G", "Visual Studio 17 2022", "-A", "x64"] if os.name == "nt" else []
    cmake(["-S", DEMO_DIR, "-B", sim] + gen, env)
    # --clean-first: the build's post-step is what copies pdex into Source/,
    # and a target CMake thinks is up to date would skip it.
    cmake(["--build", sim, "--config", "Release", "--clean-first"], env)
    print("built the simulator extension")
    if not device:
        return True
    arm_bin = os.environ.get("ARM_GCC_BIN")
    if arm_bin:
        env["PATH"] = arm_bin + os.pathsep + env["PATH"]
    if not shutil.which("arm-none-eabi-gcc", path=env["PATH"]):
        print("no arm-none-eabi-gcc: the .pdx runs in the simulator only")
        return True
    dev = os.path.join(BUILD, "demo-device")
    gen = ["-G", "Ninja"] if shutil.which("ninja") else (["-G", "MinGW Makefiles"] if os.name == "nt" else [])
    cmake(["-S", DEMO_DIR, "-B", dev, "-DCMAKE_BUILD_TYPE=Release",
           "-DCMAKE_TOOLCHAIN_FILE=" + os.path.join(sdk, "C_API", "buildsupport", "arm.cmake")] + gen, env)
    cmake(["--build", dev, "--clean-first"], env)
    print("built the device extension")
    return True


def render_jukebox(dst):
    """The Jukebox exhibit's tracks: chiptune songs as ADPCM files."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    try:
        import chiptune
        exe = chiptune.renderer()
    except SystemExit as e:
        print("jukebox tracks skipped:", e)
        return
    os.makedirs(dst, exist_ok=True)
    for song in JUKEBOX_SONGS:
        subprocess.run([exe, os.path.join(ROOT, "chiptune", "music", song + ".gbm"),
                        os.path.join(dst, song + ".wav"), "--loops", "2", "--mono", "--adpcm", "--rate", "22050"],
                       check=True, stdout=subprocess.DEVNULL)


def main():
    lua_only = "--lua-only" in sys.argv
    device = "--no-device" not in sys.argv
    sdk = find_sdk()
    staged = []
    staged_dirs = []
    try:
        for m in MODULES:
            src = os.path.join(ROOT, m)
            if not os.path.isfile(src):
                sys.exit("missing module: " + m)
            dst = os.path.join(DEMO, m)
            shutil.copy2(src, dst)
            staged.append(dst)

        for f in sorted(os.listdir(DEMO_DIR)):
            if f.endswith(".lua.in"):
                dst = os.path.join(DEMO, f[:-3])      # strip the ".in"
                shutil.copy2(os.path.join(DEMO_DIR, f), dst)
                staged.append(dst)

        # The paw effect loads images/ from the pdx root by the same relative
        # path the library uses, so the folder has to come along too.
        for name, src in (("images", os.path.join(ROOT, "images")),
                          ("music", os.path.join(ROOT, "chiptune", "music"))):
            dst = os.path.join(DEMO, name)
            shutil.copytree(src, dst, dirs_exist_ok=True)
            staged_dirs.append(dst)
        jb = os.path.join(DEMO, "jukebox")
        render_jukebox(jb)
        staged_dirs.append(jb)

        if not lua_only:
            build_native(sdk, device)

        pdc = find_pdc(sdk)
        print("pdc:", pdc)
        r = subprocess.run([pdc, "-sdkpath", sdk, DEMO, OUT])
        if r.returncode != 0:
            sys.exit(r.returncode)
        print("built", OUT)
    finally:
        for c in staged:
            if os.path.isfile(c):
                os.remove(c)
        for d in staged_dirs:
            shutil.rmtree(d, ignore_errors=True)
        # playdate_game.cmake runs pdc after each CMake build; the device one
        # leaves its own .pdx next to ours.
        shutil.rmtree(os.path.join(DEMO_DIR, "Juice_DEVICE.pdx"), ignore_errors=True)
        for pdex in ("pdex.dll", "pdex.dylib", "pdex.so", "pdex.elf"):
            p = os.path.join(DEMO, pdex)
            if os.path.isfile(p):
                os.remove(p)


if __name__ == "__main__":
    main()
