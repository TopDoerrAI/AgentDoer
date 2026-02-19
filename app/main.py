"""FastAPI application entrypoint."""
import logging
import os
import sys
from pathlib import Path

# Project root (parent of app/)
_ROOT = Path(__file__).resolve().parent.parent

# Load .env FIRST so SUPABASE_*, NVIDIA_*, etc. are set before any app code reads them.
# override=True so .env wins (important when uvicorn reload spawns a worker that may not inherit env).
from dotenv import load_dotenv
load_dotenv(_ROOT / ".env", override=True)

# Ensure project root is on path when run as: python app/main.py
if __name__ == "__main__" or "app" not in sys.modules:
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings

# Log level for agent/tools (set LOG_LEVEL=DEBUG to see memory, Supabase, etc.)
logging.basicConfig(level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO))
_log = logging.getLogger(__name__)

# Prevent third-party HTTP libs from logging at DEBUG (avoids leaking API keys/headers into logs)
for _name in ("httpx", "httpcore", "hpack", "urllib3"):
    logging.getLogger(_name).setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up agent on first request (lazy init in agent.get_agent)
    yield
    # Optional: cleanup (e.g. close browser worker) if needed


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["POST", "OPTIONS", "GET"],
        allow_headers=["Content-Type", "Authorization"],
    )
    app.include_router(router)
    return app


app = create_app()

# Log Supabase/memory status at startup
if get_settings().supabase_enabled:
    _log.info("Supabase enabled: memory and conversation persistence are on.")
else:
    _log.info("Supabase disabled (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set). Memory off.")

if __name__ == "__main__":
    import os
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")  # 127.0.0.1 = localhost only
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
