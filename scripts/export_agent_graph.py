#!/usr/bin/env python3
"""
Export the LangGraph agent as Mermaid source and PNG.
Usage (from repo root):
  python scripts/export_agent_graph.py [--output-dir DIR] [--png-only | --mermaid-only]
Output: agent_graph.mmd and agent_graph.png (default: current directory).
PNG is rendered via Mermaid.ink API (network required) or falls back to saving only .mmd.
"""
import argparse
import sys
from pathlib import Path

# Repo root and load .env before any app/tools imports
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_env = ROOT / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(_env, override=True)

from app.core.agent import get_agent


def main() -> None:
    ap = argparse.ArgumentParser(description="Export agent graph to Mermaid and PNG")
    ap.add_argument("--output-dir", "-o", type=Path, default=Path.cwd(), help="Directory for output files")
    ap.add_argument("--mermaid-only", action="store_true", help="Only write .mmd file")
    ap.add_argument("--png-only", action="store_true", help="Only write .png (still needs mermaid internally)")
    args = ap.parse_args()
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    mmd_path = out_dir / "agent_graph.mmd"
    png_path = out_dir / "agent_graph.png"

    # Build agent and get compiled graph
    compiled = get_agent()
    g = compiled.get_graph()

    # Mermaid source (always available)
    mermaid_syntax = g.draw_mermaid()
    if not args.png_only:
        mmd_path.write_text(mermaid_syntax, encoding="utf-8")
        print(f"Wrote {mmd_path}")

    # PNG: draw_mermaid_png() uses Mermaid.ink API by default (needs network)
    if not args.mermaid_only:
        try:
            # Prefer saving directly if supported; else write returned bytes
            try:
                png_bytes = g.draw_mermaid_png(output_file_path=str(png_path))
            except TypeError:
                png_bytes = g.draw_mermaid_png()
            if png_bytes:
                png_path.write_bytes(png_bytes)
            print(f"Wrote {png_path}")
        except Exception as e:
            print(f"PNG export failed: {e}", file=sys.stderr)
            print("Paste agent_graph.mmd into https://mermaid.live to get a PNG.", file=sys.stderr)
            if args.png_only:
                sys.exit(1)


if __name__ == "__main__":
    main()
