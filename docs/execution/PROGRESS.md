# R1 execution progress — mutable

Baseline: IMPLEMENT.md / IMPLEMENT.sha256. This file may be updated; the frozen baseline may not.

At initial seal, all implementation tasks are NOT_RUN. The document hash verifier has been checked locally; protected CI configuration and task M0-01 are not thereby complete.

| Task ID | Status | Owner / claimed paths | Latest receipt | Reviewer / notes |
| --- | --- | --- | --- | --- |
| M0-01 | NOT_RUN | Unassigned | None | Requires repository-admin protected baseline setup |
| M0-02 | PASS | Codex / Makefile, pyproject.toml, package.json, apps/web, services/*, packages/*, config/*, scripts/* | [M0-02-bootstrap.json](receipts/M0-02-bootstrap.json) | Local layout, locks, backend/web import/build, doctor, lint/typecheck and unit smoke passed; human review pending |
| M0-03 | IN_PROGRESS | Codex / packages/contracts, scripts/contracts-check.mjs, database/migrations | None | Exact tool/grant registry, closed input/output profiles, event/card/resource/protocol schemas and generated TS IDs pass offline; independent contract review and migration integration pending |
| M0-04 | IN_PROGRESS | Codex / tests/fixtures, tests/unit/test_fixtures.py, tests/unit/test_parquet_ingestion.py | [M0-04-parquet-fixture.json](receipts/M0-04-parquet-fixture.json) | Pinned flat Parquet fixture/hash and nested-type negative test pass; independent Data/QA review and broader fixture sign-off pending |
| M0-05 | BLOCKED | Codex / services/api/Dockerfile, apps/web/Dockerfile, apps/web/nginx.conf, infra/compose, infra/README.md | None | Local Compose config and both container builds pass; AWS deployment validation remains blocked on approved bindings, OIDC role and operator approval |
| M0-06 | IN_PROGRESS | Codex / docs/decisions/threat-model-r1.md, docs/decisions/ownership.md | None | Threat/authority matrix and shared-contract ownership policy drafted; Leads/Security review pending |
| M1-04 | BLOCKED | Codex / packages/data_profiling/src/vda_data/ingestion/sources.py, tests/unit/test_source_registry.py | [M1-04-source-admission.json](receipts/M1-04-source-admission.json) | Offline upload/session, immutable object reference, parser-ready state and ACL/tombstone negatives pass; M1-01 identity, API/S3 persistence and review remain dependencies |

Add one row per claimed task. Allowed states: NOT_RUN, IN_PROGRESS, BLOCKED, FAIL, PASS. PASS requires immutable evidence receipt and review, not a checked box here. Do not overwrite historical receipt files.
