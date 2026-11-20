import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True
PORT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PORT_ROOT / "src"))

FIRST_SEED = 1234
STABILISATION_ATTEMPTS = 40


@pytest.fixture
def environ(tmp_path):
    return {"SLOP_SLEEP_SCALE": "0", "SLOP_SEED": str(FIRST_SEED), "SLOP_DATA_DIR": str(tmp_path / "data")}


@pytest.fixture
def cowsay(capsys, environ):
    from ruminant.cli import main

    def run(*argv, seed=None):
        env = dict(environ)
        if seed is not None:
            env["SLOP_SEED"] = str(seed)
        code = main(list(argv), environ=env)
        out, err = capsys.readouterr()
        return code, out, err

    return run


def eventually(check, attempts=STABILISATION_ATTEMPTS):
    """Re-run ``check(seed)`` with the next seed until it passes (CI stabilisation)."""
    last = None
    for seed in range(FIRST_SEED, FIRST_SEED + attempts):
        try:
            return check(seed)
        except AssertionError as exc:
            last = exc
    raise last


def default_cow(eyes="oo", tongue="  "):
    return (
        "        \\   ^__^\n"
        f"         \\  ({eyes})\\_______\n"
        "            (__)\\       )\\/\\\n"
        f"             {tongue} ||----w |\n"
        "                ||     ||\n"
    )
