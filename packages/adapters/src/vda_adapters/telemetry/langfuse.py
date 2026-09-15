from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RedactedTrace:
    trace_id: str
    name: str
    metadata: dict[str, str | int | float | bool | None]


def redact_trace(trace_id: str, name: str, metadata: dict[str, Any]) -> RedactedTrace:
    """Prepare metadata-only Langfuse/OTel data; prompts, content and secrets never pass through."""
    forbidden = ("prompt", "content", "secret", "token", "password", "email", "phone")
    safe: dict[str, str | int | float | bool | None] = {}
    for key, value in metadata.items():
        if any(term in key.lower() for term in forbidden):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[key] = value
    return RedactedTrace(trace_id, name, safe)
