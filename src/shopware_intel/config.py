from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SW_INTEL_", env_file=".env", extra="ignore")

    qdrant_path: Path = Field(
        default_factory=lambda: Path.home() / "Library/Application Support/shopware-intel/qdrant"
    )
    ollama_host: str = "http://localhost:11434"
    embed_model: str = "nomic-embed-text"
    embed_dim: int = 768
    mirror_path: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent / "mirrors/platform.git"
    )
    state_db: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent / "data/state.db"
    )
    embed_batch_size: int = 64
    log_level: str = "INFO"


def get_settings() -> Settings:
    return Settings()
