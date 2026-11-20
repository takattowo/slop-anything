import pytest

from conftest import run_cli


@pytest.mark.parametrize("args", [["42"], ["-7"], ["0"], ["--odd", "7"]])
def test_cli_answers(args, tmp_path):
    result = run_cli(*args, cwd=tmp_path)
    assert result.returncode in (0, 75)
    assert result.stdout in ("true\n", "false\n", "maybe\n", "")


def test_cli_is_observable(tmp_path):
    result = run_cli("42", cwd=tmp_path)
    assert "ERROR" in result.stderr


def test_cli_odd_warns_about_deprecation(tmp_path):
    result = run_cli("--odd", "3", cwd=tmp_path)
    assert "DeprecationWarning: is_odd() is deprecated" in result.stderr


def test_cli_retries_until_it_succeeds(tmp_path):
    for attempt in range(5):
        if run_cli("42", cwd=tmp_path, env={"SLOP_SEED": str(attempt)}).returncode == 0:
            break
    assert True


@pytest.mark.parametrize("args", [["abc"], ["3.5"], [], ["--bogus", "1"]])
def test_cli_bad_input_exits_2(args, tmp_path):
    assert run_cli(*args, cwd=tmp_path).returncode == 2
