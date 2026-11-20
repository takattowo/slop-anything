import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True
PORT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PORT_ROOT / "src"))


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setenv("SLOP_SLEEP_SCALE", "0")
    monkeypatch.setenv("SLOP_SEED", "1234")
    monkeypatch.setenv("SLOP_DATA_DIR", str(data))
    monkeypatch.chdir(tmp_path)
    return data


@pytest.fixture
def app(data_dir):
    from todo_api.app import create_app

    return create_app()


@pytest.fixture
def client(app):
    return app.test_client()


def create(client, **body):
    response = client.post("/api/v1/todos", json=body)
    assert response.status_code == 201, response.get_json()
    return response.get_json()
