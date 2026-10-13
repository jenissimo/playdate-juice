"""Steel Circuit: a live PCM8 tracker band, with a vox acid voice.

Eight voices: guitar, bass, lead, kick, snare, hats, orchestra, acid.
The eight rendered instruments share one 16 KiHz bank. It is a fresh
tracker arrangement, rather than an export of studio's mastered loops.
"""
from gbm_compose import Song, studio_bank, transpose_text

SAMPLES = ('gtr_chord', 'gtr_chug', 'gtr_lead', 'bass', 'kick', 'snare', 'hat', 'orch_am',
           'clap', 'ohat', 'stab', 'pad', 'reese', 'trance_saw', 'trance_pluck', 'pad_f', 'pad_g')


def theme(directory, rate=16384):
    # ~138 BPM on the driver's 59.73 Hz clock, a six-frame row with a
    # seven-frame row every other beat: the same groove repeats at the loop.
    s = Song('Steel Circuit', groove=(6, 7), version=3, voices=8)
    bank = studio_bank(s, directory, rate=rate, only=SAMPLES)
    levels = dict(gtr_chord=10, gtr_chug=11, gtr_lead=9, bass=9,
                  kick=15, snare=13, hat=5, orch_am=7)
    for ins in s.s['instruments']:
        ins['volume'] = levels.get(ins['name'], 8)
    acid_table = s.table('acid pluck', [dict(fx=(0x10, c)) for c in (180, 145, 110, 80, 60)])
    s.voice('saw', 'acid', volume=5, envPace=2, filter=True, table=acid_table,
            length=10, width=100)
    s.s['filter'] = dict(cutoff=90, resonance=9, mode=1)
    riff = 'A2@gtr_chord . - A2@gtr_chug A2@gtr_chug - C3@gtr_chord . - A2@gtr_chug D3@gtr_chord . - A2@gtr_chug C3@gtr_chord -'
    bass = 'A1@bass . . - A1@bass . C2@bass - A1@bass . D2@bass - A1@bass . C2@bass -'
    lead_a = 'E5@gtr_lead . . D5@gtr_lead E5@gtr_lead . G5@gtr_lead . A5@gtr_lead+447 . . . . . - .'
    lead_b = 'G5@gtr_lead+400 . E5+318 . D5@gtr_lead . . . E5@gtr_lead . . D5@gtr_lead C5@gtr_lead . B4@gtr_lead -'
    kicks = 'C5@kick . . . . . C5@kick . C5@kick . . . . . C5@kick .'
    snares = '. . . . C5@snare . . . . . . . C5@snare . . .'
    hats = 'C5@hat . C5@hat . C5@hat . C5@hat . C5@hat . C5@hat . C5@hat . C5@hat .'
    # Intro -> riff and hook -> acid break -> hook; Am, F, G, E.
    for bar in range(16):
        shift = (0, -4, -2, -5)[bar % 4]
        guitar = transpose_text(riff, shift)
        low = transpose_text(bass, shift)
        lead = '.' if bar < 4 or 8 <= bar < 12 else transpose_text(lead_a if bar % 2 == 0 else lead_b, shift)
        orch = 'A4@orch_am . . . . . . . -' if bar in (0, 4, 12) else '.'
        acid = transpose_text('A2@acid . E3@acid . G3@acid . E3@acid . A3@acid . E3@acid . C3@acid . E3@acid -', shift) if 8 <= bar < 12 else '-'
        if 8 <= bar < 10:
            guitar = '-'
        if bar in (3, 7, 11, 15):
            sna = '. . . . C5@snare . . . . . . . C5@snare . C5@snare C5@snare'
        else:
            sna = snares
        # Section markers on the guitar lane, consumed by the game as Exx.
        toks = guitar.split()
        if bar % 4 == 0:
            toks[0] += f'+E{bar // 4 + 1:02X}'
        s.bar([' '.join(toks), low, lead, kicks, sna, hats, orch, acid])
    return s, bank


