"""Record original studio songs, build their bank, calibrate and compare.

All measurements use the same renderer as Playdate and 44100 Hz mono.
Lane gains solve measured LUFS targets; output make-up is measured after
the driver's clipper/limiter, not selected by ear.
"""
import json
import math
import os
import subprocess
import sys
import shutil
import hashlib

import chiptune
import studio_port
from gbm_bank_codec import pack_bank

ROOT = chiptune.ROOT
STUDIO = os.path.join(ROOT, 'chiptune', 'studio')
OUT = os.path.join(ROOT, 'build', 'studio-port')


def node(script, *args):
    subprocess.run(['node', os.path.join(STUDIO, script), *args], check=True)


def stats(path):
    source = "const C=require('./chiptune/studio/compare_tracker.cjs');console.log(JSON.stringify(C.score(C.readWav(process.argv[1]))));"
    return json.loads(subprocess.check_output(['node', '-e', source, path], cwd=ROOT, text=True))


def build(names=('menu', 'play', 'multi'), publish=False):
    os.makedirs(OUT, exist_ok=True)
    node('export_tracker.cjs', os.path.join(STUDIO, 'songs', 'overturn_rock.cjs'), os.path.join(OUT, 'events.json'), *names)
    bank_dir = os.path.join(OUT, 'bank')
    node('prepare_tracker.cjs', os.path.join(OUT, 'events.json'), bank_dir)
    studio_port.build(bank_dir, OUT, mix_gain=0, quiet=True, packed=False)
    exe = chiptune.renderer()
    with open(os.path.join(bank_dir, 'port.json')) as f:
        source = json.load(f)
    gains = {}
    for name in names:
        gains[name] = []
        for lane in range(8):
            path = os.path.join(OUT, name + f'-lane{lane}.wav')
            subprocess.run([exe, os.path.join(OUT, 'studio_' + name + '.gbm'), path,
                            '--bank', os.path.join(OUT, 'overturn.gbank'), '--loops', '2', '--mono',
                            '--mute', str(255 ^ (1 << lane))], check=True, stdout=subprocess.DEVNULL)
            measured = stats(path)['lufs']
            wanted = source['songs'][name]['laneTargets'][lane]['lufs']
            gains[name].append(10 ** ((wanted - measured) / 20) if wanted > -69 and measured > -69 else 1)
        print(name + ' measured lane gains: ' + ', '.join(f'{g:.3f}' for g in gains[name]))
    reports = {}
    for name in names:
        # Each loop's make-up is independent, while its PCM bank is shared.
        makeup = 0.6
        path = os.path.join(OUT, 'tracker_' + name + '.wav')
        for _ in range(6):
            studio_port.build(bank_dir, OUT, mix_gain=makeup, lane_gains=gains, quiet=True, packed=False)
            subprocess.run([exe, os.path.join(OUT, 'studio_' + name + '.gbm'), path,
                            '--bank', os.path.join(OUT, 'overturn.gbank'), '--loops', '2', '--mono'], check=True, stdout=subprocess.DEVNULL)
            measured = stats(path)
            error = -14.5 - measured['lufs']
            if abs(error) < 0.1:
                break
            makeup *= 10 ** (error / 20)
        reports[name] = { 'mixGain': makeup, 'stats': measured, 'laneGains': gains[name] }
    # Rebuild with each calibrated make-up, retaining one immutable bank.
    for name in names:
        with open(os.path.join(bank_dir, 'studio_' + name + '.gbm.json')) as f:
            song = json.load(f)
        song['mixGain'] = reports[name]['mixGain']
        with open(os.path.join(OUT, 'studio_' + name + '.gbm'), 'wb') as f:
            f.write(chiptune.encode_song(song))
        with open(os.path.join(bank_dir, 'studio_' + name + '.gbm.json'), 'w') as f:
            json.dump(song, f, indent=1)
        path = os.path.join(OUT, 'tracker_' + name + '.wav')
        subprocess.run([exe, os.path.join(OUT, 'studio_' + name + '.gbm'), path,
                        '--bank', os.path.join(OUT, 'overturn.gbank'), '--loops', '2', '--mono'], check=True, stdout=subprocess.DEVNULL)
        reports[name]['stats'] = stats(path)
    raw_bank = open(os.path.join(OUT, 'overturn.gbank'), 'rb').read()
    packed_bank = pack_bank(raw_bank)
    with open(os.path.join(OUT, 'overturn.gbank'), 'wb') as f:
        f.write(packed_bank)
    node('render.cjs', os.path.join(STUDIO, 'songs', 'overturn_rock.cjs'), '--only', ','.join(names),
         '--out', os.path.join(OUT, 'original'), '--preview', os.path.join(OUT, 'original-preview'))
    audits = {}
    for name in names:
        compare = os.path.join(OUT, name + '-comparison.json')
        node('compare_tracker.cjs', os.path.join(OUT, 'original-preview', name + '.wav'),
             os.path.join(OUT, 'tracker_' + name + '.wav'), compare)
        with open(compare) as f:
            comparison = json.load(f)
        if not comparison['pass']:
            raise ValueError(name + ': A/B acceptance failed')
        with open(os.path.join(bank_dir, 'studio_' + name + '.audit.json')) as f:
            audits[name] = json.load(f)
        audits[name].update(bank_bytes=len(packed_bank), bank_ram_bytes=len(raw_bank),
                           mix_gain=reports[name]['mixGain'], lane_gains=gains[name], comparison=comparison)
    sources = ['chiptune/studio/songs/overturn_rock.cjs', 'chiptune/studio/instruments.cjs',
               'chiptune/studio/compose.cjs', 'chiptune/studio/synth.cjs', 'chiptune/studio/master.cjs',
               'chiptune/studio/export_tracker.cjs', 'chiptune/studio/prepare_tracker.cjs',
               'tools/studio_port.py', 'tools/gbm_bank_codec.py']
    source_hashes = {p: hashlib.sha256(open(os.path.join(ROOT, p), 'rb').read()).hexdigest() for p in sources}
    asset_hashes = {p: hashlib.sha256(open(os.path.join(OUT, p), 'rb').read()).hexdigest()
                    for p in ['overturn.gbank'] + ['studio_' + name + '.gbm' for name in names]}
    manifest = dict(bank='overturn.gbank', bank_bytes=len(packed_bank), bank_ram_bytes=len(raw_bank),
                    codec_workspace_bytes=263168, source_hashes=source_hashes, asset_hashes=asset_hashes, songs=audits)
    with open(os.path.join(OUT, 'studio_ports.json'), 'w') as f:
        json.dump(manifest, f, indent=1)
    if publish:
        for filename in ['overturn.gbank', 'studio_ports.json'] + ['studio_' + name + '.gbm' for name in names]:
            shutil.copy2(os.path.join(OUT, filename), os.path.join(chiptune.MUSIC, filename))
    with open(os.path.join(OUT, 'calibration.json'), 'w') as f:
        json.dump(reports, f, indent=1)
    return reports


if __name__ == '__main__':
    names = tuple(a for a in sys.argv[1:] if a != '--publish') or ('menu', 'play', 'multi')
    build(names, publish='--publish' in sys.argv)
