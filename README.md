# VDaAgent R1

VDaAgent is a platform-style web messenger for human teams working with data. R1 is a
six-week AWS/GitHub Actions demo: the same runtime hosts DataAssistant, DataSteward,
DataAnalyst and ReportWriter with bounded tools, audience-scoped context, evidence and
Observatory metadata.

The frozen execution contract is [IMPLEMENT.md](IMPLEMENT.md). The current repository is
an actively implemented offline foundation; it is not yet production-certified and cloud
resources are not provisioned by local commands.

## Local checks

```bash
make doctor
make bootstrap
make contracts-check
make test-unit
make test-contract
make lint
make typecheck
corepack pnpm --filter @vda-agent/web build
```

Run the local web shell with `corepack pnpm --filter @vda-agent/web dev`. It currently
demonstrates the messenger/data/Observatory interaction shell with synthetic content; the
OIDC/API integration is an M1 implementation lane.

`OPENAI_API_KEY`, Langfuse keys and AWS credentials remain local environment bindings and
are never committed or printed. `make infra-validate` intentionally blocks until the
deployment owner supplies approved non-secret AWS bindings and a cost-approved plan.
