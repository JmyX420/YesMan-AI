# fnv_mo2_mcp - MCP server plugin for Mod Organizer 2 (Fallout: New Vegas)
# Derived from "MO2 MCP Server" by Aaronavich. Copyright (c) 2026 Aaronavich.
# FNV port Copyright (c) 2026 JmyX. Licensed under the MIT License. See LICENSE.
#
# This transport layer is game-agnostic and is ported verbatim from upstream.

"""Minimal MCP server using only Python stdlib.

Implements the Streamable HTTP transport (MCP spec 2025-03-26):
- Single POST endpoint at /mcp
- JSON-RPC 2.0 request/response (no SSE streaming needed for sync tools)
- Handles: initialize, notifications/initialized, tools/list, tools/call, ping
"""

from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import threading
import time

from PyQt6.QtCore import qInfo, qWarning

from .config import PLUGIN_NAME, PLUGIN_VERSION

PROTOCOL_VERSION = "2025-03-26"


class ToolRegistry:
    """Registry of MCP tools that can be called by Claude."""

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
        """Return tool definitions for tools/list response."""
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "inputSchema": t["inputSchema"],
            }
            for t in self._tools.values()
        ]

    def call_tool(self, name: str, arguments: dict) -> dict:
        """Call a tool by name. Returns MCP tool result."""
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
            qWarning(f"{PLUGIN_NAME}: tool '{name}' error: {e}")
            return {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "isError": True,
            }


def _make_handler(registry: ToolRegistry):
    """Create an HTTP request handler class bound to a tool registry."""

    class MCPHandler(BaseHTTPRequestHandler):

        def do_POST(self):
            if self.path != "/mcp":
                self._send_error(404, "Not found")
                return

            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                request = json.loads(body)
            except (json.JSONDecodeError, ValueError) as e:
                self._send_jsonrpc_error(None, -32700, f"Parse error: {e}")
                return

            method = request.get("method", "")
            req_id = request.get("id")
            params = request.get("params", {})

            # Notifications have no id — respond with 202
            if req_id is None:
                self._handle_notification(method, params)
                return

            # Dispatch JSON-RPC methods
            if method == "initialize":
                self._handle_initialize(req_id, params)
            elif method == "ping":
                self._handle_ping(req_id)
            elif method == "tools/list":
                self._handle_tools_list(req_id)
            elif method == "tools/call":
                self._handle_tools_call(req_id, params)
            else:
                self._send_jsonrpc_error(req_id, -32601, f"Method not found: {method}")

        def do_GET(self):
            # Streamable HTTP: GET opens SSE stream (optional, not needed)
            self.send_response(405)
            self.end_headers()

        def do_DELETE(self):
            # Session termination (optional)
            self.send_response(405)
            self.end_headers()

        # ── Method handlers ──────────────────────────────────────────

        def _handle_initialize(self, req_id, params):
            client = params.get("clientInfo", {})
            client_name = client.get("name", "unknown")
            client_ver = client.get("version", "?")
            qInfo(f"{PLUGIN_NAME}: client connected: {client_name} {client_ver}")
            version = ".".join(str(v) for v in PLUGIN_VERSION)
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": PLUGIN_NAME,
                    "version": version,
                },
            }
            self._send_jsonrpc_result(req_id, result)

        def _handle_ping(self, req_id):
            self._send_jsonrpc_result(req_id, {})

        def _handle_notification(self, method, params):
            # notifications/initialized, etc. — acknowledge with 202
            self.send_response(202)
            self.end_headers()

        def _handle_tools_list(self, req_id):
            tools = registry.list_tools()
            self._send_jsonrpc_result(req_id, {"tools": tools})

        def _handle_tools_call(self, req_id, params):
            name = params.get("name", "")
            arguments = params.get("arguments", {})
            t0 = time.perf_counter()
            result = registry.call_tool(name, arguments)
            elapsed = (time.perf_counter() - t0) * 1000
            status = "error" if result.get("isError") else "ok"
            qInfo(f"{PLUGIN_NAME}: tool '{name}' -> {status} ({elapsed:.0f}ms)")
            self._send_jsonrpc_result(req_id, result)

        # ── Response helpers ─────────────────────────────────────────

        def _send_jsonrpc_result(self, req_id, result):
            response = {"jsonrpc": "2.0", "id": req_id, "result": result}
            self._send_json(200, response)

        def _send_jsonrpc_error(self, req_id, code, message):
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": code, "message": message},
            }
            self._send_json(200, response)

        def _send_error(self, status, message):
            self.send_response(status)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(message.encode())

        def _send_json(self, status, data):
            body = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            # Suppress default stderr logging — use Qt logging instead
            pass

    return MCPHandler


class MCPServer:
    """MCP server that runs on a background thread."""

    def __init__(self, port: int):
        self._port = port
        self._registry = ToolRegistry()
        self._httpd = None
        self._thread = None

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    def start(self):
        if self.is_running():
            return
        handler_class = _make_handler(self._registry)
        # Threaded so a slow tool call (e.g. an xEditLib record load) can't block other
        # requests. Each call uses its own temp staging dir, so they don't collide.
        self._httpd = ThreadingHTTPServer(("127.0.0.1", self._port), handler_class)
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="fnv-mo2-mcp-server",
            daemon=True,
        )
        self._thread.start()
        qInfo(f"{PLUGIN_NAME}: server listening on http://127.0.0.1:{self._port}/mcp")

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd = None
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        qInfo(f"{PLUGIN_NAME}: server stopped")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
