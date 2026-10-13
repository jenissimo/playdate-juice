// Quantitative A/B evidence at a common 44100 Hz rate, on the second lap.
'use strict';
const fs = require('fs');
const S = require('./synth.cjs');
function readWav(file) {
  const b = fs.readFileSync(file);
  let align, rate;
  for (let p = 12; p + 8 <= b.length;) {
    const kind = b.toString('ascii', p, p + 4), n = b.readUInt32LE(p + 4), at = p + 8;
    if (kind === 'fmt ') { rate = b.readUInt32LE(at + 4); align = b.readUInt16LE(at + 12); }
    if (kind === 'data') {
      if (rate !== 44100 || align !== 2) throw new Error('comparison needs 44100 Hz PCM16 mono');
      const x = new Float32Array(n / 2);
      for (let j = 0; j < x.length; j++) x[j] = b.readInt16LE(at + j * 2) / 32768;
      return x;
    }
    p += 8 + n + (n & 1);
  }
  throw new Error('no PCM: ' + file);
}
function score(x, secondLap = true) {
  if (secondLap) x = x.slice(Math.floor(x.length / 2));
  const values = [], window = Math.round(0.05 * S.SR);
  for (let p = 0; p + window <= x.length; p += window) {
    let sum = 0;
    for (let j = p; j < p + window; j++) sum += x[j] * x[j];
    values.push(10 * Math.log10(sum / window + 1e-12));
  }
  values.sort((a, b) => a - b);
  return { ...S.stats(x), spread50ms: values[Math.floor(values.length * 0.9)] - values[Math.floor(values.length * 0.1)] };
}
module.exports = { readWav, score };
if (require.main === module) {
  const [original, tracker, dest] = process.argv.slice(2);
  const source = score(readWav(original)), port = score(readWav(tracker));
  const delta = { lufs: port.lufs - source.lufs, bands: port.bands.map((b, i) => b - source.bands[i]) };
  const pass = Math.abs(delta.lufs) <= 1 && delta.bands.slice(1, 4).every(b => Math.abs(b) <= 2) && Math.abs(delta.bands[5]) <= 4 && port.spread50ms <= 5;
  const report = { source, port, delta, pass };
  if (dest) fs.writeFileSync(dest, JSON.stringify(report, null, 1) + '\n');
  console.log(JSON.stringify(report, null, 1));
}
