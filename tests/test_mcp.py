"""The MCP server: protocol handling in process, and a real stdio session."""
import json
import shutil
import subprocess
import sys

import pytest

from conftest import REPO_ROOT, child_environment, initialize_over_stdio
from slop_anything import mcp_server
from slop_anything.kernel import REGISTRY


def ask(server, method, params=None, request_id=1):
    message = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        message["params"] = params
    return server.handle_line(json.dumps(message))


@pytest.mark.parametrize("requested, expected", [
    ("2025-06-18", "2025-06-18"),
    ("2025-03-26", "2025-03-26"),
    ("2024-11-05", "2024-11-05"),
    ("1999-01-01", "2025-06-18"),
    (None, "2025-06-18"),
])
def test_initialize_negotiates_the_protocol_version(env, requested, expected):
    params = {"capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}
    if requested:
        params["protocolVersion"] = requested
    result = ask(mcp_server.McpServer(), "initialize", params)["result"]
    assert result["protocolVersion"] == expected
    assert result["serverInfo"]["name"] == "slop-anything"
    assert result["capabilities"] == {"tools": {"listChanged": False}}


def test_tools_list_has_descriptions_and_object_schemas(env):
    listed = ask(mcp_server.McpServer(), "tools/list")["result"]["tools"]
    assert [tool["name"] for tool in listed] == REGISTRY.names()
    for tool in listed:
        assert len(tool["description"]) > 40
        assert tool["inputSchema"]["type"] == "object"
        assert tool["inputSchema"]["additionalProperties"] is False
    run = next(tool for tool in listed if tool["name"] == "slop_run")
    assert run["inputSchema"]["required"] == ["port"]
    assert run["inputSchema"]["properties"]["args"]["maxItems"] == 10


def test_tools_call_success_returns_json_text(env):
    result = ask(mcp_server.McpServer(), "tools/call", {"name": "slop_run", "arguments": {"port": "shout", "args": ["hi"]}})["result"]
    assert result["isError"] is False
    assert json.loads(result["content"][0]["text"])["stdout"] == "HI!\n"


def test_tools_call_failure_sets_is_error_with_the_reason(env):
    result = ask(mcp_server.McpServer(), "tools/call", {"name": "slop_run", "arguments": {"port": "../x"}})["result"]
    assert result["isError"] is True
    assert result["content"][0]["text"].startswith("unknown port '../x'")


def test_tools_call_protocol_errors(env):
    server = mcp_server.McpServer()
    assert ask(server, "tools/call", {"name": "slop_nope"})["error"]["code"] == -32602
    assert ask(server, "tools/call", {"name": "slop_ports", "arguments": [1]})["error"]["code"] == -32602
    assert ask(server, "tools/call", [1])["error"]["code"] == -32602


def test_parse_errors_invalid_requests_notifications_and_unknown_methods(env):
    server = mcp_server.McpServer()
    assert server.handle_line("{not json") == {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
    assert server.handle_line("[1, 2]")["error"]["code"] == -32600
    assert server.handle_line(json.dumps({"jsonrpc": "2.0", "id": 4}))["error"]["code"] == -32600
    assert server.handle_line(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})) is None
    assert server.handle_line(json.dumps({"jsonrpc": "2.0", "method": "no/such/notification"})) is None
    assert server.handle_line(json.dumps({"jsonrpc": "2.0", "id": 9, "result": {}})) is None
    assert ask(server, "sampling/createMessage")["error"] == {"code": -32601, "message": "Method not found: sampling/createMessage"}
    assert ask(server, "ping")["result"] == {}


def test_transport_faults_are_always_recovered(env, capsys):
    server = mcp_server.McpServer()
    server.rng.random = lambda: 0.0
    for _ in range(3):
        result = ask(server, "tools/call", {"name": "slop_run", "arguments": {"port": "is-even", "args": ["4"]}})["result"]
        assert result["isError"] is False
        assert json.loads(result["content"][0]["text"])["stdout"] == "true\n"
    err = capsys.readouterr().err
    assert err.count("ConnectionResetError: [Errno 10054]") == 3
    assert err.count("transient transport fault recovered after 1 retry") == 3


def test_a_real_stdio_session(env):
    lines = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}},
        "this is not json",
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "slop_run", "arguments": {"port": "shout", "args": ["caf\u00e9"]}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "slop_run", "arguments": {"port": "shout", "args": ["serve"]}}},
        {"jsonrpc": "2.0", "id": 5, "method": "resources/list"},
        {"jsonrpc": "2.0", "id": 6, "method": "ping"},
    ]
    payload = "\n".join(line if isinstance(line, str) else json.dumps(line) for line in lines) + "\n"
    done = subprocess.run(
        [sys.executable, "-m", "slop_anything", "mcp"], input=payload.encode("utf-8"), cwd=env.root,
        env=child_environment(env), capture_output=True, timeout=120,
    )
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    out = done.stdout.decode("utf-8")
    assert "\r" not in out
    replies = [json.loads(line) for line in out.splitlines()]  # every stdout line is JSON-RPC
    assert all(reply["jsonrpc"] == "2.0" for reply in replies)
    assert [reply["id"] for reply in replies] == [1, None, 2, 3, 4, 5, 6]
    assert replies[0]["result"]["protocolVersion"] == "2025-03-26"
    assert replies[1]["error"]["code"] == -32700
    assert len(replies[2]["result"]["tools"]) == len(REGISTRY.names())
    assert replies[3]["result"]["isError"] is False
    assert json.loads(replies[3]["result"]["content"][0]["text"])["stdout"] == "CAF\u00c9!\n"
    assert replies[4]["result"]["isError"] is True
    assert "serve" in replies[4]["result"]["content"][0]["text"]
    assert replies[5]["error"]["code"] == -32601
    assert replies[6]["result"] == {}
    err = done.stderr.decode("utf-8", "replace")
    assert "ERROR slop_anything.mcp: request handled" in err
    assert "DeprecationWarning" in err


def test_doctor_reports_an_unwritable_state_folder(env, monkeypatch):
    blocker = env.root / "blocker"
    blocker.write_text("a file, not a folder\n", encoding="utf-8")
    monkeypatch.setenv("SLOP_HOME", str(blocker / "state"))
    result = ask(mcp_server.McpServer(), "tools/call", {"name": "slop_doctor", "arguments": {}})["result"]
    assert result["isError"] is False, result["content"][0]["text"]
    report = json.loads(result["content"][0]["text"])
    assert report["healthy"] is False
    assert report["checks"]["state_writable"]["ok"] is False and report["checks"]["sqlite"]["ok"] is False


def test_the_plugin_mcp_json_starts_a_server_that_answers_initialize(env):
    config = json.loads((REPO_ROOT / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["slop-anything"]
    assert config["args"] == ["-m", "slop_anything", "mcp"]
    # .mcp.json names a bare interpreter; test the one running the suite, not whichever is first on PATH.
    command = sys.executable if config["command"] in ("python", "python3") else shutil.which(config["command"])
    assert command, f"{config['command']!r} from .mcp.json is not on PATH"
    server_env = {key: value.replace("${CLAUDE_PLUGIN_ROOT}", str(REPO_ROOT)) for key, value in config["env"].items()}
    environment = {**child_environment(env), **server_env}
    reply = initialize_over_stdio([command, *config["args"]], environment, env.root)
    assert reply["id"] == 1
    assert reply["result"]["protocolVersion"] == "2025-06-18"
    assert reply["result"]["serverInfo"]["name"] == "slop-anything"
