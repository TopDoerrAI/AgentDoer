"""
Browser session: single tab in a dedicated thread.
All session tools send commands here; worker runs Playwright in one thread (thread-safe).
Uses persistent profile/storage state, stealth launch, and human-like timing when configured.
"""
import os
import queue
import random
import threading
import time
import uuid

from playwright.sync_api import sync_playwright, Error as PlaywrightError

# Set BROWSER_HEADLESS=0 in .env to show the browser window
HEADLESS = os.getenv("BROWSER_HEADLESS", "1").strip().lower() not in ("0", "false", "no")

# Persistent session: reuse cookies/localStorage (log in once manually, then reuse)
# Path to state.json saved after manual login, or directory for Chrome user data
BROWSER_STORAGE_STATE = os.getenv("BROWSER_STORAGE_STATE", "").strip() or None
BROWSER_USER_DATA_DIR = os.getenv("BROWSER_USER_DATA_DIR", "").strip() or None
# Optional: real browser user agent (leave empty to use Playwright default)
REAL_USER_AGENT = os.getenv("REAL_USER_AGENT", "").strip() or None

# Stealth: hide automation signals
STEALTH_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
]
STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => false });
"""
DEFAULT_VIEWPORT = {"width": 1280, "height": 800}


def _human_delay(lo_sec: float, hi_sec: float) -> None:
    """Wait a random duration between lo_sec and hi_sec (human-like)."""
    time.sleep(lo_sec + random.random() * (hi_sec - lo_sec))

_command_queue: queue.Queue = queue.Queue()
_results: dict = {}
_events: dict = {}
_lock = threading.Lock()
_worker: threading.Thread | None = None


def _extract_page_content(page) -> str:
    """Extract title and visible text from the page."""
    title = page.title()
    script = (
        "() => { const body = document.body; if (!body) return '';"
        " const clone = body.cloneNode(true);"
        " for (const el of clone.querySelectorAll('script, style, noscript')) el.remove();"
        " return clone.innerText || clone.textContent || ''; }"
    )
    body_text = page.evaluate(script)
    if not isinstance(body_text, str):
        body_text = str(body_text) if body_text else ""
    lines = [line.strip() for line in body_text.splitlines() if line.strip()]
    text_block = "\n".join(lines)
    return "Title: " + title + "\n\nContent:\n" + text_block


def _run_action(page, action: str, args: dict) -> tuple[str, str]:
    """Execute one action; returns (status, data)."""
    try:
        if action == "goto":
            page.goto(args["url"], timeout=30000)
            # Human-like: scroll a bit and wait (2–6s total)
            _human_delay(0.5, 1.5)
            page.mouse.wheel(0, random.randint(200, 400))
            _human_delay(1.0, 2.0)
            page.mouse.wheel(0, random.randint(300, 500))
            _human_delay(0.5, 1.5)
            return ("ok", f"Opened {args['url']}")

        if action == "go_back":
            page.go_back(timeout=10000)
            return ("ok", "Went back")

        if action == "go_forward":
            page.go_forward(timeout=10000)
            return ("ok", "Went forward")

        if action == "reload":
            page.reload(timeout=30000)
            return ("ok", "Reloaded")

        if action == "content":
            return ("ok", _extract_page_content(page))

        if action == "get_title":
            return ("ok", page.title())

        if action == "get_url":
            return ("ok", page.url)

        if action == "get_element_text":
            loc = page.locator(args["selector"]).first
            loc.wait_for(state="visible", timeout=10000)
            return ("ok", loc.inner_text() or "")

        if action == "get_input_value":
            loc = page.locator(args["selector"]).first
            loc.wait_for(state="visible", timeout=10000)
            return ("ok", loc.input_value() or "")

        if action == "selector_hints":
            script = """() => {
                const inputs = Array.from(document.querySelectorAll('input:not([type=hidden]), textarea, select'))
                    .slice(0, 20).map(el => ({ tag: el.tagName, type: el.type || '', name: el.name || '', id: el.id || '', placeholder: el.placeholder || '' }));
                const buttons = Array.from(document.querySelectorAll('button, [role=button], input[type=submit]'))
                    .slice(0, 20).map(el => ({ tag: el.tagName, text: (el.innerText || el.value || '').slice(0, 50), id: el.id || '', name: el.name || '' }));
                return JSON.stringify({ inputs, buttons });
            }"""
            out = page.evaluate(script)
            return ("ok", out if isinstance(out, str) else str(out))

        if action == "click":
            loc = page.locator(args["selector"]).first
            loc.wait_for(state="visible", timeout=10000)
            loc.hover(timeout=10000, force=True)
            _human_delay(0.3, 1.2)  # 300–1200 ms before click
            try:
                box = loc.bounding_box()
                if box:
                    cx = box["x"] + box["width"] / 2
                    cy = box["y"] + box["height"] / 2
                    page.mouse.move(cx, cy, steps=random.randint(8, 16))
            except Exception:
                pass
            _human_delay(0.1, 0.3)
            loc.click(timeout=10000, force=True)
            return ("ok", f"Clicked {args['selector']}")

        if action == "double_click":
            loc = page.locator(args["selector"]).first
            loc.wait_for(state="visible", timeout=10000)
            loc.hover(timeout=10000, force=True)
            _human_delay(0.25, 0.8)
            loc.dblclick(timeout=10000, force=True)
            return ("ok", f"Double-clicked {args['selector']}")

        if action == "right_click":
            loc = page.locator(args["selector"]).first
            loc.wait_for(state="visible", timeout=10000)
            loc.hover(timeout=10000, force=True)
            _human_delay(0.25, 0.8)
            loc.click(button="right", timeout=10000, force=True)
            return ("ok", f"Right-clicked {args['selector']}")

        if action == "hover":
            loc = page.locator(args["selector"]).first
            loc.wait_for(state="visible", timeout=10000)
            loc.hover(timeout=10000, force=True)
            return ("ok", f"Hovered {args['selector']}")

        if action == "fill":
            loc = page.locator(args["selector"]).first
            loc.wait_for(state="visible", timeout=10000)
            loc.hover(timeout=10000, force=True)
            _human_delay(0.15, 0.5)
            loc.fill(args["value"], timeout=5000)
            _human_delay(0.2, 0.5)
            return ("ok", f"Filled {args['selector']}")

        if action == "type_text":
            loc = page.locator(args["selector"]).first
            loc.wait_for(state="visible", timeout=10000)
            loc.fill("", timeout=2000)
            # 50–150 ms per character (human-like)
            delay_ms = random.randint(50, 150)
            loc.type(args["value"], delay=delay_ms, timeout=10000)
            return ("ok", f"Typed into {args['selector']}")

        if action == "press_enter":
            loc = page.locator(args["selector"]).first
            loc.wait_for(state="visible", timeout=10000)
            loc.press("Enter")
            time.sleep(0.5)
            return ("ok", "Pressed Enter")

        if action == "press_key":
            key = args.get("key", "Enter")
            if args.get("selector"):
                loc = page.locator(args["selector"]).first
                loc.wait_for(state="visible", timeout=10000)
                loc.press(key)
            else:
                page.keyboard.press(key)
            return ("ok", f"Pressed {key}")

        if action == "check":
            loc = page.locator(args["selector"]).first
            loc.wait_for(state="visible", timeout=10000)
            loc.check(timeout=5000, force=True)
            return ("ok", f"Checked {args['selector']}")

        if action == "uncheck":
            loc = page.locator(args["selector"]).first
            loc.wait_for(state="visible", timeout=10000)
            loc.uncheck(timeout=5000, force=True)
            return ("ok", f"Unchecked {args['selector']}")

        if action == "select_option":
            loc = page.locator(args["selector"]).first
            loc.wait_for(state="visible", timeout=10000)
            value = args.get("value")
            label = args.get("label")
            if value:
                loc.select_option(value=value, timeout=5000)
            elif label:
                loc.select_option(label=label, timeout=5000)
            else:
                return ("error", "Provide value or label for select_option")
            return ("ok", f"Selected option in {args['selector']}")

        if action == "wait":
            time.sleep(float(args.get("seconds", 1)))
            return ("ok", f"Waited {args.get('seconds', 1)}s")

        if action == "wait_for_selector":
            page.wait_for_selector(args["selector"], state=args.get("state", "visible"), timeout=int(args.get("timeout", 10000)))
            return ("ok", f"Found {args['selector']}")

        if action == "scroll":
            selector = args.get("selector")
            delta = args.get("delta_y", 300)
            if selector:
                loc = page.locator(selector).first
                loc.evaluate(f"el => el.scrollBy(0, {delta})")
                _human_delay(0.3, 1.0)
                return ("ok", f"Scrolled element {selector}")
            page.mouse.wheel(0, delta)
            _human_delay(0.5, 1.5)
            return ("ok", f"Scrolled page by {delta}")

        if action == "scroll_to_bottom":
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            return ("ok", "Scrolled to bottom")

        if action == "scroll_to_top":
            page.evaluate("window.scrollTo(0, 0)")
            return ("ok", "Scrolled to top")

        if action == "screenshot":
            path = args.get("path")
            if path:
                page.screenshot(path=path, full_page=args.get("full_page", False))
                return ("ok", f"Saved screenshot to {path}")
            buf = page.screenshot(full_page=args.get("full_page", False), type="png")
            import base64
            return ("ok", "data:image/png;base64," + base64.b64encode(buf).decode())

        return ("error", f"Unknown action: {action}")
    except PlaywrightError as e:
        msg = str(e).split("\n")[0] if "\n" in str(e) else str(e)
        return ("error", msg)
    except Exception as e:
        return ("error", f"{type(e).__name__}: {e}")


def _browser_worker() -> None:
    with sync_playwright() as p:
        launch_options: dict = {
            "headless": HEADLESS,
            "args": STEALTH_LAUNCH_ARGS,
        }
        if BROWSER_USER_DATA_DIR:
            launch_options["user_data_dir"] = BROWSER_USER_DATA_DIR
        browser = p.chromium.launch(**launch_options)

        context_options: dict = {"viewport": DEFAULT_VIEWPORT}
        if REAL_USER_AGENT:
            context_options["user_agent"] = REAL_USER_AGENT
        if BROWSER_STORAGE_STATE and os.path.isfile(BROWSER_STORAGE_STATE):
            context_options["storage_state"] = BROWSER_STORAGE_STATE
        context = browser.new_context(**context_options)
        context.add_init_script(STEALTH_INIT_SCRIPT)
        page = context.new_page()
        page.set_default_timeout(15000)
        while True:
            try:
                cmd = _command_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if cmd is None:
                break
            req_id, action, args = cmd
            status, data = _run_action(page, action, args)
            with _lock:
                _results[req_id] = (status, data)
            if req_id in _events:
                _events[req_id].set()


def _ensure_worker() -> None:
    global _worker
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=_browser_worker, daemon=True)
        _worker.start()


def send(action: str, args: dict, timeout: float = 45.0) -> str:
    """Send a command to the session browser and return the result string."""
    _ensure_worker()
    req_id = str(uuid.uuid4())
    _events[req_id] = threading.Event()
    _command_queue.put((req_id, action, args))
    if not _events[req_id].wait(timeout=timeout):
        with _lock:
            _results.pop(req_id, None)
        _events.pop(req_id, None)
        return "Error: Browser action timed out."
    with _lock:
        status, data = _results.pop(req_id, ("error", "No result"))
    _events.pop(req_id, None)
    return data if status == "ok" else f"Error: {data}"
