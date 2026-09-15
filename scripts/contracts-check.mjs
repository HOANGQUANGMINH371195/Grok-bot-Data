import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = new URL('../', import.meta.url);
const registry = JSON.parse(readFileSync(new URL('packages/contracts/tools/v1/registry.json', root), 'utf8'));
const schemas = JSON.parse(readFileSync(new URL('packages/contracts/tools/v1/schemas.json', root), 'utf8'));
const generated = readFileSync(new URL('packages/contracts/generated/ts/tool_ids.ts', root), 'utf8');
const events = JSON.parse(readFileSync(new URL('packages/contracts/events/v1.json', root), 'utf8'));
const cards = JSON.parse(readFileSync(new URL('packages/contracts/cards/v1.json', root), 'utf8'));
const protocol = JSON.parse(readFileSync(new URL('packages/contracts/protocol/v1.json', root), 'utf8'));
const openapi = readFileSync(new URL('packages/contracts/openapi/v1.yaml', root), 'utf8');
const generatedApi = readFileSync(new URL('packages/contracts/generated/ts/api.ts', root), 'utf8');
const expected = {
  DataAssistant: [
    'catalog.search','catalog.describe','user.ask','runtime.status','memory.search','memory.read','memory.write','memory.forget','scratchpad.read','scratchpad.write','evidence.get','lineage.get','dataset.list','artifact.describe','profile.get','metadata.read','execution.get','agent.subtask','agent.message','agent.handoff','schedule.list'
  ],
  DataSteward: [
    'catalog.search','catalog.describe','user.ask','runtime.status','memory.search','memory.read','memory.write','memory.forget','scratchpad.read','scratchpad.write','evidence.get','lineage.get','dataset.list','artifact.describe','profile.get','metadata.read','execution.get','agent.message','agent.handoff','ingestion.import','profile.start','metadata.propose','quality.evaluate','pipeline.request','pipeline.status','schedule.propose','schedule.list','schedule.cancel'
  ],
  DataAnalyst: [
    'catalog.search','catalog.describe','user.ask','runtime.status','memory.search','memory.read','memory.write','memory.forget','scratchpad.read','scratchpad.write','evidence.get','lineage.get','dataset.list','artifact.describe','profile.get','metadata.read','execution.get','agent.subtask','agent.message','agent.handoff','analysis.open','analysis.revise','analysis.plan','analysis.preview','analysis.official','chart.create','drift.compare','statistics.run'
  ],
  ReportWriter: [
    'catalog.search','catalog.describe','user.ask','runtime.status','memory.search','memory.read','memory.write','memory.forget','scratchpad.read','scratchpad.write','evidence.get','lineage.get','dataset.list','artifact.describe','profile.get','metadata.read','execution.get','agent.message','agent.handoff','report.read','report.create','report.patch','report.snapshot','report.request_submit','report.export_draft','report.export_published'
  ]
};
const forbidden = /(^|\.)(shell|sql|http|kubectl|secret|approve|publish)(\.|$)/i;
const errors = [];
for (const path of [
  '/v1/local/workspaces/{workspace_id}/conversations:',
  '/v1/local/conversations/{conversation_id}/messages:',
  '/v1/local/conversations/{conversation_id}/events:',
  '/v1/local/conversations/{conversation_id}/bot-turn:',
]) {
  if (!openapi.includes(path)) errors.push(`OpenAPI contract missing ${path.slice(0, -1)}`);
}
for (const schema of [
  'ConversationCreated',
  'MessageAck',
  'MessageList',
  'EventReplay',
  'BotTurnResponse',
  'ErrorResponse',
]) {
  if (!openapi.includes(`${schema}:`)) errors.push(`OpenAPI schema missing ${schema}`);
}
for (const generatedExport of ['VdaApiClient', 'VdaApiError', 'EventEnvelope', 'BotTurnResponse']) {
  if (!generatedApi.includes(`export ${generatedExport.includes('Client') || generatedExport.includes('Error') ? 'class' : 'interface'} ${generatedExport}`)) {
    errors.push(`generated API client missing ${generatedExport}`);
  }
}
if (Object.keys(registry.tools).length !== 44) errors.push(`expected 44 tools, found ${Object.keys(registry.tools).length}`);
if (Object.keys(schemas.tools).length !== 44) errors.push(`expected 44 tool schemas, found ${Object.keys(schemas.tools).length}`);
if (!schemas.output?.required?.includes('status')) errors.push('output contract must require status');
if (!events.required?.includes('event_seq') || !events.required?.includes('workspace_id')) errors.push('event envelope missing ordering or tenant fields');
if (cards.properties?.card_version?.const !== 'v1' || !cards.required?.includes('evidence_refs')) errors.push('card contract missing version/evidence fields');
if (!protocol.roles?.includes('owner') || !protocol.run_states?.includes('waiting')) errors.push('protocol role/state contract incomplete');
for (const [id, spec] of Object.entries(schemas.tools)) {
  if (!registry.tools[id]) errors.push(`schema has unknown tool: ${id}`);
  if (!schemas.profiles[spec.input]) errors.push(`${id} references missing input profile ${spec.input}`);
  if (!['read', 'write', 'enqueue'].includes(spec.effect)) errors.push(`${id} has invalid effect`);
}
for (const id of Object.keys(registry.tools)) if (!schemas.tools[id]) errors.push(`registry tool has no schema: ${id}`);
const generatedIds = [...generated.matchAll(/'([^']+)'/g)].map((match) => match[1]);
if (generatedIds.length !== 44 || new Set(generatedIds).size !== 44) errors.push('generated TypeScript tool ID union is not exactly 44 unique IDs');
for (const id of Object.keys(registry.tools)) if (!generatedIds.includes(id)) errors.push(`generated TypeScript client missing ${id}`);
for (const template of Object.keys(expected)) {
  const folder = template.replace(/([a-z])([A-Z])/g, '$1_$2').toLowerCase();
  const manifest = JSON.parse(readFileSync(new URL(`packages/bot_templates/${folder}/manifest.json`, root), 'utf8'));
  const expectedTools = [...expected[template]].sort();
  const actualTools = [...manifest.invoke_tools].sort();
  if (manifest.template !== template) errors.push(`${template} manifest identity mismatch`);
  if (JSON.stringify(actualTools) !== JSON.stringify(expectedTools)) errors.push(`${template} manifest grants mismatch`);
  if (manifest.caps?.max_context_tokens !== 32000 || manifest.delegation?.max_depth !== 1) errors.push(`${template} execution caps mismatch`);
}
for (const [template, tools] of Object.entries(expected)) {
  const actual = Object.entries(registry.tools).filter(([, spec]) => spec.grants.includes(template)).map(([id]) => id).sort();
  const expectedSorted = [...tools].sort();
  if (JSON.stringify(actual) !== JSON.stringify(expectedSorted)) errors.push(`${template} grant mismatch`);
}
for (const id of Object.keys(registry.tools)) if (forbidden.test(id)) errors.push(`forbidden tool id: ${id}`);
if (errors.length) { console.error(errors.map((e) => `FAIL ${e}`).join('\n')); process.exitCode = 1; }
else console.log(`PASS contracts-check ${Object.keys(registry.tools).length} tool IDs / 4 templates`);
