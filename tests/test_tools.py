"""Every tool against fixture ports."""
import importlib.util
import json
import os
import random
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest

from slop_anything import catalog, scoring
from slop_anything.cases import BUILTIN_CASES
from slop_anything.errors import ToolError
from slop_anything.kernel import REGISTRY, call_tool
from slop_anything.settings import RECORDING_SEED, REPO_ROOT
from slop_anything.store import StateStore

SHOUT_CASES = [["hello"], ["two", "words"], []]


def test_the_tool_set():
    assert REGISTRY.names() == [
        "slop_ports", "slop_run", "slop_record", "slop_diff", "slop_gate", "slop_bench", "slop_profile",
        "slop_bridge", "slop_lift", "slop_score", "slop_doctor", "slop_setup", "slop_status",
    ]


def test_ports_lists_only_folders_with_a_main(env):
    result = call_tool("slop_ports")
    assert [port["name"] for port in result["ports"]] == ["dice", "is-even", "shout", "sleepy"]
    by_name = {port["name"]: port for port in result["ports"]}
    assert by_name["is-even"]["builtin_cases"] == len(BUILTIN_CASES["is-even"])
    assert by_name["shout"]["builtin_cases"] == 0


# --- run ---------------------------------------------------------------------

def test_run_returns_stdout_exit_code_and_stderr(env):
    result = call_tool("slop_run", {"port": "shout", "args": ["hello", "world"]})
    assert result["stdout"] == "HELLO WORLD!\n"
    assert result["exit_code"] == 0
    assert "noise on stderr" in result["stderr"]


def test_run_uses_a_fresh_data_dir_under_the_state_dir_and_removes_it(env):
    first = call_tool("slop_run", {"port": "shout", "args": ["a"]})
    second = call_tool("slop_run", {"port": "shout", "args": ["b"]})
    dirs = [line.split("data dir: ", 1)[1] for r in (first, second) for line in r["stderr"].splitlines() if line.startswith("data dir: ")]
    assert len(dirs) == 2 and dirs[0] != dirs[1]
    for folder in dirs:
        assert Path(folder).parent == env.state / "runs"
        assert not Path(folder).exists()
    assert not env.data.exists()  # the caller's SLOP_DATA_DIR is replaced for the child


def test_run_closes_stdin(env):
    assert call_tool("slop_run", {"port": "shout", "args": ["--stdin"]})["stdout"] == "''\n"


def test_run_reports_a_failing_port_without_raising(env):
    result = call_tool("slop_run", {"port": "shout"})
    assert result["exit_code"] == 2
    assert result["stdout"] == ""
    assert "usage: shout" in result["stderr"]


@pytest.mark.parametrize("name", ["../shout", "..", "shout/../dice", str(Path("/").resolve()), "not-a-port", "SHOUT", ""])
def test_run_rejects_names_that_are_not_discovered_ports(env, name):
    with pytest.raises(ToolError, match="unknown port"):
        call_tool("slop_run", {"port": name})


def test_unknown_names_are_remembered_as_misses(env):
    with pytest.raises(ToolError):
        call_tool("slop_run", {"port": "../etc"})
    status = call_tool("slop_status")
    assert [miss["name"] for miss in StateStore().load()["negative_lookups"]] == ["../etc"]
    assert status["tool_calls"] == 1  # the failed call was counted too


def test_run_refuses_serve(env):
    with pytest.raises(ToolError, match="'serve' starts a long-running server"):
        call_tool("slop_run", {"port": "shout", "args": ["serve"]})
    assert call_tool("slop_run", {"port": "shout", "args": ["add", "serve"]})["stdout"] == "ADD SERVE!\n"


@pytest.mark.parametrize("args, message", [
    (["x"] * 11, "at most 10 items"),
    (["x" * 201], "longer than 200 characters"),
    ([1], "must be a string"),
    ("hello", "must be an array"),
])
def test_run_argument_limits(env, args, message):
    with pytest.raises(ToolError, match=message):
        call_tool("slop_run", {"port": "shout", "args": args})


