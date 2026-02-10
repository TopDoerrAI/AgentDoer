"""
Browser session tools: small, composable actions.
Use open_url first, then mix read + interaction + form + wait + scroll as needed.
"""
from langchain.tools import tool

from tools.browser.session import send


# --- Navigation ---

@tool
def open_url(url: str) -> str:
    """Open a URL in the browser. Call this first. Use full URL (e.g. https://example.com)."""
    return send("goto", {"url": url})


@tool
def go_back() -> str:
    """Go back to the previous page in the browser history."""
    return send("go_back", {})


@tool
def go_forward() -> str:
    """Go forward in the browser history."""
    return send("go_forward", {})


@tool
def reload_page() -> str:
    """Reload the current page."""
    return send("reload", {})


# --- Read ---

@tool
def page_content() -> str:
    """Get the visible text content (title + body) of the current page. Use after open_url or after any action to see the result."""
    return send("content", {})


@tool
def get_title() -> str:
    """Get the current page title."""
    return send("get_title", {})


@tool
def get_url() -> str:
    """Get the current page URL."""
    return send("get_url", {})


@tool
def get_element_text(selector: str) -> str:
    """Get the visible text of one element. CSS selector, e.g. 'h1', '.message', '#result'."""
    return send("get_element_text", {"selector": selector})


@tool
def get_input_value(selector: str) -> str:
    """Get the current value of an input or textarea. CSS selector."""
    return send("get_input_value", {"selector": selector})


@tool
def selector_hints() -> str:
    """List inputs and buttons on the page with selectors (id, name, type). Use to find the right selectors for fill and click."""
    return send("selector_hints", {})


# --- Click & keyboard ---

@tool
def click(selector: str) -> str:
    """Click an element. CSS selector, e.g. 'button[type=submit]', '#login', 'a.next'."""
    return send("click", {"selector": selector})


@tool
def double_click(selector: str) -> str:
    """Double-click an element. CSS selector."""
    return send("double_click", {"selector": selector})


@tool
def right_click(selector: str) -> str:
    """Right-click an element. CSS selector."""
    return send("right_click", {"selector": selector})


@tool
def hover(selector: str) -> str:
    """Hover over an element (e.g. to open a dropdown). CSS selector."""
    return send("hover", {"selector": selector})


@tool
def fill(selector: str, value: str) -> str:
    """Fill a text input or textarea. CSS selector and the value to type."""
    return send("fill", {"selector": selector, "value": value})


@tool
def type_text(selector: str, value: str) -> str:
    """Type into an element character by character (use when fill doesn't trigger key events). CSS selector and text."""
    return send("type_text", {"selector": selector, "value": value})


@tool
def press_enter(selector: str) -> str:
    """Press Enter on an element (e.g. password field to submit login). CSS selector."""
    return send("press_enter", {"selector": selector})


@tool
def login(
    username_selector: str,
    password_selector: str,
    username_value: str,
    password_value: str,
    url: str = "",
    submit_selector: str = "",
) -> str:
    """Run the full login flow: open url (if given), wait for form, enter username and password, then submit. Use selector_hints first to find the right selectors (e.g. input[name=user], input[type=password], button[type=submit]). If submit_selector is empty, submits by pressing Enter on the password field. Returns page content after login so you can verify success."""
    steps = []
    if url and url.strip():
        r = send("goto", {"url": url.strip()})
        steps.append(r)
        if r.startswith("Error:"):
            return "\n".join(steps)
    r = send("wait_for_selector", {"selector": username_selector, "timeout": 10000})
    steps.append(f"Username field: {r}")
    if r.startswith("Error:"):
        return "\n".join(steps)
    r = send("fill", {"selector": username_selector, "value": username_value})
    steps.append(r)
    if r.startswith("Error:"):
        return "\n".join(steps)
    r = send("type_text", {"selector": password_selector, "value": password_value})
    steps.append(r)
    if r.startswith("Error:"):
        return "\n".join(steps)
    if submit_selector and submit_selector.strip():
        r = send("click", {"selector": submit_selector.strip()})
    else:
        r = send("press_enter", {"selector": password_selector})
    steps.append(r)
    if r.startswith("Error:"):
        return "\n".join(steps)
    send("wait", {"seconds": 4})
    content = send("content", {})
    steps.append("--- Page after login ---")
    steps.append(content[:3000] if len(content) > 3000 else content)
    return "\n".join(steps)


@tool
def press_key(key: str, selector: str = "") -> str:
    """Press a key. Key names: Enter, Tab, Escape, Backspace, ArrowDown, etc. Optionally give a selector to focus first."""
    return send("press_key", {"key": key, "selector": selector or None})


# --- Forms ---

@tool
def check(selector: str) -> str:
    """Check a checkbox or radio. CSS selector."""
    return send("check", {"selector": selector})


@tool
def uncheck(selector: str) -> str:
    """Uncheck a checkbox. CSS selector."""
    return send("uncheck", {"selector": selector})


@tool
def select_option(selector: str, value: str = "", label: str = "") -> str:
    """Select an option in a dropdown. CSS selector for the select element; pass value='...' or label='...' (one of them)."""
    payload = {"selector": selector}
    if value:
        payload["value"] = value
    if label:
        payload["label"] = label
    return send("select_option", payload)


# --- Wait ---

@tool
def wait(seconds: float = 1.0) -> str:
    """Wait a number of seconds (e.g. for a redirect or animation). Default 1."""
    return send("wait", {"seconds": seconds})


@tool
def wait_for_selector(selector: str, state: str = "visible", timeout: int = 10000) -> str:
    """Wait until an element appears. CSS selector; state: visible, attached, hidden. Timeout in ms."""
    return send("wait_for_selector", {"selector": selector, "state": state, "timeout": timeout})


# --- Scroll ---

@tool
def scroll(delta_y: int = 300, selector: str = "") -> str:
    """Scroll the page or an element. delta_y: pixels (positive=down). Optionally selector for an element to scroll."""
    return send("scroll", {"delta_y": delta_y, "selector": selector or None})


@tool
def scroll_to_bottom() -> str:
    """Scroll the page to the bottom."""
    return send("scroll_to_bottom", {})


@tool
def scroll_to_top() -> str:
    """Scroll the page to the top."""
    return send("scroll_to_top", {})


# --- Screenshot ---

@tool
def screenshot(full_page: bool = False, path: str = "") -> str:
    """Take a screenshot. Returns base64 image data, or pass path to save to file. full_page=True for full page."""
    return send("screenshot", {"full_page": full_page, "path": path or None})
