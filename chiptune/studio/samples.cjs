#!/usr/bin/env node
// Export a bank of instrument samples -- for a tracker to play (chiptune's driver, a MOD
// player): the studio's sound, a tracker's size.
//   node samples.cjs <bank.cjs> <outdir> [--rate 22050] [--only a,b]
// A bank module exports [{ name, root, make, loop, peak }]:
//   name   the file's name (<outdir>/<name>.wav)
//   root   the MIDI note the sample sounds as it is (C4 = 60); an unpitched one (a drum) says
//          72, C5 -- where chiptune's sample oscillator plays a sample as recorded
//   make   () => Float32Array at 44100 Hz
//   loop   false (a one-shot: its silent tail trimmed), 'auto' (a sustain loop found in its
//          steady part: whole periods of the root between rising zero crossings, the loop's end
//          crossfaded into its start), or [startSeconds, endSeconds]
//   peak   dBFS the sample is normalised to (default -1)
// Writes the WAVs (PCM 16-bit mono at 44100 Hz, or --rate) and bank.json:
//   [{ name, file, root, rate, length, loop: [start, end] | null, peak, lufs }]  (samples; the
//   loop's end exclusive -- the sample stops there and playback jumps to start)
'use strict';
const fs = require('fs');
const path = require('path');
const S = require('./synth.cjs');
const { writeWav } = require('./render.cjs');

const SR = S.SR;

function risingZero(x, from, dir = 1, limit = SR) {
  for (let k = 0; k < limit; k++) {
    const j = from + dir * k;
    if (j < 1 || j >= x.length) break;
    if (x[j - 1] < 0 && x[j] >= 0) return j;
  }
  return from;
}

// a sustain loop in the steady part of the sound: from 40% of it, at least 0.12 s of whole
// periods of the root, both ends on rising zero crossings, the last 10 ms before the end
// blended into the 10 ms before the start (so the jump back is seamless)
function autoLoop(x, root) {
  const period = SR / S.hz(root), n = x.length;
  const a = risingZero(x, Math.floor(n * 0.4));
  const k = Math.max(1, Math.round(0.12 * SR / period));
  let b = Math.round(a + k * period);
  if (b >= n - 1) b = Math.round(a + Math.max(1, Math.floor((n - 1 - a) / period)) * period);
  const near = risingZero(x, b, 1, Math.ceil(period / 2)), back = risingZero(x, b, -1, Math.ceil(period / 2));
  b = Math.abs(near - b) <= Math.abs(back - b) ? near : back;
  b = Math.min(b, n - 1);
  const c = Math.min(Math.floor((b - a) / 2), Math.round(0.01 * SR), a);
  for (let j = 0; j < c; j++) {
    const w = j / c;
    x[b - c + j] = x[b - c + j] * (1 - w) + x[a - c + j] * w;
  }
  return [a, b];
}

function trimTail(x, floorDb = -60) {
  const floor = S.dB(floorDb) * S.peak(x);
  let end = x.length;
  while (end > 1 && Math.abs(x[end - 1]) < floor) end--;
  return S.fadeOut(x.slice(0, Math.min(x.length, end + Math.round(0.005 * SR))), 0.004);
}

function wavLength(file) {
  const b = fs.readFileSync(file);
  let align = 0;
  for (let p = 12; p + 8 <= b.length;) {
    const kind = b.toString('ascii', p, p + 4), n = b.readUInt32LE(p + 4);
    if (kind === 'fmt ') align = b.readUInt16LE(p + 8 + 12);
    if (kind === 'data' && align) return n / align;
    p += 8 + n + (n & 1);
  }
  throw new Error('missing PCM data: ' + file);
}

function exportBank(bank, outdir, { rate = 0, only = null } = {}) {
  fs.mkdirSync(outdir, { recursive: true });
  const meta = [];
  for (const def of bank) {
    if (only && !only.has(def.name)) continue;
    let x = def.make();
    let loop = null;
    if (def.loop === 'auto') loop = autoLoop(x, def.root);
    else if (Array.isArray(def.loop)) loop = [Math.round(def.loop[0] * SR), Math.round(def.loop[1] * SR)];
    if (loop) x = x.slice(0, loop[1]);
    else x = trimTail(x);
    S.scale(x, S.dB(def.peak ?? -1) / Math.max(1e-9, S.peak(x)));
    const sampleRate = def.rate ?? rate;
    const file = def.name + '.wav', r = sampleRate || SR, k = r / SR;
    writeWav(path.join(outdir, file), x, { rate: sampleRate });
    // ffmpeg rounds the final resampled frame count up. Carry the actual
    // length, especially for a sustain whose loop ends at the last frame.
    const length = wavLength(path.join(outdir, file));
    const st = S.stats(x);
    meta.push({ ...def.meta, name: def.name, file, root: def.root, rate: r, length,
      loop: loop ? [Math.round(loop[0] * k), length] : null, peak: +st.peak.toFixed(2), lufs: +st.lufs.toFixed(1) });
  }
  fs.writeFileSync(path.join(outdir, 'bank.json'), JSON.stringify(meta, null, 1) + '\n');
  return meta;
}

module.exports = { exportBank, autoLoop };

if (require.main === module) {
  const argv = process.argv.slice(2);
  const opt = k => { const i = argv.indexOf(k); return i < 0 ? null : argv[i + 1]; };
  if (argv.length < 2) { console.error('usage: node samples.cjs <bank.cjs> <outdir> [--rate HZ] [--only a,b]'); process.exit(2); }
  const meta = exportBank(require(path.resolve(argv[0])), argv[1],
    { rate: Number(opt('--rate') || 0), only: opt('--only') && new Set(opt('--only').split(',')) });
  let bytes = 0;
  for (const m of meta) {
    bytes += fs.statSync(path.join(argv[1], m.file)).size;
    console.log(m.name.padEnd(14) + ' root ' + String(m.root).padStart(3) + ' ' + (m.length / m.rate).toFixed(3).padStart(6) + ' s' +
      (m.loop ? '  loop ' + m.loop[0] + '-' + m.loop[1] : '  one-shot') + '  ' + m.lufs + ' LUFS');
  }
  console.log(meta.length + ' samples, ' + (bytes / 1024).toFixed(0) + ' KiB of PCM16 in ' + argv[1]);
}
