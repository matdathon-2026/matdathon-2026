"""Application settings.

Secrets are never hardcoded here. In Azure they arrive as Container Apps
secrets backed by Key Vault; locally they come from the shell environment.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _extract_endpoint(value: str) -> str:
    """Accept a bare URL or an Aspire-style connection string.

    Aspire injects Azure resource references as ``AccountEndpoint=https://...;``
    or ``Endpoint=https://...``, while a local shell usually exports the plain
    URL. Both must work without the caller caring which one it got.
    """
    text = (value or "").strip()
    if not text or text.lower().startswith(("http://", "https://")):
        return text
    for segment in text.split(";"):
        key, _, candidate = segment.partition("=")
        if key.strip().lower() in {"accountendpoint", "endpoint"} and candidate:
            return candidate.strip()
    return text


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = Field(default="local")

    foundry_resource_url: str = Field(default="")
    foundry_model: str = Field(default="")
    ai_timeout_seconds: float = Field(default=30.0)

    cosmos_endpoint: str = Field(default="")
    cosmos_database: str = Field(default="didimheart")
    cosmos_benefits_container: str = Field(default="benefits")

    ingest_archive_account_url: str = Field(default="")
    ingest_archive_container: str = Field(default="raw-benefits")

    youthcenter_api_key: str = Field(default="")
    youthcenter_enabled: bool = Field(default=True)

    data_go_kr_service_key: str = Field(default="")
    # Endpoint shape could not be verified without a real key, so this source
    # stays off until someone confirms it against the live service.
    data_go_kr_enabled: bool = Field(default=False)

    snapshot_enabled: bool = Field(default=True)
    snapshot_path: str = Field(default="data/benefits.seed.json")

    http_timeout_seconds: float = Field(default=15.0)
    ingest_max_records_per_source: int = Field(default=60)
    ingest_dry_run: bool = Field(default=False)

    @field_validator(
        "cosmos_endpoint",
        "foundry_resource_url",
        "ingest_archive_account_url",
        mode="before",
    )
    @classmethod
    def _normalize_endpoint(cls, value: object) -> object:
        return _extract_endpoint(value) if isinstance(value, str) else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
