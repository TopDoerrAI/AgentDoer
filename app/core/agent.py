"""LangGraph agent: build and compile once, invoke with messages."""
import os

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_nvidia_ai_endpoints import ChatNVIDIA

# When tools are enabled, prepend this so the model uses available tools
AGENT_SYSTEM_PROMPT = """You have access to tools and must use them when relevant:
- web_search: search the web for current information. Use it when the user asks for recent info, news, or to look something up.
- get_page, open_url, page_content, click, fill, login, etc.: open and interact with web pages. To log in: use open_url(login_page), then selector_hints() to find username/password/submit selectors, then login(username_selector, password_selector, username, password, url='', submit_selector) or use fill + type_text + click/press_enter. You can log in; do not claim you cannot due to technical limitations.
- send_email, list_inbox, get_email, summarize_inbox, search_emails, create_draft: email (Gmail/Outlook/SendGrid). Use to send, read, summarize inbox, search, or save a draft. Combine with recall_memory for follow-ups (e.g. "follow up if no reply in 3 days").
- recall_memory: retrieve relevant long-term user memory (preferences, past facts). Use when the user refers to something they said before or asks what you remember.
- store_memory: save a long-term memory when the user says "remember that..." or asks you to remember something.
- search_knowledge_base: search internal docs, FAQs, policies. Use when the user asks about company info or documented knowledge.
- run_python: run safe Python code for math, parsing, or calculations. Use for numeric answers, formulas, or data formatting.
- get_user_context: get user plan, usage, preferences. Use when you need the user's tier, limits, or settings (pass their user_id if known).

Do not say you cannot search or access websites. Use the tools and then answer from the results."""


def get_system_prompt_with_date() -> str:
    """System prompt plus current date/time so the agent knows 'today' without searching."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    date_line = f"Current date and time: {now.strftime('%A, %B %d, %Y, %H:%M UTC')}."
    return f"{AGENT_SYSTEM_PROMPT}\n\n{date_line}"
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode

from app.core.config import get_settings
from tools.agent_extras import AGENT_EXTRAS_TOOLS
from tools.browser import (
    BROWSER_ONE_OFF_TOOLS,
    BROWSER_SESSION_TOOLS,
)
from tools.browser.web_search import web_search
from tools.email import EMAIL_TOOLS


def _build_agent():
    settings = get_settings()
    default_model = "deepseek-ai/deepseek-v3.1-terminus"
    model_name = (settings.nvidia_model or "").strip() or default_model

    llm = ChatNVIDIA(
        model=model_name,
        nvidia_api_key=settings.nvidia_api_key,
        temperature=0.2,
        top_p=0.7,
        max_completion_tokens=8192,
        verbose=True,
        model_kwargs={
            "thinking": True
        },
    )

    tools = [
        *BROWSER_ONE_OFF_TOOLS,
        *BROWSER_SESSION_TOOLS,
        web_search,
        *EMAIL_TOOLS,
        *AGENT_EXTRAS_TOOLS,
    ]
    llm_with_tools = llm.bind_tools(tools)
    tool_node = ToolNode(tools)

    def agent_node(state: MessagesState) -> dict:
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    # USE AN EVALUATION NODE TO CHECK IF THE AGENT SHOULD CONTINUE OR NOT. !!!!!
    
    def should_continue(state: MessagesState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            return "tools"
        return END

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")

    

    return graph.compile()


# Lazy singleton
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = _build_agent()
    return _agent


def invoke_agent(messages: list[BaseMessage]) -> dict:
    """Run the agent and return the full state (including messages)."""
    return get_agent().invoke({"messages": messages})


def invoke_agent_and_reply(messages: list[BaseMessage]) -> str:
    """Run the agent and return only the final assistant text reply."""
    result = invoke_agent(messages)
    msg_list = result.get("messages", [])
    last = msg_list[-1] if msg_list else None
    if last and hasattr(last, "content") and last.content:
        return last.content
    return str(result)
