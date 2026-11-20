"""Integration against the real ports in ports/. A port without __main__.py is skipped."""
import json

import pytest

from slop_anything.kernel import call_tool
from slop_anything.settings import REPO_ROOT

HAPPY_PATHS = {
    "is-even": (["4"], lambda out: out == "true\n"),
    "left-pad": (["5", "3", "0"], lambda out: out == "005\n"),
    "cowsay": (["hello"], lambda out: "< hello >" in out),
    "todo-api": (["list"], lambda out: json.loads(out) == []),
}


@pytest.fixture
def real_ports(env, monkeypatch):
    monkeypatch.delenv("SLOP_PORTS_DIR")
    return env


def needs(name):
    if not (REPO_ROOT / "ports" / name / "__main__.py").is_file():
        pytest.skip(f"ports/{name} has no __main__.py yet")


@pytest.mark.parametrize("name", sorted(HAPPY_PATHS))
def test_happy_path(real_ports, name):
    needs(name)
    args, check = HAPPY_PATHS[name]
    result = call_tool("slop_run", {"port": name, "args": args})
    assert result["exit_code"] == 0, result["stderr"]
    assert check(result["stdout"]), result["stdout"]


@pytest.mark.parametrize("name", sorted(HAPPY_PATHS))
def test_record_then_diff_has_no_mismatches(real_ports, name):
    needs(name)
    recorded = call_tool("slop_record", {"port": name})
    assert 10 <= recorded["cases"] <= 20
    diff = call_tool("slop_diff", {"port": name})
    assert diff["mismatch_count"] == 0, diff["mismatches"][:3]


@pytest.mark.parametrize("name", sorted(HAPPY_PATHS))
def test_lift_matches_the_port(real_ports, name):
    needs(name)
    args, _ = HAPPY_PATHS[name]
    assert call_tool("slop_lift", {"port": name, "args": args})["verified"] is True
