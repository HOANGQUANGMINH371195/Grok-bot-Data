from pathlib import Path

from vda_adapters.fake_model import FakeModelProvider, ModelResponse, ToolCall
from vda_platform.memory import ContextBudget, MemoryRecord
from vda_platform.runtime import BotRuntime, TurnStatus
from vda_platform.tools import ToolRegistry

ROOT = Path(__file__).parents[2]


def _runtime(provider: FakeModelProvider) -> BotRuntime:
    return BotRuntime(provider, ToolRegistry.from_contract_root(ROOT))


def _kwargs() -> dict[str, object]:
    return {
        "actor_id": "human-1",
        "bot_id": "bot-1",
        "bot_template": "DataSteward",
        "workspace_id": "workspace-1",
        "conversation_id": "room-1",
        "fence": 1,
        "idempotency_key": "turn-1",
        "system": "Use verified data.",
        "history": ("Please profile the dataset.",),
    }


def test_runtime_dispatches_only_granted_tool_and_keeps_effect_idempotent() -> None:
    payload = {
        "workspace_id": "workspace-1",
        "resource_id": "dataset-1",
        "idempotency_key": "job-1",
    }
    provider = FakeModelProvider(
        (ModelResponse("queued profile", (ToolCall("profile.start", payload),)),)
    )
    runtime = _runtime(provider)
    calls = 0

    def handler(_context, _payload):
        nonlocal calls
        calls += 1
        return {"status": "queued", "job_ref": "profile-1"}

    result = runtime.execute(**_kwargs(), handlers={"profile.start": handler})
    assert result.status is TurnStatus.OK
    assert result.tool_results[0].data["job_ref"] == "profile-1"
    assert calls == 1


def test_runtime_returns_needs_input_instead_of_truncating_mandatory_context() -> None:
    provider = FakeModelProvider((ModelResponse("should not be called"),))
    kwargs = _kwargs()
    kwargs["history"] = ("x" * 100,)
    result = _runtime(provider).execute(
        **kwargs,
        budget=ContextBudget(history=4),
    )
    assert result.status is TurnStatus.NEEDS_INPUT
    assert result.error_code == "context_budget_exceeded"
    assert provider.calls == 0


def test_runtime_denies_provider_tool_call_without_handler_or_grant() -> None:
    class ForgedProvider:
        def complete(self, *, context, tool_ids):
            del context, tool_ids
            return ModelResponse(
                "",
                (ToolCall("analysis.plan", {"analysis_id": "a", "idempotency_key": "x"}),),
            )

    result = _runtime(ForgedProvider()).execute(
        **_kwargs(), handlers={"analysis.plan": lambda *_: None}
    )
    assert result.status is TurnStatus.DENIED
    assert result.tool_results[0].error == "tool_denied"


def test_runtime_does_not_load_private_memory_from_another_conversation() -> None:
    provider = FakeModelProvider((ModelResponse("grounded"),))
    result = _runtime(provider).execute(
        **_kwargs(),
        memories=(MemoryRecord("dm", "private-dm", "bot-1", "secret", 1, "private"),),
    )
    assert result.status is TurnStatus.OK
    assert all(item.content != "secret" for item in result.context.items)
