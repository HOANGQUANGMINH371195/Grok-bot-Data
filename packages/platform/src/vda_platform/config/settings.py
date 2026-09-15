from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment contract; secret values are intentionally not exposed in repr/serialization."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    openai_api_key: SecretStr | None = None
    model_name: str = "fake-grounded-v1"
    llm_provider: str = "fake"
    embedding_provider: str = "fake"
    embedding_model: str = "fake-embedding-v1"
    embedding_dimensions: int = 1536
    embedding_batch_size: int = 32
    langfuse_secret_key: SecretStr | None = None
    langfuse_public_key: str | None = None
    langfuse_base_url: str | None = None
    aws_access_key_id: SecretStr | None = None
    aws_secret_access_key: SecretStr | None = None
    aws_default_region: str | None = None

    @field_validator("embedding_dimensions", "embedding_batch_size")
    @classmethod
    def positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("embedding settings must be positive")
        return value

    @field_validator("aws_default_region")
    @classmethod
    def valid_region(cls, value: str | None) -> str | None:
        if value is not None and (len(value) > 32 or " " in value):
            raise ValueError("aws_default_region must be a compact region name")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
