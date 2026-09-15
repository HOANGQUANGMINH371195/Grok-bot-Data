from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


class ObservatoryViolation(ValueError):
    """Raw content, secrets or invalid metadata reached the journal boundary."""


@dataclass(frozen=True)
class JournalRecord:
    record_id: str
    workspace_id: str
    conversation_id: str
    run_id: str
    actor_id: str
    event_type: str
    audience_principals: frozenset[str]
    metadata: dict[str, Any]
    occurred_at: str


class ObservatoryJournal:
    def __init__(self) -> None:
        self._records: list[JournalRecord] = []

    @property
    def records(self) -> tuple[JournalRecord, ...]:
        return tuple(self._records)

    def append(
        self,
        *,
        record_id: str,
        workspace_id: str,
        conversation_id: str,
        run_id: str,
        actor_id: str,
        event_type: str,
        audience_principals: frozenset[str],
        metadata: dict[str, Any],
    ) -> JournalRecord:
        if not record_id or not workspace_id or not conversation_id or not run_id:
            raise ObservatoryViolation("journal identity fields are required")
        if any(
            token in key.lower()
            for key in metadata
            for token in ("prompt", "secret", "token", "content")
        ):
            raise ObservatoryViolation("raw prompt/content/secret metadata is forbidden")
        safe_metadata = {
            key: value
            for key, value in metadata.items()
            if isinstance(value, (str, int, float, bool, type(None), list, dict))
        }
        record = JournalRecord(
            record_id,
            workspace_id,
            conversation_id,
            run_id,
            actor_id,
            event_type,
            frozenset(audience_principals),
            safe_metadata,
            datetime.now(UTC).isoformat(),
        )
        self._records.append(record)
        return record

    def visible_to(
        self, principal_id: str, workspace_id: str, conversation_id: str
    ) -> tuple[JournalRecord, ...]:
        return tuple(
            record
            for record in self._records
            if record.workspace_id == workspace_id
            and record.conversation_id == conversation_id
            and principal_id in record.audience_principals
        )
