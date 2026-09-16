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

Run the local profiling UI with `corepack pnpm --filter @vda-agent/web dev`. With the local
API below running, it uploads CSV/flat Parquet files, pins an immutable source and displays a
deterministic aggregate profile. OIDC/API persistence remains an M1 implementation lane.

The guarded local API contract harness can be run separately:

```bash
VDA_LOCAL_DEMO=true PYTHONPATH=services/api/src:packages/platform/src:packages/adapters/src:packages/data_profiling/src \
  uv run uvicorn vda_api.main:app --reload --port 8080
```

`/v1/local/*` is intentionally disabled unless `VDA_LOCAL_DEMO=true`; it is in-memory and
must not be used as the demo deployment persistence layer.

The local messenger slice accepts `X-Principal-Id` as a synthetic identity. A minimal
human+bot round trip is:

```bash
curl -X POST http://127.0.0.1:8080/v1/local/workspaces/demo/conversations \
  -H 'X-Principal-Id: human-1' -H 'content-type: application/json' \
  -d '{"conversation_id":"room-1","member_ids":["human-1","bot-1"]}'
curl -X POST http://127.0.0.1:8080/v1/local/conversations/room-1/bot-turn \
  -H 'X-Principal-Id: human-1' -H 'content-type: application/json' \
  -d '{"bot_id":"bot-1","turn_id":"turn-1"}'
curl 'http://127.0.0.1:8080/v1/local/conversations/room-1/events?after_seq=0' \
  -H 'X-Principal-Id: human-1'
```

The bot turn uses the deterministic fake provider and the same bounded context/tool
runtime as the future worker path; it does not call OpenAI or mutate AWS.

`OPENAI_API_KEY`, Langfuse keys and AWS credentials remain local environment bindings and
are never committed or printed. `make infra-validate` intentionally blocks until the
deployment owner supplies approved non-secret AWS bindings and a cost-approved plan.
