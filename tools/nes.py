"""NES-style instrument presets for a four-voice format-2 song:
two pulses, a triangle and noise.

Pulse volume curves are tables, not the hardware envelope. vox keeps GBM's
clock and noise periods, so this is close to an NES, not an APU emulation.
"""
from gbm_compose import noise_kick


def _pulse(song, name, width, peak, step, drop=1, vibrato=False):
    # Table levels, because the hardware envelope can't do a slow step
    # or drop several levels at once.
    levels = list(range(peak, 0, -drop)) + [0]
    table = song.table(name + ' decay', [dict(env=level << 4) for level in levels])
    song.voice('pulse', name, width=width, volume=peak, envPace=0,
               table=table, tableSpeed=step - 1,
               vibSpeed=15 if vibrato else 0, vibDepth=2 if vibrato else 0)


def nes_kit(song):
    """Add the NES instruments to `song` (format 2, four voices).

    Pulse widths 32/64/128/192 = 12.5/25/50/75%. Each lead has a quieter
    twin for echoes and harmonies. Triangle has constant volume. Noise:
    hats at #43, snare at #32.
    """
    if song.s['version'] != 2 or song.voices != 4:
        raise ValueError('nes_kit needs a four-voice format-2 song')
    presets = [
        ('air_square', 128, 14, 16, 1, False),
        ('bright_pulse', 64, 14, 4, 1, False),
        ('riff_harmony', 64, 10, 4, 1, False),
        ('pulse_echo', 128, 10, 18, 1, False),
        ('thin_lead', 32, 15, 21, 3, True),
        ('thin_riff', 32, 10, 4, 1, False),
        ('wide_lead', 192, 15, 21, 3, True),
        ('reprise_square', 128, 15, 21, 3, True),
        ('reprise_echo', 128, 10, 10, 1, False),
        ('final_pulse', 64, 15, 21, 3, True),
        ('final_harmony', 64, 10, 10, 1, False),
    ]
    names = {p[0] for p in presets} | {'triangle_bass', 'triangle_tom',
             'noise_kick', 'noise_snare', 'noise_hat', 'noise_open'}
    if names.intersection(i['name'] for i in song.s['instruments']):
        raise ValueError('NES instrument names already exist')
    for preset in presets:
        _pulse(song, *preset)
    song.voice('triangle', 'triangle_bass', volume=15, envPace=0)
    tom = song.table('triangle fall', [dict(pitch=-24 * i) for i in range(6)]
                     + [dict(fx=(0xA, 1))])
    song.voice('triangle', 'triangle_tom', volume=15, envPace=0, table=tom)
    noise_kick(song, name='noise_kick', volume=15)
    for name, levels, speed in [('noise_hat', (15, 5, 0), 0),
                                ('noise_snare', (15, 11, 7, 3, 0), 1),
                                ('noise_open', (15, 11, 8, 5, 3, 1, 0), 1)]:
        table = song.table(name + ' transient', [dict(env=x << 4) for x in levels])
        song.voice('noise', name, duty=0, volume=15, envPace=0, table=table, tableSpeed=speed)
