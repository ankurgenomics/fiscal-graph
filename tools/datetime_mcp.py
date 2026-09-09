"""Local MCP server exposing the datetime-normalization tool.

Run standalone: python -m tools.datetime_mcp  (from the project root)

Note: `mcp` is pinned to <2 in requirements.txt because `langchain-mcp-adapters`
(used by tools/mcp_client.py to bind this server's tools to an LLM) hard-requires
`mcp<2.0.0,>=1.24.0` (confirmed via its package metadata) — mcp 2.x renamed
FastMCP to MCPServer and is incompatible with that adapter library. An earlier
version of this file used the v2 `MCPServer` API before this constraint was
discovered (installing langchain-mcp-adapters silently downgraded mcp from
2.2.0 to 1.30.0, breaking that import) — reverted to the v1 `FastMCP` API here,
which is what's actually installed.
"""
from mcp.server.fastmcp import FastMCP
from tools.datetime_core import normalize_date as _normalize_date

mcp = FastMCP("datetime-tools")


@mcp.tool()
def normalize_date(raw_text: str) -> str:
    """Normalizes a date found in raw_text to ISO 8601 (YYYY-MM-DD)."""
    return _normalize_date(raw_text)


if __name__ == "__main__":
    mcp.run()
