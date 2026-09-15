import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const receipts = fileURLToPath(new URL('../docs/execution/receipts/', import.meta.url));
if (!existsSync(receipts) || readdirSync(receipts).length === 0) {
  console.error('FAIL evidence-check: no task receipts exist yet; skeleton cannot be marked PASS.');
  process.exitCode = 1;
} else {
  const baseline = createHash('sha256').update(readFileSync(fileURLToPath(new URL('../IMPLEMENT.md', import.meta.url)))).digest('hex');
  const files = readdirSync(receipts).filter((file) => file.endsWith('.json'));
  const errors = [];
  for (const file of files) {
    let receipt;
    try { receipt = JSON.parse(readFileSync(`${receipts}/${file}`, 'utf8')); }
    catch { errors.push(`${file}: invalid JSON`); continue; }
    for (const field of ['task_id', 'baseline_sha256', 'status', 'owner', 'commands', 'environment', 'artifacts']) {
      if (!(field in receipt)) errors.push(`${file}: missing ${field}`);
    }
    if (receipt.baseline_sha256 !== baseline) errors.push(`${file}: baseline hash mismatch`);
    if (!['PASS', 'FAIL', 'BLOCKED', 'NOT_RUN'].includes(receipt.status)) errors.push(`${file}: invalid status`);
    if (!Array.isArray(receipt.commands) || receipt.commands.some((command) => typeof command.exit_code !== 'number')) {
      errors.push(`${file}: commands must include numeric exit_code`);
    }
    if (!Array.isArray(receipt.artifacts) || receipt.artifacts.some((artifact) => !artifact.path_or_uri || !/^[a-f0-9]{64}$/.test(artifact.sha256))) {
      errors.push(`${file}: artifacts require path_or_uri and SHA-256`);
    }
    if (receipt.status === 'PASS' && (!receipt.git_commit || receipt.commands.every((command) => command.exit_code !== 0))) {
      errors.push(`${file}: PASS requires git_commit and a zero-exit command`);
    }
  }
  if (errors.length) {
    console.error(errors.map((error) => `FAIL ${error}`).join('\n'));
    process.exitCode = 1;
  } else console.log(`PASS evidence-check ${files.length} receipt(s), baseline ${baseline}`);
}
