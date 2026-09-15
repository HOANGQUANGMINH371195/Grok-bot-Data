import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const result = spawnSync(
  'corepack',
  [
    'pnpm',
    '--filter',
    '@vda-agent/web',
    'exec',
    'tsc',
    '--noEmit',
    '--strict',
    '--target',
    'ES2022',
    '--module',
    'ESNext',
    '--moduleResolution',
    'Bundler',
    '../../packages/contracts/generated/ts/index.ts',
  ],
  { cwd: root, stdio: 'inherit' },
);

if (result.error) {
  console.error(`FAIL contracts-ts-check ${result.error.message}`);
  process.exitCode = 1;
} else {
  if (result.status === 0) console.log('PASS contracts-ts-check generated API client');
  process.exitCode = result.status ?? 1;
}
