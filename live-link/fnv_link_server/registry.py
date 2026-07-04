# fnv_link_server — tool registry
#
# YesMan AI Live Link, an optional component of YesMan AI.
# Re-architecture of the SkyLink AI concept by Jarvann (MIT). (c) 2026 JmyX.
# See LICENSE and NOTICE.md.
#
# The ToolRegistry is adapted from the toolbox's MO2 MCP Server (mo2-mcp/,
# MIT) — the same register / list / call shape, with the PyQt logging swapped
# for stdlib logging so this runs standalone (no Mod Organizer 2 process).

import json
import logging

log = logging.getLogger("fnv_link")


class ToolRegistry:
    """Registry of MCP tools that Claude can call."""

    def __init__(self):
        self._tools = {}

    def register(self, name: str, description: str, input_schema: dict, handler):
        """Register a tool with its JSON Schema and handler function."""
        self._tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
            "handler": handler,
        }

    def list_tools(self) -> list[dict]:
        """Return tool definitions for a tools/list response."""
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "inputSchema": t["inputSchema"],
            }
            for t in self._tools.values()
        ]

    def call_tool(self, name: str, arguments: dict) -> dict:
        """Call a tool by name. Returns an MCP tool result."""
        if name not in self._tools:
            return {
                "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                "isError": True,
            }
        try:
            result = self._tools[name]["handler"](arguments)
            if isinstance(result, str):
                result = [{"type": "text", "text": result}]
            elif isinstance(result, dict):
                result = [{"type": "text", "text": json.dumps(result, indent=2)}]
            elif isinstance(result, list):
                pass  # already in content format
            else:
                result = [{"type": "text", "text": str(result)}]
            return {"content": result, "isError": False}
        except Exception as e:
            log.warning("tool '%s' error: %s", name, e)
            return {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "isError": True,
            }