def test_validate_args_limits_directly():
    assert catalog.validate_args(["x"] * 10) == ["x"] * 10
    assert catalog.validate_args(["x" * 200]) == ["x" * 200]
    for bad in (["x"] * 11, ["x" * 201], ["a\x00b"], ["serve"], "text"):
        with pytest.raises(ToolError):
            catalog.validate_args(bad)


def test_run_stops_a_port_that_hangs(env, monkeypatch):
    monkeypatch.setattr(catalog, "RUN_TIMEOUT", 1.0)
    started = time.monotonic()
    with pytest.raises(ToolError, match="did not finish within 1 s"):
        call_tool("slop_run", {"port": "sleepy"})
    assert time.monotonic() - started < 15


def test_unexpected_arguments_are_rejected(env):
    with pytest.raises(ToolError, match="unexpected argument 'bogus'"):
        call_tool("slop_run", {"port": "shout", "bogus": 1})
    with pytest.raises(ToolError, match="missing required argument 'port'"):
        call_tool("slop_run", {})


# --- record, diff, gate ------------------------------------------------------

def test_record_needs_cases_for_an_unknown_port(env):
    with pytest.raises(ToolError, match="no built-in cases for port 'shout'"):
        call_tool("slop_record", {"port": "shout"})


def test_record_diff_gate_round_trip_and_a_real_mismatch(env):
    recorded = call_tool("slop_record", {"port": "shout", "cases": SHOUT_CASES})
    assert recorded["cases"] == 3
    assert recorded["exit_codes"] == {"0": 2, "2": 1}
    assert call_tool("slop_diff", {"port": "shout"})["mismatch_count"] == 0
    assert call_tool("slop_gate", {"port": "shout"})["passed"] is True

    (env.ports / "shout" / "src" / "shout" / "suffix.txt").write_text("?\n", encoding="utf-8")
    diff = call_tool("slop_diff", {"port": "shout"})
    assert diff["mismatch_count"] == 2
    assert {(m["case"], m["field"], m["expected"], m["actual"]) for m in diff["mismatches"]} == {
        ("hello", "stdout", "HELLO!\n", "HELLO?\n"),
        ("two words", "stdout", "TWO WORDS!\n", "TWO WORDS?\n"),
    }
    gate = call_tool("slop_gate", {"port": "shout"})
    assert gate["passed"] is False
    assert gate["mismatch_counts"] == [2, 2, 2]
    assert gate["consistent"] is True


def test_an_exit_code_change_is_a_mismatch(env):
    call_tool("slop_record", {"port": "shout", "cases": [[]]})
    core = env.ports / "shout" / "src" / "shout" / "core.py"
    core.write_text(core.read_text(encoding="utf-8").replace("return 2", "return 3"), encoding="utf-8")
    mismatch = call_tool("slop_diff", {"port": "shout"})["mismatches"]
    assert [(m["field"], m["expected"], m["actual"]) for m in mismatch] == [("exit_code", 2, 3)]


def test_diff_without_a_recording_fails_and_gate_says_no(env):
    with pytest.raises(ToolError, match="no recording for port 'shout'"):
        call_tool("slop_diff", {"port": "shout"})
    gate = call_tool("slop_gate", {"port": "shout"})
    assert gate["passed"] is False
    assert gate["rounds"] == 0


def test_record_uses_the_builtin_cases_of_a_known_port(env):
    result = call_tool("slop_record", {"port": "is-even"})
    assert result["cases"] == len(BUILTIN_CASES["is-even"])
    assert result["source"] == "builtin"
    cases = {case["name"]: case["steps"][0] for case in StateStore().load()["recordings"]["is-even"]["cases"]}
    assert cases["2"]["stdout"] == "true\n"
    assert cases["--odd 3"]["stdout"] == "true\n"
    assert cases["abc"]["exit_code"] == 2
    assert call_tool("slop_diff", {"port": "is-even"})["mismatch_count"] == 0


