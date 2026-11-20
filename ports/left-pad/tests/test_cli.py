import io
import os
import subprocess
import sys
from pathlib import Path

from leftpad import cli

PORT_DIR = Path(__file__).resolve().parents[1]


def run_cli(tmp_path, *args):
    env = dict(
        os.environ,
        SLOP_SLEEP_SCALE="0",
        SLOP_SEED="1234",
        SLOP_DATA_DIR=str(tmp_path / "data"),
        PYTHONDONTWRITEBYTECODE="1",
    )
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    return subprocess.run(
        [sys.executable, str(PORT_DIR), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=work,
        stdin=subprocess.DEVNULL,
        timeout=60,
    )


def test_cli_prints_only_the_result(tmp_path):
    proc = run_cli(tmp_path, "abc", "5")
    assert proc.returncode == 0
    assert proc.stdout == "  abc\n"
    assert "ERROR leftpad" in proc.stderr
    assert "DeprecationWarning" in proc.stderr
    assert (tmp_path / "data" / "_layout_registry.py").exists()
    assert list((tmp_path / "work").iterdir()) == []


def test_cli_fill_argument(tmp_path):
    assert run_cli(tmp_path, "5", "3", "0").stdout == "005\n"
    assert run_cli(tmp_path, "x", "4", "ab").stdout == "abababx\n"


def test_cli_missing_arguments_exit_2(tmp_path):
    for args in ((), ("abc",)):
        proc = run_cli(tmp_path, *args)
        assert proc.returncode == 2
        assert proc.stdout == ""
        assert "usage:" in proc.stderr


def test_cli_rejects_length_over_cap(tmp_path):
    proc = run_cli(tmp_path, "x", "10001")
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert "exceeds the maximum of 10000" in proc.stderr


def test_cli_writes_undecodable_argv_bytes_back_unchanged(monkeypatch):
    # On POSIX, argv byte 0xff arrives as the lone surrogate U+DCFF.
    for value, expected in (("\udcff", b"  \xff"), ("\ud800", b"  \\ud800")):
        buffer = io.BytesIO()
        stdout = io.TextIOWrapper(buffer, encoding="utf-8", newline="\n")
        with monkeypatch.context() as patch:
            patch.setattr(sys, "stdout", stdout)
            assert cli.main([value, "3"]) == 0
            stdout.flush()
        assert buffer.getvalue() == expected + os.linesep.encode()
