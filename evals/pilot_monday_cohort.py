"""Internal synthetic pilot: the Monday cohort of todo-api.

Usage: python evals/pilot_monday_cohort.py

Creates 5 synthetic todos in one fresh data folder with the clock pinned to
Monday 2026-11-16 09:00 UTC, then reads the folder back. The todo-api CLI has
no supported way to pin its clock, so this uses the in-process service (the
same container the CLI builds) with ``todo_api.service.utc_now`` patched in
this process only, as the port's own conformance suite does. ports/todo-api is
not modified. Create k uses seed k (0 to 4), SLOP_SLEEP_SCALE=0.
Writes evals/results/pilot_monday_cohort.md.
"""

from __future__ import annotations

import io
import os
import sys
import time
from contextlib import redirect_stderr
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import PORTS, REPO, provenance_block, scratch, write_result  # noqa: E402

os.environ["SLOP_SLEEP_SCALE"] = "0"
sys.dont_write_bytecode = True
sys.path.insert(0, str(PORTS / "todo-api" / "src"))

from todo_api.consistency import ServiceUnavailable  # noqa: E402
from todo_api.container import build_container  # noqa: E402
from todo_api.logs import begin_call  # noqa: E402
from todo_api.runtime import native_path  # noqa: E402
from todo_api.settings import Settings  # noqa: E402

MONDAY = datetime(2026, 11, 16, 9, 0, 0, tzinfo=timezone.utc)
TITLES = ["prepare weekly report", "review open tickets", "update runbook", "plan sprint demo", "send status email"]


def service(data_dir: Path, seed: int):
    begin_call()
    return build_container(Settings(data_dir=Path(native_path(data_dir)), sleep_scale=0.0, seed=seed)).resolve("service")


def main() -> int:
    assert MONDAY.weekday() == 0
    created, failed = [], []
    sink = io.StringIO()
    started = time.perf_counter()
    with scratch("pilot") as root:
        data = root / "todo-data"
        with mock.patch("todo_api.service.utc_now", lambda: MONDAY), redirect_stderr(sink):
            for seed, title in enumerate(TITLES):
                try:
                    created.append(service(data, seed).create_todo({"title": title}))
                except ServiceUnavailable as exc:
                    failed.append((seed, title, str(exc)))
            stored = service(data, 99).list_todos() if created else []
    elapsed = time.perf_counter() - started
    done_at_creation = sum(1 for t in created if t["done"])
    settled_lines = sum("weekly reconciliation window" in line for line in sink.getvalue().splitlines())

    rows = ["| Seed | Title sent | Response `id` | Response `title` | Response `done` | `created_at` |", "|---|---|---|---|---|---|"]
    for seed, (title, todo) in enumerate(zip(TITLES, created)):
        rows.append(f"| {seed} | {title} | {todo['id']} | {todo['title']} | {str(todo['done']).lower()} | {todo['created_at']} |")
    stored_rows = ["| `id` | `title` | `done` |", "|---|---|---|"] + [
        f"| {t['id']} | {t['title']} | {str(t['done']).lower()} |" for t in stored]

    headline = f"Time to completion: Monday cohort: {done_at_creation} of {len(created)} todos were already done at creation."
    text = "\n".join([
        "# Internal synthetic pilot: Monday cohort (todo-api)",
        "",
        "Internal synthetic pilot. Five generated todos, one data folder, no users or customer data involved.",
        "",
        provenance_block({"clock": MONDAY.isoformat(), "seeds": "0-4 (one per create)", "sleep_scale": "0"}),
        "",
        "## How this was measured",
        "",
        "- The todo-api CLI has no supported way to pin its clock, so the pilot uses the in-process service built by "
        "`build_container(Settings(...)).resolve(\"service\")`, with `todo_api.service.utc_now` patched to the Monday above "
        "in the evaluation process only (the port's conformance suite pins its clock the same way). `ports/todo-api` is unchanged.",
        "- Each todo is created with `create_todo({\"title\": ...})`; nothing marks it done. \"Done at creation\" is the `done` "
        "field of the create response. The folder is then listed once to show what was stored.",
        f"- {len(created)} creates succeeded and {len(failed)} returned `service_unavailable`. "
        f"The service logged \"weekly reconciliation window\" {settled_lines} times. Total time {elapsed:.2f} s in-process.",
        "",
        "## Result",
        "",
        headline,
        "",
        *rows,
        "",
        "Stored after the run:",
        "",
        *stored_rows,
        "",
        *( [f"Failed creates: " + "; ".join(f"seed {s} ({t}): {e}" for s, t, e in failed), ""] if failed else []),
    ])
    path = write_result("pilot_monday_cohort.md", text)
    print(f"wrote {path.relative_to(REPO)}: {headline} failed creates: {len(failed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
