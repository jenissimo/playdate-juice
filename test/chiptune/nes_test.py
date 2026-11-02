"""NES instrument presets: palette, envelope timing in the C driver, and a
full render of iron_spire."""
import math
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from gbm_compose import Song
from gbm_format import encode_song
from nes import nes_kit


class NesTests(unittest.TestCase):
    def test_palette(self):
        song = Song('own song', version=2, voices=4)
        nes_kit(song)
        song.bar(['C#5@air_square . G#5 . -', 'C#4@bright_pulse E4 G#4',
                  'C#4@triangle_bass . -', '#32@noise_snare #43@noise_hat'])
        blob = encode_song(song.project())
        self.assertEqual((blob[2], blob[7]), (2, 4))
        by_name = {i['name']: i for i in song.s['instruments']}
        self.assertEqual({by_name[n]['width'] for n in
                          ('bright_pulse', 'air_square', 'thin_lead', 'wide_lead')}, {32, 64, 128, 192})
        self.assertGreater(by_name['air_square']['volume'], by_name['pulse_echo']['volume'])
        for name in ('triangle_bass', 'triangle_tom'):
            self.assertEqual(by_name[name]['osc'], 'triangle')
            self.assertEqual((by_name[name]['volume'], by_name[name]['envPace']), (15, 0))
        for name in ('noise_kick', 'noise_snare', 'noise_hat', 'noise_open'):
            self.assertEqual(by_name[name]['kind'], 'noise')
            self.assertEqual(by_name[name]['duty'], 0)
        with self.assertRaisesRegex(ValueError, 'already exist'):
            nes_kit(song)
        for version, voices in ((1, 4), (2, 8), (4, 4)):
            with self.assertRaisesRegex(ValueError, 'four-voice format-2'):
                nes_kit(Song('wrong format', version=version, voices=voices))

    def test_driver_envelope_timing(self):
        from chiptune import compile_c, CORE
        with tempfile.TemporaryDirectory() as tmp:
            fixtures = []
            for name, voices in [('song', ['C#4@air_square', 'C#4@pulse_echo',
                                          'C#4@triangle_bass', '#43@noise_hat']),
                                 ('solo', ['C#4@bright_pulse', 'C#4@thin_lead',
                                           'C#4@triangle_bass', '#32@noise_snare'])]:
                song = Song(name, version=2, voices=4, groove=(255,))
                nes_kit(song)
                song.bar(voices)
                path = os.path.join(tmp, name + '.gbm')
                Path(path).write_bytes(encode_song(song.project()))
                fixtures.append(path)
            exe = compile_c(['test/chiptune/nes_probe.c'] + CORE, 'nes_probe')
            subprocess.run([exe] + fixtures, check=True)

    def test_iron_spire_render(self):
        from chiptune import renderer
        exe = renderer()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'full.wav')
            # A whole loop (~43 s) and well into the second.
            subprocess.run([exe, str(ROOT / 'chiptune/music/iron_spire.gbm'), path,
                            '--seconds', '77', '--mono'], check=True, stdout=subprocess.DEVNULL)
            with wave.open(path) as w:
                self.assertEqual((w.getnchannels(), w.getframerate()), (1, 44100))
                self.assertGreater(w.getnframes(), 76 * 44100)
                for second in range(76):
                    data = [v[0] for v in struct.iter_unpack('<h', w.readframes(44100))]
                    rms = math.sqrt(sum(x * x for x in data) / len(data))
                    self.assertGreater(rms, 500, f'silent second {second}')
                    self.assertLess(max(abs(x) for x in data), 32767)


if __name__ == '__main__':
    unittest.main()
