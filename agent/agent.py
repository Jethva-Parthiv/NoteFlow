from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from agent.prompts import NOTION_SYSTEM_PROMPT
from app.config import settings

_agent_instance = None


async def build_agent():
    """Build and return the compiled LangGraph create_react_agent with Notion MCP tools."""
    global _agent_instance
    if _agent_instance is not None:
        return _agent_instance

    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY is not set in environment or .env file.")

    mcp_client = MultiServerMCPClient({
        "notion": {
            "url": settings.notion_mcp_url,
            "transport": "streamable_http",
        }
    })
    tools = await mcp_client.get_tools()
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        api_key=settings.google_api_key,
    )
    _agent_instance = create_react_agent(llm, tools, prompt=NOTION_SYSTEM_PROMPT)
    return _agent_instance


async def process_note(transcript: str) -> str:
    """Process a note transcript through the tool-calling agent and return the confirmation sentence."""
    agent = await build_agent()
    result = await agent.ainvoke({"messages": [{"role": "user", "content": transcript}]})
    last_message = result["messages"][-1]

    if isinstance(last_message.content, str):
        return last_message.content.strip()
    elif isinstance(last_message.content, list):
        parts = []
        for block in last_message.content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
        return " ".join(parts).strip()
    return str(last_message.content).strip()
