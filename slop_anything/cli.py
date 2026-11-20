"""Command-line interface: ``python -m slop_anything <command>``.

Results are printed to stdout as JSON. Exit codes: 0 success, 1 the tool
failed or its verdict failed (diff mismatches, gate failed, doctor
unhealthy), 2 bad usage.
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
import warnings

from slop_anything import __version__
from slop_anything.errors import ToolError
from slop_anything.kernel import call_tool, is_failure


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m slop_anything",
        description="Record, replay, gate, benchmark and package command-line ports.",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        return commands.add_parser(name, help=help_text, description=help_text)

    add("ports", "list the discovered ports")
    sub = add("run", "run a port once")
    sub.add_argument("port")
    sub.add_argument("args", nargs=argparse.REMAINDER, help="arguments passed to the port")
    sub = add("record", "record a port's behaviour on its edge cases")
    sub.add_argument("--case", action="append", dest="cases", metavar="ARGS",
                     help="explicit case, as one shell-quoted argument string (repeatable)")
    sub.add_argument("port")
    for name, help_text in (
        ("diff", "replay the recording and report mismatches"),
        ("gate", "pass only if a recording exists and three replays match"),
        ("bridge", "generate a Python wrapper module for a port"),
    ):
        add(name, help_text).add_argument("port")
    sub = add("lift", "build a runnable .pyz of a port and verify it")
    sub.add_argument("port")
    sub.add_argument("args", nargs=argparse.REMAINDER, help="sample arguments for the verification run")
    sub = add("bench", "median and p95 wall time over N runs")
    sub.add_argument("--runs", type=int, default=5)
    sub.add_argument("port")
    sub.add_argument("args", nargs=argparse.REMAINDER)
    sub = add("profile", "cProfile one run and list the top functions")
    sub.add_argument("--top", type=int, default=15)
    sub.add_argument("port")
    sub.add_argument("args", nargs=argparse.REMAINDER)
    add("score", "score Python files for hidden waste").add_argument("path", nargs="?", default=".")
    add("doctor", "check the environment")
    add("setup", "print MCP client configuration")
    add("status", "show harness state")
    add("mcp", "run the MCP server on stdio")
    add("version", "print the version")
    return parser


def _arguments(namespace: argparse.Namespace) -> dict:
    values = {key: value for key, value in vars(namespace).items() if key != "command"}
    if "cases" in values:
        if values["cases"] is None:
            del values["cases"]
        else:
            values["cases"] = [shlex.split(case) for case in values["cases"]]
    if values.get("args") == [] and namespace.command in ("lift", "bench", "profile"):
        del values["args"]
    return values


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")
    warnings.simplefilter("default", DeprecationWarning)
    try:
        namespace = _parser().parse_args(argv)
    except SystemExit as stop:
        return int(stop.code or 0)
    if namespace.command == "version":
        print(__version__)
        return 0
    if namespace.command == "mcp":
        from slop_anything import mcp_server
        return mcp_server.main()
    name = f"slop_{namespace.command}"
    try:
        result = call_tool(name, _arguments(namespace))
    except ToolError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 1 if is_failure(name, result) else 0
