"""
Browser tools: session-based actions + one-off get_page.

Session (one shared tab): use open_url first, then any combination of:
  Navigation: open_url, go_back, go_forward, reload_page
  Read: page_content, get_title, get_url, get_element_text, get_input_value, selector_hints
  Click/keyboard: click, double_click, right_click, hover, fill, type_text, press_enter, press_key
  Forms: check, uncheck, select_option
  Wait: wait, wait_for_selector
  Scroll: scroll, scroll_to_bottom, scroll_to_top
  Screenshot: screenshot

One-off (no session): get_page
"""
from tools.browser.actions import (
    open_url,
    go_back,
    go_forward,
    reload_page,
    page_content,
    get_title,
    get_url,
    get_element_text,
    get_input_value,
    selector_hints,
    click,
    double_click,
    right_click,
    hover,
    fill,
    type_text,
    press_enter,
    press_key,
    check,
    uncheck,
    select_option,
    wait,
    wait_for_selector,
    scroll,
    scroll_to_bottom,
    scroll_to_top,
    screenshot,
)
from tools.browser.one_off import get_page

# Flat list for agent registration
BROWSER_SESSION_TOOLS = [
    open_url,
    go_back,
    go_forward,
    reload_page,
    page_content,
    get_title,
    get_url,
    get_element_text,
    get_input_value,
    selector_hints,
    click,
    double_click,
    right_click,
    hover,
    fill,
    type_text,
    press_enter,
    press_key,
    check,
    uncheck,
    select_option,
    wait,
    wait_for_selector,
    scroll,
    scroll_to_bottom,
    scroll_to_top,
    screenshot,
]

BROWSER_ONE_OFF_TOOLS = [get_page]

__all__ = [
    "get_page",
    "open_url",
    "go_back",
    "go_forward",
    "reload_page",
    "page_content",
    "get_title",
    "get_url",
    "get_element_text",
    "get_input_value",
    "selector_hints",
    "click",
    "double_click",
    "right_click",
    "hover",
    "fill",
    "type_text",
    "press_enter",
    "press_key",
    "check",
    "uncheck",
    "select_option",
    "wait",
    "wait_for_selector",
    "scroll",
    "scroll_to_bottom",
    "scroll_to_top",
    "screenshot",
    "BROWSER_SESSION_TOOLS",
    "BROWSER_ONE_OFF_TOOLS",
]
