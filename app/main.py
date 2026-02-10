"""FastAPI application entrypoint."""
import sys
from pathlib import Path

# Project root (parent of app/)
_ROOT = Path(__file__).resolve().parent.parent

# Ensure project root is on path when run as: python app/main.py
if __name__ == "__main__" or "app" not in sys.modules:
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings

# Load .env from project root so it works when run via run_api.py or uvicorn from any cwd
load_dotenv(_ROOT / ".env")


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

if __name__ == "__main__":
    import os
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")  # 127.0.0.1 = localhost only
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
