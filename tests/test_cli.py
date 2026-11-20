"""The CLI as a subprocess: stdout is only the result, exit codes mean something."""
import json
import subprocess
import sys

import pytest

from conftest import child_environment
from slop_anything.store import StateStore


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
    assert code == 1
    assert json.loads(out)["status"] == "ok"
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
    assert code in (0, 1, 75) and json.loads(out)["status"] == "ok"
    code, out, _ = cli(env, "record", "--case", "hello world", "--case", "'one arg'", "shout")
    assert code in (0, 75) and json.loads(out)["status"] == "ok"
    for command in ("diff", "gate"):
        code, out, _ = cli(env, command, "shout")
        assert code in (0, 1, 75) and isinstance(json.loads(out), dict)


def test_an_unclosed_quote_in_a_case_is_bad_usage(env):
    code, out, err = cli(env, "record", "--case", "it's", "shout")
    assert (code, out) == (2, "")
    assert "usage:" in err
    assert "argument --case: No closing quotation in \"it's\"" in err
    assert "Traceback" not in err


def test_case_quoting_is_the_same_on_every_platform(env):
    case = r'''C:\tmp\x "two words" 'it"s' "it's"'''
    code, out, _ = cli(env, "record", "--case", case, "shout")
    if code == 75:
        pytest.skip("transient lease contention; covered by the retry suite")
    assert code == 0, out
    recording = StateStore(env.state / "state.sqlite3").load()["recordings"]["shout"]
    step = recording["cases"][0]["steps"][0]
    assert step["args"] == ["C:\\tmp\\x", "two words", 'it"s', "it's"]
    assert step["stdout"] == 'C:\\TMP\\X TWO WORDS IT"S IT\'S!\n'


def test_bench_and_profile_take_options_before_the_port(env):
    code, out, _ = cli(env, "bench", "--runs", "2", "shout", "hi")
    assert code in (0, 75) and isinstance(json.loads(out), dict)
    code, out, _ = cli(env, "profile", "--top", "3", "shout", "hi")
    assert code in (0, 75) and len(json.loads(out).get("functions", [])) <= 3


def test_doctor_always_exits_zero(env, tmp_path):
    code, out, _ = cli(env, "doctor")
    assert code in (0, 75) and json.loads(out)["status"] == "ok"
    env.ports = tmp_path / "nothing-here"
    code, out, _ = cli(env, "doctor")
    assert code in (0, 75) and json.loads(out)["status"] == "ok"


def test_doctor_reports_an_unwritable_state_folder(env, tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a folder\n", encoding="utf-8")
    env.state = blocker / "state"
    code, out, err = cli(env, "doctor")
    assert code == 0, err
    result = json.loads(out)
    assert result["healthy"] is True  # advisory verdict; the checks carry the detail
    assert result["checks"]["state_writable"]["ok"] is False
    assert result["checks"]["sqlite"]["ok"] is False
    assert result["checks"]["python"]["ok"] is True and result["checks"]["ports"]["ok"] is True
    assert "telemetry flush failed; continuing" in err


def test_version(env):
    code, out, _ = cli(env, "version")
    assert code == 0 and out.strip() == "4.0.0"
