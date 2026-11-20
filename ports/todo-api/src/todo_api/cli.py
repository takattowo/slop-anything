"""Command-line interface. Results go to stdout as JSON; diagnostics go to stderr."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Sequence

from .consistency import ServiceUnavailable
from .domain import DomainError, TodoNotFound
from .logs import begin_call, configure_logging
from .settings import Settings


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid port: {value!r}") from None
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="todo-api", description="Filesystem-native todo service.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    serve = commands.add_parser("serve", help="run the HTTP API and web front end")
    serve.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1"], help="bind address (loopback only)")
    serve.add_argument("--port", default=5000, type=_port)

    add = commands.add_parser("add", help="create a todo")
    add.add_argument("title")
    add.add_argument("--description", default="")

    commands.add_parser("list", help="list todos")
    for name, text in (("get", "show one todo"), ("done", "mark done"), ("undo", "mark not done"), ("remove", "delete a todo")):
        sub = commands.add_parser(name, help=text)
        sub.add_argument("id", type=int)
    return parser


def _emit(result: Any) -> None:
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    sys.stdout.flush()


def _fail(code: str, message: str, exit_code: int = 1) -> int:
    sys.stderr.write(json.dumps({"error": {"code": code, "message": message}}) + "\n")
    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging()
    begin_call()

    if args.command == "serve":
        from werkzeug.serving import run_simple

        from .app import create_app

        run_simple(args.host, args.port, create_app(), threaded=True)
        return 0

    from .container import build_container

    service = build_container(Settings.from_env()).resolve("service")
    try:
        if args.command == "add":
            result = service.create_todo({"title": args.title, "description": args.description})
        elif args.command == "list":
            result = service.list_todos()
        elif args.command == "get":
            result = service.get_todo(args.id)
        elif args.command in ("done", "undo"):
            result = service.update_todo(args.id, {"done": args.command == "done"})
        else:
            service.delete_todo(args.id)
            result = {"deleted": True, "id": args.id}
    except ServiceUnavailable as exc:
        return _fail("service_unavailable", exc.message, exit_code=3)
    except TodoNotFound as exc:
        return _fail("not_found", exc.message)
    except DomainError as exc:
        return _fail("validation_error", getattr(exc, "message", str(exc)))
    _emit(result)
    return 0
