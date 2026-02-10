"""Application settings from environment."""
import os
from functools import lru_cache


@lru_cache
def get_settings() -> "Settings":
    return Settings()


class Settings:
    """Central config. Load .env in main before using."""

    # NVIDIA LLM
    nvidia_api_key: str = os.getenv("NVIDIA_API_KEY", "")
    nvidia_model: str = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")
    use_tools: bool = os.getenv("USE_TOOLS", "0").strip().lower() in ("1", "true", "yes")

    # Browser
    browser_headless: bool = os.getenv("BROWSER_HEADLESS", "1").strip().lower() not in ("0", "false", "no")
    # Persistent session: path to state.json (save after manual login) or Chrome user data dir
    browser_storage_state: str = os.getenv("BROWSER_STORAGE_STATE", "").strip()
    browser_user_data_dir: str = os.getenv("BROWSER_USER_DATA_DIR", "").strip()
    # Optional: real browser user agent (empty = Playwright default)
    real_user_agent: str = os.getenv("REAL_USER_AGENT", "").strip()

    # Supabase (optional): use SERVICE ROLE key (Settings → API), not the anon/publishable key
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_KEY", "")
    supabase_enabled: bool = bool(supabase_url and supabase_key)

    # API
    api_title: str = os.getenv("API_TITLE", "NVIDIA Agent API")
    api_version: str = os.getenv("API_VERSION", "0.1.0")

    # Embeddings (for recall_memory, store_memory, search_knowledge_base)
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "nvidia/nv-embedqa-e5-v5")
    embedding_dim: int = int(os.getenv("EMBEDDING_DIM", "1024"))

    # Memory extraction (post-response): model for extracting facts (small/fast preferred)
    extraction_model: str = os.getenv("EXTRACTION_MODEL", "nvidia/llama-3.2-3b-instruct-v1")

    # Code execution (run_python): timeout in seconds
    python_timeout_seconds: int = int(os.getenv("PYTHON_TIMEOUT_SECONDS", "10"))

    # CORS: comma-separated origins (e.g. http://localhost:3000) or * for all
    @property
    def cors_origins(self) -> list[str]:
        raw = os.getenv("CORS_ORIGINS", "*").strip()
        if not raw or raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]
