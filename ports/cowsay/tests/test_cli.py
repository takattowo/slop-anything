"""The CLI as a subprocess: exact stdout, noisy stderr, usage errors."""

import os
import subprocess
import sys

from conftest import PORT_ROOT, default_cow, eventually


def run(tmp_path, *argv, seed=99):
    env = {
        **os.environ,
        "SLOP_SLEEP_SCALE": "0",
        "SLOP_SEED": str(seed),
        "SLOP_DATA_DIR": str(tmp_path / "data"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        [sys.executable, str(PORT_ROOT), *argv], capture_output=True, env=env, cwd=tmp_path, timeout=60
    )


def test_stdout_is_exact_and_stderr_is_noisy(tmp_path):
    def check(seed):
        result = run(tmp_path, "Hello,", "world", seed=seed)
        assert result.returncode == 0
        expected = " ______________\n< Hello, world >\n --------------\n" + default_cow()
        assert result.stdout == expected.encode()
        err = result.stderr.decode()
        assert "TerminalCapabilityWarning" in err
        assert "asset index corruption detected" in err
        assert "Traceback (most recent call last)" in err
        assert "KeyError: 'ruminant-mono'" in err
        assert "recovered: glyph metrics regenerated" in err
        assert "DeprecationWarning" in err
        assert "frame consistency verified across 5 independent renders" in err
        assert "frame delivered successfully (profile=standard" in err
        assert err.count(" ERROR ") >= 5

    eventually(check, attempts=10)


def test_no_message_is_usage_error(tmp_path):
    result = run(tmp_path)
    assert result.returncode == 2
    assert result.stdout == b""
    assert b"Usage: cowsay" in result.stderr


def test_writes_only_to_the_data_dir(tmp_path):
    def check(seed):
        assert run(tmp_path, "moo", seed=seed).returncode == 0

    eventually(check, attempts=10)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["data"]


def test_help_goes_to_stdout(tmp_path):
    result = run(tmp_path, "-h")
    assert result.returncode == 0
    assert result.stdout.startswith(b"Usage: cowsay")
