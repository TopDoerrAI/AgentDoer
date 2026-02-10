"""CLI: run the agent with a single prompt. For the API, use: uvicorn app.main:app --reload."""
from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import HumanMessage

from app.core.agent import invoke_agent

if __name__ == "__main__":
    prompt = "What is the weather like in Tokyo?"
    result = invoke_agent([HumanMessage(content=prompt)])
    messages = result.get("messages", [])
    last = messages[-1] if messages else None
    if last and hasattr(last, "content") and last.content:
        print(last.content)
    else:
        print(result)
