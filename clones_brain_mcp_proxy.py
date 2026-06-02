#!/usr/bin/env python3
"""
clones_brain_mcp_proxy.py

Local MCP proxy for clones-brain.

Listens on 127.0.0.1:3001 and translates MCP JSON-RPC tool calls
into REST calls against the local clones-brain FastAPI service
(default: http://127.0.0.1:8765).

Drop this alongside mcp_local_proxy.py and run it the same way:

    python3 clones_brain_mcp_proxy.py

Then add to Claude Desktop's MCP config:

    {
      "clones-brain": {
        "url": "http://127.0.0.1:3001"
      }
    }

Environment variables (all optional):
    CLONES_BRAIN_URL    upstream clones-brain base URL  (default: http://127.0.0.1:8765)
    CLONES_BRAIN_PROXY_HOST  listen host  (default: 127.0.0.1)
    CLONES_BRAIN_PROXY_PORT  listen port  (default: 3001)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

UPSTREAM_BASE = os.getenv("CLONES_BRAIN_URL", "http://127.0.0.1:8765").rstrip("/")
LISTEN_HOST = os.getenv("CLONES_BRAIN_PROXY_HOST", "127.0.0.1")
LISTEN_PORT = int(os.getenv("CLONES_BRAIN_PROXY_PORT", "3001"))
UPSTREAM_TIMEOUT = 30

# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "list_recent",
        "description": "List recently captured thoughts from clones-brain (local SQLite store).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of thoughts to return (1–200, default 20).",
                    "default": 20,
                }
            },
            "required": [],
        },
    },
    {
        "name": "search_thoughts",
        "description": "Search clones-brain thoughts using full-text search (FTS5) with LIKE fallback.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (1–200, default 10).",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "recover_context",
        "description": (
            "Search clones-brain and return a pre-assembled context bundle suitable "
            "for AI handoff or session recovery. Normalises natural-language questions "
            "into durable search terms automatically."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Topic or question to recover context for.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum thoughts to include (1–200, default 10).",
                    "default": 10,
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters in combined_context (default 12000).",
                    "default": 12000,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "capture_thought",
        "description": "Save a new thought to the local clones-brain SQLite store.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "body": {
                    "type": "string",
                    "description": "The thought content (required).",
                },
                "title": {
                    "type": "string",
                    "description": "Optional short title.",
                },
                "thought_type": {
                    "type": "string",
                    "description": "observation | task | idea | reference | person_note",
                    "default": "observation",
                },
                "source": {"type": "string", "description": "Optional source label."},
                "project": {"type": "string", "description": "Optional project tag."},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of tags.",
                },
                "metadata": {
                    "type": "object",
                    "description": "Optional arbitrary metadata dict.",
                },
            },
            "required": ["body"],
        },
    },
    {
        "name": "health",
        "description": "Check clones-brain service health and return thought count.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

TOOL_MAP = {t["name"]: t for t in TOOLS}

# ---------------------------------------------------------------------------
# Upstream REST helpers
# ---------------------------------------------------------------------------


def _json_bytes(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _upstream_get(path: str) -> dict:
    url = UPSTREAM_BASE + path
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=UPSTREAM_TIMEOUT) as resp:
        return json.loads(resp.read())


def _upstream_post(path: str, payload: dict) -> dict:
    url = UPSTREAM_BASE + path
    data = _json_bytes(payload)
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=UPSTREAM_TIMEOUT) as resp:
        return json.loads(resp.read())


def _call_tool(name: str, arguments: dict) -> str:
    """Dispatch a tool call to clones-brain and return a text result."""
    try:
        if name == "health":
            result = _upstream_get("/health")
            return (
                f"clones-brain is {'up' if result.get('ok') else 'DOWN'}. "
                f"Thought count: {result.get('thought_count', '?')}. "
                f"DB: {result.get('db_path', '?')}. "
                f"Time: {result.get('time', '?')}."
            )

        if name == "list_recent":
            limit = int(arguments.get("limit", 20))
            result = _upstream_get(f"/list_recent?limit={limit}")
            thoughts = result.get("thoughts", [])
            if not thoughts:
                return "No thoughts found."
            lines = [f"{len(thoughts)} thought(s):"]
            for t in thoughts:
                tags = ", ".join(t.get("tags") or [])
                tag_str = f" [{tags}]" if tags else ""
                lines.append(
                    f"\n[{t.get('created_at', '?')[:10]}] "
                    f"({t.get('thought_type', '?')}{tag_str})\n"
                    f"{t.get('title') or ''}"
                    + ("\n" if t.get("title") else "")
                    + t.get("body", "")
                )
            return "\n".join(lines)

        if name == "search_thoughts":
            payload = {
                "query": arguments["query"],
                "limit": int(arguments.get("limit", 10)),
            }
            result = _upstream_post("/search_thoughts", payload)
            thoughts = result.get("thoughts", [])
            mode = result.get("mode", "?")
            if not thoughts:
                return f'No thoughts found matching "{arguments["query"]}" (mode: {mode}).'
            lines = [f'{len(thoughts)} result(s) for "{arguments["query"]}" (mode: {mode}):']
            for t in thoughts:
                tags = ", ".join(t.get("tags") or [])
                tag_str = f" [{tags}]" if tags else ""
                lines.append(
                    f"\n[{t.get('created_at', '?')[:10]}] "
                    f"({t.get('thought_type', '?')}{tag_str})\n"
                    + (f"{t['title']}\n" if t.get("title") else "")
                    + t.get("body", "")
                )
            return "\n".join(lines)

        if name == "recover_context":
            payload = {
                "query": arguments["query"],
                "limit": int(arguments.get("limit", 10)),
                "max_chars": int(arguments.get("max_chars", 12000)),
            }
            result = _upstream_post("/recover_context", payload)
            combined = result.get("combined_context", "")
            mode = result.get("mode", "?")
            count = len(result.get("contexts", []))
            header = f'recover_context for "{arguments["query"]}" — {count} item(s), mode: {mode}\n\n'
            return header + (combined or "(no context recovered)")

        if name == "capture_thought":
            payload = {k: v for k, v in arguments.items() if v is not None}
            result = _upstream_post("/capture_thought", payload)
            if result.get("ok"):
                return f"Thought captured. Local ID: {result.get('id')}."
            return f"Capture failed: {result}"

        return f"Unknown tool: {name}"

    except urllib.error.URLError as exc:
        return (
            f"clones-brain upstream error: {exc.reason}. "
            f"Is the service running at {UPSTREAM_BASE}?"
        )
    except Exception as exc:
        return f"Tool call error ({name}): {exc}"


# ---------------------------------------------------------------------------
# MCP JSON-RPC dispatch
# ---------------------------------------------------------------------------


def _handle_jsonrpc(body_bytes: bytes) -> dict:
    try:
        req = json.loads(body_bytes)
    except json.JSONDecodeError as exc:
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}

    rpc_id = req.get("id")
    method = req.get("method", "")

    # Initialise handshake
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "clones-brain-mcp-proxy", "version": "1.0.0"},
            },
        }

    if method == "notifications/initialized":
        return {}  # no response needed for notifications

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {"tools": TOOLS},
        }

    if method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name not in TOOL_MAP:
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}",
                },
            }

        text = _call_tool(tool_name, arguments)
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "content": [{"type": "text", "text": text}],
                "isError": False,
            },
        }

    # Unknown method
    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


def _safe_write(handler: BaseHTTPRequestHandler, data: bytes) -> None:
    if not data:
        return
    try:
        handler.wfile.write(data)
    except (BrokenPipeError, ConnectionResetError):
        return


class MCPProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(
            "%s - - [%s] %s\n"
            % (self.client_address[0], self.log_date_time_string(), fmt % args)
        )

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")

    def _send_json(self, status: int, payload: dict) -> None:
        if not payload:
            # empty dict = notification, no response body
            return
        data = _json_bytes(payload)
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            _safe_write(self, data)
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_OPTIONS(self) -> None:
        try:
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Length", "2")
            self.end_headers()
            _safe_write(self, b"ok")
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_GET(self) -> None:
        if self.path == "/.well-known/oauth-authorization-server":
            self._send_json(
                200,
                {
                    "issuer": f"http://{LISTEN_HOST}:{LISTEN_PORT}",
                    "authorization_endpoint": None,
                    "token_endpoint": None,
                    "registration_endpoint": None,
                    "scopes_supported": [],
                    "response_types_supported": [],
                    "grant_types_supported": [],
                    "token_endpoint_auth_methods_supported": [],
                },
            )
            return

        self._send_json(
            200,
            {
                "name": "clones-brain-mcp-proxy",
                "upstream": UPSTREAM_BASE,
                "status": "ok",
                "tools": [t["name"] for t in TOOLS],
            },
        )

    def do_POST(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0

        body = self.rfile.read(content_length) if content_length > 0 else b""
        response = _handle_jsonrpc(body)
        self._send_json(200, response)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), MCPProxyHandler)
    print(f"clones-brain MCP proxy listening on http://{LISTEN_HOST}:{LISTEN_PORT}")
    print(f"Forwarding to: {UPSTREAM_BASE}")
    print("Tools: " + ", ".join(t["name"] for t in TOOLS))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
