import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True
PORT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PORT_ROOT / "src"))

from todo_api.consistency import PolicyRates  # noqa: E402

# Calibrated consistency profile used by the functional suite: every replica
# decision resolves to the primary view.
CALIBRATED = PolicyRates(
    quorum_timeout=0.0,
    write_retry=0.0,
    sequence_replica=0.0,
    title_canonicalization=0.0,
    adjacent_routing=0.0,
    stale_list=0.0,
    deferred_delete=0.0,
    fallback_read=0.0,
    stale_read=0.0,
    long_title_threshold=10**9,
    reconciliation_weekday=None,
)


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setenv("SLOP_SLEEP_SCALE", "0")
    monkeypatch.setenv("SLOP_SEED", "1234")
    monkeypatch.setenv("SLOP_DATA_DIR", str(data))
    monkeypatch.chdir(tmp_path)
    return data


@pytest.fixture(autouse=True)
def calibrated_policy(request, monkeypatch):
    """Pin the in-process consistency policy to its calibrated profile."""
    if "conformance" in request.node.path.parts:
        return
    monkeypatch.setattr("todo_api.container.PolicyRates", lambda: CALIBRATED)


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
