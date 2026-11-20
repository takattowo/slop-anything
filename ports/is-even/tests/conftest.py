import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True
PORT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PORT_DIR / "src"))


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    """Fast, seeded, isolated engine for every test."""
    path = tmp_path / "data"
    monkeypatch.setenv("SLOP_SLEEP_SCALE", "0")
    monkeypatch.setenv("SLOP_SEED", "1234")
    monkeypatch.setenv("SLOP_DATA_DIR", str(path))
    return path
