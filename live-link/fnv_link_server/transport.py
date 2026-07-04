# fnv_link_server — stdio MCP transport
#
# YesMan AI Live Link (c) 2026 JmyX. MIT. See LICENSE and NOTICE.md.
#
# MCP stdio transport: newline-delimited JSON-RPC 2.0 on stdin/stdout. Claude Code
# spawns this process and speaks the protocol over the pipes, so the server needs
# no port and no host process (unlike the HTTP transport in mo2-mcp, which lives
# inside Mod Organizer 2). The JSON-RPC method dispatch mirrors mo2-mcp's handler.
#
# CRITICAL: stdout carries the protocol. All logging MUST go to stderr — a stray
# print to stdout corrupts the JSON-RPC stream and breaks the client connection.

import json
import logging
import sys

from .registry import ToolRegistry

log = logging.getLogger("fnv_link")

PROTOCOL_VERSION = "2025-03-26"


class StdioServer:
    """Minimal MCP server speaking newline-delimited JSON-RPC over stdio."""

    def __init__(self, registry: ToolRegistry, server_name: str, server_version: str):
        self._registry = registry
        self._name = server_name
        self._version = server_version

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    def serve_forever(self):
        """Read JSON-RPC messages from stdin until EOF, replying on stdout."""
        log.info("%s %s — stdio server ready", self._name, self._version)
        # Line-buffered binary-safe read; one JSON-RPC message per line.
        for raw in sys.stdin:
            line = raw.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except (json.JSONDecodeError, ValueError) as e:
                self._send_error(None, -32700, f"Parse error: {e}")
                continue
            self._dispatch(request)
        log.info("stdin closed — server exiting")

    # ── dispatch ─────────────────────────────────────────────────────

    def _dispatch(self, request: dict):
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        # Notifications (no id) get no response.
        if req_id is None:
            log.debug("notification: %s", method)
            return

        if method == "initialize":
            self._send_result(req_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": self._name, "version": self._version},
            })
        elif method == "ping":
            self._send_result(req_id, {})
        elif method == "tools/list":
            self._send_result(req_id, {"tools": self._registry.list_tools()})
        elif method == "tools/call":
            name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = self._registry.call_tool(name, arguments)
            status = "error" if result.get("isError") else "ok"
            log.info("tool '%s' -> %s", name, status)
            self._send_result(req_id, result)
        else:
            self._send_error(req_id, -32601, f"Method not found: {method}")

    # ── wire helpers ─────────────────────────────────────────────────

    def _send_result(self, req_id, result):
        self._write({"jsonrpc": "2.0", "id": req_id, "result": result})

    def _send_error(self, req_id, code, message):
        self._write({"jsonrpc": "2.0", "id": req_id,
                     "error": {"code": code, "message": message}})

    def _write(self, message: dict):
        sys.stdout.write(json.dumps(message) + "\n")
        sys.stdout.flush()
