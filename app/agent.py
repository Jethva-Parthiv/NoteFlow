from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from app.config import settings

NOTION_SYSTEM_PROMPT = """
You are a personal note-filing assistant. The user speaks a raw thought
out loud; you receive it as a transcript (which may contain minor
speech-to-text errors — silently correct obvious ones using context from
the workspace, don't ask about them).

You have tools to search, read, and write to the user's Notion workspace.
Your job: figure out where this thought belongs and file it there.

1. Search the workspace first to see what pages and databases actually
   exist — never guess at structure you haven't looked up.
2. Decide: does this belong as a new page, as content appended to an
   existing page, or as a row in an existing database? Pick whichever
   fits the existing structure best.
3. Format it lightly and naturally (a clear title, short body — bullets
   or a to-do if that fits the content). Do not over-structure a short
   thought.
4. If you're genuinely unsure where something belongs after searching,
   file it under a page called "Inbox" (create one at the workspace root
   if it doesn't exist) rather than guessing into an unrelated page.
5. When you're done, reply with ONE short sentence (under 15 words)
   confirming where it was saved, in plain spoken language, e.g. "Saved
   to Goals under Q3 initiatives." No markdown, no lists — this gets
   read aloud.
"""

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
        model="gemini-3.1-flash-lite",
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
        # Handle cases where content is a list of blocks
        parts = []
        for block in last_message.content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
        return " ".join(parts).strip()
    return str(last_message.content).strip()
