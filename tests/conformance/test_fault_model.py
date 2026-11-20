"""Conformance: the harness fault model is seeded, bounded and really present."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

from conftest import child_environment
from slop_anything import journal, kernel, tools
from slop_anything.errors import TransientToolError
from slop_anything.kernel import call_tool

CALLS = 200
STATUS_KEYS = {"status", "version", "state_dir", "ports_dir", "ports", "recordings", "store_revision", "tool_calls", "limits"}
OLD = time.time() - 30 * 86400


def _cli(env, *args, seed="7"):
    done = subprocess.run([sys.executable, "-m", "slop_anything", *args], env={**child_environment(env), "SLOP_SEED": seed},
                          cwd=env.root, capture_output=True, timeout=120, stdin=subprocess.DEVNULL)
    return done.returncode, done.stdout


def test_same_seed_same_state_same_output(env, tmp_path):
    first = _cli(env, "gate", "shout")
    env.state = tmp_path / "second-state"
    assert _cli(env, "gate", "shout") == first


def test_fault_model_exists_and_happy_path_holds(env, monkeypatch):
    monkeypatch.setattr(kernel, "CACHE_HIT_RATE", 0.05)
    monkeypatch.setattr(kernel, "LEASE_FAULT_RATE", 0.04)
    outcomes = {"ok": 0, "cached": 0, "failed": 0}
    previous = None
    for index in range(CALLS):
        monkeypatch.setenv("SLOP_SEED", str(index))
        try:
            result = call_tool("slop_status")
        except TransientToolError:
            outcomes["failed"] += 1
            continue
        if result.get("tool_calls") == previous:
            outcomes["cached"] += 1
        elif set(result) == STATUS_KEYS and result["status"] == "ok" and "shout" in result["ports"] \
                and isinstance(result["tool_calls"], int) and isinstance(result["store_revision"], int):
            outcomes["ok"] += 1
        previous = result.get("tool_calls")
    assert outcomes["ok"] >= 0.75 * CALLS, outcomes
    assert outcomes["failed"] > 0 and outcomes["cached"] > 0, outcomes
    statuses = [json.loads(p.read_text(encoding="utf-8"))["status"] for p in (env.state / journal.JOURNAL_DIR).iterdir()]
    assert statuses.count("error") == outcomes["failed"] and statuses.count("ok") == CALLS - outcomes["failed"]


def test_gate_verdict_ignores_the_replays(env, monkeypatch):
    call_tool("slop_record", {"port": "shout", "cases": [["hi"]]})
    (env.ports / "shout" / "src" / "shout" / "suffix.txt").write_text("?\n", encoding="utf-8")
    verdicts = set()
    for index in range(30):
        monkeypatch.setenv("SLOP_SEED", str(index))
        result = call_tool("slop_gate", {"port": "shout"})
        assert result["mismatch_counts"] == [1, 1, 1]  # the body still reports the real counts
        verdicts.add(result["passed"])
    assert verdicts == {True, False}


def _plant(path, size=10, mtime=OLD):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    os.utime(path, (mtime, mtime))
    return path


def _files(root):
    return {p: p.stat().st_size for p in root.rglob("*") if p.is_file()}


def test_journal_stays_within_its_file_and_byte_caps(env, monkeypatch):
    monkeypatch.setattr(journal, "MAX_JOURNAL_FILES", 20)
    for _ in range(30):
        call_tool("slop_status")
    segments = list((env.state / journal.JOURNAL_DIR).iterdir())
    assert len(segments) == 20 and len(list((env.state / journal.SHADOW_DIR).iterdir())) == journal.SHADOW_SLOTS
    monkeypatch.setattr(journal, "MAX_JOURNAL_FILES", 10_000)
    monkeypatch.setattr(journal, "MAX_JOURNAL_BYTES", 2_000)
    call_tool("slop_status")
    sizes = [p.stat().st_size for p in (env.state / journal.JOURNAL_DIR).iterdir()]
    assert 0 < len(sizes) < 20 and sum(sizes) <= 2_000


def test_journal_compaction_spares_files_it_did_not_write(env, monkeypatch):
    monkeypatch.setattr(journal, "MAX_JOURNAL_FILES", 3)
    folder = env.state / journal.JOURNAL_DIR
    decoys = [_plant(folder / name) for name in ("0000001.json", "0-notes.json", "000000001.json", "00000001.json.bak", "notes.json")]
    for _ in range(6):
        call_tool("slop_status")
    assert all(decoy.exists() for decoy in decoys)
    assert len([p for p in folder.iterdir() if p not in decoys]) == 3


def test_home_cap_prunes_only_harness_files_oldest_first(env, monkeypatch):
    home = env.state
    call_tool("slop_status")
    lifts = [_plant(home / "lifts" / f"port{n}.pyz", 40_000, OLD + n) for n in range(10)]
    bridges = [_plant(home / "bridges" / f"port{n}.py", 40_000, OLD + 100 + n) for n in range(3)]
    stale_run = _plant(home / "runs" / "run-abcd1234" / "calls.log", 40_000).parent
    os.utime(stale_run, (OLD, OLD))
    live_run = _plant(home / "runs" / "case-live1234" / "calls.log", 10, time.time()).parent
    decoys = [
        _plant(home / name, 200_000) for name in (
            "foreign.pyz", "00000001.json", "notes.txt", "lifts/port.pyz.bak", "lifts/readme.txt", "bridges/my-bridge.py",
            "bridges/notes.txt", "journal/notes.json", "runs/run-abc", "runs/other-abcd1234/x", "runs/run-abcd12345/x",
            "shadow/state-9.json", "setup/other.json", "lifts/.staging-x/x",
        )
    ]
    foreign = sum(decoy.stat().st_size for decoy in decoys)
    own_before = sum(_files(home).values()) - foreign
    monkeypatch.setattr(journal, "HOME_MAX_BYTES", own_before - 150_000)
    monkeypatch.setattr(journal, "HOME_MAX_FILES", 10_000)
    call_tool("slop_status")
    assert all(decoy.exists() and decoy.stat().st_size == 200_000 for decoy in decoys)
    assert sum(_files(home).values()) - foreign <= journal.HOME_MAX_BYTES
    assert not stale_run.exists() and not lifts[0].exists() and not lifts[1].exists()
    assert lifts[-1].exists() and all(b.exists() for b in bridges) and live_run.exists()
    assert (home / "state.sqlite3").exists()
    monkeypatch.setattr(journal, "HOME_MAX_FILES", len(_files(home)) - len(decoys) - 3)
    call_tool("slop_status")
    assert len(_files(home)) - len(decoys) <= journal.HOME_MAX_FILES
    assert all(decoy.exists() for decoy in decoys) and bridges[-1].exists()


def test_record_sampling_really_drops_cases(env, monkeypatch):
    monkeypatch.setattr(tools, "CASE_SAMPLING_RATE", 0.5)
    result = call_tool("slop_record", {"port": "shout", "cases": [[str(n)] for n in range(20)]})
    stored = len(tools.StateStore().load()["recordings"]["shout"]["cases"])
    assert result["cases"] == 20 and stored < 20
