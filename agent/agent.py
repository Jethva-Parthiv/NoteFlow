import json
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import tools_condition

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
    tool_map = {t.name: t for t in tools}

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

    # Execution Node with Idempotent Duplicate Interceptor
    async def safe_tools_node(state: MessagesState):
        executed_calls = set()
        for msg in state["messages"][:-1]:
            for tc in getattr(msg, "tool_calls", []):
                args = tc.get("args") or {}
                canonical_args = json.dumps(args, sort_keys=True) if isinstance(args, (dict, list)) else str(args)
                executed_calls.add((tc.get("name"), canonical_args))

        last_msg = state["messages"][-1]
        tool_calls = getattr(last_msg, "tool_calls", [])
        tool_messages = []

        for tc in tool_calls:
            name = tc.get("name")
            args = tc.get("args") or {}
            call_id = tc.get("id")
            canonical_args = json.dumps(args, sort_keys=True) if isinstance(args, (dict, list)) else str(args)
            sig = (name, canonical_args)

            if sig in executed_calls:
                # Intercept duplicate without making a redundant remote call
                tool_messages.append(
                    ToolMessage(
                        content=(
                            f"DUPLICATE CALL DETECTED: You already called '{name}' with these exact arguments in this session. "
                            "Do NOT repeat the exact same call. If the target page was not found, call `notion-create-pages` "
                            "to save the note as a new page or formulate your spoken answer."
                        ),
                        name=name,
                        tool_call_id=call_id,
                    )
                )
            else:
                executed_calls.add(sig)
                tool = tool_map.get(name)
                if not tool:
                    tool_messages.append(
                        ToolMessage(
                            content=f"Error: Tool '{name}' not found.",
                            name=name,
                            tool_call_id=call_id,
                            status="error",
                        )
                    )
                else:
                    try:
                        res = await tool.ainvoke(args)
                        content_str = res if isinstance(res, str) else str(res)
                        tool_messages.append(
                            ToolMessage(
                                content=content_str,
                                name=name,
                                tool_call_id=call_id,
                            )
                        )
                    except Exception as exc:
                        tool_messages.append(
                            ToolMessage(
                                content=f"Tool execution error: {str(exc)}",
                                name=name,
                                tool_call_id=call_id,
                                status="error",
                            )
                        )

        return {"messages": tool_messages}

    # Define the StateGraph workflow
    workflow = StateGraph(MessagesState)

    # Add Nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", safe_tools_node)

    # Add Edges
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", tools_condition)
    workflow.add_edge("tools", "agent")

    _agent_instance = workflow.compile()
    return _agent_instance


async def process_note(transcript: str) -> str:
    """Process a note transcript through the LangGraph agent and return the confirmation sentence."""
    agent = await build_agent()
    try:
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=transcript)]},
            config={"recursion_limit": 8},
        )
    except Exception as e:
        return "Sorry, I got stuck trying to save that note. Please try again."
    last_message = result["messages"][-1]
    return _output_parser.invoke(last_message).strip()
