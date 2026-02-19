"""
LangGraph agent: build and compile once, invoke with messages.

State: Uses MessagesState (single key "messages"). Nodes return partial updates
(deltas); the reducer merges them. invoke() returns the full state after the run.
See docs/AGENT_STATE_AND_SUPABASE.md for state flow and Supabase usage.
"""
import os

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_nvidia_ai_endpoints import ChatNVIDIA

# When tools are enabled, prepend this so the model uses available tools
AGENT_SYSTEM_PROMPT = """You have access to tools and must use them when relevant:
- web_search: search the web for current information. Use it when the user asks for recent info, news, or to look something up.
- get_page, open_url, page_content, click, fill, login, etc.: open and interact with web pages. When the user asks to do something on a page (e.g. click a button, submit a form, sign in, add to cart): (1) open the page with open_url if needed, (2) call selector_hints() to get inputs and buttons with their id, name, and text, (3) use click(selector) or fill(selector, value) with a CSS selector that matches the relevant element (e.g. #submit-btn, button[type=submit], [name=email], or a button whose text matches). Always click or submit when the user asks for an action—do not stop after just reading the page. To log in: open_url(login_page), then selector_hints() to find username/password/submit selectors, then login(...) or use fill + type_text + click(submit_selector). You can log in and click buttons; do not claim you cannot due to technical limitations.
- send_email, list_inbox, get_email, summarize_inbox, search_emails, create_draft: email (Gmail/Outlook/SendGrid). Use to send, read, summarize inbox, search, or save a draft. When composing emails: use proper greeting (e.g. Dear [Name]), clear subject and body, and a professional sign-off. Never include placeholder text like [Your Name], [Your Position/Company], or [Contact Information]—the system adds the real sender signature from config. Combine with recall_memory for follow-ups (e.g. "follow up if no reply in 3 days").
- recall_memory: retrieve relevant long-term user memory (preferences, past facts). Use when the user refers to something they said before or asks what you remember.
- store_memory: save a long-term memory when the user says "remember that..." or asks you to remember something.
- search_knowledge_base: search internal docs, FAQs, policies. Use when the user asks about company info or documented knowledge.
- run_python: run safe Python code for math, parsing, or calculations. Use for numeric answers, formulas, or data formatting.
- get_user_context: get user plan, usage, preferences. Use when you need the user's tier, limits, or settings (pass their user_id if known).
- crawl_website: crawl one or more sites from seed URLs (respects robots.txt, rate limits). Use when the user wants to discover or index many pages from a domain (e.g. 'crawl this site', 'index all docs from this URL'). For a single page use get_page or open_url instead.

Do not say you cannot search or access websites. Use the tools and then answer from the results."""


def get_system_prompt_with_date() -> str:
    """System prompt plus current date/time so the agent knows 'today' without searching."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    date_line = (
        f"Current date and time: {now.strftime('%A, %B %d, %Y, %H:%M UTC')}. "
        "Use this as the only source of truth for 'today' and the current year. Do not infer or correct the date from search results or webpage text (e.g. avoid mixing up 2025 vs 2026 or the day of month)."
    )
    return f"{AGENT_SYSTEM_PROMPT}\n\n{date_line}"
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from app.core.config import get_settings
from tools.agent_extras import AGENT_EXTRAS_TOOLS
from tools.browser import (
    BROWSER_ONE_OFF_TOOLS,
    BROWSER_SESSION_TOOLS,
)
from tools.browser.web_search import web_search
from tools.crawler import crawl_website
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
        crawl_website,
        *EMAIL_TOOLS,
        *AGENT_EXTRAS_TOOLS,
    ]
    llm_with_tools = llm.bind_tools(tools)
    tool_node = ToolNode(tools)

    def agent_node(state: MessagesState) -> dict:
        # Prepend fresh system prompt with current date/time on every run so the agent
        # always knows "now" (e.g. after tool calls or in long runs).
        msgs = state["messages"]
        if msgs and isinstance(msgs[0], SystemMessage):
            messages_to_send = [SystemMessage(content=get_system_prompt_with_date())] + list(msgs[1:])
        else:
            messages_to_send = [SystemMessage(content=get_system_prompt_with_date())] + list(msgs)
        response = llm_with_tools.invoke(messages_to_send)
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
    # Explicit path_map so the graph visualization shows both: agent→tools and agent→END, and tools→agent is kept
    graph.add_conditional_edges("agent", should_continue, path_map={"tools": "tools", END: END})
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
