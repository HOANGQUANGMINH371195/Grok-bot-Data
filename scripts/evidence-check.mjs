import { existsSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const receipts = fileURLToPath(new URL('../docs/execution/receipts/', import.meta.url));
if (!existsSync(receipts) || readdirSync(receipts).length === 0) {
  console.error('FAIL evidence-check: no task receipts exist yet; skeleton cannot be marked PASS.');
  process.exitCode = 1;
} else {
  console.log('PASS evidence-check: receipt directory is non-empty; detailed validation is pending M0 evidence schema.');
}
