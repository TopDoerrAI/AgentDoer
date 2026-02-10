#!/usr/bin/env python3
"""
Ingest knowledge from a JSON array into Supabase knowledge_chunks.
Usage: python scripts/ingest_knowledge.py examples/knowledge_chunks_example.json

JSON format: [ {"source": "...", "content": "..."}, ... ]
Embeddings are computed at ingest time (NVIDIA embedder). Vector size must be 1024.
"""
import json
import sys
from pathlib import Path

# Project root
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from dotenv import load_dotenv
load_dotenv(_root / ".env")

from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

from app.core.config import get_settings
from app.core.supabase_client import get_supabase_client


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_knowledge.py <path-to-json>")
        sys.exit(1)
    path = Path(sys.argv[1])
    if not path.is_file():
        print("File not found:", path)
        sys.exit(1)
    client = get_supabase_client()
    if not client:
        print("Supabase not configured (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY).")
        sys.exit(1)
    s = get_settings()
    embedder = NVIDIAEmbeddings(model=s.embedding_model, nvidia_api_key=s.nvidia_api_key)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        data = [data]
    for i, row in enumerate(data):
        source = row.get("source", "")
        content = row.get("content", "").strip()
        if not content:
            continue
        try:
            emb = embedder.embed_query(content)
            emb_str = "[" + ",".join(str(x) for x in emb) + "]"
            client.table("knowledge_chunks").insert({
                "source": source or None,
                "content": content,
                "embedding": emb_str,
            }).execute()
            print("Inserted:", source or "(no source)", "-", content[:60] + "..." if len(content) > 60 else content)
        except Exception as e:
            print("Error at item", i, e)
    print("Done.")


if __name__ == "__main__":
    main()
