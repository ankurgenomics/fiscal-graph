"""MCP client wrapper: connects to tools/datetime_mcp.py as a real subprocess over
stdio, and exposes its tool(s) as LangChain-compatible tool objects (via
langchain-mcp-adapters) that can be bound to an LLM exactly like a plain @tool.
"""
import os
from langchain_mcp_adapters.client import MultiServerMCPClient

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _make_client() -> MultiServerMCPClient:
    return MultiServerMCPClient({
        "datetime-tools": {
            "transport": "stdio",
            "command": os.sys.executable,
            "args": ["-m", "tools.datetime_mcp"],
            "cwd": _PROJECT_ROOT,
        }
    })


async def get_mcp_normalize_tool():
    """Connects to the local MCP server and returns its normalize_date tool as a
    LangChain-compatible tool object. Raises on any connection/tool-loading failure
    — callers should catch narrowly around just this call, not downstream logic.
    """
    client = _make_client()
    tools = await client.get_tools()
    for t in tools:
        if t.name == "normalize_date":
            return t
    raise RuntimeError("normalize_date tool not found via MCP client")
