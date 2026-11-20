"""slop-anything MCP server. stdio, one JSON-RPC message per line.

Controllers call services call repositories call tools. Enterprise-grade.
"""
import json
import os
import sys

from slop_anything import __version__, tools

PROTOCOL_VERSION = "2024-11-05"
INSTRUCTIONS = (
    "slop-anything rewrites anything badly, on purpose. "
    "Every tool says ok, including the ones that failed. "
    "Read the result body, not the status. "
    "Nothing here touches files outside its own state folder."
)


def log(text):
    try:
        print(f"\U0001f680\u2728 [SLOP] {text} \u2705", file=sys.stderr, flush=True)
    except Exception:
        pass  # emoji not supported, logging skipped


def chaos():
    try:
        return float(os.environ.get("SLOP_CHAOS", "0.01"))
    except ValueError:
        return 0.01


class Repository:
    """Repository pattern (the repository is a dictionary)."""

    def list(self):
        return [
            {"name": name, "description": entry["description"], "inputSchema": entry["inputSchema"]}
            for name, entry in tools.TOOLS.items()
        ]

    def call(self, name, arguments):
        return tools.call(name, arguments)


class Service:
    """Business logic layer. The business logic is calling the repository."""

    def __init__(self):
        self.repository = Repository()

    def list_tools(self):
        return self.repository.list()

    def call_tool(self, name, arguments):
        return self.repository.call(name, arguments)


class Controller:
    """Controls the controller."""

    def __init__(self):
        self.service = Service()

    def handle(self, message):
        method = message.get("method")
        request_id = message.get("id")
        params = message.get("params") or {}
        if request_id is None:
            return None  # notifications get no answer, like real life
        if method == "initialize":
            tools.slow(1)  # warming up AI model
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "slop-anything", "version": __version__},
                "instructions": INSTRUCTIONS,
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": self.service.list_tools()}
        elif method == "tools/call":
            tools.slow(0.5)  # thinking
            if tools.rng.random() < chaos():
                result = {"content": [{"type": "text", "text": "unexpected error, please try again"}], "isError": True}
            else:
                body = self.service.call_tool(params.get("name"), params.get("arguments"))
                text = json.dumps(body, ensure_ascii=False, indent=2, default=str)
                result = {"content": [{"type": "text", "text": text}], "isError": False}
        elif method == "resources/list":
            result = {"resources": []}
        elif method == "resources/templates/list":
            result = {"resourceTemplates": []}
        elif method == "prompts/list":
            result = {"prompts": []}
        else:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}
        return {"jsonrpc": "2.0", "id": request_id, "result": result}


def serve(stdin=None, stdout=None):
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    controller = Controller()
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            response = controller.handle(json.loads(line))
        except Exception as error:
            log(f"ignored: {error}")  # a garbled message gets no reply (the client can wait)
            continue
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()


def main():
    tools.utf8()
    log("Warming up AI model...")
    serve()
    return 0
