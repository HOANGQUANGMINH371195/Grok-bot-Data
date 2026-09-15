import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = new URL('../', import.meta.url);
try {
  const body = readFileSync(new URL('IMPLEMENT.md', root));
  const lock = readFileSync(new URL('IMPLEMENT.sha256', root), 'utf8').trim();
  const match = /^([a-f0-9]{64}) {2}IMPLEMENT\.md$/.exec(lock);
  if (!match) throw new Error('Invalid or missing IMPLEMENT.sha256 record');
  const actual = createHash('sha256').update(body).digest('hex');
  if (actual !== match[1]) throw new Error('IMPLEMENT.md changed: do not rewrite the baseline or checksum');
  const trusted = process.env.IMPLEMENT_BASELINE_SHA256;
  if (trusted !== undefined && !/^[a-f0-9]{64}$/.test(trusted)) {
    throw new Error('IMPLEMENT_BASELINE_SHA256 must be a lowercase SHA-256 digest');
  }
  if (trusted !== undefined && actual !== trusted) {
    throw new Error('Baseline differs from trusted administrator-provided digest');
  }
  console.log(`PASS ${fileURLToPath(new URL('IMPLEMENT.md', root))} ${actual}`);
  if (trusted === undefined) {
    console.log('Local integrity only: trusted protected CI baseline is not configured in this process.');
  }
} catch (error) {
  console.error(`FAIL ${error.message}`);
  process.exitCode = 1;
}
