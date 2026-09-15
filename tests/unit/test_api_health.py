from vda_api.main import app, healthz, readyz


def test_health_contract_is_local_and_non_secret() -> None:
    assert app.title == "VDaAgent API"
    assert healthz() == {"status": "ok"}


def test_readiness_does_not_claim_unconfigured_dependencies() -> None:
    assert readyz()["status"] == "not_ready"
