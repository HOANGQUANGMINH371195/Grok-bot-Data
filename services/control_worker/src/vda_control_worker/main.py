"""Process entrypoint for the PostgreSQL-backed control worker.

The control worker is deliberately a thin composition root.  Runtime handlers
are supplied by an import path so this process owns leases and orchestration,
while bot/compute/export domains can evolve independently.  A missing handler
or disabled process fails closed; it never reports a fabricated successful run.
"""

from __future__ import annotations

import importlib
import logging
import os
import signal
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from threading import Event
from types import FrameType
from typing import Any, cast

from sqlalchemy import Engine, create_engine
from vda_platform.jobs import JobOutcome, PostgresControlWorker, PostgresRuntimeRepository, RunLease

RuntimeHandler = Callable[[RunLease], JobOutcome]
LOGGER = logging.getLogger("vda_control_worker")


class WorkerConfigurationError(ValueError):
    """Configuration is incomplete or unsafe for starting a worker."""


@dataclass(frozen=True)
class ControlWorkerConfig:
    """12-factor settings for one stateless control-worker process."""

    database_url: str
    workspace_id: str
    worker_id: str
    handler_path: str
    enabled: bool = False
    lease_seconds: int = 60
    heartbeat_interval_seconds: float | None = None
    poll_interval_seconds: float = 1.0

    def __repr__(self) -> str:
        """Keep credentials in a DSN out of logs and debugging output."""

        return (
            "ControlWorkerConfig(database_url='<redacted>', "
            f"workspace_id={self.workspace_id!r}, worker_id={self.worker_id!r}, "
            f"handler_path={self.handler_path!r}, enabled={self.enabled!r}, "
            f"lease_seconds={self.lease_seconds!r}, "
            f"heartbeat_interval_seconds={self.heartbeat_interval_seconds!r}, "
            f"poll_interval_seconds={self.poll_interval_seconds!r})"
        )

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> ControlWorkerConfig:
        values = os.environ if environ is None else environ
        database_url = _required(values, "VDA_DATABASE_URL", fallback="DATABASE_URL")
        workspace_id = _required(values, "VDA_CONTROL_WORKSPACE_ID")
        worker_id = _required(values, "VDA_CONTROL_WORKER_ID")
        handler_path = _required(values, "VDA_CONTROL_HANDLER")
        enabled = _boolean(values.get("VDA_CONTROL_WORKER_ENABLED", "false"))
        lease_seconds = _positive_int(values.get("VDA_CONTROL_LEASE_SECONDS", "60"), "lease")
        poll_interval = _positive_float(
            values.get("VDA_CONTROL_POLL_INTERVAL_SECONDS", "1"), "poll interval"
        )
        heartbeat_raw = values.get("VDA_CONTROL_HEARTBEAT_INTERVAL_SECONDS")
        heartbeat = (
            None if heartbeat_raw is None else _positive_float(heartbeat_raw, "heartbeat interval")
        )
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise WorkerConfigurationError("VDA_DATABASE_URL must use PostgreSQL")
        return cls(
            database_url=database_url,
            workspace_id=workspace_id,
            worker_id=worker_id,
            handler_path=handler_path,
            enabled=enabled,
            lease_seconds=lease_seconds,
            heartbeat_interval_seconds=heartbeat,
            poll_interval_seconds=poll_interval,
        )


@dataclass(frozen=True)
class ControlWorkerRuntime:
    worker: PostgresControlWorker
    engine: Engine


def load_handler(path: str) -> RuntimeHandler:
    """Load a configured ``module:callable`` without putting code in env vars."""

    module_name, separator, attribute = path.partition(":")
    if not separator or not module_name or not attribute:
        raise WorkerConfigurationError("VDA_CONTROL_HANDLER must be module:callable")
    try:
        candidate: Any = getattr(importlib.import_module(module_name), attribute)
    except (ImportError, AttributeError) as exc:
        raise WorkerConfigurationError(
            "configured control-worker handler cannot be loaded"
        ) from exc
    if not callable(candidate):
        raise WorkerConfigurationError("configured control-worker handler is not callable")
    return cast(RuntimeHandler, candidate)


def build_runtime(
    config: ControlWorkerConfig,
    *,
    handler: RuntimeHandler | None = None,
) -> ControlWorkerRuntime:
    """Create the repository and worker; no network connection is opened yet."""

    engine = create_engine(config.database_url, pool_pre_ping=True)
    repository = PostgresRuntimeRepository(engine, default_lease_seconds=config.lease_seconds)
    effective_handler = handler if handler is not None else load_handler(config.handler_path)
    worker = PostgresControlWorker(
        repository,
        workspace_id=config.workspace_id,
        worker_id=config.worker_id,
        handler=effective_handler,
        lease_seconds=config.lease_seconds,
        heartbeat_interval_seconds=config.heartbeat_interval_seconds,
    )
    return ControlWorkerRuntime(worker=worker, engine=engine)


def main() -> int:
    """Run until SIGINT/SIGTERM, returning a non-zero code for bad config."""

    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    try:
        config = ControlWorkerConfig.from_env()
        if not config.enabled:
            raise WorkerConfigurationError("VDA_CONTROL_WORKER_ENABLED must be true")
        runtime = build_runtime(config)
    except WorkerConfigurationError as exc:
        LOGGER.error("control_worker_not_ready: %s", exc)
        return 2

    stop_event = Event()

    def request_shutdown(signum: int, _frame: FrameType | None) -> None:
        LOGGER.info("control_worker_shutdown_requested signal=%s", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)
    try:
        runtime.worker.run_forever(
            stop_event=stop_event,
            poll_interval_seconds=config.poll_interval_seconds,
            on_error=lambda exc: LOGGER.exception("control_worker_iteration_failed: %s", exc),
        )
    finally:
        runtime.engine.dispose()
    return 0


def _required(values: Mapping[str, str], name: str, *, fallback: str | None = None) -> str:
    value = values.get(name)
    if not value and fallback is not None:
        value = values.get(fallback)
    if value is None or not value.strip():
        raise WorkerConfigurationError(f"{name.lower()} is required")
    return value.strip()


def _boolean(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise WorkerConfigurationError("boolean setting must be true/false")


def _positive_int(value: str, label: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise WorkerConfigurationError(f"{label} must be an integer") from exc
    if parsed <= 0:
        raise WorkerConfigurationError(f"{label} must be positive")
    return parsed


def _positive_float(value: str, label: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise WorkerConfigurationError(f"{label} must be a number") from exc
    if parsed <= 0:
        raise WorkerConfigurationError(f"{label} must be positive")
    return parsed
