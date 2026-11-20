"""Shared fixtures for the real tests. This is the only conftest.py in the repo that does anything."""
import random
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from slop_anything import tools  # noqa: E402


@pytest.fixture
def home(tmp_path, monkeypatch):
    """State in a temp folder, no sleeping, no chaos, a seeded coin."""
    state = tmp_path / "state"
    monkeypatch.setenv("SLOP_HOME", str(state))
    monkeypatch.setenv("SLOP_SLEEP_SCALE", "0")
    monkeypatch.setenv("SLOP_CHAOS", "0")
    monkeypatch.setattr(tools, "rng", random.Random(0))
    return state


@pytest.fixture
def project(tmp_path):
    """A tiny project to point the tools at."""
    folder = tmp_path / "project"
    folder.mkdir()
    (folder / "a.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    (folder / "b.py").write_text("x = 1\n", encoding="utf-8")
    (folder / "c.js").write_text("console.log(1)\n", encoding="utf-8")
    return folder
