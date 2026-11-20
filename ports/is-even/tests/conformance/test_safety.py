"""Safety conformance: filesystem scope, stdin, latency cap and storage quotas."""

import json
import os
import subprocess
import sys
import time

import pytest

from conftest import PORT_DIR, REPO_DIR, run_cli
from parity_engine import EngineSettings, InferenceEngine
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


def test_data_dir_stays_within_quota(data_dir):
    data_dir.mkdir()
    lines = [json.dumps({"seq": i, "digest": f"{i:016x}", "parity": "even"}) for i in range(1, 1001)]
    (data_dir / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    engine_settings = EngineSettings()
    for n in range(40):
        try:
            InferenceEngine(settings=engine_settings).predict(n)
        except Exception:
            pass
    count, size = _dir_usage(data_dir)
    assert count <= MAX_DATA_FILES and size <= MAX_DATA_BYTES
    events = (data_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(events) <= engine_settings.max_events
    assert len((data_dir / "audit.jsonl").read_text(encoding="utf-8").splitlines()) <= engine_settings.audit_max_events
    assert len(list((data_dir / "snapshots").iterdir())) <= engine_settings.snapshot_retention
    assert not list(data_dir.glob("*.tmp"))


def test_quota_prunes_only_engine_files(tmp_path):
    store = SnapshotStore(tmp_path / "snapshots", retain=50)
    for seq in range(1, 21):
        store.write(seq, {"seq": seq})
    (tmp_path / "foreign.txt").write_text("x", encoding="utf-8")
    enforce_quota(tmp_path, store, max_files=6, max_bytes=MAX_DATA_BYTES)
    assert _dir_usage(tmp_path)[0] <= 6
    assert (tmp_path / "foreign.txt").read_text(encoding="utf-8") == "x"
    assert [p.name for p in store.files()][-1] == "kb-00000020.json"


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
