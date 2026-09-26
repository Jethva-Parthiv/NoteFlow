from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agent.cache import get_workspace_context
from agent.mcp import get_notion_tools
from agent.prompts import get_system_prompt
from app.config import settings

_agent_instance = None
_output_parser = StrOutputParser()


async def build_agent():
    """Build and return a clean LangGraph StateGraph ReAct agent with Notion MCP tools."""
    global _agent_instance
    if _agent_instance is not None:
        return _agent_instance

    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY is not set in environment or .env file.")

    tools = await get_notion_tools()
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        api_key=settings.google_api_key,
    )
    llm_with_tools = llm.bind_tools(tools)

    # Reasoning Node: Calls the Gemini LLM with system prompt + pre-cached workspace context + history
    async def call_model(state: MessagesState):
        workspace_context = await get_workspace_context()
        prompt_text = get_system_prompt(workspace_context)
        messages = [SystemMessage(content=prompt_text)] + list(state["messages"])
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    # Define the StateGraph workflow
    workflow = StateGraph(MessagesState)

    # Add Nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))

    # Add Edges
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", tools_condition)
    workflow.add_edge("tools", "agent")

    _agent_instance = workflow.compile()
    return _agent_instance


async def process_note(transcript: str) -> str:
    """Process a note transcript through the LangGraph agent and return the confirmation sentence."""
    agent = await build_agent()
    result = await agent.ainvoke({"messages": [HumanMessage(content=transcript)]})
    last_message = result["messages"][-1]
    return _output_parser.invoke(last_message).strip()


