"""Fetch a URL via HTTP. Polite: fixed User-Agent, timeout, only HTML when needed."""
import logging
from urllib.parse import urlparse

import requests

from tools.crawler.robots import CRAWLER_USER_AGENT, can_fetch

logger = logging.getLogger(__name__)


def fetch(
    url: str,
    *,
    timeout: int = 15,
    check_robots: bool = True,
    user_agent: str = CRAWLER_USER_AGENT,
) -> tuple[int, str, str]:
    """
    GET the URL. Returns (status_code, content_type, body).
    If check_robots is True and robots.txt disallows, returns (0, "", "").
    """
    if check_robots and not can_fetch(url, user_agent=user_agent, timeout=min(10, timeout)):
        logger.info("Robots.txt disallows: %s", url)
        return (0, "", "")
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"},
            allow_redirects=True,
        )
        ct = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if "text/html" not in ct and "application/xhtml" not in ct:
            return (resp.status_code, ct, "")
        return (resp.status_code, ct, resp.text)
    except requests.RequestException as e:
        logger.warning("Fetch failed %s: %s", url, e)
        raise
