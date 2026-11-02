"""Importer checks with actual WAVs, including filtered resampling and loops."""
import json
import os
import struct
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
from gbm_bank import import_bank, encode_bank, bank_hash
from gbm_compose import Song, sample_bank
from gbm_format import encode_song


class BankTests(unittest.TestCase):
    def test_resampled_loop_end(self):
        # An odd resampled length once disagreed with the WAV by a frame.
        with tempfile.TemporaryDirectory() as directory:
            data = [(i * 37) % 2000 - 1000 for i in range(3001)]
            with wave.open(os.path.join(directory, 'pad.wav'), 'wb') as w:
                w.setparams((1, 2, 22050, len(data), 'NONE', 'not compressed'))
                w.writeframes(struct.pack('<' + 'h' * len(data), *data))
            with open(os.path.join(directory, 'bank.json'), 'w') as f:
                json.dump([dict(name='pad', file='pad.wav', rate=22050, length=len(data),
                                root=57, loop=[1000, len(data)])], f)
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
            s = Song('import', version=4, voices=1)
            self.assertEqual(sample_bank(s, directory, rate=11025), blob)
            s.bar(['A4@tone . . -'])
            song = encode_song(s.project())
            self.assertEqual(song[2], 4)
            self.assertEqual(song[28:32], blob[8:12])
            with self.assertRaisesRegex(ValueError, 'no such sample'):
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
            s = Song('invalid', version=5, voices=1)
            s.bar(['C4'])
            encode_song(s.project())

    def test_sampler_layout_is_explicit(self):
        s = Song('format 3 with a bank', version=3, voices=1)
        s.s['sampleBank'] = dict(count=1, hash=1)
        s.bar(['C4'])
        with self.assertRaisesRegex(ValueError, 'external sample banks need format 4'):
            encode_song(s.project())
        s = Song('wrong sampler oscillator', version=4, voices=1)
        s.voice('pcm', 'wrong')
        s.bar(['C4@wrong'])
        with self.assertRaisesRegex(ValueError, 'bank instruments use the sample oscillator'):
            encode_song(s.project())


if __name__ == '__main__':
    unittest.main()
