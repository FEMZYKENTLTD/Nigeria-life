"""Runtime configuration. Everything is read from environment variables so no secret is ever written to disk."""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("NLIE_DATA_DIR", "./nlie-data")).resolve())
    database_url: str = ""
    user_agent: str = "NigeriaLifeIntelligenceEngine/0.1 (+research; honours robots.txt)"
    ai_base_url: str = field(default_factory=lambda: os.environ.get("NLIE_AI_BASE_URL", ""))
    ai_api_key: str = field(default_factory=lambda: os.environ.get("NLIE_AI_API_KEY", ""))
    ai_model_simple: str = field(default_factory=lambda: os.environ.get("NLIE_AI_MODEL_SIMPLE", ""))
    ai_model_complex: str = field(default_factory=lambda: os.environ.get("NLIE_AI_MODEL_COMPLEX", ""))
    ai_model_vision: str = field(default_factory=lambda: os.environ.get("NLIE_AI_MODEL_VISION", ""))
    github_token: str = field(default_factory=lambda: os.environ.get("GITHUB_TOKEN", ""))
    worker_poll_seconds: float = 0.5

    def __post_init__(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        for sub in ("evidence", "screenshots", "reports", "backups", "profiles"):
            (self.data_dir / sub).mkdir(exist_ok=True)
        # SQLite by default (local-first). Set NLIE_DATABASE_URL=postgresql+psycopg://... for a central database.
        self.database_url = os.environ.get("NLIE_DATABASE_URL") or f"sqlite:///{self.data_dir / 'nlie.db'}"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    global _settings
    _settings = None
