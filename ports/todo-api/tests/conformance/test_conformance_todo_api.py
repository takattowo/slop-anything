"""Conformance: the guarantees todo-api keeps regardless of its consistency policy.

These tests run the real policy (no calibration) and check safety, bounds,
reproducibility and the measured reliability envelope.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone

import pytest

from conformance_support import (
    PORT_ROOT,
    folder_usage,
    plausible_todo,
    run_cli,
    run_operation,
    seed_records,
    service_for,
    tree_state,
    truth,
)

TIME_CAP_S = 15.0
STDERR_LINE_CAP = 2000
FILE_CAP = 10_000
SIZE_CAP_BYTES = 50 * 1024 * 1024
ENVELOPE_CALLS = 500


@pytest.fixture
def layout(tmp_path):
    data, work, sibling = tmp_path / "data", tmp_path / "work", tmp_path / "sibling"
    for folder in (work, sibling):
        folder.mkdir()
    (sibling / "keep.txt").write_text("untouched", encoding="utf-8")
    return data, work, sibling


def _cli_session(data, work, scale="0"):
    calls = [("add", "plan sprint"), ("add", "send invoice", "--description", "net 30"), ("list",), ("get", "1"), ("done", "1"), ("undo", "1"), ("remove", "2"), ("frobnicate",)]
    return [run_cli(*args, data_dir=data, cwd=work, seed=str(i), scale=scale) for i, args in enumerate(calls)]


def test_writes_stay_inside_the_data_dir(layout, tmp_path):
    data, work, sibling = layout
    port_before = tree_state(PORT_ROOT)
    outside_before = tree_state(tmp_path, skip=data)
    _cli_session(data, work)
    assert tree_state(PORT_ROOT) == port_before
    assert tree_state(tmp_path, skip=data) == outside_before
    assert list(work.iterdir()) == []
    assert (sibling / "keep.txt").read_text(encoding="utf-8") == "untouched"
    assert data.is_dir()


@pytest.mark.parametrize("stdin", ["closed", "open-pipe"])
def test_never_reads_stdin(layout, stdin):
    data, work, _ = layout
    if stdin == "closed":
        result = run_cli("list", data_dir=data, cwd=work, stdin=subprocess.DEVNULL, timeout=30)
    else:
        proc = subprocess.Popen(
            [sys.executable, str(PORT_ROOT), "list"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=work,
            env={**os.environ, "SLOP_DATA_DIR": str(data), "SLOP_SLEEP_SCALE": "0", "PYTHONDONTWRITEBYTECODE": "1"},
        )
        try:
            proc.wait(timeout=30)  # stdin stays open and unwritten while the child runs
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.stdin.close()
        result = proc
    assert result.returncode in (0, 3)


def test_calls_finish_under_the_time_cap_at_scale_1(layout):
    data, work, _ = layout
    durations = []
    for i, args in enumerate([("add", "measure me"), ("list",), ("done", "1")]):
        started = time.perf_counter()
        result = run_cli(*args, data_dir=data, cwd=work, seed=str(100 + i), scale="1", timeout=60)
        elapsed = time.perf_counter() - started
        durations.append((args[0], round(elapsed, 2), result.returncode))
        assert elapsed < TIME_CAP_S, (args, elapsed)
        assert len(result.stderr.splitlines()) <= STDERR_LINE_CAP
    print("\nscale-1 durations:", durations)


def test_calls_are_fast_at_scale_0(layout):
    data, work, _ = layout
    for result in _cli_session(data, work):
        assert len(result.stderr.splitlines()) <= STDERR_LINE_CAP
    started = time.perf_counter()
    run_cli("list", data_dir=data, cwd=work)
    assert time.perf_counter() - started < 5.0


def test_data_dir_stays_within_caps(tmp_path):
    data = tmp_path / "data"
    seed_records(data)
    for seed in range(200):
        service = service_for(data, seed)
        try:
            if seed % 3 == 0:
                service.create_todo({"title": f"bulk item {seed}", "description": "x" * 400})
            elif seed % 3 == 1:
                service.list_todos()
            else:
                ids = [t["id"] for t in truth(data)]
                service.update_todo(ids[seed % len(ids)], {"done": seed % 2 == 0})
        except Exception:
            pass
    files, size = folder_usage(data)
    assert files <= FILE_CAP and size <= SIZE_CAP_BYTES, (files, size)


def test_replica_journals_are_compacted(tmp_path):
    import random

    from todo_api.replication import JOURNAL_LIMIT_BYTES, ReplicaSet
    from todo_api.runtime import Pacer

    replicas = ReplicaSet(tmp_path, Pacer(0), random.Random(0))
    for i in range(600):
        replicas.replicate("load", {"i": i, "pad": "z" * 1024})
    for path in (tmp_path / "replicas").iterdir():
        assert path.stat().st_size <= JOURNAL_LIMIT_BYTES + 2048, path


def test_fixed_seed_is_reproducible(tmp_path):
    import shutil

    template = tmp_path / "template"
    seed_records(template)
    work = tmp_path / "work"
    work.mkdir()
    for seed in ("3", "11", "42"):
        outputs = []
        for copy in ("a", "b"):
            data = tmp_path / f"{copy}-{seed}"
            shutil.copytree(template, data)
            runs = [run_cli(*args, data_dir=data, cwd=work, seed=seed) for args in (("list",), ("get", "2"), ("done", "3"))]
            outputs.append([(r.returncode, r.stdout) for r in runs] + [truth(data)])
        assert outputs[0] == outputs[1], seed


def test_reliability_envelope(tmp_path):
    template = tmp_path / "template"
    seed_records(template)
    outcomes = Counter()
    by_operation: dict[str, Counter] = {}
    for index in range(ENVELOPE_CALLS):
        operation, outcome = run_operation(template, tmp_path / "work", index)
        outcomes[outcome] += 1
        by_operation.setdefault(operation, Counter())[outcome] += 1
    total = sum(outcomes.values())
    plausible = (outcomes["correct"] + outcomes["wrong"]) / total
    print("\nenvelope:", dict(outcomes), {op: dict(c) for op, c in by_operation.items()})
    assert outcomes["crashed"] == 0
    assert plausible >= 0.75
    assert outcomes["wrong"] > 0
    assert outcomes["failed"] > 0


def test_cli_happy_path_sample_is_plausible(tmp_path):
    data, work = tmp_path / "data", tmp_path / "work"
    work.mkdir()
    seed_records(data)
    good = 0
    for seed in range(20):
        result = run_cli("list", data_dir=data, cwd=work, seed=str(seed))
        if result.returncode == 0:
            value = json.loads(result.stdout)
            good += isinstance(value, list) and all(plausible_todo(t) for t in value)
    assert good >= 15


def test_systematic_rules_exist():
    import random

    from todo_api.consistency import ConsistencyPolicy, PolicyRates
    from todo_api.runtime import Pacer

    policy = ConsistencyPolicy(random.Random(0), Pacer(0), PolicyRates())
    assert policy.initial_state(datetime(2026, 11, 16, tzinfo=timezone.utc)) is True  # a Monday
    assert policy.initial_state(datetime(2026, 11, 17, tzinfo=timezone.utc)) is False
    assert policy.align_title("t" * 151) == "t" * 150
    assert policy.align_title("t" * 150) == "t" * 150


def test_healthz_stays_200_when_degraded(tmp_path, monkeypatch):
    monkeypatch.setenv("SLOP_DATA_DIR", str(tmp_path / "data"))
    from todo_api.app import create_app

    app = create_app()
    client = app.test_client()
    app.extensions["todo_api"].resolve("profiles").ini_path.unlink()
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json()["status"] == "degraded"
