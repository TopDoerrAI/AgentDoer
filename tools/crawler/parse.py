"""Parse HTML: extract title, description, main text, and links."""
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def parse_html(html: str, base_url: str) -> dict:
    """
    Parse HTML and return {
        "title": str,
        "description": str,
        "text": str (main content, cleaned),
        "links": list[str] (absolute URLs from <a href>,
    }.
    """
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    description = ""
    meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if meta and meta.get("content"):
        description = meta["content"].strip()
    # Remove script/style
    for tag in soup(["script", "style"]):
        tag.decompose()
    # Prefer main/article, else body
    body = soup.find("main") or soup.find("article") or soup.find("body") or soup
    text = body.get_text(separator=" ", strip=True) if body else ""
    text = re.sub(r"\s+", " ", text)[:50000]
    # Links: all a[href] that look like same-doc or HTTP(S)
    links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        full = urljoin(base_url, href)
        p = urlparse(full)
        if p.scheme not in ("http", "https"):
            continue
        if full not in seen:
            seen.add(full)
            links.append(full)
    return {"title": title, "description": description, "text": text, "links": links}
