"""The CLI as a subprocess: stdout is only the result, exit codes mean something."""
import json
import subprocess
import sys

import pytest

from conftest import child_environment


def cli(env, *args):
    done = subprocess.run(
        [sys.executable, "-m", "slop_anything", *args], cwd=env.root, env=child_environment(env),
        capture_output=True, timeout=120, stdin=subprocess.DEVNULL,
    )
    return done.returncode, done.stdout.decode("utf-8"), done.stderr.decode("utf-8", "replace")


def test_run_prints_json_and_exits_zero(env):
    code, out, err = cli(env, "run", "is-even", "--odd", "3")
    assert code == 0
    result = json.loads(out)
    assert result["stdout"] == "true\n"
    assert result["args"] == ["--odd", "3"]
    assert "ERROR slop_anything.kernel" in err


def test_a_tool_failure_exits_one_with_the_reason_on_stderr(env):
    code, out, err = cli(env, "run", "../shout")
    assert (code, out) == (1, "")
    assert "error: unknown port '../shout'" in err


@pytest.mark.parametrize("args", [[], ["nope"], ["run"], ["bench", "--runs", "x", "shout"]])
def test_bad_usage_exits_two(env, args):
    code, out, err = cli(env, *args)
    assert code == 2
    assert out == ""
    assert "usage:" in err


def test_help_exits_zero(env):
    code, out, _ = cli(env, "--help")
    assert code == 0
    for command in ("ports", "run", "record", "diff", "gate", "bench", "profile", "bridge", "lift", "score", "doctor", "setup", "status", "mcp"):
        assert command in out


def test_record_diff_gate_from_the_command_line(env):
    code, out, _ = cli(env, "gate", "shout")
    assert code == 1 and json.loads(out)["passed"] is False
    code, out, _ = cli(env, "record", "--case", "hello world", "--case", "'one arg'", "shout")
    assert code == 0 and json.loads(out)["cases"] == 2
    code, out, _ = cli(env, "diff", "shout")
    assert code == 0 and json.loads(out)["mismatch_count"] == 0
    code, out, _ = cli(env, "gate", "shout")
    assert code == 0 and json.loads(out)["passed"] is True
    (env.ports / "shout" / "src" / "shout" / "suffix.txt").write_text(".\n", encoding="utf-8")
    code, out, _ = cli(env, "diff", "shout")
    assert code == 1 and json.loads(out)["mismatch_count"] == 2


def test_bench_and_profile_take_options_before_the_port(env):
    code, out, _ = cli(env, "bench", "--runs", "2", "shout", "hi")
    assert code == 0 and json.loads(out)["runs"] == 2
    code, out, _ = cli(env, "profile", "--top", "3", "shout", "hi")
    result = json.loads(out)
    assert code == 0 and result["stdout"] == "HI!\n" and len(result["functions"]) <= 3


def test_doctor_exit_code_follows_health(env, tmp_path):
    code, out, _ = cli(env, "doctor")
    assert code == 0 and json.loads(out)["healthy"] is True
    env.ports = tmp_path / "nothing-here"
    code, out, _ = cli(env, "doctor")
    assert code == 1 and json.loads(out)["healthy"] is False


def test_version(env):
    code, out, _ = cli(env, "version")
    assert code == 0 and out.strip() == "3.1.0"
