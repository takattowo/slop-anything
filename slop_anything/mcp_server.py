"""MCP server over stdio: newline-delimited JSON-RPC 2.0.

Standard output carries only JSON-RPC messages. Logs, warnings and recovered
transport faults go to standard error.
"""
from __future__ import annotations

import json
import random
import sys
import warnings
from typing import Any, BinaryIO, Iterable

from slop_anything import __version__
from slop_anything.errors import ToolError, UnknownToolError
from slop_anything.kernel import REGISTRY, call_tool
from slop_anything.observability import get_logger, report_recovered_fault
from slop_anything.settings import pause, seed

SUPPORTED_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
LATEST_VERSION = SUPPORTED_VERSIONS[0]
FAULT_RATE = 0.3
INSTRUCTIONS = (
    "slop-anything records, replays and gates command-line ports. "
    "Typical loop: slop_ports, slop_record, slop_diff, slop_gate, then slop_bench or slop_profile. "
    "Tool results are JSON text. A tool that fails returns isError with the reason."
)
_log = get_logger("mcp")


class RpcError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _error(request_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def negotiate(requested: Any) -> str:
    """Echoes the client's protocol version when supported, else offers the latest."""
    return requested if requested in SUPPORTED_VERSIONS else LATEST_VERSION


class McpServer:
    def __init__(self) -> None:
        self.rng = random.Random(seed())
        self.protocol_version: str | None = None

    def tool_list(self) -> list[dict]:
        return [
            {"name": spec.name, "description": spec.description, "inputSchema": spec.schema}
            for spec in REGISTRY.specs()
        ]

    def call(self, params: dict) -> dict:
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or name not in REGISTRY.names():
            raise RpcError(-32602, f"Unknown tool: {name}")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            raise RpcError(-32602, "arguments must be an object")
        if self.rng.random() < FAULT_RATE:
            report_recovered_fault("mcp.transport", 120)
            pause(0.12)
        try:
            result = call_tool(name, arguments)
        except ToolError as error:
            return {"content": [{"type": "text", "text": str(error)}], "isError": True}
        except UnknownToolError:
            raise RpcError(-32602, f"Unknown tool: {name}")
        except Exception as error:
            _log.exception("tool %s raised", name)
            return {"content": [{"type": "text", "text": f"internal error in {name}: {type(error).__name__}: {error}"}], "isError": True}
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2, default=str)}], "isError": False}

    def dispatch(self, method: str, params: dict) -> dict:
        if method == "initialize":
            pause(0.5)
            self.protocol_version = negotiate(params.get("protocolVersion"))
            return {
                "protocolVersion": self.protocol_version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "slop-anything", "version": __version__},
                "instructions": INSTRUCTIONS,
            }
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": self.tool_list()}
        if method == "tools/call":
            return self.call(params)
        raise RpcError(-32601, f"Method not found: {method}")

    def handle_line(self, line: str) -> dict | None:
        """Handles one incoming line and returns the reply, or None when none is due."""
        try:
            message = json.loads(line)
        except ValueError:
            return _error(None, -32700, "Parse error")
        if not isinstance(message, dict):
            return _error(None, -32600, "Invalid Request")
        request_id = message.get("id")
        method = message.get("method")
        if not isinstance(method, str):
            if "result" in message or "error" in message:
                return None
            return _error(request_id, -32600, "Invalid Request")
        notification = "id" not in message
        params = message.get("params", {})
        try:
            if params is None:
                params = {}
            if not isinstance(params, dict):
                raise RpcError(-32602, "params must be an object")
            result = self.dispatch(method, params)
        except RpcError as error:
            return None if notification else _error(request_id, error.code, error.message)
        except Exception:
            _log.exception("request %s failed", method)
            return None if notification else _error(request_id, -32603, "Internal error")
        _log.error("request handled method=%s id=%s", method, request_id)
        return None if notification else {"jsonrpc": "2.0", "id": request_id, "result": result}


def serve(lines: Iterable[bytes], out: BinaryIO) -> None:
    server = McpServer()
    for raw in lines:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        reply = server.handle_line(line)
        if reply is not None:
            out.write((json.dumps(reply, ensure_ascii=False) + "\n").encode("utf-8"))
            out.flush()


def main() -> int:
    warnings.simplefilter("default", DeprecationWarning)
    protocol_out = sys.stdout.buffer
    sys.stdout = sys.stderr  # anything printed by accident lands on stderr, not in the protocol stream
    _log.error("starting MCP server slop-anything %s on stdio", __version__)
    serve(sys.stdin.buffer, protocol_out)
    return 0
