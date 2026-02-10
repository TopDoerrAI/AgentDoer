"""One-off browser tool: open a URL and return content without using the session (no click/fill)."""
import os
import random
import time

from langchain.tools import tool
from playwright.sync_api import sync_playwright, Error as PlaywrightError

from tools.browser.session import (
    BROWSER_STORAGE_STATE,
    BROWSER_USER_DATA_DIR,
    DEFAULT_VIEWPORT,
    HEADLESS,
    REAL_USER_AGENT,
    STEALTH_INIT_SCRIPT,
    STEALTH_LAUNCH_ARGS,
    _extract_page_content,
)


def _human_delay(lo_sec: float, hi_sec: float) -> None:
    time.sleep(lo_sec + random.random() * (hi_sec - lo_sec))


@tool
def get_page(url: str) -> str:
    """Open a URL and return the page content (title + visible text). Use for a quick read when you don't need to click or fill. Full URL required."""
    try:
        with sync_playwright() as p:
            launch_options = {"headless": HEADLESS, "args": STEALTH_LAUNCH_ARGS}
            if BROWSER_USER_DATA_DIR:
                launch_options["user_data_dir"] = BROWSER_USER_DATA_DIR
            browser = p.chromium.launch(**launch_options)
            context_options = {"viewport": DEFAULT_VIEWPORT}
            if REAL_USER_AGENT:
                context_options["user_agent"] = REAL_USER_AGENT
            if BROWSER_STORAGE_STATE and os.path.isfile(BROWSER_STORAGE_STATE):
                context_options["storage_state"] = BROWSER_STORAGE_STATE
            context = browser.new_context(**context_options)
            context.add_init_script(STEALTH_INIT_SCRIPT)
            page = context.new_page()
            page.goto(url, timeout=30000)
            _human_delay(0.5, 1.5)
            page.mouse.wheel(0, random.randint(200, 500))
            _human_delay(0.5, 1.0)
            content = _extract_page_content(page)
            browser.close()
        return content
    except PlaywrightError as e:
        msg = str(e).split("\n")[0] if "\n" in str(e) else str(e)
        if "ERR_NAME_NOT_RESOLVED" in msg or "net::" in msg:
            return f"Could not load {url}: address could not be resolved (DNS error). Details: {msg}"
        if "timeout" in msg.lower():
            return f"Could not load {url}: page took too long to load. Details: {msg}"
        return f"Could not load {url}: {msg}"
    except Exception as e:
        return f"Browser error loading {url}: {type(e).__name__}: {e}"
