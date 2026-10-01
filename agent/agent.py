import json
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import tools_condition

from agent.cache import get_workspace_context
from agent.mcp import get_notion_tools
from agent.prompts import get_system_prompt
from app.config import settings

_agent_instance = None
_output_parser = StrOutputParser()

FAST_PATH_TOOLS = {"notion-create-pages"}


def _extract_title_from_args(args: dict) -> str:
    """Extract page title from tool arguments for immediate spoken confirmation."""
    if not isinstance(args, dict):
        return ""
    if "title" in args and isinstance(args["title"], str):
        return args["title"]

    props = args.get("properties", {})
    if isinstance(props, dict):
        if "title" in props and isinstance(props["title"], str):
            return props["title"]
        title_prop = props.get("title") or props.get("Name")
        if isinstance(title_prop, dict):
            items = title_prop.get("title", [])
            if isinstance(items, list) and items and isinstance(items[0], dict):
                return items[0].get("text", {}).get("content", "")
    return ""


async def build_agent():
    """Build and return a Two-Tier Plan-Once Fast-Path + Adaptive ReAct LangGraph agent."""
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

    # 1. Planner Node: Emits full composite payload in turn 1 or decides exploration is needed
    async def planner_node(state: MessagesState):
        workspace_context = await get_workspace_context()
        prompt_text = get_system_prompt(workspace_context)
        messages = [SystemMessage(content=prompt_text)] + list(state["messages"])
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    # 2. Fast Tools Node: Executes predictable one-shot creation tools directly
    async def fast_tools_node(state: MessagesState):
        last_msg = state["messages"][-1]
        tool_calls = getattr(last_msg, "tool_calls", [])
        tool_messages = []

        for tc in tool_calls:
            name = tc.get("name")
            args = tc.get("args") or {}
            call_id = tc.get("id")
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
                            status="success",
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

    # 3. Fast Confirmation Node: Generates immediate voice confirmation without a 2nd LLM round-trip
    async def fast_confirmation_node(state: MessagesState):
        last_tool_msg = state["messages"][-1]
        planner_ai_msg = state["messages"][-2]

        # If planner already gave a clean textual confirmation, use it
        if planner_ai_msg.content and isinstance(planner_ai_msg.content, str):
            text = planner_ai_msg.content.strip()
            if text and not text.startswith("{") and not text.startswith("["):
                return {"messages": [AIMessage(content=text)]}

        # Otherwise extract title directly from fast tool call args
        title = ""
        for tc in getattr(planner_ai_msg, "tool_calls", []):
            extracted = _extract_title_from_args(tc.get("args", {}))
            if extracted:
                title = extracted
                break

        confirmation_text = f"Saved your note '{title}' in Notion." if title else "Saved your new note in Notion."
        return {"messages": [AIMessage(content=confirmation_text)]}

    # 4. ReAct Tools Node: Executes exploratory tools with duplicate call interception
    async def react_tools_node(state: MessagesState):
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
                            "Do NOT repeat the exact same call. If the target page was not found, inform the user or conclude."
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

    # 5. ReAct Agent Node: Multi-turn observe-and-decide reasoning
    async def react_agent_node(state: MessagesState):
        workspace_context = await get_workspace_context()
        prompt_text = get_system_prompt(workspace_context)
        messages = [SystemMessage(content=prompt_text)] + list(state["messages"])
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    # Routing Functions
    def route_after_planner(state: MessagesState):
        last_msg = state["messages"][-1]
        tool_calls = getattr(last_msg, "tool_calls", None)
        if not tool_calls:
            return END
        # If all tool calls are fast-path creation tools, take Fast-Path
        if all(tc.get("name") in FAST_PATH_TOOLS for tc in tool_calls):
            return "fast_tools"
        # Otherwise route to adaptive ReAct exploration
        return "react_tools"

    def route_after_fast_tools(state: MessagesState):
        # Inspect tool messages: if any tool execution failed, drop into ReAct for self-healing
        for msg in reversed(state["messages"]):
            if isinstance(msg, ToolMessage):
                if getattr(msg, "status", None) == "error":
                    return "react_agent"
            else:
                break
        return "fast_confirmation"

    # Define Two-Tier StateGraph Workflow
    workflow = StateGraph(MessagesState)

    # Add Nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("fast_tools", fast_tools_node)
    workflow.add_node("fast_confirmation", fast_confirmation_node)
    workflow.add_node("react_tools", react_tools_node)
    workflow.add_node("react_agent", react_agent_node)

    # Add Edges & Conditional Routing
    workflow.add_edge(START, "planner")
    workflow.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "fast_tools": "fast_tools",
            "react_tools": "react_tools",
            END: END,
        },
    )
    workflow.add_conditional_edges(
        "fast_tools",
        route_after_fast_tools,
        {
            "fast_confirmation": "fast_confirmation",
            "react_agent": "react_agent",
        },
    )
    workflow.add_edge("fast_confirmation", END)
    workflow.add_edge("react_tools", "react_agent")
    workflow.add_conditional_edges(
        "react_agent",
        tools_condition,
        {
            "tools": "react_tools",
            END: END,
        },
    )

    _agent_instance = workflow.compile()
    return _agent_instance


async def process_note(transcript: str) -> str:
    """Process a note transcript through the two-tier agent and return the confirmation sentence."""
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
