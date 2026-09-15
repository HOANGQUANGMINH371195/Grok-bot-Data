# Repository ownership and shared-contract policy

This is the mutable M0-06 operating policy. The frozen task contract remains in
`IMPLEMENT.md`.

- Leads own release decisions and baseline integrity.
- Core owns identity, membership, messaging, migrations and API composition.
- Runtime owns bot execution, context, tools, model adapters and recovery.
- Data owns ingestion, profiling, quality, analysis, evidence, reports and Airflow.
- Web owns messenger, data/report cards and Observatory UI.
- Platform/SRE owns CI, AWS demo, telemetry, backups and runbooks.
- QA/Security owns independent contract, tenant, fault and load evidence.

Shared migrations, events, tool schemas and cards require a producer owner plus at least
one consumer review. A migration coordinator serializes revisions; feature branches must
not create competing revision chains. Every PR records task ID, allowed paths, contract
diff, tests and rollback. A conflict with IMPLEMENT is a change request, never a silent
compatibility shim.
