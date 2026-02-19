"""URL normalization and deduplication for the crawl queue."""
from urllib.parse import urljoin, urlparse, urlunparse


def normalize_url(url: str, base: str | None = None) -> str | None:
    """
    Normalize URL: absolute form, strip fragment, lowercase scheme/host, default path /.
    Returns None if scheme is not http/https.
    """
    if base:
        url = urljoin(base, url)
    try:
        p = urlparse(url)
    except Exception:
        return None
    if p.scheme not in ("http", "https"):
        return None
    # Lowercase host
    netloc = (p.netloc or "").lower()
    path = p.path.rstrip("/") or "/"
    # Remove fragment
    normalized = urlunparse((p.scheme.lower(), netloc, path, p.params, p.query, ""))
    return normalized


def same_origin(url1: str, url2: str) -> bool:
    """True if both URLs have the same scheme and netloc."""
    p1, p2 = urlparse(url1), urlparse(url2)
    return (p1.scheme or "").lower() == (p2.scheme or "").lower() and (p1.netloc or "").lower() == (p2.netloc or "").lower()


def allow_domain(url: str, allowed_origins: set[str] | None) -> bool:
    """
    If allowed_origins is None, allow all. Else allow only if url's origin is in the set.
    allowed_origins contains e.g. {"https://example.com", "https://docs.github.com"}.
    """
    if not allowed_origins:
        return True
    p = urlparse(url)
    origin = f"{(p.scheme or 'https').lower()}://{(p.netloc or '').lower()}"
    return origin in allowed_origins
