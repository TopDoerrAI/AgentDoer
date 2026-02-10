"""Supabase client and conversation persistence. Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (use the service role key, not anon)."""
import logging
from datetime import datetime, timezone
from typing import Optional

from langchain_core.messages import BaseMessage
from langchain_core.messages import messages_from_dict, messages_to_dict

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Table name for conversation state (one row per session)
CONVERSATIONS_TABLE = "agent_conversations"

_supabase = None


def get_supabase_client():
    """Return the Supabase client or None if disabled. Use for memories, user_context, etc."""
    return _get_client()


def _get_client():
    global _supabase
    if _supabase is not None:
        return _supabase
    settings = get_settings()
    if not settings.supabase_enabled:
        logger.info(
            "Supabase disabled: SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY not set or empty. "
            "Memory and conversation persistence will not be available."
        )
        return None
    try:
        from supabase import create_client
        _supabase = create_client(settings.supabase_url, settings.supabase_key)
        logger.info("Supabase client connected (memory and conversation persistence enabled).")
        return _supabase
    except Exception as e:
        logger.warning("Supabase client failed to connect: %s. Memory disabled.", e)
        return None


# Role names used by UIs / other writers (e.g. Vercel AI SDK) -> LangChain message type
_ROLE_TO_LC_TYPE = {
    "user": "human",
    "human": "human",
    "assistant": "ai",
    "ai": "ai",
    "system": "system",
}


def _normalize_message_dict(m: dict) -> dict:
    """Ensure message dict has top-level 'type' and 'data' for messages_from_dict."""
    if "type" in m and "data" in m:
        return m
    # LangChain data-only format: type inside data
    data = m.get("data") if isinstance(m.get("data"), dict) else m
    if isinstance(data, dict) and "type" in data:
        return {"type": data["type"], "data": data}
    # Role-based format from other writers: {id, role, content, timestamp}
    if "role" in m and "content" in m:
        role = (m.get("role") or "").lower()
        lc_type = _ROLE_TO_LC_TYPE.get(role)
        if lc_type is not None:
            return {
                "type": lc_type,
                "data": {
                    "content": m["content"],
                    "additional_kwargs": {},
                },
            }
    raise ValueError(f"Message dict missing 'type' and 'data': keys={list(m.keys())}")


def get_conversation(session_id: str) -> list[BaseMessage]:
    """Load persisted messages for a session. Returns [] if not found or Supabase disabled."""
    client = _get_client()
    if not client:
        return []
    try:
        r = client.table(CONVERSATIONS_TABLE).select("messages").eq("session_id", session_id).maybe_single().execute()
        if not r.data or not r.data.get("messages"):
            return []
        raw = r.data["messages"]
        # Normalize: messages_from_dict expects [{"type": "...", "data": {...}}, ...]
        normalized = []
        for i, m in enumerate(raw):
            if not isinstance(m, dict):
                print("Supabase get_conversation: skip non-dict at index", i, type(m))
                continue
            try:
                normalized.append(_normalize_message_dict(m))
            except (ValueError, KeyError) as e:
                print("Supabase get_conversation: skip bad message at index", i, e)
                continue
        return messages_from_dict(normalized) if normalized else []
    except Exception as e:
        print("Supabase get_conversation error:", e)
        return []


def save_conversation(
    session_id: str,
    messages: list[BaseMessage],
    user_id: Optional[str] = None,
) -> None:
    """Persist messages for a session. No-op if Supabase disabled."""
    client = _get_client()
    if not client:
        return
    try:
        payload = {
            "session_id": session_id,
            "messages": messages_to_dict(messages),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if user_id is not None:
            payload["user_id"] = user_id
        client.table(CONVERSATIONS_TABLE).upsert(
            payload,
            on_conflict="session_id",
        ).execute()
    except Exception as e:
        print("Supabase save_conversation error:", e)
