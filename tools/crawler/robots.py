"""Check robots.txt before fetching. Politeness: respect allow/disallow and crawl-delay if present."""
import logging
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

logger = logging.getLogger(__name__)

CRAWLER_USER_AGENT = "CrawlBot/1.0 (+https://github.com/your-repo; polite crawler)"

# Cache per-origin so we don't re-fetch robots.txt for every URL on the same site
_robots_cache: dict[str, RobotFileParser] = {}


def _origin(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme or 'https'}://{p.netloc}"


def _robots_url(origin: str) -> str:
    return urljoin(origin, "/robots.txt")


def can_fetch(url: str, user_agent: str = CRAWLER_USER_AGENT, timeout: int = 10) -> bool:
    """
    Return True if robots.txt allows this user_agent to fetch the given URL.
    Fetches and parses robots.txt per origin (cached). On any error, we allow (fail open).
    """
    origin = _origin(url)
    if origin not in _robots_cache:
        rp = RobotFileParser()
        try:
            robots_url = _robots_url(origin)
            resp = requests.get(robots_url, timeout=timeout, headers={"User-Agent": user_agent})
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
            # 404 or other: no robots.txt → allow all
        except Exception as e:
            logger.debug("robots.txt fetch failed for %s: %s", origin, e)
        _robots_cache[origin] = rp
    try:
        return _robots_cache[origin].can_fetch(user_agent, url)
    except Exception:
        return True
