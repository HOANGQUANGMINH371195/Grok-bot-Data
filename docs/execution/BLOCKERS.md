# Implementation blockers — mutable

No runtime task has started at baseline seal. Deployment still needs nonsecret AWS account/approved region/domain, budget, model configuration, secret references and demo-operator bindings. AWS/GitHub Actions have already been chosen; do not choose a different platform to bypass missing access.

Record each blocker with ID, affected task, observed evidence, safe checks attempted, decision required, owner and status. Never include secret values. A cloud binding blocker does not block unrelated offline implementation.

## Active blockers

| ID | Affected task | Evidence / safe checks | Decision / owner | Status |
| --- | --- | --- | --- | --- |
| BLK-M0-01 | M0-01, release CI | `node scripts/verify-implement.mjs` passes locally but reports trusted administrator baseline is not configured; branch protection/required check cannot be observed from this workspace | Repository admin must configure protected `main`, required `r1-ci`, CODEOWNERS/reviewers and trusted `IMPLEMENT_BASELINE_SHA256` | OPEN |
| BLK-M0-04 | M0-04 | CSV/JSON/Decimal/PII/adversarial/provider fixtures exist; pinned binary flat-Parquet fixture and independent fixture review are still missing | Data/QA owner supplies or approves a synthetic Parquet fixture and SHA-256 | OPEN |
| BLK-M0-05 | M0-05, M1-06 | AWS is confirmed by user, but approved account/region/domain/budget/operator and nonsecret secret-reference bindings are not present in repository configuration; `make infra-validate` intentionally returns BLOCKED | Deployment owner supplies bindings and approves Terraform plan/cost before any apply | OPEN |
| BLK-M0-06 | M0-06 | Threat/authority and ownership docs are drafted; no independent Leads/Security review receipt exists | Leads/Security owner reviews grant matrix and signs receipt | OPEN |
