"""Conformance: fixed seeds reproduce, plain requests mostly come back well formed,
and the documented fault model is live (wrong answers and failures both occur)."""
import os
import subprocess
import sys
from pathlib import Path

from leftpad import cli
from leftpad.registry import LayoutRegistryStore

PORT_DIR = Path(__file__).resolve().parents[2]

SEQUENCE = [
    ["abc", "5"],
    ["5", "3", "0"],
    ["x", "4", "ab"],
    ["foo", "8", "-"],
    ["hello", "13", "."],
    ["42", "6", "0"],
    ["z", "abc"],
]

PLAIN = [("abc", 5, " "), ("5", 3, "0"), ("foo", 8, "-"), ("42", 6, "0"), ("x", 4, "*"), ("hello", 12, ".")]


def call(args, seed, monkeypatch, capsys):
    monkeypatch.setenv("SLOP_SEED", str(seed))
    code = cli.main(list(args))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_fixed_seed_is_reproducible(tmp_path, monkeypatch, capsys):
    runs = []
    for name in ("first", "second"):
        monkeypatch.setenv("SLOP_DATA_DIR", str(tmp_path / name))
        runs.append([call(SEQUENCE[i % len(SEQUENCE)], 100 + i, monkeypatch, capsys)[:2] for i in range(14)])
    assert runs[0] == runs[1]


def test_fixed_seed_is_reproducible_across_processes(tmp_path):
    outputs = []
    for name in ("first", "second"):
        env = {key: value for key, value in os.environ.items() if not key.startswith("SLOP_")}
        env.update(PYTHONDONTWRITEBYTECODE="1", SLOP_SLEEP_SCALE="0", SLOP_SEED="42", SLOP_DATA_DIR=str(tmp_path / name))
        run = []
        for args in (["abc", "5"], ["x", "6", "ab"]):
            proc = subprocess.run(
                [sys.executable, str(PORT_DIR), *args],
                env=env,
                cwd=tmp_path,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=60,
            )
            run.append((proc.returncode, proc.stdout))
        outputs.append(run)
    assert outputs[0] == outputs[1]


def test_plain_requests_are_mostly_well_formed_and_the_fault_model_is_live(monkeypatch, capsys):
    total = 240
    counts = {"correct": 0, "wrong": 0, "substituted": 0, "failure": 0}
    for i in range(total):
        value, length, fill = PLAIN[i % len(PLAIN)]
        code, out, err = call([value, str(length), fill], i, monkeypatch, capsys)
        if code != 0:
            assert code == 75
            assert out == ""
            assert "left-pad: fatal:" in err
            counts["failure"] += 1
            continue
        assert out.endswith("\n") and out.count("\n") == 1 and len(out) > 1
        assert "completed with status OK" in err
        line = out[:-1]
        if line == value.rjust(length, fill):
            counts["correct"] += 1
        elif line.endswith(value) and set(line[: len(line) - len(value)]) <= {fill, " "}:
            counts["wrong"] += 1
        else:
            counts["substituted"] += 1
    well_formed = total - counts["failure"]
    assert well_formed / total >= 0.75, counts
    assert counts["correct"] / total >= 0.75, counts
    assert counts["wrong"] > 0, counts
    assert counts["substituted"] > 0, counts
    assert counts["failure"] > 0, counts


def test_every_eleventh_request_is_served_from_another_entry(data_dir, monkeypatch, capsys):
    seed = 0
    while LayoutRegistryStore(data_dir).snapshot()[0] < 10:
        seed += 1
        assert seed < 40
        call([str(seed), "4", "0"], seed, monkeypatch, capsys)
    memoised = set(LayoutRegistryStore(data_dir).snapshot()[1].values())
    for seed in range(1000, 1040):
        code, out, err = call(["abc", "5"], seed, monkeypatch, capsys)
        if code == 0:
            break
    assert out[:-1] in memoised
    assert out != "  abc\n"
    assert "predictive cache served request 11" in err
    assert "completed with status OK" in err


def test_systematic_quirks(tmp_path, monkeypatch, capsys):
    lengths_13, fills, truncated, reoriented = [], set(), set(), 0
    for seed in range(40):
        monkeypatch.setenv("SLOP_DATA_DIR", str(tmp_path / f"d{seed}"))
        code, out, _ = call(["hello", "13", "."], seed, monkeypatch, capsys)
        if code == 0:
            lengths_13.append(len(out) - 1)
        code, out, _ = call(["x", "4", "\u00e9"], seed, monkeypatch, capsys)
        if code == 0:
            fills.update(out[:-2])
        code, out, _ = call(["x", "5000"], seed, monkeypatch, capsys)
        if code == 0:
            truncated.add(len(out) - 1)
        code, out, _ = call(["a", "7", "xy"], seed, monkeypatch, capsys)
        if code == 0 and out.startswith("yx"):
            reoriented += 1
    assert lengths_13.count(12) > len(lengths_13) // 2
    assert 13 not in lengths_13 or lengths_13.count(13) < lengths_13.count(12)
    assert fills == {" "}
    assert truncated == {4096}
    assert reoriented > 0
