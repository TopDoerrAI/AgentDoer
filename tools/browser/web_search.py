import warnings

from langchain.tools import tool

# Prefer ddgs (new package); fall back to duckduckgo_search and silence rename warning
warnings.filterwarnings("ignore", message=".*renamed to `ddgs`.*", module="duckduckgo_search")
try:
    from ddgs import DDGS
    try:
        from ddgs.exceptions import DuckDuckGoSearchException
    except ImportError:
        DuckDuckGoSearchException = Exception
except ImportError:
    from duckduckgo_search import DDGS
    from duckduckgo_search.exceptions import DuckDuckGoSearchException


@tool
def web_search(query: str) -> str:
    """Search the web for current information."""
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=5)
    except DuckDuckGoSearchException as e:
        return f"Search failed: {e}"
    except Exception as e:
        return f"Search error: {type(e).__name__}: {e}"
    if not results:
        return "No results found."
    return "\n".join(
        f"{r.get('title', '')}: {r.get('body', '')}" for r in results
    )

