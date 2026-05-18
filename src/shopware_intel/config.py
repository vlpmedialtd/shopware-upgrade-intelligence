from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SW_INTEL_", env_file=".env", extra="ignore")

    qdrant_url: str = "http://localhost:6333"
    # Legacy embedded-mode path. Kept as a fallback when qdrant_url is unreachable; the
    # Phase-R stack expects the Docker daemon.
    qdrant_path: Path = Field(
        default_factory=lambda: Path.home() / "Library/Application Support/shopware-intel/qdrant"
    )
    # Ollama with nomic-embed-text is the right pragmatic choice on Apple Silicon:
    # Metal-accelerated, ~40 emb/s for realistic Shopware chunks. multilingual-e5-large
    # via fastembed was measured 8x slower (CPU-only ONNX path); bge-m3 via Ollama is
    # 5x slower than nomic-embed-text because of its 567M-param size. The retrieval-
    # quality gap is closed by tree-sitter method-level chunks + chunk-header metadata
    # rather than a heavier embedding model.
    embed_model: str = "nomic-embed-text"
    embed_dim: int = 768
    ollama_host: str = "http://localhost:11434"
    mirror_path: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent / "mirrors/platform.git"
    )
    state_db: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent / "data/state.db"
    )
    embed_batch_size: int = 32
    ingest_workers: int = 4
    log_level: str = "INFO"


def get_settings() -> Settings:
    return Settings()
