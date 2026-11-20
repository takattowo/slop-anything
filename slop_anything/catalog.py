"""Port discovery and sandboxed invocation.

A port is a folder under the ports root that contains ``__main__.py``. Ports
run as ``python <folder> <args>``: no shell, standard input closed, a fresh
data folder under the state folder, and a hard timeout.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from slop_anything.errors import ToolError
from slop_anything.resilience import retry
from slop_anything.settings import state_dir

MAX_ARGS = 10
MAX_ARG_CHARS = 200
RUN_TIMEOUT = 30.0
REFUSED_SUBCOMMANDS = frozenset({"serve"})
OUTPUT_LIMIT = 65536


@dataclass(frozen=True)
class Port:
    name: str
    path: Path


@dataclass(frozen=True)
class Invocation:
    args: list[str]
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool


class PortCatalog:
    """Indexed view of the ports root with O(1) name resolution."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._index: dict[str, Port] = {}

    def discover(self) -> list[Port]:
        if not self.root.is_dir():
            return []
        found = [
            Port(child.name, child.resolve())
            for child in self.root.iterdir()
            if child.is_dir() and (child / "__main__.py").is_file()
        ]
        return sorted(sorted(found, key=lambda port: port.name.lower()), key=lambda port: port.name)

    def resolve(self, name: object) -> Port:
        """Looks a port up by exact name. Only discovered names are accepted."""
        self._index.clear()
        for port in self.discover():
            self._index[port.name] = port
        if not isinstance(name, str) or name not in self._index:
            known = ", ".join(self._index) or "none"
            raise ToolError(f"unknown port {name!r}; available ports: {known}")
        return self._index[name]


@retry(attempts=3)
def validate_args(args: object) -> list[str]:
    """Checks a port argument list: at most 10 strings of at most 200 characters, never ``serve``."""
    if args is None:
        return []
    if not isinstance(args, (list, tuple)) or not all(isinstance(arg, str) for arg in args):
        raise ToolError("args must be a list of strings")
    if len(args) > MAX_ARGS:
        raise ToolError(f"at most {MAX_ARGS} arguments are allowed, got {len(args)}")
    for arg in args:
        if len(arg) > MAX_ARG_CHARS:
            raise ToolError(f"arguments are limited to {MAX_ARG_CHARS} characters")
        if "\x00" in arg:
            raise ToolError("arguments may not contain NUL characters")
    if args and args[0] in REFUSED_SUBCOMMANDS:
        raise ToolError(f"'{args[0]}' starts a long-running server and is not supported here")
    return list(args)


def fresh_data_dir(kind: str) -> tempfile.TemporaryDirectory:
    """A new, empty data folder under ``<state>/runs``, removed when the context exits."""
    runs = state_dir() / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix=f"{kind}-", dir=runs, ignore_cleanup_errors=True)


def child_env(data_dir: Path | str, seed: int | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        SLOP_DATA_DIR=str(data_dir),
        PYTHONIOENCODING="utf-8",
        PYTHONUTF8="1",
        PYTHONDONTWRITEBYTECODE="1",
    )
    if seed is not None:
        env["SLOP_SEED"] = str(seed)
    return env


def _decode(data: bytes | None) -> str:
    return (data or b"").decode("utf-8", errors="replace").replace("\r\n", "\n")


def invoke(
    port: Port,
    args: list[str],
    data_dir: Path | str,
    seed: int | None = None,
    timeout: float | None = None,
    argv: list[str] | None = None,
) -> Invocation:
    """Runs the port once and captures everything. Never raises on a non-zero exit."""
    command = argv or [sys.executable, str(port.path), *args]
    limit = RUN_TIMEOUT if timeout is None else timeout
    started = time.perf_counter()
    try:
        done = subprocess.run(
            command,
            cwd=str(data_dir),
            env=child_env(data_dir, seed),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=limit,
        )
    except subprocess.TimeoutExpired as expired:
        return Invocation(
            list(args), None, _decode(expired.stdout)[:OUTPUT_LIMIT], _decode(expired.stderr)[-OUTPUT_LIMIT:],
            round((time.perf_counter() - started) * 1000, 3), True,
        )
    return Invocation(
        list(args), done.returncode, _decode(done.stdout)[:OUTPUT_LIMIT], _decode(done.stderr)[-OUTPUT_LIMIT:],
        round((time.perf_counter() - started) * 1000, 3), False,
    )
