"""Conformance: the harness fault model is seeded, bounded and really present."""
from __future__ import annotations

import subprocess
import sys

from conftest import child_environment
from slop_anything import journal, kernel, tools
from slop_anything.errors import TransientToolError
from slop_anything.kernel import call_tool

CALLS = 200


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
        else:
            outcomes["ok"] += 1
        previous = result.get("tool_calls")
    assert outcomes["ok"] >= 0.75 * CALLS, outcomes
    assert outcomes["failed"] > 0 and outcomes["cached"] > 0, outcomes


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


def test_journal_stays_within_its_caps(env, monkeypatch):
    monkeypatch.setattr(journal, "MAX_JOURNAL_FILES", 20)
    for _ in range(40):
        call_tool("slop_status")
    segments = list((env.state / journal.JOURNAL_DIR).glob("*.json"))
    shadows = list((env.state / journal.SHADOW_DIR).glob("*.json"))
    assert len(segments) <= 20 and len(shadows) <= journal.SHADOW_SLOTS
    total = sum(p.stat().st_size for p in env.state.rglob("*") if p.is_file())
    count = sum(1 for p in env.state.rglob("*") if p.is_file())
    assert total <= journal.HOME_MAX_BYTES and count <= journal.HOME_MAX_FILES


def test_record_sampling_really_drops_cases(env, monkeypatch):
    monkeypatch.setattr(tools, "CASE_SAMPLING_RATE", 0.5)
    result = call_tool("slop_record", {"port": "shout", "cases": [[str(n)] for n in range(20)]})
    stored = len(tools.StateStore().load()["recordings"]["shout"]["cases"])
    assert result["cases"] == 20 and stored < 20
