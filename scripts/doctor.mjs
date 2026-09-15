import { existsSync, readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

const root = new URL('../', import.meta.url);
const path = (name) => new URL(name, root);
const failures = [];

function version(command, args = ['--version']) {
  try { return execFileSync(command, args, { encoding: 'utf8' }).trim(); }
  catch { failures.push(`${command} is not available`); return 'missing'; }
}

const nodeVersion = version('node');
const pythonVersion = version('python3');
const uvVersion = version('uv');
for (const file of ['config/versions.lock.yaml', 'config/deployment.schema.json', 'config/demo.example.yaml']) {
  if (!existsSync(path(file))) failures.push(`missing ${file}`);
}

const envPath = path('.env');
if (existsSync(envPath)) {
  const allowed = new Set([
    'OPENAI_API_KEY', 'MODEL_NAME', 'LLM_PROVIDER', 'EMBEDDING_PROVIDER',
    'EMBEDDING_MODEL', 'EMBEDDING_DIMENSIONS', 'EMBEDDING_BATCH_SIZE',
    'LANGFUSE_SECRET_KEY', 'LANGFUSE_PUBLIC_KEY', 'LANGFUSE_BASE_URL',
    'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_DEFAULT_REGION',
    'VDA_LOCAL_DEMO', 'VDA_DATABASE_URL', 'VDA_CONTROL_WORKSPACE_ID',
    'VDA_CONTROL_WORKER_ID', 'VDA_CONTROL_HANDLER', 'VDA_CONTROL_WORKER_ENABLED',
    'VDA_CONTROL_LEASE_SECONDS', 'VDA_CONTROL_HEARTBEAT_INTERVAL_SECONDS',
    'VDA_CONTROL_POLL_INTERVAL_SECONDS', 'LOG_LEVEL',
  ]);
  const names = readFileSync(envPath, 'utf8').split(/\r?\n/)
    .map((line) => line.match(/^\s*([A-Z][A-Z0-9_]*)\s*=/)?.[1])
    .filter(Boolean);
  const unknown = names.filter((name) => !allowed.has(name));
  if (unknown.length) failures.push(`unknown .env keys: ${unknown.join(', ')}`);
}

console.log(JSON.stringify({ node: nodeVersion, python: pythonVersion, uv: uvVersion, env_checked: existsSync(envPath) }));
if (failures.length) {
  console.error(failures.map((failure) => `FAIL ${failure}`).join('\n'));
  process.exitCode = 1;
} else {
  console.log('PASS doctor checks (secret values are never printed)');
}
