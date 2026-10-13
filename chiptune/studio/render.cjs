#!/usr/bin/env node
// Render a song module's loops to WAV files for Playdate.
//   node render.cjs <songs.cjs> [--out DIR] [--prefix music_] [--only a,b] [--adpcm] [--rate 22050]
//                   [--preview DIR] [--mix]
// A song module exports { name: (report) => Float32Array }: one mastered loop at 44100 Hz (see
// master.cjs). Each becomes <out>/<prefix><name>.wav: PCM 16-bit mono, or with --adpcm IMA
// ADPCM (~22 KB a second at 44.1 kHz, a quarter of PCM; pdc keeps it as it is and trims the
// last block to the true length, so a looping fileplayer has no gap at the seam). --rate
// resamples (22050 halves the size; the Playdate's speaker loses nothing above 11 kHz,
// headphones do). ffmpeg does the ADPCM and the resampling: FFMPEG=path, or ffmpeg on the PATH.
// --preview DIR writes each loop twice over (the seam in the middle) as PCM, for listening;
// --mix prints the master's report (stem loudness, bus and limiter work, bands).
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');
const S = require('./synth.cjs');

const FFMPEG = process.env.FFMPEG || (fs.existsSync('/opt/homebrew/bin/ffmpeg') ? '/opt/homebrew/bin/ffmpeg' : 'ffmpeg');

function pcm16Wav(x, sr = S.SR) {
  const b = Buffer.alloc(44 + x.length * 2);
  b.write('RIFF', 0); b.writeUInt32LE(36 + x.length * 2, 4); b.write('WAVEfmt ', 8); b.writeUInt32LE(16, 16);
  b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22); b.writeUInt32LE(sr, 24); b.writeUInt32LE(sr * 2, 28);
  b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34); b.write('data', 36); b.writeUInt32LE(x.length * 2, 40);
  for (let j = 0; j < x.length; j++) b.writeInt16LE(Math.round(Math.max(-1, Math.min(1, x[j])) * 32767), 44 + j * 2);
  return b;
}

// write x as a WAV: PCM, or through ffmpeg (ADPCM and/or another rate)
function writeWav(dest, x, { adpcm = false, rate = 0 } = {}) {
  if (!adpcm && !rate) return fs.writeFileSync(dest, pcm16Wav(x));
  const tmp = path.join(os.tmpdir(), 'studio-' + process.pid + '-' + path.basename(dest));
  fs.writeFileSync(tmp, pcm16Wav(x));
  const args = ['-y', '-loglevel', 'error', '-i', tmp];
  if (adpcm) args.push('-acodec', 'adpcm_ima_wav'); else args.push('-acodec', 'pcm_s16le');
  args.push('-ar', String(rate || S.SR), '-ac', '1', dest);
  try { execFileSync(FFMPEG, args, { stdio: 'inherit' }); } finally { fs.rmSync(tmp, { force: true }); }
}

module.exports = { pcm16Wav, writeWav };

if (require.main === module) {
  const argv = process.argv.slice(2);
  const opt = k => { const i = argv.indexOf(k); return i < 0 ? null : argv[i + 1]; };
  const file = argv[0];
  if (!file || file.startsWith('--')) {
    console.error('usage: node render.cjs <songs.cjs> [--out DIR] [--prefix P] [--only a,b] [--adpcm] [--rate HZ] [--preview DIR] [--mix]');
    process.exit(2);
  }
  const songs = require(path.resolve(file));
  const out = opt('--out') || '.', prefix = opt('--prefix') || '', only = opt('--only') && new Set(opt('--only').split(','));
  const preview = opt('--preview'), mix = argv.includes('--mix'), adpcm = argv.includes('--adpcm'), rate = Number(opt('--rate') || 0);
  fs.mkdirSync(out, { recursive: true });
  if (preview) fs.mkdirSync(preview, { recursive: true });
  for (const [name, make] of Object.entries(songs)) {
    if (typeof make !== 'function' || (only && !only.has(name))) continue;
    const report = mix ? [] : null, t0 = Date.now();
    const loop = make(report);
    const dest = path.join(out, prefix + name + '.wav');
    writeWav(dest, loop, { adpcm, rate });
    const st = S.stats(loop);
    console.log(path.basename(dest).padEnd(24) + (loop.length / S.SR).toFixed(2).padStart(7) + ' s ' + st.lufs.toFixed(1).padStart(6) + ' LUFS ' +
      st.peak.toFixed(1).padStart(6) + ' dBFS  speaker ' + st.speaker.toFixed(1).padStart(5) + ' dB ' + String(fs.statSync(dest).size).padStart(9) + ' B  ' +
      ((Date.now() - t0) / 1000).toFixed(1) + ' s');
    if (report) console.log('  ' + report.join('\n  '));
    if (st.peak >= -0.1) { console.error(name + ': too hot (' + st.peak.toFixed(2) + ' dBFS)'); process.exitCode = 1; }
    if (preview) {
      const two = new Float32Array(loop.length * 2);
      two.set(loop); two.set(loop, loop.length);
      fs.writeFileSync(path.join(preview, prefix + name + '.wav'), pcm16Wav(two));
    }
  }
}