def jungle(directory, rate=16384):
    s = Song('Chrome Breaks', groove=(5, 5, 5, 6), version=3, voices=8)
    bank = studio_bank(s, directory, rate=rate, only=SAMPLES)
    levels = dict(kick=14, snare=13, hat=5, ohat=5, reese=10, stab=8,
                  trance_pluck=7, orch_am=6)
    for ins in s.s['instruments']:
        ins['volume'] = levels.get(ins['name'], 8)
    s.voice('pulse', 'bleep', width=64, volume=5, envPace=1, length=7)
    bass_a = 'A1@reese . . - A2@reese . G2@reese - A1@reese . C2@reese . E2+310 . - .'
    bass_b = 'A1@reese . E2@reese - G1@reese . . - A1@reese . C2@reese - G1@reese . A1@reese -'
    kicks = ('C5@kick . . . . . C5@kick . . . C5@kick . . . . .',
             'C5@kick . . C5@kick . . . . . C5@kick . . . . C5@kick .')
    snares = (' . . . C5@snare+540 C5@snare . . . . . . C5@snare+530 C5@snare . . C5@snare+560',
              '. . . . C5@snare . . C5@snare+550 . . C5@snare+540 . C5@snare . C5@snare+580 .')
    for bar in range(16):
        shift = (0, 0, -2, -5)[(bar // 2) % 4]
        low = transpose_text(bass_a if bar % 2 == 0 else bass_b, shift)
        hats = ' '.join('C5@hat' if i % 2 == 0 else 'C5@hat+530' for i in range(16))
        if bar % 4 == 3:
            hats = 'C5@hat . C5@hat C5@hat C5@hat . C5@ohat . C5@hat C5@hat C5@hat . C5@hat C5@hat C5@hat C5@ohat'
        stab = transpose_text('A3@stab . . - . . A3@stab . . - . . . . A3@stab -', shift) if bar >= 4 else '.'
        pluck = 'A5@trance_pluck . E5@trance_pluck . G5@trance_pluck . E5@trance_pluck . A5@trance_pluck . C6@trance_pluck . B5@trance_pluck . E5@trance_pluck .' if bar >= 12 else '.'
        orch = 'A4@orch_am . . . . . . . -' if bar in (0, 8) else '.'
        bleep = 'A5@bleep . . - . . . . E6@bleep . . - . . . .' if 8 <= bar < 12 else '-'
        kick = kicks[bar % 2]
        if bar % 4 == 0:
            kick = kick.replace('C5@kick', f'C5@kick+E{bar // 4 + 1:02X}', 1)
        s.bar([low, stab, pluck, kick, snares[bar % 2], hats, orch, bleep])
    return s, bank


def trance(directory, rate=16384):
    s = Song('Prism Drive', groove=(7, 7, 6, 7), version=3, voices=8)
    bank = studio_bank(s, directory, rate=rate, only=SAMPLES)
    levels = dict(kick=15, snare=10, clap=9, hat=4, ohat=5, bass=9,
                  trance_saw=8, trance_pluck=8, pad=5, pad_f=5, pad_g=5)
    for ins in s.s['instruments']:
        ins['volume'] = levels.get(ins['name'], 7)
    t = s.table('acid decay', [dict(fx=(0x10, c)) for c in (210, 180, 140, 100, 70)])
    s.voice('saw', 'acid', volume=4, envPace=2, filter=True, table=t, length=8)
    s.s['filter'] = dict(cutoff=100, resonance=8, mode=1)
    changes = [('A2', 'A3', 'pad', 'A3', ('A4', 'C5', 'E5', 'B4')),
               ('F2', 'F3', 'pad_f', 'F3', ('A4', 'C5', 'F5', 'C5')),
               ('G2', 'G3', 'pad_g', 'G3', ('G4', 'B4', 'D5', 'B4')),
               ('A2', 'A3', 'pad', 'A3', ('E5', 'C5', 'B4', 'A4'))]
    for bar in range(16):
        root, pad_note, pad_inst, chord_root, arp = changes[(bar // 2) % 4]
        bass = ' '.join(root + '@bass+A03' if i % 4 == 2 else '.' for i in range(16))
        pad = pad_note + '@' + pad_inst + ' ' + ' '.join('.' for _ in range(15)) if bar % 2 == 0 else '.'
        lead = ' '.join(arp[(i // 2) % 4] + '@trance_saw+A07' if i % 2 == 0 else '.' for i in range(16)) if bar >= 8 else '-'
        pluck = ' '.join(arp[i % 4] + '@trance_pluck' for i in range(16)) if bar >= 4 else '.'
        kick = 'C5@kick . . . C5@kick . . . C5@kick . . . C5@kick . . .'
        if bar % 4 == 0:
            kick = kick.replace('C5@kick', f'C5@kick+E{bar // 4 + 1:02X}', 1)
        snare = '. . . . C5@clap . . . . . . . C5@snare . . .'
        hats = 'C5@hat . C5@ohat . C5@hat . C5@ohat . C5@hat . C5@ohat . C5@hat . C5@ohat .'
        acid = ' '.join(root + '@acid' if i % 4 in (1, 3) else '.' for i in range(16)) if bar >= 12 else '-'
        # A two-bar breakdown before the final build.
        if bar in (10, 11):
            kick, bass, snare = '-', '-', '-'
        s.bar([lead, bass, pad, kick, snare, hats, pluck, acid])
    return s, bank


THEMES = {'steel_circuit': theme, 'chrome_breaks': jungle, 'prism_drive': trance}
