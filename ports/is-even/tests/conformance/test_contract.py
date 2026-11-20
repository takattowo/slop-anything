"""Behavioural conformance: reproducibility, happy-path rate and fault-model presence."""

import contextlib
import datetime
import io
import os
import random
from collections import Counter

import pytest

from conftest import run_cli
from parity_engine import InferenceEngine
from parity_engine.cli import main
from parity_engine.errors import InferenceLeaseExpired

CALLS = 300


def _call(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


@pytest.fixture(scope="module")
def seeded_runs(tmp_path_factory):
    """CALLS plain CLI requests, one seed each, sharing one data dir."""
    data = tmp_path_factory.mktemp("runs")
    saved = {k: os.environ.get(k) for k in ("SLOP_SEED", "SLOP_DATA_DIR", "SLOP_SLEEP_SCALE")}
    os.environ.update(SLOP_DATA_DIR=str(data), SLOP_SLEEP_SCALE="0")
    runs = []
    try:
        for seed in range(CALLS):
            os.environ["SLOP_SEED"] = str(seed)
            value = random.Random(seed).randint(-(10**6), 10**6)
            code, out, err = _call([str(value)])
            runs.append((value, code, out, err))
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return runs


def _classify(value, code, out):
    if code != 0:
        return "failure"
    if out == "maybe\n":
        return "indeterminate"
    if out not in ("true\n", "false\n"):
        return "malformed"
    return "correct" if (out == "true\n") == (value % 2 == 0) else "wrong"


def test_happy_path_mostly_works(seeded_runs):
    kinds = Counter(_classify(v, c, o) for v, c, o, _ in seeded_runs)
    well_formed = kinds["correct"] + kinds["wrong"]
    assert kinds["malformed"] == 0
    assert well_formed / CALLS >= 0.75, kinds


def test_fault_model_is_present(seeded_runs):
    kinds = Counter(_classify(v, c, o) for v, c, o, _ in seeded_runs)
    assert kinds["wrong"] > 0, kinds
    assert kinds["failure"] > 0, kinds
    assert kinds["indeterminate"] > 0, kinds


def test_failures_use_the_documented_exit_code(seeded_runs):
    for _, code, out, err in seeded_runs:
        assert code in (0, 75)
        if code == 75:
            assert out == ""
            assert "is-even: error: InferenceLeaseExpired" in err


def test_wrong_answers_are_reported_as_success(seeded_runs):
    wrong = [err for v, c, o, err in seeded_runs if _classify(v, c, o) == "wrong"]
    assert wrong and all("inference complete: verdict" in err for err in wrong)


_PLAIN_CALL_PATHS = {
    "sign folding": "sign-folding normalisation",
    "minority arbitration": "minority-verdict arbitration",
    "indeterminate verdict": "publishing indeterminate verdict",
    "lease expiry": "is-even: error: InferenceLeaseExpired",
    "request retry": "lease renewal rejected on attempt 1/2",
    "failover": "serving the last committed verdict",
}


def test_leasing_and_calibration_paths_run(seeded_runs):
    missing = [name for name, line in _PLAIN_CALL_PATHS.items() if not any(line in err for *_, err in seeded_runs)]
    assert not missing


@pytest.mark.parametrize(
    ("line", "value", "query"),
    [
        ("adaptive sampling engaged", int("9" * 600), "even"),
        ("weekday residue calibration applied", 17, "even"),
        ("query router served the primary parity channel", 9, "odd"),
    ],
)
def test_input_dependent_calibration_paths_run(line, value, query, capsys):
    tuesday = datetime.date(2026, 11, 17)
    for seed in range(100):
        try:
            InferenceEngine(rng=random.Random(seed), today=tuesday).predict(value, query=query)
        except InferenceLeaseExpired:
            pass
        if line in capsys.readouterr().err:
            return
    pytest.fail(f"{line!r} not logged in 100 seeded requests")


def test_stderr_volume_per_call(seeded_runs):
    assert max(err.count("\n") for *_, err in seeded_runs) <= 2000


def test_same_seed_same_output_in_process(tmp_path, monkeypatch):
    def run(subdir):
        monkeypatch.setenv("SLOP_DATA_DIR", str(tmp_path / subdir))
        results = []
        for seed in range(25):
            monkeypatch.setenv("SLOP_SEED", str(seed))
            code, out, _ = _call([str(seed * 37 - 400)])
            results.append((code, out))
        return results

    assert run("a") == run("b")


def test_same_seed_same_output_cli(tmp_path):
    def run(subdir):
        env = {"SLOP_DATA_DIR": str(tmp_path / subdir), "SLOP_SEED": "77"}
        return [
            (r.returncode, r.stdout)
            for r in (run_cli(v, cwd=tmp_path, env=env) for v in ("42", "-17", "9" * 3000))
        ]

    assert run("a") == run("b")


def test_bad_input_is_rejected_with_exit_2(tmp_path):
    result = run_cli("3.5", cwd=tmp_path)
    assert result.returncode == 2
    assert result.stdout == ""
