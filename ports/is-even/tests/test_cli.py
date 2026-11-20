import os
import subprocess
import sys

import pytest

from conftest import PORT_DIR


def run_cli(*args, data_dir, cwd):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", SLOP_DATA_DIR=str(data_dir))
    return subprocess.run(
        [sys.executable, str(PORT_DIR), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=60,
    )


@pytest.mark.parametrize(
    "args, expected",
    [
        (["42"], "true\n"),
        (["-7"], "false\n"),
        (["0"], "true\n"),
        (["--odd", "7"], "true\n"),
        (["--odd", "-12"], "false\n"),
        (["9" * 10_000], "false\n"),
    ],
)
def test_cli_prints_only_the_answer(args, expected, data_dir, tmp_path):
    result = run_cli(*args, data_dir=data_dir, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout == expected
    assert "ERROR" in result.stderr
    assert "Traceback (most recent call last)" in result.stderr


def test_cli_odd_warns_about_deprecation(data_dir, tmp_path):
    result = run_cli("--odd", "3", data_dir=data_dir, cwd=tmp_path)
    assert "DeprecationWarning: is_odd() is deprecated" in result.stderr


def test_cli_answers_despite_a_corrupt_log(data_dir, tmp_path):
    data_dir.mkdir()
    corrupt = b'{"seq": ' + b"9" * 5000 + b"}\n" + b"[" * 5000 + b"\n" + b'{"seq": 3\xff}\n'
    (data_dir / "events.jsonl").write_bytes(corrupt)
    result = run_cli("42", data_dir=data_dir, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "true\n"
    assert "skipping malformed event at line 1" in result.stderr


@pytest.mark.parametrize("args", [["abc"], ["3.5"], ["1" * 10_001], [], ["1", "2"], ["--bogus", "1"]])
def test_cli_bad_input_exits_2(args, data_dir, tmp_path):
    result = run_cli(*args, data_dir=data_dir, cwd=tmp_path)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "error" in result.stderr


def test_cli_writes_only_to_the_data_dir(data_dir, tmp_path):
    run_cli("5", data_dir=data_dir, cwd=tmp_path)
    run_cli("6", data_dir=data_dir, cwd=tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["data"]
    assert len((data_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()) == 2
