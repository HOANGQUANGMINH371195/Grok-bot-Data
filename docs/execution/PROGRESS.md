# R1 execution progress — mutable

Baseline: IMPLEMENT.md / IMPLEMENT.sha256. This file may be updated; the frozen baseline may not.

At initial seal, all implementation tasks are NOT_RUN. The document hash verifier has been checked locally; protected CI configuration and task M0-01 are not thereby complete.

| Task ID | Status | Owner / claimed paths | Latest receipt | Reviewer / notes |
| --- | --- | --- | --- | --- |
| M0-01 | NOT_RUN | Unassigned | None | Requires repository-admin protected baseline setup |
| M0-02 | PASS | Codex / Makefile, pyproject.toml, package.json, apps/web, services/*, packages/*, config/*, scripts/* | [M0-02-bootstrap.json](receipts/M0-02-bootstrap.json) | Local layout, locks, backend/web import/build, doctor, lint/typecheck and unit smoke passed; human review pending |
| M0-03 | IN_PROGRESS | Codex / packages/contracts, scripts/contracts-check.mjs | None | Registry created; schemas/generated clients and contract receipt pending |

Add one row per claimed task. Allowed states: NOT_RUN, IN_PROGRESS, BLOCKED, FAIL, PASS. PASS requires immutable evidence receipt and review, not a checked box here. Do not overwrite historical receipt files.
