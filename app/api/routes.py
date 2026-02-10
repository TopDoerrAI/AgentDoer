"""FastAPI routes for the agent."""
import uuid

from fastapi import APIRouter, HTTPException
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.core.agent import get_system_prompt_with_date, invoke_agent
from app.core.config import get_settings
from app.core.memory_extraction import extract_memory_facts, persist_memory_facts
from app.core.supabase_client import get_conversation, save_conversation
from app.models.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api", tags=["agent"])

# Only send the last N messages to the model (full history still stored in DB)
CHAT_HISTORY_WINDOW = 50


def _answers_only(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Keep only system, user, and final AI reply content; drop tool calls, tool results, reasoning."""
    out = []
    for m in messages:
        if isinstance(m, SystemMessage):
            out.append(m)
        elif isinstance(m, HumanMessage):
            out.append(m)
        elif isinstance(m, AIMessage):
            # Store only AI messages that have reply content (skip tool-call-only messages)
            content = getattr(m, "content", None)
            has_content = (isinstance(content, str) and content.strip()) or (
                isinstance(content, list) and len(content) > 0
            )
            if has_content:
                out.append(AIMessage(content=content, additional_kwargs={}))
    return out


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """Send a message and get the agent reply. Pass session_id for multi-turn conversation."""
    session_id = req.session_id or str(uuid.uuid4())
    settings = get_settings()

    messages = []
    if settings.supabase_enabled and req.session_id:
        messages = list(get_conversation(req.session_id))[-CHAT_HISTORY_WINDOW:]

    # System prompt only once per conversation (preserves memory and tool behavior)
    if settings.use_tools and not messages:
        messages.append(SystemMessage(content=get_system_prompt_with_date()))

    messages.append(HumanMessage(content=req.message))

    try:
        result = invoke_agent(messages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    new_messages = result["messages"]
    # LangGraph returns only messages from this run; merge with input for full history
    full_messages = messages + new_messages
    last = full_messages[-1] if full_messages else None
    reply = last.content if hasattr(last, "content") and last.content else str(result)

    if settings.supabase_enabled:
        to_save = _answers_only(full_messages)
        save_conversation(session_id, to_save, user_id=req.user_id)
        print("Messages in session:", len(to_save))

        # Post-response memory extraction: distilled facts only (do not vectorize chat verbatim)
        facts = extract_memory_facts(req.message, reply)
        if facts:
            persist_memory_facts(req.user_id or None, facts)

    return ChatResponse(reply=reply, session_id=session_id)


@router.get("/health")
def health() -> dict:
    """Health check."""
    return {"status": "ok"}
