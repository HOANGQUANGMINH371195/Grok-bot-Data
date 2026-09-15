import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = new URL('../', import.meta.url);
const registry = JSON.parse(readFileSync(new URL('packages/contracts/tools/v1/registry.json', root), 'utf8'));
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
if (Object.keys(registry.tools).length !== 44) errors.push(`expected 44 tools, found ${Object.keys(registry.tools).length}`);
for (const [template, tools] of Object.entries(expected)) {
  const actual = Object.entries(registry.tools).filter(([, spec]) => spec.grants.includes(template)).map(([id]) => id).sort();
  const expectedSorted = [...tools].sort();
  if (JSON.stringify(actual) !== JSON.stringify(expectedSorted)) errors.push(`${template} grant mismatch`);
}
for (const id of Object.keys(registry.tools)) if (forbidden.test(id)) errors.push(`forbidden tool id: ${id}`);
if (errors.length) { console.error(errors.map((e) => `FAIL ${e}`).join('\n')); process.exitCode = 1; }
else console.log(`PASS contracts-check ${Object.keys(registry.tools).length} tool IDs / 4 templates`);
