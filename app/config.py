"""Application settings loaded from environment (pydantic-settings)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # AI / Copilot. Token is injected ONLY via COPILOT_GITHUB_TOKEN (Container Apps secret).
    foundry_resource_url: str = ""
    foundry_model: str = ""
    ai_timeout_seconds: float = 120.0
    ai_enabled: bool = True

    # Data store. When cosmos_endpoint is empty we use the JSON-file memory repository.
    cosmos_endpoint: str = ""
    cosmos_database: str = "didimheart"
    data_dir: str = str(REPO_ROOT / "data")
    seed_path: str = str(REPO_ROOT / "data" / "benefits.seed.json")
    state_path: str = str(REPO_ROOT / "data" / "state.local.json")

    # Web
    web_dist: str = str(REPO_ROOT / "web" / "dist")
    cors_allow_origins: str = ""  # comma separated; empty => same-origin only

    # Demo sponsorship figures (simulation only)
    demo_sponsor_total_krw: int = 5_000_000

    @property
    def use_cosmos(self) -> bool:
        return bool(self.cosmos_endpoint)


@lru_cache
def get_settings() -> Settings:
    return Settings()
