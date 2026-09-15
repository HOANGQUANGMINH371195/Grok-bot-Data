# R1 threat model and authority matrix

Status: implementation baseline for M0-06; security owner review is required before the
M1 identity lane is marked PASS. This document does not grant production approval.

## Assets and trust boundaries

| Asset | Authority | Main threats | Required control |
| --- | --- | --- | --- |
| Workspace, membership, grants | PostgreSQL primary | IDOR, rejoin history leak, stale ACL | scoped foreign keys, RLS, transaction-local workspace, policy generation |
| Human messages/events | PostgreSQL + outbox | duplicate ACK, ordering loss, forged sender | message idempotency key, message sequence separate from event sequence |
| Bot memory/scratchpad | PostgreSQL | cross-room prompt injection, private memory leak | bot+conversation scope, revision/CAS, audience filter before context build |
| Dataset/source objects | versioned private S3 | overwrite, confused deputy, zip/bomb/SSRF | immutable key/version/SHA, approved source broker, byte/row/column caps |
| Tool execution | platform policy service | forged model tool call, privilege escalation | default deny registry, injected ToolContext, grant intersection, effect ledger |
| Report approval/publish | human authority | bot impersonation, maker-checker bypass | bot can request only; distinct human submitter/reviewer; immutable snapshot |
| Secrets and provider usage | AWS Secrets Manager/KMS | log/prompt exfiltration, fork CI access | reference injection only, redaction tests, OIDC subject pinning, no fork secrets |
| Observatory | journal + ACL read model | raw prompt/PII exposure, graph side channel | metadata-only events, audience-filtered nodes/edges/counts, durable journal |

## Abuse cases and required negative tests

1. A model sends a valid tool ID with a forged workspace or grant: reject before handler.
2. A user leaves and rejoins a room: the new membership interval cannot read prior messages
   without an explicit audited share.
3. The same bot is in a private DM and a group: private memory, tool output, counts and
   Observatory graph edges never enter the group context.
4. A stale worker commits after lease loss: fencing token rejects the commit and emits a
   reconciliable journal record.
5. A report bot calls an approval/publish-shaped payload: no such tool exists; API requires
   a human principal and current policy generation.
6. A CSV contains formulas, multiline Unicode, PII, malformed rows or oversized content:
   parser policy rejects or labels it; it never executes a formula or silently skips data.
7. A tool or export worker receives an arbitrary URL: egress policy denies it; export only
   references approved object-store artifacts.
8. A GitHub fork attempts deployment: OIDC trust rejects repository/ref/environment mismatch.

## Authority matrix

| Action | Human Viewer | Human Editor | Workspace Owner | Bot | Service worker |
| --- | --- | --- | --- | --- | --- |
| Read shared resource | yes | yes | yes | only granted audience | only scoped run |
| Add/configure bot | no | scoped create | yes | no | no |
| Write bot memory | own bot scope | own bot scope | policy-managed | own bot/conversation only | checkpoint only |
| Import/profile/preview | no | yes | yes | request within grant | execute pinned run |
| Metadata decision | no | no | yes/human delegate | propose only | no |
| Official approval | no | no | human approver | request only | execute approved action |
| Report submit | no | yes | yes | request only | export draft only |
| Report review/publish | no | no | distinct human owner | no | no |
| Cancel/retry run | own allowed run | scoped run | any scoped run | request/cancel own run | reconcile with fence |
| Read Observatory | shared scope | shared scope | workspace scope | own run/audience | append redacted metadata |

## Release conditions

- No critical tenant/audience or human-authority bypass is known on the tested path.
- Every negative case above has a named test ID and artifact before M4 security sign-off.
- Any exception becomes a blocker/change request; this file is not permission to weaken the
  frozen IMPLEMENT contract.
