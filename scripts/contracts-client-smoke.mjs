import assert from 'node:assert/strict';
import { VdaApiClient, VdaApiError } from '../packages/contracts/generated/ts/api.ts';

const calls = [];
const fetcher = async (input, init) => {
  const url = String(input);
  calls.push({ input: url, init });
  let body = { conversation_id: 'c', workspace_id: 'w' };
  if (url.endsWith('/datasets')) body = { dataset_id: 'sales', workspace_id: 'w' };
  if (url.includes('/uploads/')) {
    body = {
      artifact_id: 'sales:abc',
      dataset_id: 'sales',
      workspace_id: 'w',
      source_sha256: 'a'.repeat(64),
      object_version_id: 'v1-abc',
      size_bytes: 17,
      format: 'csv',
      headers: ['amount'],
      row_count: 1,
      status: 'ready',
    };
  }
  if (url.endsWith('/profiles')) {
    body = {
      profile_id: 'profile:sales:abc:profile-v1',
      dataset_id: 'sales',
      workspace_id: 'w',
      artifact_id: 'sales:abc',
      source_sha256: 'a'.repeat(64),
      row_count: 1,
      column_count: 1,
      method_version: 'profile-v1',
      status: 'completed',
      evidence: {
        evidence_id: 'profile:sales:abc:profile-v1',
        source_version: 'v1-abc',
        method_version: 'profile-v1',
        cell_refs: ['table.row_count'],
        limitations: ['local demo only'],
        approved: false,
      },
      columns: [{
        name: 'amount', physical_type: 'numeric', non_null_count: 1, null_count: 0,
        null_rate: '0', distinct_non_null_count: 1, pii_signal_counts: {},
      }],
    };
  }
  return new Response(JSON.stringify(body), {
    status: 201,
    headers: { 'content-type': 'application/json' },
  });
};
const client = new VdaApiClient('http://localhost:8080/', fetcher);
const created = await client.createConversation('w/1', 'actor-1', {
  conversation_id: 'c',
  member_ids: ['actor-1', 'bot-1'],
  bot_templates: { 'bot-1': 'DataAssistant' },
});
assert.deepEqual(created, { conversation_id: 'c', workspace_id: 'w' });
assert.equal(calls[0].input, 'http://localhost:8080/v1/local/workspaces/w%2F1/conversations');
assert.equal(calls[0].init.headers.get('X-Principal-Id'), 'actor-1');

const dataset = await client.createDataset('w/1', 'actor-1', { dataset_id: 'sales' });
assert.equal(dataset.dataset_id, 'sales');
const artifact = await client.uploadDataset(
  'w/1',
  'sales',
  'upload/1',
  'actor-1',
  'sales.csv',
  new Blob(['amount\n1\n'], { type: 'text/csv' }),
);
assert.equal(artifact.status, 'ready');
assert.equal(calls[2].input, 'http://localhost:8080/v1/local/workspaces/w%2F1/datasets/sales/uploads/upload%2F1');
assert.equal(calls[2].init.headers.get('Content-Type'), 'text/csv');
assert.equal(calls[2].init.headers.get('X-File-Name'), 'sales.csv');
const profile = await client.profileDataset('w/1', 'sales', 'actor-1', {
  artifact_id: artifact.artifact_id,
});
assert.equal(profile.status, 'completed');
assert.equal(profile.columns[0].name, 'amount');

const denied = new VdaApiClient('http://localhost:8080', async () =>
  new Response(JSON.stringify({ detail: 'denied', code: 'forbidden' }), {
    status: 403,
    headers: { 'content-type': 'application/json' },
  }),
);
await assert.rejects(() => denied.readMessages('c', 'actor-1'), (error) => {
  assert.ok(error instanceof VdaApiError);
  assert.equal(error.status, 403);
  assert.equal(error.body.code, 'forbidden');
  return true;
});
console.log('PASS contracts-client-smoke typed request/error behavior');
