#!/usr/bin/env python3
"""Run the FastAPI server. Usage: python run_api.py. Set HOST=0.0.0.0 to allow network access."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (same folder as run_api.py)
load_dotenv(Path(__file__).resolve().parent / ".env")

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
