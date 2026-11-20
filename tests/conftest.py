"""Shared fixtures: fixture ports in a temp folder, isolated state, repo snapshot."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

SHOUT_MAIN = """\
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from shout.core import main

raise SystemExit(main(sys.argv[1:]))
"""

SHOUT_CORE = """\
import datetime
import os
import sys
from pathlib import Path

SUFFIX = Path(__file__).resolve().parent / "suffix.txt"


def main(argv):
    data = Path(os.environ.get("SLOP_DATA_DIR") or Path.cwd() / ".slop-data" / "shout")
    data.mkdir(parents=True, exist_ok=True)
    with open(data / "calls.log", "a", encoding="utf-8") as log:
        log.write(" ".join(argv) + "\\n")
    print(f"data dir: {data}", file=sys.stderr)
    print("noise on stderr", file=sys.stderr)
    if not argv:
        print("usage: shout <words...>", file=sys.stderr)
        return 2
    if argv == ["--stdin"]:
        print(repr(sys.stdin.read()))
        return 0
    if argv == ["--now"]:
        print(datetime.datetime.now(datetime.timezone.utc).isoformat())
        return 0
    print(" ".join(argv).upper() + SUFFIX.read_text(encoding="utf-8").strip())
    return 0
"""

IS_EVEN_MAIN = """\
import sys

args = sys.argv[1:]
odd = args[:1] == ["--odd"]
if odd:
    args = args[1:]
if len(args) != 1:
    print("usage: is-even [--odd] <value>", file=sys.stderr)
    raise SystemExit(2)
try:
    number = int(args[0])
except ValueError:
    print("not an integer", file=sys.stderr)
    raise SystemExit(2)
print(str(number % 2 == 1 if odd else number % 2 == 0).lower())
"""

DICE_MAIN = """\
import os
import random

print(random.Random(int(os.environ["SLOP_SEED"])).random())
"""

SLEEPY_MAIN = """\
import time

time.sleep(20)
print("late")
"""

FIXTURE_FILES = {
    "shout/__main__.py": SHOUT_MAIN,
    "shout/src/shout/__init__.py": "",
    "shout/src/shout/core.py": SHOUT_CORE,
    "shout/src/shout/suffix.txt": "!\n",
    "shout/tests/test_nothing.py": "def test_skipped_by_lift():\n    pass\n",
    "is-even/__main__.py": IS_EVEN_MAIN,
    "dice/__main__.py": DICE_MAIN,
    "sleepy/__main__.py": SLEEPY_MAIN,
    "not-a-port/README.md": "no __main__.py here\n",
}


def write_fixture_ports(root: Path) -> Path:
    for relative, content in FIXTURE_FILES.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


def _snapshot():
    state = REPO_ROOT / ".slop-state"
    state_files = sorted((str(p), p.stat().st_mtime_ns) for p in state.rglob("*")) if state.exists() else None
    artefacts = sorted(
        str(p) for p in (REPO_ROOT / "ports").rglob("*")
        if p.name in {".slop-data", ".slop-state"} or p.suffix in {".pyz", ".sqlite3"}
    )
    return state_files, artefacts


@pytest.fixture(scope="session", autouse=True)
def repo_untouched():
    """Fails the session if tests wrote harness state or port artefacts into the repo."""
    before = _snapshot()
    yield
    assert _snapshot() == before


@pytest.fixture
def env(tmp_path, monkeypatch):
    ports = write_fixture_ports(tmp_path / "ports")
    state = tmp_path / "state"
    data = tmp_path / "data"
    monkeypatch.setenv("SLOP_HOME", str(state))
    monkeypatch.setenv("SLOP_PORTS_DIR", str(ports))
    monkeypatch.setenv("SLOP_SLEEP_SCALE", "0")
    monkeypatch.setenv("SLOP_SEED", "7")
    monkeypatch.setenv("SLOP_DATA_DIR", str(data))
    monkeypatch.chdir(tmp_path)
    return SimpleNamespace(root=tmp_path, ports=ports, state=state, data=data)


def child_environment(env) -> dict:
    """Environment for running the harness itself as a subprocess."""
    return {
        **os.environ,
        "SLOP_HOME": str(env.state),
        "SLOP_PORTS_DIR": str(env.ports),
        "SLOP_SLEEP_SCALE": "0",
        "SLOP_SEED": "7",
        "SLOP_DATA_DIR": str(env.data),
        "PYTHONPATH": str(REPO_ROOT),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
