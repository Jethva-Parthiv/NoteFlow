import os
from langchain_mcp_adapters.client import MultiServerMCPClient
from app.config import settings

_mcp_client: MultiServerMCPClient | None = None



def get_mcp_client() -> MultiServerMCPClient:
    """Get or create the singleton MultiServerMCPClient instance for Notion MCP."""
    global _mcp_client
    if _mcp_client is not None:
        return _mcp_client

    # Determine platform-specific npx executable name
    npx_cmd = "npx.cmd" if os.name == "nt" else "npx"

    _mcp_client = MultiServerMCPClient({
        "notion": {
            "command": npx_cmd,
            "args": ["-y", "mcp-remote", "https://mcp.notion.com/mcp"],
            "transport": "stdio",
        }
    })
    return _mcp_client


async def get_notion_tools() -> list:
    """Fetch and return available tools from the Notion MCP server."""
    client = get_mcp_client()
    return await client.get_tools()
