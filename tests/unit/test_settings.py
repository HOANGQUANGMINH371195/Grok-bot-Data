import pytest
from pydantic import ValidationError
from vda_platform.config import Settings


def test_settings_validate_provider_bindings_without_exposing_secret_values(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_NAME", "test-model")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    settings = Settings(
        openai_api_key="secret-not-printed",
        embedding_dimensions=768,
        embedding_batch_size=16,
        aws_default_region="us-east-1",
    )
    assert settings.embedding_dimensions == 768
    assert settings.model_name == "test-model"
    assert settings.llm_provider == "openai"
    assert "secret-not-printed" not in repr(settings)
    assert settings.openai_api_key is not None


def test_settings_reject_invalid_embedding_bounds_and_region() -> None:
    with pytest.raises(ValidationError):
        Settings(embedding_dimensions=0)
    with pytest.raises(ValidationError):
        Settings(aws_default_region="invalid region with spaces")
