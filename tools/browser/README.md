# Browser tools

Session-based tools share one browser tab (one thread). Use **open_url** first, then any combination of small actions.

## Anti-detection & persistent session

To make the agent look like a real user and reuse logins:

1. **Persistent profile / storage state**  
   Log in once manually, then reuse cookies and localStorage:
   - **Storage state**: Run `python scripts/save_browser_state.py [start_url]` to open the browser, log in manually, then press Enter to save `state.json`. Set `BROWSER_STORAGE_STATE=./state.json` in `.env`.
   - **Chrome user data dir**: Set `BROWSER_USER_DATA_DIR=./browser-profile` to reuse a full Chrome profile (cookies, cache, extensions).

2. **Non-headless**  
   Set `BROWSER_HEADLESS=0` to show the browser. The launch uses `--disable-blink-features=AutomationControlled` and overrides `navigator.webdriver` so the session looks less like automation.

3. **Human-like timing**  
   Clicks use hover → 300–1200 ms delay → optional mouse move with steps → click. Typing uses 50–150 ms per character. After opening a URL, the session scrolls a bit and waits 2–6 seconds. Scroll actions add short random delays.

4. **Optional user agent**  
   Set `REAL_USER_AGENT` in `.env` to a real browser UA string if you want to match a specific browser.

## One-off (no session)
| Tool | Description |
|------|-------------|
| `get_page(url)` | Open URL, return title + visible text, close. Use for quick reads. |

## Session – Navigation
| Tool | Description |
|------|-------------|
| `open_url(url)` | Open a URL. Call first. |
| `go_back()` | Back in history. |
| `go_forward()` | Forward in history. |
| `reload_page()` | Reload current page. |

## Session – Read
| Tool | Description |
|------|-------------|
| `page_content()` | Full page text (title + body). |
| `get_title()` | Current page title. |
| `get_url()` | Current URL. |
| `get_element_text(selector)` | Text of one element. |
| `get_input_value(selector)` | Value of input/textarea. |
| `selector_hints()` | List inputs and buttons with selectors (id, name, type). |

## Session – Click & keyboard
| Tool | Description |
|------|-------------|
| `click(selector)` | Click element. |
| `double_click(selector)` | Double-click. |
| `right_click(selector)` | Right-click. |
| `hover(selector)` | Hover (e.g. open dropdown). |
| `fill(selector, value)` | Fill input/textarea. |
| `type_text(selector, value)` | Type char-by-char (triggers key events). |
| `press_enter(selector)` | Press Enter on element (submit forms). |
| `press_key(key, selector?)` | Press key (Enter, Tab, Escape, etc.). |

## Session – Forms
| Tool | Description |
|------|-------------|
| `check(selector)` | Check checkbox/radio. |
| `uncheck(selector)` | Uncheck checkbox. |
| `select_option(selector, value?, label?)` | Select dropdown option. |

## Session – Wait & scroll
| Tool | Description |
|------|-------------|
| `wait(seconds)` | Pause (e.g. for redirect). |
| `wait_for_selector(selector, state?, timeout?)` | Wait until element visible. |
| `scroll(delta_y, selector?)` | Scroll page or element. |
| `scroll_to_bottom()` | Scroll to bottom. |
| `scroll_to_top()` | Scroll to top. |

## Session – Screenshot
| Tool | Description |
|------|-------------|
| `screenshot(full_page?, path?)` | PNG as base64 or save to path. |

All selectors are CSS (e.g. `#id`, `.class`, `button[type=submit]`, `input[name=email]`). Use **selector_hints** to discover selectors on the current page.
