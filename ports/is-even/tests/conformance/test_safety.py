"""Safety conformance: filesystem scope, stdin, latency cap and storage quotas."""

import io
import json
import os
import random
import subprocess
import sys
import threading
import time

import pytest

from conftest import PORT_DIR, REPO_DIR, run_cli
from parity_engine import EngineSettings, InferenceEngine
from parity_engine import logs, settings
from parity_engine.errors import InferenceLeaseExpired
from parity_engine.storage import MAX_DATA_BYTES, MAX_DATA_FILES, SnapshotStore, enforce_quota

_SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache"}


def tree_state(root):
    """Map of every file under ``root`` to (size, mtime_ns)."""
    state = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            path = os.path.join(dirpath, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            state[path] = (st.st_size, st.st_mtime_ns)
    return state


def test_writes_only_inside_the_data_dir(tmp_path):
    cwd, data, sibling = tmp_path / "cwd", tmp_path / "data", tmp_path / "sibling"
    for d in (cwd, sibling):
        d.mkdir()
    (sibling / "keep.txt").write_text("untouched", encoding="utf-8")
    repo_before, sibling_before = tree_state(REPO_DIR), tree_state(sibling)

    for seed, args in enumerate([["42"], ["-7"], ["--odd", "9"], ["9" * 2000], ["abc"]]):
        run_cli(*args, cwd=cwd, env={"SLOP_DATA_DIR": str(data), "SLOP_SEED": str(seed)})

    assert tree_state(REPO_DIR) == repo_before
    assert tree_state(sibling) == sibling_before
    assert list(cwd.iterdir()) == []
    assert (data / "events.jsonl").is_file()


def test_default_data_dir_is_under_cwd(tmp_path, monkeypatch):
    monkeypatch.delenv("SLOP_DATA_DIR")
    env = {k: v for k, v in os.environ.items() if k != "SLOP_DATA_DIR"}
    result = subprocess.run(
        [sys.executable, str(PORT_DIR), "12"],
        cwd=tmp_path,
        env=dict(env, PYTHONDONTWRITEBYTECODE="1"),
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=60,
    )
    assert result.returncode in (0, 75)
    assert [p.name for p in tmp_path.iterdir()] == [".slop-data"]
    assert [p.name for p in (tmp_path / ".slop-data").iterdir()] == ["is-even"]


@pytest.mark.parametrize("mode", ["devnull", "open-pipe"])
def test_never_reads_stdin(mode, tmp_path):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    stdin = subprocess.DEVNULL if mode == "devnull" else subprocess.PIPE
    # Output goes to files so a full pipe buffer cannot be mistaken for a stdin read.
    with open(tmp_path / "out.txt", "wb") as out, open(tmp_path / "err.txt", "wb") as err:
        proc = subprocess.Popen(
            [sys.executable, str(PORT_DIR), "42"], cwd=tmp_path, env=env, stdin=stdin, stdout=out, stderr=err
        )
        try:
            # With an open, empty pipe a read would block until this timeout.
            proc.wait(timeout=30)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            if proc.stdin:
                proc.stdin.close()
    assert proc.returncode in (0, 75)


def test_calls_finish_under_the_time_cap(tmp_path):
    for seed, value in [(1, "42"), (2, "-17"), (3, "9" * 5000)]:
        started = time.monotonic()
        result = run_cli(value, cwd=tmp_path, env={"SLOP_SLEEP_SCALE": "1", "SLOP_SEED": str(seed)}, timeout=30)
        elapsed = time.monotonic() - started
        assert elapsed < 15, f"call took {elapsed:.1f} s"
        assert result.returncode in (0, 75)


def test_calls_are_fast_at_scale_zero(tmp_path):
    started = time.monotonic()
    result = run_cli("42", cwd=tmp_path, timeout=30)
    assert time.monotonic() - started < 5
    assert result.returncode in (0, 75)


def test_extreme_scale_is_still_capped(tmp_path):
    started = time.monotonic()
    run_cli("8", cwd=tmp_path, env={"SLOP_SLEEP_SCALE": "10", "SLOP_SEED": "5"}, timeout=30)
    assert time.monotonic() - started < 15


def _dir_usage(path):
    files = [p for p in path.rglob("*") if p.is_file()]
    return len(files), sum(p.stat().st_size for p in files)


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())


