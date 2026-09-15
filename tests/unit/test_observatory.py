import pytest
from vda_platform.observatory import ObservatoryJournal, ObservatoryViolation


def test_observatory_is_metadata_only_and_audience_filtered() -> None:
    journal = ObservatoryJournal()
    journal.append(
        record_id="j1",
        workspace_id="w",
        conversation_id="c",
        run_id="r",
        actor_id="bot",
        event_type="tool.executed",
        audience_principals=frozenset({"human-1"}),
        metadata={"tool_id": "profile.get", "status": "ok", "duration_ms": 12},
    )
    assert len(journal.visible_to("human-1", "w", "c")) == 1
    assert not journal.visible_to("human-2", "w", "c")


def test_observatory_rejects_raw_prompt_or_secret_metadata() -> None:
    journal = ObservatoryJournal()
    with pytest.raises(ObservatoryViolation):
        journal.append(
            record_id="j1",
            workspace_id="w",
            conversation_id="c",
            run_id="r",
            actor_id="bot",
            event_type="model.called",
            audience_principals=frozenset({"human-1"}),
            metadata={"prompt": "private", "api_secret": "do-not-store"},
        )
