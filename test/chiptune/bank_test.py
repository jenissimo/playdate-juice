"""Importer checks with actual WAVs, including filtered resampling and loops."""
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
from gbm_bank import import_bank, encode_bank, bank_hash
from gbm_compose import Song, studio_bank
from gbm_format import encode_song


class BankTests(unittest.TestCase):
    def test_studio_resampled_metadata(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run(['node', os.path.join(root, 'chiptune', 'studio', 'samples.cjs'),
                            os.path.join(root, 'chiptune', 'studio', 'banks', 'rock.cjs'), directory,
                            '--only', 'pad', '--rate', '16384'], check=True, stdout=subprocess.DEVNULL)
            # An odd resampled length formerly disagreed with the WAV by a frame.
            samples = import_bank(directory, rate=16384)
            self.assertEqual(samples[0]['loop'][1], len(samples[0]['pcm8']))

    def test_bank_import(self):
        with tempfile.TemporaryDirectory() as directory:
            data = [(-20000, -10000, 10000, 20000)[i % 4] for i in range(2205)]
            with wave.open(os.path.join(directory, 'tone.wav'), 'wb') as w:
                w.setparams((1, 2, 22050, len(data), 'NONE', 'not compressed'))
                w.writeframes(struct.pack('<' + 'h' * len(data), *data))
            meta = [dict(name='tone', file='tone.wav', rate=22050, length=len(data), root=69, loop=[882, 2205])]
            path = os.path.join(directory, 'bank.json')
            with open(path, 'w') as f:
                json.dump(meta, f)
            samples = import_bank(directory, rate=11025)
            self.assertEqual(samples[0]['root'], 69)
            self.assertEqual(samples[0]['rate'], 11025)
            self.assertEqual(samples[0]['loop'], [441, len(samples[0]['pcm8'])])
            self.assertEqual(samples, import_bank(directory, rate=11025))
            blob = encode_bank(samples)
            self.assertEqual(struct.unpack_from('<I', blob, 8)[0], bank_hash(blob))
            self.assertEqual(struct.unpack_from('<I', blob, 24)[0], 440000)
            s = Song('import', version=3, voices=1)
            self.assertEqual(studio_bank(s, directory, rate=11025), blob)
            s.bar(['A4@tone . . -'])
            song = encode_song(s.project())
            self.assertEqual(song[2], 3)
            self.assertEqual(song[28:32], blob[8:12])
            with self.assertRaisesRegex(ValueError, 'no studio sample'):
                import_bank(directory, only=['missing'])
            meta[0]['loop'] = [2000, 1000]
            with open(path, 'w') as f:
                json.dump(meta, f)
            with self.assertRaisesRegex(ValueError, 'loop outside'):
                import_bank(directory)

    def test_bank_validation(self):
        with self.assertRaises(ValueError):
            encode_bank([])
        with self.assertRaises(ValueError):
            encode_bank([dict(pcm8=b'\x00', rate=16384, root=69, loop=[0, 2])])
        with self.assertRaisesRegex(ValueError, 'version'):
            s = Song('invalid', version=4, voices=1)
            s.bar(['C4'])
            encode_song(s.project())


if __name__ == '__main__':
    unittest.main()
