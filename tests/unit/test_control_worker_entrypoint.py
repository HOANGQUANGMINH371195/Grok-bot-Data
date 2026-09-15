import pytest
from vda_control_worker.main import ControlWorkerConfig, WorkerConfigurationError


def _environment(**overrides: str) -> dict[str, str]:
    values = {
        "VDA_DATABASE_URL": "postgresql+psycopg://user:password@db/vda",
        "VDA_CONTROL_WORKSPACE_ID": "workspace-demo",
        "VDA_CONTROL_WORKER_ID": "control-1",
        "VDA_CONTROL_HANDLER": "tests.unit.test_control_worker_entrypoint:handler",
        "VDA_CONTROL_WORKER_ENABLED": "true",
    }
    values.update(overrides)
    return values


def handler(_lease: object) -> object:
    return object()


def test_config_parses_12_factor_settings_without_logging_secrets() -> None:
    config = ControlWorkerConfig.from_env(
        _environment(
            VDA_CONTROL_LEASE_SECONDS="45",
            VDA_CONTROL_HEARTBEAT_INTERVAL_SECONDS="5",
            VDA_CONTROL_POLL_INTERVAL_SECONDS="0.25",
        )
    )

    assert config.enabled is True
    assert config.lease_seconds == 45
    assert config.heartbeat_interval_seconds == 5
    assert config.poll_interval_seconds == 0.25
    assert "password" not in repr(config)


def test_config_requires_explicit_handler_and_postgres() -> None:
    with pytest.raises(WorkerConfigurationError, match="handler"):
        ControlWorkerConfig.from_env(_environment(VDA_CONTROL_HANDLER=""))
    with pytest.raises(WorkerConfigurationError, match="PostgreSQL"):
        ControlWorkerConfig.from_env(_environment(VDA_DATABASE_URL="sqlite:///not-supported"))


def test_config_defaults_to_disabled_until_operator_enables_process() -> None:
    config = ControlWorkerConfig.from_env(
        _environment(VDA_CONTROL_WORKER_ENABLED="false")
    )

    assert config.enabled is False
