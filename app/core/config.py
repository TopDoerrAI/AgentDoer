"""Application settings from environment."""
import os
from functools import lru_cache


@lru_cache
def get_settings() -> "Settings":
    return Settings()


class Settings:
    """Central config. Load .env in main/run_api before using. Key settings are @property so they read env at access time."""

    # NVIDIA LLM (properties so they read after .env is loaded)
    @property
    def nvidia_api_key(self) -> str:
        return os.getenv("NVIDIA_API_KEY", "").strip()

    @property
    def nvidia_model(self) -> str:
        return (os.getenv("NVIDIA_MODEL", "") or "").strip()

    @property
    def use_tools(self) -> bool:
        return os.getenv("USE_TOOLS", "0").strip().lower() in ("1", "true", "yes")

    # Browser
    @property
    def browser_headless(self) -> bool:
        return os.getenv("BROWSER_HEADLESS", "1").strip().lower() not in ("0", "false", "no")
    # Persistent session: path to state.json (save after manual login) or Chrome user data dir
    @property
    def browser_storage_state(self) -> str:
        return os.getenv("BROWSER_STORAGE_STATE", "").strip()

    @property
    def browser_user_data_dir(self) -> str:
        return os.getenv("BROWSER_USER_DATA_DIR", "").strip()

    @property
    def real_user_agent(self) -> str:
        return os.getenv("REAL_USER_AGENT", "").strip()

    # Email (IMAP + SMTP for Gmail/Outlook, or SendGrid for send-only)
    @property
    def email_imap_host(self) -> str:
        return os.getenv("EMAIL_IMAP_HOST", "").strip()

    @property
    def email_imap_port(self) -> int:
        return int(os.getenv("EMAIL_IMAP_PORT", "993"))

    @property
    def email_imap_user(self) -> str:
        return os.getenv("EMAIL_IMAP_USER", "").strip()

    @property
    def email_imap_password(self) -> str:
        return os.getenv("EMAIL_IMAP_PASSWORD", "").strip()

    @property
    def email_smtp_host(self) -> str:
        return os.getenv("EMAIL_SMTP_HOST", "").strip()

    @property
    def email_smtp_port(self) -> int:
        return int(os.getenv("EMAIL_SMTP_PORT", "587"))

    @property
    def email_smtp_user(self) -> str:
        return os.getenv("EMAIL_SMTP_USER", "").strip()

    @property
    def email_smtp_password(self) -> str:
        return os.getenv("EMAIL_SMTP_PASSWORD", "").strip()

    @property
    def sendgrid_api_key(self) -> str:
        return os.getenv("SENDGRID_API_KEY", "").strip()

    # Sender identity for email sign-off (avoids [Your Name] / [Company] placeholders)
    @property
    def email_sender_name(self) -> str:
        return os.getenv("EMAIL_SENDER_NAME", "").strip()

    @property
    def email_sender_company(self) -> str:
        return os.getenv("EMAIL_SENDER_COMPANY", "").strip()

    @property
    def email_sender_contact(self) -> str:
        return os.getenv("EMAIL_SENDER_CONTACT", "").strip()

    @property
    def email_enabled(self) -> bool:
        """True if we can send (SMTP or SendGrid) or read (IMAP)."""
        can_send = (self.email_smtp_host and self.email_smtp_user and self.email_smtp_password) or bool(self.sendgrid_api_key)
        can_read = bool(self.email_imap_host and self.email_imap_user and self.email_imap_password)
        return can_send or can_read

    # Supabase (optional): use SERVICE ROLE key (Settings → API), not the anon/publishable key
    # Properties so values are read when accessed (after .env is loaded), not at import time
    @property
    def supabase_url(self) -> str:
        return os.getenv("SUPABASE_URL", "").strip()

    @property
    def supabase_key(self) -> str:
        return (os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_KEY", "")).strip()

    @property
    def supabase_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    @property
    def supabase_timeout_seconds(self) -> float:
        raw = os.getenv("SUPABASE_TIMEOUT_SECONDS", "10").strip()
        try:
            return max(1.0, min(60.0, float(raw)))
        except ValueError:
            return 10.0

    # API
    @property
    def api_title(self) -> str:
        return os.getenv("API_TITLE", "NVIDIA Agent API").strip()

    @property
    def api_version(self) -> str:
        return os.getenv("API_VERSION", "0.1.0").strip()

    # Embeddings (for recall_memory, store_memory, search_knowledge_base)
    @property
    def embedding_model(self) -> str:
        return os.getenv("EMBEDDING_MODEL", "nvidia/nv-embedqa-e5-v5").strip()

    @property
    def embedding_dim(self) -> int:
        return int(os.getenv("EMBEDDING_DIM", "1024"))

    # Memory extraction (post-response): model for extracting facts (small/fast preferred; use a valid NIM model ID)
    @property
    def extraction_model(self) -> str:
        return os.getenv("EXTRACTION_MODEL", "meta/llama-3.1-8b-instruct").strip()

    # Code execution (run_python): timeout in seconds
    @property
    def python_timeout_seconds(self) -> int:
        return int(os.getenv("PYTHON_TIMEOUT_SECONDS", "10"))

    # Crawler: limits and politeness
    @property
    def crawl_max_pages(self) -> int:
        return max(1, min(500, int(os.getenv("CRAWL_MAX_PAGES", "50"))))

    @property
    def crawl_max_depth(self) -> int:
        return max(1, min(20, int(os.getenv("CRAWL_MAX_DEPTH", "3"))))

    @property
    def crawl_timeout_seconds(self) -> int:
        return max(5, min(300, int(os.getenv("CRAWL_TIMEOUT_SECONDS", "60"))))

    @property
    def crawl_request_delay_seconds(self) -> float:
        raw = os.getenv("CRAWL_REQUEST_DELAY", "1.0").strip()
        try:
            return max(0.0, min(10.0, float(raw)))
        except ValueError:
            return 1.0

    # CORS: comma-separated origins (e.g. http://localhost:3000) or * for all
    @property
    def cors_origins(self) -> list[str]:
        raw = os.getenv("CORS_ORIGINS", "*").strip()
        if not raw or raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]
