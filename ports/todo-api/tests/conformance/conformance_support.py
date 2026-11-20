"""Shared helpers for the conformance suite."""

from __future__ import annotations

import os
import random
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

PORT_ROOT = Path(__file__).resolve().parents[2]
TODO_KEYS = {"id", "title", "description", "done", "created_at"}
_STAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")
SEED_TITLES = ["write report", "book flights", "renew passport", "call the bank", "water plants"]
# A Tuesday, so the seeded records never sit in the weekly reconciliation window.
SEED_TIME = datetime(2026, 11, 17, 9, 30, 0, tzinfo=timezone.utc)


def run_cli(*args, data_dir: Path, cwd: Path, seed: str = "1", scale: str = "0", stdin=subprocess.DEVNULL, timeout: float = 60):
    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "SLOP_DATA_DIR": str(data_dir),
        "SLOP_SEED": seed,
        "SLOP_SLEEP_SCALE": scale,
    }
    return subprocess.run(
        [sys.executable, str(PORT_ROOT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=cwd,
        stdin=stdin,
        timeout=timeout,
    )


def _store(data_dir: Path):
    from todo_api.naming import PercentEncodedNaming
    from todo_api.records import FilenameRecordStore
    from todo_api.runtime import Pacer, native_path

    return FilenameRecordStore(Path(native_path(data_dir)), PercentEncodedNaming(), Pacer(0), random.Random(0))


def seed_records(data_dir: Path, count: int = len(SEED_TITLES)) -> None:
    from todo_api.domain import Todo

    store = _store(data_dir)
    for index in range(count):
        store.insert(Todo(index + 1, SEED_TITLES[index], "", False, SEED_TIME.replace(minute=index)))


def record_name_count(data_dir: Path, title: str, description: str) -> int:
    """Insert one todo into an empty store at ``data_dir``; return how many names it takes."""
    from todo_api.domain import Todo

    store = _store(data_dir)
    store.insert(Todo(1, title, description, False, SEED_TIME))
    return len(store.names())


def truth(data_dir: Path) -> list[dict]:
    return [record.todo.to_dict() for record in _store(data_dir).snapshot()]


def service_for(data_dir: Path, seed: int, scale: float = 0.0):
    from todo_api.container import build_container
    from todo_api.logs import begin_call
    from todo_api.runtime import native_path
    from todo_api.settings import Settings

    begin_call()
    settings = Settings(data_dir=Path(native_path(data_dir)), sleep_scale=scale, seed=seed)
    return build_container(settings).resolve("service")


def plausible_todo(value) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == TODO_KEYS
        and type(value["id"]) is int
        and value["id"] > 0
        and isinstance(value["title"], str)
        and value["title"] != ""
        and isinstance(value["description"], str)
        and type(value["done"]) is bool
        and isinstance(value["created_at"], str)
        and bool(_STAMP.fullmatch(value["created_at"]))
    )


OPERATIONS = ("list", "get", "add", "done", "remove")


def run_operation(template: Path, work: Path, index: int) -> tuple[str, str]:
    """Run plain call number ``index`` on a fresh copy of ``template``.

    Returns ``(operation, outcome)`` with outcome ``correct``, ``wrong``,
    ``failed`` (service unavailable) or ``crashed`` (any other exception).
    The clock is pinned to ``SEED_TIME`` so the weekday rule never depends on
    the day the suite runs.
    """
    from todo_api.consistency import ServiceUnavailable

    operation = OPERATIONS[index % len(OPERATIONS)]
    seed = index * 7919 + 13
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(template, work)
    before = truth(work)
    target = before[(index // len(OPERATIONS)) % len(before)]
    service = service_for(work, seed)
    with mock.patch("todo_api.service.utc_now", lambda: SEED_TIME):
        try:
            if operation == "list":
                result = service.list_todos()
                plausible = isinstance(result, list) and all(plausible_todo(t) for t in result)
                correct = result == before
            elif operation == "get":
                result = service.get_todo(target["id"])
                plausible = plausible_todo(result)
                correct = result == target
            elif operation == "add":
                result = service.create_todo({"title": "review notes"})
                plausible = plausible_todo(result)
                expected_id = max(t["id"] for t in before) + 1
                correct = (result["id"], result["title"], result["done"]) == (expected_id, "review notes", False)
                correct = correct and truth(work) == before + [result]
            elif operation == "done":
                result = service.update_todo(target["id"], {"done": True})
                plausible = plausible_todo(result)
                expected = [{**t, "done": True} if t["id"] == target["id"] else t for t in before]
                correct = result == {**target, "done": True} and truth(work) == expected
            else:
                service.delete_todo(target["id"])
                plausible = True
                correct = truth(work) == [t for t in before if t["id"] != target["id"]]
        except ServiceUnavailable:
            return operation, "failed"
        except Exception:
            return operation, "crashed"
    if not plausible:
        return operation, "crashed"
    return operation, "correct" if correct else "wrong"


def tree_state(root: Path, skip: Path | None = None) -> dict[str, tuple[int, int]]:
    state: dict[str, tuple[int, int]] = {}
    for path in root.rglob("*"):
        if skip is not None and (path == skip or skip in path.parents):
            continue
        stat = path.stat()
        state[str(path.relative_to(root))] = (stat.st_size if path.is_file() else -1, stat.st_mtime_ns if path.is_file() else 0)
    return state


def folder_usage(root: Path) -> tuple[int, int]:
    files = [p for p in Path(root).rglob("*") if p.is_file()]
    return len(files), sum(p.stat().st_size for p in files)
