from pathlib import Path

import pytest
from vda_platform.tools import ToolContext, ToolDenied, ToolRegistry, ToolValidationError

ROOT = Path(__file__).parents[2]


def _context(template: str = "DataSteward") -> ToolContext:
    return ToolContext("bot-1", template, "workspace-1", "room-1", 1, 1, 1, "idem-1")


def test_grant_intersection_denies_forged_model_tool_request() -> None:
    registry = ToolRegistry.from_contract_root(ROOT)
    with pytest.raises(ToolDenied):
        registry.invoke(
            "analysis.plan",
            _context(),
            {"analysis_id": "a", "idempotency_key": "x"},
            lambda *_: None,
        )
    with pytest.raises(ToolDenied):
        registry.invoke("shell.exec", _context("DataAssistant"), {}, lambda *_: None)


def test_schema_is_checked_before_handler_and_side_effect_is_idempotent() -> None:
    registry = ToolRegistry.from_contract_root(ROOT)
    calls = 0

    def handler(_context: ToolContext, _payload: dict[str, object]) -> str:
        nonlocal calls
        calls += 1
        return "queued-1"

    with pytest.raises(ToolValidationError):
        registry.invoke(
            "profile.start", _context(), {"workspace_id": "w", "unexpected": "x"}, handler
        )
    payload = {"workspace_id": "w", "resource_id": "dataset-1", "idempotency_key": "idem-1"}
    assert registry.invoke("profile.start", _context(), payload, handler) == "queued-1"
    assert registry.invoke("profile.start", _context(), payload, handler) == "queued-1"
    assert calls == 1
