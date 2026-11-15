"""Runtime configuration.

Everything is environment-driven (12-factor). The platform is local-first:
SQLite by default; set RICE_DB_URL to a postgresql+asyncpg:// URL for central
PostgreSQL deployment. No target-site, product name or feature is hardcoded
anywhere in the core.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Storage lives in the platform data dir (platform/data) regardless of the
# process cwd — the engine is local-first and that dir is the single,
# documented location for the SQLite DB, evidence files and exports.
_PLATFORM_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = _PLATFORM_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RICE_", env_file=".env", extra="ignore")

    # --- storage ---
    db_url: str = f"sqlite+aiosqlite:///{DEFAULT_DATA_DIR / 'rice.db'}"
    data_dir: str = str(DEFAULT_DATA_DIR)
    # --- api ---
    host: str = "0.0.0.0"
    port: int = 8787
    cors_origins: str = "*"
    # --- ai provider layer (provider-independent adapter) ---
    ai_provider: str = "off"            # off | openai_compatible | ollama
    ai_base_url: str = ""               # any OpenAI-compatible /chat/completions endpoint
    ai_api_key: str = ""
    ai_model_small: str = "gpt-4o-mini" # used for routine subtasks
    ai_model_large: str = "gpt-4o"      # used for planning / synthesis
    ai_request_timeout: float = 60.0
    # --- browser automation ---
    browser_timeout_ms: int = 30000
    browser_max_retries: int = 2
    browser_retry_backoff_s: float = 2.0
    # --- research policy (defaults; overridable per project) ---
    default_delay_between_fetches_s: float = 2.0
    max_pages_per_session: int = 40
    # --- github ---
    github_repo: str = "FEMZYKENTLTD/Nigeria-life"  # central project repo (display + remote ops)
    local_repo_path: str = ""                        # if set, operate on the local checkout via git
    # --- multi-user / Supabase (optional; local-first default is single-user) ---
    supabase_url: str = ""        # e.g. https://xyz.supabase.co — enables JWT auth when set with the secret
    supabase_jwt_secret: str = ""  # project JWT secret (HS256 verification; never logged)
    admin_emails: str = ""        # comma-separated emails auto-granted the admin role
    # --- declared browser identity (configurable so re-branded deployments
    #     can change it; always a declared, identifiable user agent) ---
    browser_ua: str = "NigeriaLifeResearchBot/1.0 (+research-platform; authorised-research-only)"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    return s
