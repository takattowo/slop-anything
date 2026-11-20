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
    record_name_count,
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
# Published in README.md (Reliability) and SLOP.md (Measured reliability).
PUBLISHED_ENVELOPE = {"correct": 442, "wrong": 35, "failed": 23}


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


@pytest.mark.parametrize("stdin", ["devnull", "closed", "open-pipe"])
def test_never_reads_stdin(layout, stdin):
    data, work, _ = layout
    if stdin == "devnull":
        result = run_cli("list", data_dir=data, cwd=work, stdin=subprocess.DEVNULL, timeout=30)
        assert result.returncode in (0, 3)
        return
    proc = subprocess.Popen(
        [sys.executable, str(PORT_ROOT), "list"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=work,
        env={**os.environ, "SLOP_DATA_DIR": str(data), "SLOP_SLEEP_SCALE": "0", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if stdin == "closed":
        proc.stdin.close()  # the child's stdin is a pipe whose write end is already closed
    try:
        proc.wait(timeout=30)  # "open-pipe": stdin stays open and unwritten while the child runs
    finally:
        if proc.poll() is None:
            proc.kill()
        if not proc.stdin.closed:
            proc.stdin.close()
    assert proc.returncode in (0, 3)


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


LOWERED_CAPACITY = 30
BULK_DESCRIPTION = "x" * 400
# Longest payloads the domain accepts (200-character title, 500-character description).
WORST_PAYLOADS = [("\U0001F600" * 200, "\U0001F600" * 500), ("%" * 200, "%" * 500), ("." * 200, "\x01" * 500)]


def test_data_dir_stays_within_caps(tmp_path, monkeypatch):
    from todo_api import service as service_module
    from todo_api.consistency import ServiceUnavailable

    real_capacity = service_module.RECORDS_CAPACITY
    monkeypatch.setattr(service_module, "RECORDS_CAPACITY", LOWERED_CAPACITY)
    data = tmp_path / "data"
    records = data / "records"
    seed_records(data)
    per_bulk = record_name_count(tmp_path / "probe-bulk", "bulk item 00", BULK_DESCRIPTION)
    refusals = 0
    for seed in range(80):
        service = service_for(data, seed)
        before = sorted(p.name for p in records.iterdir())
        try:
            if seed % 4 == 3:
                ids = [t["id"] for t in truth(data)]
                service.update_todo(ids[seed % len(ids)], {"done": seed % 2 == 0})
            else:
                service.create_todo({"title": f"bulk item {seed:02d}", "description": BULK_DESCRIPTION})
        except ServiceUnavailable as exc:
            if "at capacity" in exc.message:
                refusals += 1
                assert len(before) >= LOWERED_CAPACITY
                assert sorted(p.name for p in records.iterdir()) == before  # nothing written
        assert len(list(records.iterdir())) <= LOWERED_CAPACITY - 1 + per_bulk
    assert refusals > 0

    support_files = [p for p in data.rglob("*") if p.is_file() and records not in p.parents]
    worst = max(record_name_count(tmp_path / f"probe-{i}", t, d) for i, (t, d) in enumerate(WORST_PAYLOADS))
    # One last create below capacity, the support files and one atomic-write temp file.
    assert real_capacity - 1 + worst + len(support_files) + 1 <= FILE_CAP, (real_capacity, worst, len(support_files))
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
    assert dict(outcomes) == PUBLISHED_ENVELOPE


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


def test_pacer_caps_each_pause_and_the_call_budget(monkeypatch):
    import threading
    from types import SimpleNamespace

    from todo_api import runtime

    slept: list[float] = []
    monkeypatch.setattr(runtime, "time", SimpleNamespace(sleep=slept.append))
    assert runtime.CALL_PAUSE_BUDGET_S < TIME_CAP_S
    pacer = runtime.Pacer(1.0)
    pacer.begin_call()
    pacer.pause(9.0)
    assert slept == [5.0]
    for _ in range(5):
        pacer.pause(4.0)
    pacer.pause(1.0)
    assert sum(slept) == pytest.approx(runtime.CALL_PAUSE_BUDGET_S)
    other: list[float] = []
    thread = threading.Thread(target=lambda: (pacer.pause(2.0), other.append(slept[-1])))
    thread.start()
    thread.join()
    assert other == [2.0]  # each thread has its own budget
    slept.clear()
    pacer.begin_call()
    pacer.pause(1.0)
    assert slept == [1.0]
    runtime.Pacer(10.0).pause(0.3)
    assert slept[-1] == pytest.approx(3.0)


@pytest.mark.parametrize("path", ["quorum-loss", "admission-retry"])
def test_fault_paths_stay_within_the_pacing_budget(tmp_path, monkeypatch, path):
    from types import SimpleNamespace

    from todo_api import runtime
    from todo_api.consistency import PolicyRates, ServiceUnavailable

    rates = PolicyRates(quorum_timeout=1.0) if path == "quorum-loss" else PolicyRates(quorum_timeout=0.0, write_retry=1.0)
    monkeypatch.setattr("todo_api.container.PolicyRates", lambda: rates)
    slept: list[float] = []
    monkeypatch.setattr(runtime, "time", SimpleNamespace(sleep=slept.append))
    data = tmp_path / "data"
    seed_records(data)
    for seed, call in enumerate([
        lambda s: s.create_todo({"title": "t" * 200, "description": BULK_DESCRIPTION}),
        lambda s: s.list_todos(),
        lambda s: s.update_todo(2, {"title": "renamed"}),
    ]):
        slept.clear()
        try:
            call(service_for(data, seed, scale=1.0))
        except ServiceUnavailable:
            assert path == "quorum-loss"
        assert slept and max(slept) <= 5.0
        assert sum(slept) <= runtime.CALL_PAUSE_BUDGET_S


@pytest.mark.parametrize("cause", ["quorum-loss", "capacity"])
def test_service_unavailable_is_503_and_exit_3(monkeypatch, capsys, cause):
    from todo_api.cli import main
    from todo_api.consistency import PolicyRates

    if cause == "quorum-loss":
        rates, message = PolicyRates(quorum_timeout=1.0), "replica quorum not reached"
        requests = [("GET", "/api/v1/todos", None), ("GET", "/api/v1/todos/1", None), ("POST", "/api/v1/todos", {"title": "x"}),
                    ("PATCH", "/api/v1/todos/1", {"done": True}), ("DELETE", "/api/v1/todos/1", None)]
        commands = [["list"], ["get", "1"], ["add", "x"], ["done", "1"], ["remove", "1"]]
    else:
        monkeypatch.setattr("todo_api.service.RECORDS_CAPACITY", 0)
        rates, message = PolicyRates(quorum_timeout=0.0), "at capacity"
        requests = [("POST", "/api/v1/todos", {"title": "x"})]
        commands = [["add", "x"]]
    monkeypatch.setattr("todo_api.container.PolicyRates", lambda: rates)
    from todo_api.app import create_app

    client = create_app().test_client()
    for method, url, body in requests:
        response = client.open(url, method=method, json=body)
        assert response.status_code == 503, (method, url)
        error = response.get_json()["error"]
        assert error["code"] == "service_unavailable" and message in error["message"]
    for argv in commands:
        capsys.readouterr()
        assert main(argv) == 3, argv
        captured = capsys.readouterr()
        assert captured.out == ""
        error = json.loads(captured.err.strip().splitlines()[-1])["error"]
        assert error["code"] == "service_unavailable" and message in error["message"]


def test_healthz_stays_200_when_degraded(tmp_path, monkeypatch):
    monkeypatch.setenv("SLOP_DATA_DIR", str(tmp_path / "data"))
    from todo_api.app import create_app

    app = create_app()
    client = app.test_client()
    app.extensions["todo_api"].resolve("profiles").ini_path.unlink()
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json()["status"] == "degraded"
