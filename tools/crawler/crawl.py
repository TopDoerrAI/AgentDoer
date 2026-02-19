"""
Crawl loop: seed URLs → queue → fetch (respect robots) → parse → extract links → enqueue.
Limits: max_pages, max_depth, timeout. Policy: optional same-origin or allowed domains.
"""
import logging
import time
from collections import deque
from dataclasses import dataclass
from urllib.parse import urlparse

from app.core.config import get_settings
from tools.crawler.fetch import fetch
from tools.crawler.parse import parse_html
from tools.crawler.url_utils import allow_domain, normalize_url

logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    url: str
    depth: int
    title: str
    description: str
    snippet: str  # first ~300 chars of text
    status_code: int
    links_found: int = 0


def _snippet(text: str, max_len: int = 300) -> str:
    t = (text or "").strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 3].rsplit(maxsplit=1)[0] + "..."


def run_crawl(
    seed_urls: list[str],
    *,
    max_pages: int | None = None,
    max_depth: int | None = None,
    timeout_seconds: int | None = None,
    same_origin_only: bool = True,
    allowed_origins: set[str] | None = None,
    request_delay: float | None = None,
) -> list[CrawlResult]:
    """
    Crawl from seed URLs. BFS by depth. Respects robots.txt, rate limit (delay), and limits.
    - same_origin_only: if True, only follow links that share origin with their referring page (and seeds).
    - allowed_origins: if set, only crawl URLs whose origin is in this set (overrides same_origin for cross-origin).
    Returns list of CrawlResult (url, depth, title, description, snippet, status_code).
    """
    settings = get_settings()
    max_pages = max_pages if max_pages is not None else settings.crawl_max_pages
    max_depth = max_depth if max_depth is not None else settings.crawl_max_depth
    timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.crawl_timeout_seconds
    request_delay = request_delay if request_delay is not None else settings.crawl_request_delay_seconds

    # Normalize seeds and build initial queue: (url, depth)
    queue: deque[tuple[str, int]] = deque()
    seen: set[str] = set()
    seed_origins: set[str] = set()
    for u in seed_urls:
        n = normalize_url(u)
        if n and n not in seen:
            seen.add(n)
            queue.append((n, 0))
            p = urlparse(n)
            seed_origins.add(f"{p.scheme}://{p.netloc}".lower())

    results: list[CrawlResult] = []
    start = time.monotonic()
    fetch_timeout = min(15, timeout_seconds // 3)

    while queue and len(results) < max_pages and (time.monotonic() - start) < timeout_seconds:
        url, depth = queue.popleft()
        if depth > max_depth:
            continue
        # Policy: only crawl allowed origins (when same_origin_only, that's seed_origins)
        effective_allowed = seed_origins if same_origin_only else allowed_origins
        if not allow_domain(url, effective_allowed):
            continue

        if request_delay > 0:
            time.sleep(request_delay)

        try:
            status, _ct, body = fetch(url, timeout=fetch_timeout, check_robots=True)
        except Exception as e:
            logger.warning("Crawl fetch failed %s: %s", url, e)
            continue

        if status != 200 or not body:
            results.append(CrawlResult(url=url, depth=depth, title="", description="", snippet=f"[HTTP {status}]", status_code=status))
            continue

        try:
            parsed = parse_html(body, url)
        except Exception as e:
            logger.warning("Crawl parse failed %s: %s", url, e)
            results.append(CrawlResult(url=url, depth=depth, title="", description="", snippet=str(e)[:200], status_code=status))
            continue

        title = parsed.get("title") or ""
        desc = parsed.get("description") or ""
        text = parsed.get("text") or ""
        links = parsed.get("links") or []
        results.append(CrawlResult(
            url=url,
            depth=depth,
            title=title,
            description=desc,
            snippet=_snippet(desc or text),
            status_code=status,
            links_found=len(links),
        ))

        # Enqueue new URLs (depth + 1)
        for link in links:
            n = normalize_url(link, url)
            if not n or n in seen:
                continue
            if not allow_domain(n, effective_allowed):
                continue
            seen.add(n)
            queue.append((n, depth + 1))

    return results