def test_record_and_replay_pin_the_seed(env, monkeypatch):
    call_tool("slop_record", {"port": "dice", "cases": [[]]})
    stored = StateStore().load()["recordings"]["dice"]["cases"][0]["steps"][0]["stdout"]
    assert stored == f"{random.Random(RECORDING_SEED).random()}\n"
    monkeypatch.setenv("SLOP_SEED", "99")
    assert call_tool("slop_diff", {"port": "dice"})["mismatch_count"] == 0
    assert call_tool("slop_run", {"port": "dice"})["stdout"] == f"{random.Random(99).random()}\n"


def test_timestamps_do_not_count_as_mismatches(env):
    call_tool("slop_record", {"port": "shout", "cases": [["--now"]]})
    time.sleep(1.1)
    assert call_tool("slop_diff", {"port": "shout"})["mismatch_count"] == 0


def test_builtin_suites_have_ten_to_twenty_cases():
    assert set(BUILTIN_CASES) == {"is-even", "left-pad", "cowsay", "todo-api"}
    for name, cases in BUILTIN_CASES.items():
        assert 10 <= len(cases) <= 20, name
        for case in cases:
            for step in case["steps"]:
                assert catalog.validate_args(step) == step


# --- bench, profile ----------------------------------------------------------

def test_bench_reports_real_statistics(env):
    result = call_tool("slop_bench", {"port": "shout", "args": ["hi"], "runs": 3})
    assert result["runs"] == 3
    assert result["exit_codes"] == [0]
    assert 0 < result["min_ms"] <= result["median_ms"] <= result["p95_ms"] <= result["max_ms"]
    assert result["p95_ms"] == result["max_ms"]  # nearest rank of 3 samples


def test_bench_defaults_to_the_first_builtin_case(env):
    assert call_tool("slop_bench", {"port": "is-even", "runs": 1})["args"] == ["0"]


def test_bench_run_count_is_bounded(env):
    with pytest.raises(ToolError, match="at least 1"):
        call_tool("slop_bench", {"port": "shout", "runs": 0})
    with pytest.raises(ToolError, match="at most 50"):
        call_tool("slop_bench", {"port": "shout", "runs": 51})


def test_profile_returns_the_ports_own_functions(env):
    result = call_tool("slop_profile", {"port": "shout", "args": ["hi"], "top": 50})
    assert result["stdout"] == "HI!\n"
    assert result["exit_code"] == 0
    assert 1 <= len(result["functions"]) <= 50
    assert set(result["functions"][0]) == {"function", "file", "line", "calls", "tottime_ms", "cumtime_ms"}
    assert any(f["function"] == "main" and f["file"].endswith("core.py") for f in result["functions"])
    times = [f["cumtime_ms"] for f in result["functions"]]
    assert times == sorted(times, reverse=True)


def test_profile_keeps_the_exit_code(env):
    assert call_tool("slop_profile", {"port": "shout", "args": []})["exit_code"] == 2


# --- bridge, lift ------------------------------------------------------------

