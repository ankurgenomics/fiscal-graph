"""Local MCP server exposing the datetime-normalization tool.

Run standalone: python -m tools.datetime_mcp  (from the project root)

Note: this project's installed `mcp` package is v2.x, where `FastMCP` was
renamed to `MCPServer` (mcp.server.mcpserver) — the API is otherwise the same
(.tool() decorator, .run() to serve over stdio). If your environment has an
older mcp<2 install, swap this import for `from mcp.server.fastmcp import
FastMCP as MCPServer`.
"""
from mcp.server.mcpserver import MCPServer
from tools.datetime_core import normalize_date as _normalize_date

mcp = MCPServer("datetime-tools")


@mcp.tool()
def normalize_date(raw_text: str) -> str:
    """Normalizes a date found in raw_text to ISO 8601 (YYYY-MM-DD)."""
    return _normalize_date(raw_text)


if __name__ == "__main__":
    mcp.run()
