from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast


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
        self._by_id: dict[str, JournalRecord] = {}

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
        if not audience_principals:
            raise ObservatoryViolation("journal audience cannot be empty")
        existing = self._by_id.get(record_id)
        if existing is not None:
            if (
                existing.workspace_id != workspace_id
                or existing.conversation_id != conversation_id
                or existing.run_id != run_id
                or existing.metadata != metadata
            ):
                raise ObservatoryViolation("record_id was reused with different metadata")
            return existing
        safe_metadata = cast(dict[str, Any], _safe_metadata(metadata))
        try:
            if len(json.dumps(safe_metadata, separators=(",", ":"))) > 16_384:
                raise ObservatoryViolation("journal metadata exceeds 16KiB")
        except (TypeError, ValueError) as exc:
            raise ObservatoryViolation("journal metadata is not JSON-safe") from exc
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
        self._by_id[record_id] = record
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


_FORBIDDEN_KEYS = ("prompt", "secret", "token", "content", "password", "authorization")


def _safe_metadata(value: object, *, key: str = "metadata") -> object:
    if any(term in key.lower() for term in _FORBIDDEN_KEYS):
        raise ObservatoryViolation("raw prompt/content/secret metadata is forbidden")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(child_key): _safe_metadata(child_value, key=str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [_safe_metadata(child, key=key) for child in value]
    raise ObservatoryViolation(f"unsupported metadata type for {key}")
