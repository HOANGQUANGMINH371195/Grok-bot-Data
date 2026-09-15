import pytest
from vda_platform.memory import ContextBudget, ContextOverflow, MemoryRecord, build_context


def test_context_filters_private_dm_memory_from_group() -> None:
    records = (
        MemoryRecord("private-dm", "dm-1", "bot-1", "DM secret", 1, "private"),
        MemoryRecord("group-note", "group-1", "bot-1", "Group note", 2, "conversation"),
        MemoryRecord("other-bot", "group-1", "bot-2", "Other bot private", 1, "conversation"),
    )
    context = build_context(
        conversation_id="group-1", bot_id="bot-1", system="system", tool_descriptions=(),
        history=("hello",), memories=records, results=(),
    )
    contents = [item.content for item in context.items]
    assert "Group note" in contents
    assert "DM secret" not in contents
    assert "Other bot private" not in contents


def test_context_rejects_overflow_instead_of_silently_dropping_mandatory_history() -> None:
    with pytest.raises(ContextOverflow, match="history"):
        build_context(
            conversation_id="c", bot_id="b", system="s", tool_descriptions=(),
            history=("x" * 500,), memories=(), results=(),
            budget=ContextBudget(history=10),
        )
