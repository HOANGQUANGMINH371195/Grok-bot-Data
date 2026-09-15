# Change requests — mutable

No changes to R1 scope approved at baseline seal. This log cannot override IMPLEMENT.md.

Record requirement/conflict, evidence, affected task/contract, options, risk, human decision and date. Stop affected implementation when changing the baseline would be necessary. Preserve IMPLEMENT.md unchanged; do not treat a local ADR or this file as implicit authorization.

## Open requests

| ID | Requirement/conflict | Evidence | Affected task/contract | Options / risk | Decision / date |
| --- | --- | --- | --- | --- | --- |
| CR-2026-09-OPENAI | User-provided `.env` selects an OpenAI provider, while ARCHITECTURE/IMPLEMENT R1 stack names Anthropic adapter + deterministic fake | Typed settings now loads `LLM_PROVIDER` and an OpenAI adapter is covered only by mock transport; no live call was made | M2-02 model provider binding and deployment manifest; frozen IMPLEMENT remains unchanged | (A) approve OpenAI as an additional R1 adapter with same ModelProvider/tool policy; (B) use Anthropic/fake only for R1 and retain OpenAI adapter as FUTURE. A without budget/model approval can cause cost/compliance drift | Human decision required |
