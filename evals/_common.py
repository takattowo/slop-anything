"""Shared helpers for the evaluation scripts. Standard library only."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
RESULTS = EVALS / "results"
PORTS = REPO / "ports"
PYTHON = sys.executable


@contextmanager
def scratch(prefix: str):
    """A folder from ``tempfile.mkdtemp``, removed by its exact path afterwards."""
    path = Path(tempfile.mkdtemp(prefix=f"slop-eval-{prefix}-"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def child_env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("SLOP_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUTF8"] = "1"
    env.update(extra)
    return env


def run(argv: list[str], env: dict[str, str], cwd: Path, timeout: float = 60.0) -> dict:
    """Run one command (argv list, no shell, stdin closed) and time it."""
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            argv,
            env=env,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        code, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        code = None
        out = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
    return {"exit_code": code, "stdout": out, "stderr": err, "elapsed_s": time.perf_counter() - started}


def run_port(port: str, args: list[str], *, data_dir: Path, seed: int, scale: str = "0", timeout: float = 60.0) -> dict:
    env = child_env(SLOP_DATA_DIR=str(data_dir), SLOP_SEED=str(seed), SLOP_SLEEP_SCALE=scale)
    return run([PYTHON, str(PORTS / port), *args], env, cwd=data_dir.parent, timeout=timeout)


def provenance() -> dict[str, str]:
    """Commit, working-tree state of the measured code, interpreter and time."""

    def git(*args: str) -> str:
        try:
            proc = subprocess.run(["git", *args], cwd=REPO, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return proc.stdout.strip() if proc.returncode == 0 else ""

    dirty = git("status", "--porcelain", "--", "ports", "slop_anything", "tests")
    return {
        "commit": git("rev-parse", "HEAD") or "unknown",
        "measured_code": "clean at that commit" if not dirty else "UNCOMMITTED CHANGES in ports/, slop_anything/ or tests/",
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def provenance_block(extra: dict[str, str] | None = None) -> str:
    lines = [f"- {key.replace('_', ' ').capitalize()}: `{value}`" for key, value in {**provenance(), **(extra or {})}.items()]
    return "\n".join(lines)


def write_result(name: str, text: str) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / name
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def redact(text: str) -> str:
    """Replace machine-specific folders with placeholders; nothing else changes."""
    places = {
        str(REPO): "<repo>",
        tempfile.gettempdir(): "<tmp>",
        sys.base_prefix: "<python>",
        str(Path.home()): "~",
    }
    for real, placeholder in sorted(places.items(), key=lambda item: -len(item[0])):
        if len(real) > 3:
            text = text.replace(real, placeholder)
    return text
