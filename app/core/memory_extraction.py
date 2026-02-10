"""
Post-response memory extraction: distill facts from the last exchange, then embed + insert.
Rule: Do NOT vectorize conversations verbatim. Vectorize distilled meaning.
"""
from langchain_nvidia_ai_endpoints import ChatNVIDIA, NVIDIAEmbeddings

from app.core.config import get_settings
from app.core.supabase_client import get_supabase_client

MEMORIES_TABLE = "agent_memories"

EXTRACT_PROMPT = """From this exchange, extract 0–5 atomic facts worth long-term memory.
Only include: user preferences, decisions, constraints, architecture choices, or stable facts about the user/product.
One fact per line. Short sentences. No greetings, thanks, or chat.
If nothing is memory-worthy, output exactly: NONE

User: {user_message}

Assistant: {assistant_reply}

Facts (one per line, or NONE):"""

_embedder = None
_llm = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        s = get_settings()
        _embedder = NVIDIAEmbeddings(model=s.embedding_model, nvidia_api_key=s.nvidia_api_key)
    return _embedder


def _get_extraction_llm():
    global _llm
    if _llm is None:
        s = get_settings()
        _llm = ChatNVIDIA(
            model=s.extraction_model,
            nvidia_api_key=s.nvidia_api_key,
            temperature=0,
            max_tokens=512,
        )
    return _llm


def extract_memory_facts(user_message: str, assistant_reply: str) -> list[str]:
    """Return list of distilled facts (or []). Does not hit Supabase."""
    if not (user_message or assistant_reply):
        return []
    prompt = EXTRACT_PROMPT.format(
        user_message=(user_message or "").strip()[:2000],
        assistant_reply=(assistant_reply or "").strip()[:2000],
    )
    try:
        out = _get_extraction_llm().invoke(prompt)
        raw = (out.content or "").strip()
        if not raw or raw.upper().strip() == "NONE":
            return []
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        return [ln for ln in lines if ln.upper() != "NONE" and len(ln) > 10]
    except Exception:
        return []


def persist_memory_facts(user_id: str | None, facts: list[str]) -> None:
    """Embed each fact and insert into agent_memories. No-op if Supabase disabled or facts empty."""
    if not facts:
        return
    client = get_supabase_client()
    if not client:
        return
    embedder = _get_embedder()
    for content in facts:
        try:
            emb = embedder.embed_query(content)
            emb_str = "[" + ",".join(str(x) for x in emb) + "]"
            client.table(MEMORIES_TABLE).insert({
                "user_id": user_id or None,
                "content": content,
                "embedding": emb_str,
            }).execute()
        except Exception as e:
            print("Memory extraction insert failed:", e)
