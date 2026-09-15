from __future__ import annotations

import json
import math
import multiprocessing
from dataclasses import dataclass, field
from queue import Empty
from typing import Any

from vda_data.ingestion import IngestionError, IngestionPolicy

from .engine import ProfileResult, profile_csv, profile_parquet


class ComputeError(RuntimeError):
    """A bounded profile process failed without a trustworthy result."""


class ComputeLimitError(ComputeError):
    """The profile process exceeded an admission or resource limit."""


@dataclass(frozen=True)
class ComputeLimits:
    """R1 compute budget; values are explicit and validated at the boundary."""

    ingestion: IngestionPolicy = field(default_factory=IngestionPolicy)
    deadline_seconds: float = 600.0
    max_memory_bytes: int = 4 * 1024 * 1024 * 1024
    max_result_bytes: int = 32 * 1024 * 1024

    def __post_init__(self) -> None:
        if not math.isfinite(self.deadline_seconds) or self.deadline_seconds <= 0:
            raise ValueError("deadline_seconds must be finite and positive")
        if self.max_memory_bytes <= 0 or self.max_result_bytes <= 0:
            raise ValueError("compute byte limits must be positive")


class ComputeSupervisor:
    """Run one profile in a killable process with no local durable state."""

    def __init__(self, limits: ComputeLimits | None = None) -> None:
        self._limits = limits or ComputeLimits()

    @property
    def limits(self) -> ComputeLimits:
        return self._limits

    def profile(self, payload: bytes, format_name: str) -> ProfileResult:
        if format_name not in {"csv", "parquet"}:
            raise ComputeError("unsupported profile format")
        if len(payload) > self._limits.ingestion.max_file_bytes:
            raise ComputeLimitError("source exceeds max_file_bytes")

        context = multiprocessing.get_context("spawn")
        result_queue: Any = context.Queue(maxsize=1)
        process = context.Process(
            target=_profile_process,
            args=(payload, format_name, self._limits, result_queue),
            name="vda-profile-compute",
        )
        process.start()
        process.join(self._limits.deadline_seconds)
        if process.is_alive():
            process.terminate()
            process.join(2.0)
            process.close()
            result_queue.close()
            result_queue.join_thread()
            raise ComputeLimitError("profile compute deadline exceeded")
        try:
            status, value = result_queue.get(timeout=1.0)
        except Empty as exc:
            process.close()
            raise ComputeError(f"profile process exited with code {process.exitcode}") from exc
        finally:
            result_queue.close()
            result_queue.join_thread()
        process.close()
        if status != "ok":
            error_type, message = value
            if error_type == "limit":
                raise ComputeLimitError(message)
            raise ComputeError(message)
        if not isinstance(value, ProfileResult):
            raise ComputeError("profile process returned an invalid result")
        return value


def _profile_process(
    payload: bytes,
    format_name: str,
    limits: ComputeLimits,
    result_queue: Any,
) -> None:
    _apply_process_limits(limits)
    try:
        result = (
            profile_csv(payload, limits.ingestion)
            if format_name == "csv"
            else profile_parquet(payload, limits.ingestion)
        )
        encoded_size = len(
            json.dumps(result.as_dict(), separators=(",", ":"), allow_nan=False).encode()
        )
        if encoded_size > limits.max_result_bytes:
            result_queue.put(("error", ("limit", "profile result exceeds max_result_bytes")))
            return
        result_queue.put(("ok", result))
    except IngestionError as exc:
        kind = "limit" if "exceeds" in str(exc) else "error"
        result_queue.put(("error", (kind, str(exc))))
    except MemoryError as exc:
        result_queue.put(("error", ("limit", str(exc))))
    except ValueError as exc:
        result_queue.put(("error", ("error", str(exc))))
    except Exception as exc:  # the parent records a sanitized class/message only
        result_queue.put(("error", ("error", f"profile compute failed: {exc.__class__.__name__}")))


def _apply_process_limits(limits: ComputeLimits) -> None:
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (limits.max_memory_bytes, limits.max_memory_bytes))
        cpu_seconds = max(1, math.ceil(limits.deadline_seconds))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
    except (ImportError, OSError, ValueError):
        # Windows and restricted containers may not expose rlimits; the parent
        # deadline and parser bounds remain mandatory controls.
        return
