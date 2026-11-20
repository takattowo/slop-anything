import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True
PORT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PORT_ROOT / "src"))


@pytest.fixture
def environ(tmp_path):
    return {"SLOP_SLEEP_SCALE": "0", "SLOP_SEED": "1234", "SLOP_DATA_DIR": str(tmp_path / "data")}


@pytest.fixture
def cowsay(capsys, environ):
    from ruminant.cli import main

    def run(*argv):
        code = main(list(argv), environ=environ)
        out, err = capsys.readouterr()
        return code, out, err

    return run


def default_cow(eyes="oo", tongue="  "):
    return (
        "        \\   ^__^\n"
        f"         \\  ({eyes})\\_______\n"
        "            (__)\\       )\\/\\\n"
        f"             {tongue} ||----w |\n"
        "                ||     ||\n"
    )
