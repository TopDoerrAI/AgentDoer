#!/usr/bin/env python3
"""
Launch the browser (same stealth setup as the agent), let you log in manually,
then save cookies/localStorage to state.json for reuse.

Usage:
  python scripts/save_browser_state.py
  python scripts/save_browser_state.py https://accounts.google.com
  python scripts/save_browser_state.py https://accounts.google.com ./my-state.json

Then set BROWSER_STORAGE_STATE=./state.json (or your output path) in .env.
"""
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from dotenv import load_dotenv
load_dotenv(_root / ".env")

from playwright.sync_api import sync_playwright

from tools.browser.session import (
    DEFAULT_VIEWPORT,
    REAL_USER_AGENT,
    STEALTH_INIT_SCRIPT,
    STEALTH_LAUNCH_ARGS,
)


def main() -> None:
    start_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.google.com"
    out_path = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else _root / "state.json"

    print("Launching browser (non-headless, same stealth as agent)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=STEALTH_LAUNCH_ARGS,
        )
        context_options = {"viewport": DEFAULT_VIEWPORT}
        if REAL_USER_AGENT:
            context_options["user_agent"] = REAL_USER_AGENT
        context = browser.new_context(**context_options)
        context.add_init_script(STEALTH_INIT_SCRIPT)
        page = context.new_page()
        page.goto(start_url, timeout=60000)
        print()
        print("  Log in (or navigate) in the browser.")
        print("  When done, press Enter here to save state and exit.")
        print()
        input()
        context.storage_state(path=str(out_path))
        browser.close()
    print(f"Saved to {out_path}")
    print("Set in .env: BROWSER_STORAGE_STATE=" + str(out_path))


if __name__ == "__main__":
    main()
