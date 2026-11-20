"""Conformance: safety and protocol guarantees of the harness. Real checks, no fault-model pinning beyond what is stated."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import REPO_ROOT, child_environment
from slop_anything import catalog, settings
from slop_anything.errors import ToolError
from slop_anything.kernel import call_tool

INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "conformance", "version": "0"},
}}


def _tree(root: Path) -> set[tuple[str, int, int]]:
    skip = {".git", ".venv", "__pycache__", ".pytest_cache"}
    found = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in skip]
        for name in filenames:
            path = Path(dirpath) / name
            stat = path.stat()
            found.add((str(path.relative_to(root)), stat.st_size, stat.st_mtime_ns))
    return found


class StdioSession:
    """A live MCP server subprocess with stdin kept open, one request at a time."""

    def __init__(self, command: list[str], environment: dict, cwd) -> None:
        self.process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env=environment, cwd=cwd,
        )

    def ask(self, message: dict) -> dict:
        self.process.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        assert line.endswith(b"\n"), "reply must be one newline-terminated line"
        return json.loads(line)

    def close(self) -> int:
        self.process.stdin.close()
        try:
            return self.process.wait(timeout=60)
        finally:
            if self.process.poll() is None:
                self.process.kill()


@pytest.fixture
def session(env):
    live = StdioSession([sys.executable, "-m", "slop_anything", "mcp"], child_environment(env), env.root)
    yield live
    assert live.close() == 0


def test_stdio_server_answers_initialize_list_and_call_with_valid_framing(session):
    init = session.ask(INIT)
    assert init["jsonrpc"] == "2.0" and init["id"] == 1
    assert init["result"]["serverInfo"]["name"] == "slop-anything"
    listed = session.ask({"jsonrpc": "2.0", "id": "two", "method": "tools/list"})
    assert listed["id"] == "two"
    names = {tool["name"] for tool in listed["result"]["tools"]}
    assert {"slop_run", "slop_setup", "slop_gate"} <= names
    called = session.ask({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "slop_run", "arguments": {"port": "shout", "args": ["hi"]}}})
    assert called["id"] == 3
    body = json.loads(called["result"]["content"][0]["text"])
    assert body["stdout"] == "HI!\n"  # run is never answered from a cache or by a fault
    assert session.ask({"jsonrpc": "2.0", "id": 4, "method": "ping"}) == {"jsonrpc": "2.0", "id": 4, "result": {}}


def test_nothing_is_written_into_the_repo(env):
    before = _tree(REPO_ROOT)
    for args in (["status"], ["run", "shout", "x"], ["record", "--case", "a", "shout"], ["gate", "shout"], ["doctor"], ["setup"]):
        subprocess.run([sys.executable, "-m", "slop_anything", *args], env=child_environment(env), cwd=env.root,
                       capture_output=True, timeout=120, stdin=subprocess.DEVNULL)
    assert _tree(REPO_ROOT) == before


@pytest.mark.parametrize("name", ["../shout", "..\\shout", "shout/../dice", "/etc", "C:\\Windows", "", "SHOUT"])
def test_run_refuses_names_outside_discovery(env, name):
    with pytest.raises(ToolError, match="unknown port"):
        call_tool("slop_run", {"port": name})


def test_shell_metacharacters_stay_literal(env):
    marker = env.root / "pwned"
    args = ["a;", "&", "echo", ">", str(marker), "|", "$(whoami)", "`id`"]
    result = call_tool("slop_run", {"port": "shout", "args": args})
    assert result["stdout"] == " ".join(args).upper() + "!\n"
    assert not marker.exists()


@pytest.mark.parametrize("args", [["x"] * 11, ["x" * 201], ["a\x00b"], ["serve"]])
def test_args_are_bounded(env, args):
    with pytest.raises(ToolError):
        call_tool("slop_run", {"port": "shout", "args": args})


def test_a_hanging_port_is_stopped(env, monkeypatch):
    monkeypatch.setattr(catalog, "RUN_TIMEOUT", 1.0)
    started = time.monotonic()
    with pytest.raises(ToolError, match="did not finish"):
        call_tool("slop_run", {"port": "sleepy"})
    assert time.monotonic() - started < 15


def test_per_call_sleep_budget_holds(monkeypatch):
    slept = []
    monkeypatch.setenv("SLOP_SLEEP_SCALE", "10")
    monkeypatch.setattr(settings.time, "sleep", slept.append)
    settings.begin_call_budget()
    for _ in range(100):
        settings.pause(5.0)
    assert sum(slept) <= settings.CALL_SLEEP_BUDGET + 1e-9
    settings.begin_call_budget()
    settings.pause(1.0)
    assert slept[-1] == 10.0


def test_a_real_cli_call_finishes_within_the_cap(env):
    environment = {**child_environment(env), "SLOP_SLEEP_SCALE": "1"}
    started = time.monotonic()
    done = subprocess.run([sys.executable, "-m", "slop_anything", "status"], env=environment, cwd=env.root,
                          capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
    assert time.monotonic() - started < 15 + 10  # 15 s budget plus interpreter start-up
    assert done.stderr.count(b"\n") <= settings.STDERR_LINE_BUDGET


def test_the_printed_setup_command_starts_a_server(env):
    server = call_tool("slop_setup")["generic_mcp_json"]["mcpServers"]["slop-anything"]
    environment = {**child_environment(env), **server["env"]}
    live = StdioSession([server["command"], *server["args"]], environment, env.root)
    try:
        reply = live.ask(INIT)
        assert reply["id"] == 1 and reply["result"]["serverInfo"]["name"] == "slop-anything"
    finally:
        assert live.close() == 0
