#!/usr/bin/env python3
"""Run the FastAPI server. Usage: python run_api.py. Set HOST=0.0.0.0 to allow network access."""
import os
from pathlib import Path

# Project root = directory containing this file. Load .env first so env vars are set
# before uvicorn (and the reload worker) start. override=True so .env wins over shell env.
_ROOT = Path(__file__).resolve().parent
_env_path = _ROOT / ".env"
from dotenv import load_dotenv
load_dotenv(_env_path, override=True)

import uvicorn

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True,
    )
