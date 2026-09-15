/** Generated from packages/contracts/tools/v1/registry.json; do not edit by hand. */
export const TOOL_IDS = [
  'catalog.search','catalog.describe','user.ask','runtime.status','memory.search','memory.read','memory.write','memory.forget','scratchpad.read','scratchpad.write','evidence.get','lineage.get','dataset.list','artifact.describe','profile.get','metadata.read','execution.get','agent.subtask','agent.message','agent.handoff','ingestion.import','profile.start','metadata.propose','quality.evaluate','pipeline.request','pipeline.status','analysis.open','analysis.revise','analysis.plan','analysis.preview','analysis.official','chart.create','drift.compare','statistics.run','report.read','report.create','report.patch','report.snapshot','report.request_submit','report.export_draft','report.export_published','schedule.propose','schedule.list','schedule.cancel',
] as const;

export type ToolId = (typeof TOOL_IDS)[number];
