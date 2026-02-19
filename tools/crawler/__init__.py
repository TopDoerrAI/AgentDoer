"""
Crawler: seed list → fetch (robots.txt, rate limit) → parse → link extract → queue → repeat.
Limits: max_pages, max_depth, timeout. Exposed as crawl_website tool for the agent.
"""
from langchain.tools import tool

from app.core.config import get_settings
from tools.crawler.crawl import CrawlResult, run_crawl


def _format_crawl_results(results: list[CrawlResult], max_snippets: int = 20) -> str:
    lines = [f"Crawled {len(results)} page(s)."]
    for i, r in enumerate(results[:max_snippets]):
        lines.append(f"\n[{i+1}] {r.url} (depth={r.depth}, status={r.status_code})")
        if r.title:
            lines.append(f"  Title: {r.title}")
        if r.snippet:
            lines.append(f"  Snippet: {r.snippet[:400]}")
    if len(results) > max_snippets:
        lines.append(f"\n... and {len(results) - max_snippets} more.")
    return "\n".join(lines)


@tool
def crawl_website(
    seed_urls: str,
    max_pages: int = 0,
    max_depth: int = 0,
    same_origin_only: bool = True,
) -> str:
    """
    Crawl one or more websites starting from seed URLs. Use when the user wants to discover or index
    multiple pages from a site (e.g. 'crawl example.com', 'index all docs from this URL').
    Pass seed_urls as a newline- or comma-separated list of full URLs (e.g. https://example.com).
    Respects robots.txt and rate limits. By default only follows links on the same site (same domain).
    Returns a summary of crawled pages (title and snippet). Use get_page or open_url for a single page.
    """
    urls = [u.strip() for u in seed_urls.replace(",", "\n").split() if u.strip()]
    if not urls:
        return "No valid seed URLs provided. Example: https://example.com"
    settings = get_settings()
    mp = max_pages if max_pages > 0 else settings.crawl_max_pages
    md = max_depth if max_depth > 0 else settings.crawl_max_depth
    try:
        results = run_crawl(
            urls,
            max_pages=mp,
            max_depth=md,
            same_origin_only=same_origin_only,
            allowed_origins=None,
        )
        return _format_crawl_results(results)
    except Exception as e:
        return f"Crawl failed: {e}"


__all__ = ["crawl_website", "run_crawl", "CrawlResult"]
