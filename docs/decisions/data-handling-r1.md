# R1 data handling and approval matrix

Status: implementation decision for M0-06. Leads/Security must review this document
before the identity/deployment lanes can be approved. It is not a production compliance
certification and it does not authorize live customer data.

## Data classes and allowed destinations

| Class | Examples | Allowed storage/processing | Prohibited handling |
| --- | --- | --- | --- |
| Public/demo | Synthetic sales fixtures, schema names | Git fixtures, local tests, demo database/object store | Real personal data in fixtures or receipts |
| Workspace content | Messages, bot memory, analysis plans, report drafts | Tenant-scoped PostgreSQL/S3 with resource grants and RLS | Cross-workspace cache, public URL, unscoped telemetry labels |
| Restricted source | Uploaded CSV/Parquet, PII columns, provider input | Versioned private object store and bounded compute; provider only after policy/audience check | Raw prompt/log/Observatory capture, arbitrary connector egress |
| Sensitive authority | Sessions, grants, approvals, secrets, usage/cost | PostgreSQL authority tables; secrets only via Secrets Manager/KMS references | Model context, browser storage, Git, receipt, client-controlled actor/grant |
| Operational metadata | Latency, status, trace links, sanitized error classes | Redacted OTel/CloudWatch and durable journal metadata | Prompt/body/SQL/OAuth headers, user IDs as metric labels |

## Processing rules

1. Admission verifies UTF-8/flat Parquet, byte/row/column/decoded caps, SHA and immutable
   object version before a source is `ready`. PII classification is a restriction signal,
   not an automatic grant.
2. Context construction filters by workspace, conversation audience, resource grant,
   policy generation and bot memory scope before any provider call. A model never receives
   actor, workspace, grant or secret overrides from its own tool payload.
3. Provider requests use the approved adapter and pinned model/config; live calls require
   deployment bindings, budget and human approval. Fake-provider tests are deterministic and
   must not be described as model quality evidence.
4. Export workers may read approved evidence/artifact references only. They run with network
   deny and sanitize HTML/chart input; published output points to an immutable snapshot.
5. Observatory and telemetry keep metadata (status, hashes, versions, restricted refs and
   bounded cost/latency). Raw prompts, full tool arguments/results and secret values are
   never captured in R1.
6. Delete/revoke blocks reads and new tool/effect commits immediately. Purge active stores
   follows the retention policy; deletion/revocation ledger is replayed after restore.

## Human authority matrix

| Decision | Requester | Required authority | Bot behavior | Evidence |
| --- | --- | --- | --- | --- |
| Share source/resource | Human editor/owner | Current grant + policy generation | Cannot grant itself or another bot | Grant record + audit ref |
| Metadata label | Bot or editor proposal | Human owner/delegate | Propose only | Proposal, decision, source version |
| Official full-source run | Analyst/Steward request | Human approver, current plan/source/context | Request only | Approval ID + expected versions |
| Pipeline/schedule | Steward request | Human owner approval | Request/status only | Pinned definition/source manifest |
| Report submit | Editor or owner | Human submitter | Request only | Immutable draft/snapshot |
| Report review/publish | Human submitter != reviewer | Distinct human owner/reviewer | Never approve/publish | Review decision + published pointer |
| Cancel/retry/reconcile | Authorized human/operator | Scoped run capability + expected fence | Request own run only | Reason, actor, state/fence |
| Secret/connection | Human owner/operator | Explicit capability + expiry | No tool ID for secret read | Secret reference, never value |

## Review checklist

- [ ] Security verifies tenant/audience boundaries and no confused-deputy grant path.
- [ ] Data verifies synthetic fixtures, PII handling, retention and provider policy.
- [ ] Runtime verifies ToolContext injection, fence/approval/version checks and unknown effects.
- [ ] Leads freeze this matrix against the R1 contract or open a change request.

Any disagreement with `IMPLEMENT.md`, `PLAN.md` or `ARCHITECTURE.md` is recorded in
`docs/execution/BLOCKERS.md` or `docs/execution/CHANGE_REQUESTS.md`; this file cannot
weaken those contracts.
