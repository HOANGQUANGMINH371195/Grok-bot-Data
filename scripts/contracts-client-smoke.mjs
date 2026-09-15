import assert from 'node:assert/strict';
import { VdaApiClient, VdaApiError } from '../packages/contracts/generated/ts/api.ts';

const calls = [];
const fetcher = async (input, init) => {
  calls.push({ input: String(input), init });
  return new Response(JSON.stringify({ conversation_id: 'c', workspace_id: 'w' }), {
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
assert.equal(calls[0].init.headers['X-Principal-Id'], 'actor-1');

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
