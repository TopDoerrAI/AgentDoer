"""Extra agent tools: recall_memory, store_memory, search_knowledge_base, run_python, get_user_context."""
import logging
import re
import subprocess
import sys

from langchain.tools import tool
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

from app.core.config import get_settings
from app.core.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

# Lazy embedding model (needs NVIDIA_API_KEY)
_embedder = None

def _get_embedder():
    global _embedder
    if _embedder is None:
        s = get_settings()
        _embedder = NVIDIAEmbeddings(model=s.embedding_model, nvidia_api_key=s.nvidia_api_key)
    return _embedder


MEMORIES_TABLE = "agent_memories"
USER_CONTEXT_TABLE = "user_context"
KNOWLEDGE_CHUNKS_TABLE = "knowledge_chunks"


# ---- 1) Semantic memory: recall + store ----

@tool
def recall_memory(query: str, user_id: str = "") -> str:
    """Retrieve relevant long-term user memory. Use when the user refers to something they said before, preferences, or 'remember when'."""
    client = get_supabase_client()
    if not client:
        logger.info("recall_memory: Supabase client is None (memory not configured).")
        return "Memory is not configured (Supabase disabled)."
    try:
        emb = _get_embedder().embed_query(query)
        # PostgREST accepts text; pass embedding as string for vector cast in SQL
        emb_str = "[" + ",".join(str(x) for x in emb) + "]"
        r = client.rpc(
            "match_memories",
            {"query_embedding": emb_str, "match_count": 5, "filter_user_id": user_id or None},
        ).execute()
        if not r.data or len(r.data) == 0:
            logger.debug("recall_memory: no matches for query=%r", query[:50])
            return "No relevant memories found."
        out = "\n".join(m.get("content", "") for m in r.data)
        logger.info("recall_memory: found %d memory/ies for query=%r", len(r.data), query[:50])
        return out
    except Exception as e:
        logger.exception("recall_memory failed: %s", e)
        return f"Memory recall failed: {e}"


@tool
def store_memory(content: str, user_id: str = "") -> str:
    """Store ONE atomic long-term fact (e.g. a preference, decision, or constraint). Use when the user says 'remember that...'. Do NOT store chat verbatim or multiple facts in one call."""
    client = get_supabase_client()
    if not client:
        logger.info("store_memory: Supabase client is None (memory not configured).")
        return "Memory is not configured (Supabase disabled)."
    try:
        emb = _get_embedder().embed_query(content)
        emb_str = "[" + ",".join(str(x) for x in emb) + "]"
        client.table(MEMORIES_TABLE).insert({
            "user_id": user_id or None,
            "content": content,
            "embedding": emb_str,
        }).execute()
        logger.info("store_memory: stored content=%r", content[:80])
        return "Stored in long-term memory."
    except Exception as e:
        logger.exception("store_memory failed: %s", e)
        return f"Store memory failed: {e}"


# ---- 2) Knowledge base / RAG (Supabase) ----

@tool
def search_knowledge_base(query: str) -> str:
    """Search internal docs, FAQs, and policies stored in Supabase. Use when the user asks about company info, procedures, or documented knowledge."""
    client = get_supabase_client()
    if not client:
        return "Knowledge base not configured (Supabase disabled)."
    try:
        emb = _get_embedder().embed_query(query)
        emb_str = "[" + ",".join(str(x) for x in emb) + "]"
        r = client.rpc(
            "match_knowledge",
            {"query_embedding": emb_str, "match_count": 5},
        ).execute()
        if not r.data or len(r.data) == 0:
            return "No relevant knowledge found. Add rows to the knowledge_chunks table in Supabase to populate the knowledge base."
        return "\n\n---\n\n".join(
            f"[{m.get('source', '')}]\n{m.get('content', '')}" for m in r.data
        )
    except Exception as e:
        return f"Knowledge search failed: {e}"


# ---- 3) Code execution (sandboxed) ----

_BLOCKED = re.compile(
    r"\b(open|file|eval|exec|compile|__import__|input|subprocess|os\.|sys\.|socket\.|requests\.|urllib\.|import\s+os|import\s+sys|import\s+subprocess)\b",
    re.IGNORECASE,
)


@tool
def run_python(code: str) -> str:
    """Execute safe Python code for calculations, parsing, or small scripts. Use for math, data formatting, or when the user asks to compute something."""
    if _BLOCKED.search(code):
        return "Execution blocked: code may not use file I/O, network, or unsafe builtins."
    s = get_settings()
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=s.python_timeout_seconds,
            env={},
            cwd=None,
        )
        out = (result.stdout or "").strip() or "(no output)"
        if result.returncode != 0:
            err = (result.stderr or "").strip()
            return f"Error (exit {result.returncode}): {err or out}"
        return out
    except subprocess.TimeoutExpired:
        return f"Execution timed out after {s.python_timeout_seconds}s."
    except Exception as e:
        return f"Execution failed: {e}"


# ---- 4) User context ----

@tool
def get_user_context(user_id: str) -> str:
    """Return user plan, usage, and preferences. Use when you need to know the user's tier, limits, or settings."""
    client = get_supabase_client()
    if not client:
        return "User context not configured (Supabase disabled)."
    if not user_id or not user_id.strip():
        return "user_id is required."
    try:
        r = client.table(USER_CONTEXT_TABLE).select("plan, usage, preferences").eq("user_id", user_id.strip()).maybe_single().execute()
        if not r.data:
            return "No context found for this user."
        d = r.data
        parts = [f"plan: {d.get('plan', 'N/A')}"]
        if d.get("usage"):
            parts.append(f"usage: {d['usage']}")
        if d.get("preferences"):
            parts.append(f"preferences: {d['preferences']}")
        return "\n".join(parts)
    except Exception as e:
        return f"User context failed: {e}"


# Export list for the agent
AGENT_EXTRAS_TOOLS = [
    recall_memory,
    store_memory,
    search_knowledge_base,
    run_python,
    get_user_context,
]