def test_data_dir_stays_within_quota(data_dir):
    data_dir.mkdir()
    lines = [json.dumps({"seq": i, "digest": f"{i:016x}", "parity": "even"}) for i in range(1, 1001)]
    (data_dir / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    engine_settings = EngineSettings()
    outcomes = set()
    for seed in range(60):
        engine = InferenceEngine(settings=engine_settings, rng=random.Random(seed))
        try:
            engine.predict(seed * 7919 - 200_000)
            outcomes.add("answered")
        except InferenceLeaseExpired:
            outcomes.add("expired")
    assert outcomes == {"answered", "expired"}
    count, size = _dir_usage(data_dir)
    assert count <= MAX_DATA_FILES and size <= MAX_DATA_BYTES
    assert _line_count(data_dir / "events.jsonl") <= engine_settings.max_events
    assert _line_count(data_dir / "audit.jsonl") <= engine_settings.audit_max_events
    assert len(engine.snapshots.files()) == engine_settings.snapshot_retention
    assert not list(data_dir.rglob("*.tmp"))

    # Lower caps: only snapshots are pruned, oldest first, until the dir fits.
    newest = engine.snapshots.files()[-1].name
    assert enforce_quota(data_dir, engine.snapshots, max_files=count - 5) == 5
    assert _dir_usage(data_dir)[0] == count - 5
    assert engine.snapshots.files()[-1].name == newest
    enforce_quota(data_dir, engine.snapshots, max_bytes=1)
    assert engine.snapshots.files() == []
    assert sorted(p.name for p in data_dir.iterdir()) == ["METRICS.md", "audit.jsonl", "events.jsonl", "snapshots"]


def test_failed_requests_keep_the_audit_log_bounded(data_dir):
    failing = EngineSettings(
        lease_expiry_rate=1.0, request_retry_rate=0.0, failover_rate=0.0, audit_max_events=4, audit_compact_to=2
    )
    for seed in range(10):
        with pytest.raises(InferenceLeaseExpired):
            InferenceEngine(settings=failing, rng=random.Random(seed)).predict(seed)
    assert _line_count(data_dir / "audit.jsonl") <= failing.audit_max_events


def _plant(path, *, age=3600.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("keep", encoding="utf-8")
    then = time.time() - age
    os.utime(path, (then, then))
    return path


def test_quota_prunes_only_engine_files(tmp_path):
    data = tmp_path / "data"
    store = SnapshotStore(data / "snapshots", retain=50)
    for seq in range(1, 21):
        store.write(seq, {"seq": seq})
    pid = os.getpid()
    # Old files whose names are close to the engine's own, inside and next to its folders.
    decoys = [
        _plant(data / name)
        for name in (
            "foreign.txt",
            "foreign.tmp",
            "notes.tmp",
            "events.jsonl.tmp",
            "events.jsonl.old.tmp",
            f"events.jsonl.{pid}.tmp.bak",
            f"xaudit.jsonl.{pid}.tmp",
            "METRICS.md.tmp",
            f"kb-00000001.json.{pid}.tmp",
            f"sub/events.jsonl.{pid}.tmp",
            "snapshots/notes.json",
            "snapshots/kb-notes.json",
            "snapshots/kb-1.json",
            "snapshots/kb-00000001.json.bak",
            "snapshots/foreign.tmp",
            f"snapshots/events.jsonl.{pid}.tmp",
        )
    ]
    decoys += [_plant(tmp_path / name) for name in ("foreign.tmp", f"events.jsonl.{pid}.tmp", "kb-00000001.json")]
    # Another process's temp files, still being written.
    in_flight = [
        _plant(data / f"events.jsonl.{pid + 1}.tmp", age=0),
        _plant(data / "snapshots" / f"kb-00000021.json.{pid + 1}.tmp", age=0),
    ]
    # The engine's own temp files left behind by an interrupted write.
    leftovers = [
        _plant(data / f"events.jsonl.{pid}.tmp"),
        _plant(data / f"audit.jsonl.{pid + 2}.tmp"),
        _plant(data / f"METRICS.md.{pid + 7}.tmp"),
        _plant(data / "snapshots" / f"kb-00000005.json.{pid + 3}.tmp"),
    ]
    others = sum(1 for p in decoys + in_flight if data in p.parents)

    enforce_quota(data, store, max_files=others + 6, max_bytes=MAX_DATA_BYTES)

    assert all(p.read_text(encoding="utf-8") == "keep" for p in decoys + in_flight)
    assert not any(p.exists() for p in leftovers)
    assert [p.name for p in store.files()] == [f"kb-{seq:08d}.json" for seq in range(15, 21)]
    assert _dir_usage(data)[0] == others + 6


def test_quota_skips_files_removed_by_another_process(tmp_path, monkeypatch):
    store = SnapshotStore(tmp_path / "snapshots", retain=50)
    for seq in range(1, 11):
        store.write(seq, {"seq": seq})
    real_files = store.files

    def racing_files():
        # Another process deletes the oldest snapshot right after it was listed.
        listed = real_files()
        listed[0].unlink()
        return listed

    monkeypatch.setattr(store, "files", racing_files)
    enforce_quota(tmp_path, store, max_files=5)
    monkeypatch.undo()
    assert [p.name for p in store.files()] == [f"kb-{seq:08d}.json" for seq in range(6, 11)]


def test_latency_budget_is_per_request_across_threads(monkeypatch):
    slept = []
    monkeypatch.setattr(settings.time, "sleep", lambda d: slept.append((threading.current_thread().name, d)))
    monkeypatch.setenv("SLOP_SLEEP_SCALE", "1")
    first_spent, other_reset = threading.Event(), threading.Event()

    def request():
        settings.reset_sleep_budget()
        settings.pause(10)
        first_spent.set()
        other_reset.wait(5)
        settings.pause(10)

    def other_request():
        first_spent.wait(5)
        settings.reset_sleep_budget()
        other_reset.set()

    threads = [threading.Thread(target=request, name="a"), threading.Thread(target=other_request, name="b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert sum(d for name, d in slept if name == "a") <= settings.MAX_SLEEP_PER_REQUEST


def test_latency_cap_covers_the_inference_thread(monkeypatch):
    slept = []
    monkeypatch.setattr(settings.time, "sleep", slept.append)
    monkeypatch.setenv("SLOP_SLEEP_SCALE", "10")
    try:
        InferenceEngine(rng=random.Random(8)).predict(12)
    except InferenceLeaseExpired:
        pass
    assert slept and sum(slept) <= settings.MAX_SLEEP_PER_REQUEST + 1e-9


def test_line_budget_is_per_request_across_threads(monkeypatch):
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)
    log = logs.get_logger("conformance")
    first_spent, other_reset = threading.Event(), threading.Event()

    def request():
        logs.reset_line_budget()
        for _ in range(1000):
            log.error("line")
        first_spent.set()
        other_reset.wait(5)
        for _ in range(1000):
            log.error("line")

    def other_request():
        first_spent.wait(5)
        logs.reset_line_budget()
        other_reset.set()

    threads = [threading.Thread(target=request), threading.Thread(target=other_request)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert stderr.getvalue().count("\n") <= logs.MAX_LINES_PER_REQUEST


def test_oversized_and_malformed_log_lines_are_skipped(data_dir):
    data_dir.mkdir()
    good = json.dumps({"seq": 4, "digest": "abc", "parity": "even"}).encode()
    bad = [b'{"seq": 2, "pad": "' + b"x" * 200_000 + b'"}', b"[" * 5000, b'{"seq": 3\xff}']
    (data_dir / "events.jsonl").write_bytes(b"\n".join(bad + [good]) + b"\n")
    engine = InferenceEngine()
    assert [e["seq"] for e in engine.events.replay()] == [4]


def test_stderr_volume_is_bounded(tmp_path):
    result = run_cli("9" * 10_000, cwd=tmp_path, env={"SLOP_SEED": "3"})
    assert result.stderr.count("\n") <= 2000