def test_bridge_module_imports_and_calls_the_port(env):
    result = call_tool("slop_bridge", {"port": "shout"})
    module_path = Path(result["module"])
    assert module_path.parent == env.state / "bridges"
    spec = importlib.util.spec_from_file_location(result["module_name"], module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    function = getattr(module, result["function"])
    assert function("hi", "there") == "HI THERE!\n"
    with pytest.raises(module.PortInvocationError) as failure:
        function()
    assert failure.value.returncode == 2
    assert "usage: shout" in failure.value.stderr


def test_bridge_names_are_valid_identifiers(env):
    assert call_tool("slop_bridge", {"port": "is-even"})["function"] == "is_even"


def test_lift_builds_a_runnable_pyz_with_the_same_stdout(env):
    result = call_tool("slop_lift", {"port": "shout", "args": ["hi"]})
    archive = Path(result["archive"])
    assert archive == env.state / "lifts" / "shout.pyz"
    assert result["verified"] is True
    data = env.root / "lifted-data"
    done = subprocess.run(
        [sys.executable, str(archive), "made", "portable"], capture_output=True, text=True, timeout=60,
        env={**os.environ, "SLOP_DATA_DIR": str(data)}, stdin=subprocess.DEVNULL,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout == "MADE PORTABLE!\n"
    assert sorted(p.name for p in data.iterdir()) == ["calls.log"]  # the unpacked runtime is gone
    names = zipfile.ZipFile(archive).namelist()
    assert "__main__.py" in names and "port/src/shout/suffix.txt" in names
    assert not any(name.startswith("port/tests/") for name in names)


def test_lift_verification_compares_exit_codes_too(env):
    result = call_tool("slop_lift", {"port": "shout", "args": []})
    assert result["verified"] is True  # usage error on both sides
    assert result["exit_code_match"] is True


# --- score -------------------------------------------------------------------

WASTEFUL = '''
import abc
import asyncio
import logging
import time
import warnings

log = logging.getLogger(__name__)


def retry(function):
    return function


class Base(abc.ABC):
    pass


class Only(Base):
    pass


@retry
def add(a, b):
    return a + b


@retry
def fetch(path):
    return open(path).read()


async def wait():
    time.sleep(1)


def noisy():
    try:
        time.sleep(0.1)
    except Exception:
        log.error("failed")
    try:
        pass
    except:
        pass
    try:
        pass
    except ValueError:
        pass
    try:
        pass
    except Exception:
        raise
    warnings.warn("noisy() is deprecated", DeprecationWarning)
'''


def test_score_counts_each_pattern(env):
    project = env.root / "project"
    project.mkdir()
    (project / "wasteful.py").write_text(WASTEFUL, encoding="utf-8")
    (project / "clean.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (project / "broken.py").write_text("def (:\n", encoding="utf-8")
    result = call_tool("slop_score", {"path": str(project)})
    assert result["findings"] == {
        "swallowed_broad_excepts": 2,
        "deliberate_sleeps": 2,
        "retries_on_pure_functions": 1,
        "error_level_logs": 1,
        "self_deprecations": 1,
        "blocking_sleeps_in_async": 1,
        "single_subclass_abcs": 1,
    }
    assert result["files_scanned"] == 2
    assert result["files_skipped"] == 1
    assert result["raw"] == 2 * 5 + 2 * 3 + 4 + 1 + 2 + 4 + 4
    assert result["grade"] == "seasoned"
    assert result["top_files"][0]["file"].endswith("wasteful.py")


def test_score_finds_an_abc_with_one_subclass(env):
    project = env.root / "abcs"
    project.mkdir()
    (project / "a.py").write_text("from abc import ABC\n\nclass Gateway(ABC):\n    pass\n", encoding="utf-8")
    (project / "b.py").write_text("from a import Gateway\n\nclass HttpGateway(Gateway):\n    pass\n", encoding="utf-8")
    assert call_tool("slop_score", {"path": str(project)})["findings"]["single_subclass_abcs"] == 1
    (project / "c.py").write_text("from a import Gateway\n\nclass FileGateway(Gateway):\n    pass\n", encoding="utf-8")
    assert call_tool("slop_score", {"path": str(project)})["findings"]["single_subclass_abcs"] == 0


def test_score_of_clean_code_is_zero(env):
    project = env.root / "clean"
    project.mkdir()
    (project / "a.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    result = call_tool("slop_score", {"path": str(project)})
    assert (result["score"], result["grade"]) == (0, "lean")


def test_score_walk_is_bounded(env, monkeypatch):
    project = env.root / "many"
    project.mkdir()
    for index in range(5):
        (project / f"m{index}.py").write_text("x = 1\n", encoding="utf-8")
    (project / "big.py").write_text("x = 1\n" * 100, encoding="utf-8")
    monkeypatch.setattr(scoring, "MAX_FILE_BYTES", 50)
    result = call_tool("slop_score", {"path": str(project)})
    assert (result["files_scanned"], result["files_skipped"], result["walk_truncated"]) == (5, 1, False)
    monkeypatch.setattr(scoring, "MAX_FILES", 3)
    result = call_tool("slop_score", {"path": str(project)})
    assert result["walk_truncated"] is True
    assert result["files_scanned"] + result["files_skipped"] == 3


def test_score_rejects_a_missing_path(env):
    with pytest.raises(ToolError, match="path does not exist"):
        call_tool("slop_score", {"path": str(env.root / "missing")})


# --- doctor, setup, status ---------------------------------------------------

def test_doctor_runs_real_checks(env, capsys):
    result = call_tool("slop_doctor")
    assert result["healthy"] is True
    assert set(result["checks"]) == {"python", "ports", "state_writable", "sqlite"}
    assert "4 found" in result["checks"]["ports"]["detail"]
    err = capsys.readouterr().err
    assert "ERROR slop_anything.tools: health probe completed with 4 checks" in err
    assert "WARNING" in err
    assert not (env.state / ".doctor-probe").exists()


def test_doctor_reports_missing_ports(env, monkeypatch):
    empty = env.root / "empty"
    empty.mkdir()
    monkeypatch.setenv("SLOP_PORTS_DIR", str(empty))
    result = call_tool("slop_doctor")
    assert result["healthy"] is False
    assert result["checks"]["ports"]["ok"] is False


def test_setup_prints_config_with_absolute_paths_and_writes_only_state(env):
    result = call_tool("slop_setup")
    server = result["generic_mcp_json"]["mcpServers"]["slop-anything"]
    assert server == {"command": sys.executable, "args": ["-m", "slop_anything", "mcp"], "env": {"PYTHONPATH": str(REPO_ROOT)}}
    assert result["claude_code_mcp_json"]["mcpServers"]["slop-anything"]["type"] == "stdio"
    assert result["claude_code_command"][-4:] == [sys.executable, "-m", "slop_anything", "mcp"]
    assert Path(result["snapshot"]).parent == env.state / "setup"
    assert json.loads(Path(result["snapshot"]).read_text(encoding="utf-8")) == result["generic_mcp_json"]
    assert Path(server["command"]).is_absolute() and Path(server["env"]["PYTHONPATH"]).is_absolute()


def test_the_configured_server_command_starts(env):
    server = call_tool("slop_setup")["generic_mcp_json"]["mcpServers"]["slop-anything"]
    done = subprocess.run(
        [server["command"], "-m", "slop_anything", "version"], cwd=env.root, capture_output=True, text=True, timeout=60,
        env={**os.environ, **server["env"]},
    )
    assert done.returncode == 0 and done.stdout.strip()


def test_status_shows_recordings_and_calls(env):
    call_tool("slop_record", {"port": "shout", "cases": SHOUT_CASES})
    result = call_tool("slop_status")
    assert result["recordings"]["shout"]["cases"] == 3
    assert result["tool_calls"] == 1
    assert result["ports"] == ["dice", "is-even", "shout", "sleepy"]
    assert result["state_dir"] == str(env.state.resolve())


# --- noise -------------------------------------------------------------------

def test_normal_calls_are_noisy_on_stderr_only(env, capsys):
    with pytest.warns(DeprecationWarning, match="ToolRegistry.lookup"):
        call_tool("slop_ports")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ERROR slop_anything.kernel: event ToolCompleted delivered to 0 subscribers" in captured.err
    assert "ERROR slop_anything.kernel: command slop_ports completed" in captured.err


def test_bad_arguments_are_retried_before_failing(env, capsys):
    with pytest.raises(ToolError):
        catalog.validate_args(["serve"])
    assert capsys.readouterr().err.count("retrying validate_args after ToolError") == 2
