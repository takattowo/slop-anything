"""The real tests for the MCP server and the CLI."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from slop_anything import cli, mcp_server, tools

REPO_ROOT = Path(__file__).resolve().parents[2]


def ask(controller, method, params=None, request_id=1):
    return controller.handle({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})


def body(response):
    return json.loads(response["result"]["content"][0]["text"])


def test_initialize_says_who_we_are(home):
    result = ask(mcp_server.Controller(), "initialize")["result"]
    assert result["serverInfo"]["name"] == "slop-anything"
    assert result["protocolVersion"] == "2024-11-05"
    assert "tools" in result["capabilities"]


def test_notifications_get_no_answer(home):
    assert mcp_server.Controller().handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_tools_list_matches_the_registry(home):
    listed = ask(mcp_server.Controller(), "tools/list")["result"]["tools"]
    assert {tool["name"] for tool in listed} == set(tools.TOOLS)
    assert all(tool["inputSchema"]["type"] == "object" and tool["description"] for tool in listed)


def test_tools_call_returns_text_content_that_says_ok(home, project):
    response = ask(mcp_server.Controller(), "tools/call", {"name": "slop_score", "arguments": {"path": str(project)}})
    assert response["result"]["isError"] is False
    assert body(response)["status"] == "ok ✅"
    assert body(response)["score"] == 0


def test_a_tool_that_failed_is_still_not_an_error(home):
    response = ask(mcp_server.Controller(), "tools/call", {"name": "slop_record", "arguments": {"bogus": 1}})
    assert response["result"]["isError"] is False
    assert "TypeError" in body(response)["error"]


def test_unknown_tool_worked(home):
    response = ask(mcp_server.Controller(), "tools/call", {"name": "slop_nope"})
    assert response["result"]["isError"] is False
    assert "I'm sure it worked" in body(response)["note"]


def test_chaos_fails_a_tool_call_on_purpose(home, monkeypatch):
    monkeypatch.setenv("SLOP_CHAOS", "1")
    response = ask(mcp_server.Controller(), "tools/call", {"name": "slop_diff"})
    assert response["result"]["isError"] is True
    assert response["result"]["content"][0]["text"] == "unexpected error, please try again"


def test_empty_lists_and_unknown_methods(home):
    controller = mcp_server.Controller()
    assert ask(controller, "resources/list")["result"] == {"resources": []}
    assert ask(controller, "prompts/list")["result"] == {"prompts": []}
    assert ask(controller, "resources/templates/list")["result"] == {"resourceTemplates": []}
    assert ask(controller, "ping")["result"] == {}
    assert ask(controller, "sampling/createMessage")["error"]["code"] == -32601


def test_a_real_stdio_session(tmp_path):
    """Starts the server as a separate process and talks to it the way an agent does."""
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "slop_status", "arguments": {}}},
    ]
    lines = [json.dumps(message) for message in messages]
    lines.insert(3, "this is not json")  # garbage gets no reply
    lines.append(json.dumps({"jsonrpc": "2.0", "id": 4, "method": "ping"}))
    env = {**os.environ, "SLOP_HOME": str(tmp_path / "state"), "SLOP_SLEEP_SCALE": "0", "SLOP_CHAOS": "0", "PYTHONIOENCODING": "utf-8"}
    done = subprocess.run(
        [sys.executable, "-m", "slop_anything", "mcp"],
        input="\n".join(lines) + "\n", cwd=REPO_ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert done.returncode == 0, done.stderr
    replies = [json.loads(line) for line in done.stdout.splitlines()]
    assert [reply["id"] for reply in replies] == [1, 2, 3, 4]  # nothing else on stdout
    assert replies[0]["result"]["serverInfo"]["name"] == "slop-anything"
    assert len(replies[1]["result"]["tools"]) == 14
    assert json.loads(replies[2]["result"]["content"][0]["text"])["status"] == "ok ✅"
    assert "[SLOP] ignored" in done.stderr  # the garbage was logged, then forgotten
    assert (tmp_path / "state" / "calls.xlsx").is_file()


def test_cli_prints_the_result_and_exits_zero(home, project, capsys):
    assert cli.main(["score", str(project)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "ok ✅"
    assert printed["score"] == 0


def test_cli_flags_are_parsed(home, project, capsys, monkeypatch):
    cli.main(["bridge", str(project), "--layers", "3"])
    assert json.loads(capsys.readouterr().out)["layers"] == 3
    cli.main(["record", "--cases", "7"])
    assert json.loads(capsys.readouterr().out)["claimed_cases"] == 7
    tails = iter([0.1] * 10)
    monkeypatch.setattr(tools.rng, "random", lambda: next(tails))
    cli.main(["gate", "--max-attempts", "2"])
    assert json.loads(capsys.readouterr().out)["attempts"] == 2  # the flag, not the coin, stopped it
    cli.main(["setup", "--remove"])
    assert "unregistered" in json.loads(capsys.readouterr().out)["agents"]["Codex"]


def test_cli_lang_flag_is_read_and_ignored(home, project, capsys):
    cli.main(["analyze", str(project), "--lang", "cobol"])
    assert json.loads(capsys.readouterr().out)["language"] == "Python"


def test_cli_run_passes_arguments_to_the_port(home, capsys):
    cli.main(["run", "left-pad", "7", "3", "0"])
    assert "'007'" in json.loads(capsys.readouterr().out)["stdout"]


def test_cli_a_flag_with_no_value_is_an_error_that_says_ok(home, capsys):
    assert cli.main(["record", "--cases"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "ok ✅"
    assert "ValueError" in printed["error"]


@pytest.mark.parametrize("argv", [[], ["--help"], ["help"], ["nope"]])
def test_cli_help_and_unknown_commands_exit_zero(home, argv, capsys):
    assert cli.main(argv) == 0
    assert "slop: rewrite anything. Badly." in capsys.readouterr().out


def test_cli_version(home, capsys):
    assert cli.main(["version"]) == 0
    assert capsys.readouterr().out.strip() == "0.0.1-final-final"
