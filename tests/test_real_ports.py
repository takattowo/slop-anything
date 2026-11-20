"""Integration against the real ports in ports/. Ports are probabilistic, so only the shape is checked."""
import pytest

from slop_anything.kernel import call_tool
from slop_anything.settings import REPO_ROOT

HAPPY_PATHS = {
    "calc": ["2+2"],
    "cowsay": ["hello"],
    "is-even": ["4"],
    "left-pad": ["5", "3", "0"],
    "todo-api": ["list"],
}
EXIT_CLASSES = {0, 1, 2, 3, 74, 75}


@pytest.fixture
def real_ports(env, monkeypatch):
    monkeypatch.delenv("SLOP_PORTS_DIR")
    return env


def needs(name):
    if not (REPO_ROOT / "ports" / name / "__main__.py").is_file():
        pytest.skip(f"ports/{name} has no __main__.py yet")


@pytest.mark.parametrize("name", sorted(HAPPY_PATHS))
def test_happy_path_has_the_right_shape(real_ports, name):
    needs(name)
    result = call_tool("slop_run", {"port": name, "args": HAPPY_PATHS[name]})
    assert result["exit_code"] in EXIT_CLASSES, result["stderr"]
    assert isinstance(result["stdout"], str)
    if result["exit_code"] == 0:
        assert result["stdout"].strip()


@pytest.mark.parametrize("name", sorted(HAPPY_PATHS))
def test_record_then_diff_reports_a_count(real_ports, name):
    needs(name)
    recorded = call_tool("slop_record", {"port": name})
    assert 10 <= recorded["cases"] <= 20
    diff = call_tool("slop_diff", {"port": name})
    assert isinstance(diff["mismatch_count"], int) and diff["mismatch_count"] >= 0


@pytest.mark.parametrize("name", sorted(HAPPY_PATHS))
def test_lift_reports_a_verdict(real_ports, name):
    needs(name)
    assert isinstance(call_tool("slop_lift", {"port": name, "args": HAPPY_PATHS[name]})["verified"], bool)
