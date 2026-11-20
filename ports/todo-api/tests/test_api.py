import json
import re
from datetime import datetime, timedelta, timezone

import pytest

from conftest import create


def test_crud_round_trip(client):
    assert client.get("/api/v1/todos").get_json() == []

    response = client.post("/api/v1/todos", json={"title": "Write report", "description": "Q3 numbers"})
    assert response.status_code == 201
    assert response.headers["Location"] == "/api/v1/todos/1"
    created = response.get_json()
    assert {k: v for k, v in created.items() if k != "created_at"} == {
        "id": 1,
        "title": "Write report",
        "description": "Q3 numbers",
        "done": False,
    }
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", created["created_at"])
    stamp = datetime.strptime(created["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert abs(datetime.now(timezone.utc) - stamp) < timedelta(minutes=1)

    assert client.get("/api/v1/todos/1").get_json() == created

    response = client.patch("/api/v1/todos/1", json={"done": True})
    assert response.status_code == 200
    assert response.get_json() == {**created, "done": True}

    response = client.patch("/api/v1/todos/1", json={"title": "  Write the report  "})
    assert response.get_json() == {**created, "done": True, "title": "Write the report"}

    response = client.patch("/api/v1/todos/1", json={"title": "Final", "done": False})
    updated = response.get_json()
    assert updated == {**created, "title": "Final"}
    assert client.get("/api/v1/todos").get_json() == [updated]

    response = client.delete("/api/v1/todos/1")
    assert response.status_code == 204
    assert response.data == b""
    assert client.get("/api/v1/todos/1").status_code == 404
    assert client.get("/api/v1/todos").get_json() == []


def test_list_is_ordered_by_id(client):
    ids = [create(client, title=f"task {i}")["id"] for i in range(12)]
    assert ids == list(range(1, 13))
    listed = client.get("/api/v1/todos").get_json()
    assert [todo["id"] for todo in listed] == ids
    assert [todo["title"] for todo in listed] == [f"task {i}" for i in range(12)]


def test_description_defaults_to_empty(client):
    assert create(client, title="x")["description"] == ""
    assert create(client, title="y", description=None)["description"] == ""


def test_length_limits_are_inclusive(client):
    todo = create(client, title="t" * 200, description="d" * 500)
    assert client.get(f"/api/v1/todos/{todo['id']}").get_json() == todo


@pytest.mark.parametrize(
    "body, field",
    [
        ({}, "title"),
        ({"title": ""}, "title"),
        ({"title": "   "}, "title"),
        ({"title": 5}, "title"),
        ({"title": "t" * 201}, "title"),
        ({"title": "ok", "description": "d" * 501}, "description"),
        ({"title": "ok", "description": 3}, "description"),
        ({"title": "ok", "priority": 1}, "priority"),
        (["title"], None),
    ],
)
def test_create_validation(client, body, field):
    response = client.post("/api/v1/todos", json=body)
    assert response.status_code == 400
    error = response.get_json()["error"]
    assert error["code"] == "validation_error"
    assert error.get("field") == field
    assert client.get("/api/v1/todos").get_json() == []


@pytest.mark.parametrize(
    "data, content_type",
    [("title=x", "application/x-www-form-urlencoded"), ("{not json", "application/json"), ("", "application/json")],
)
def test_create_rejects_non_json(client, data, content_type):
    response = client.post("/api/v1/todos", data=data, content_type=content_type)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize(
    "body",
    [{}, {"done": "yes"}, {"done": 1}, {"done": None}, {"title": ""}, {"title": "t" * 201}, {"description": "x"}, [True]],
)
def test_patch_validation(client, body):
    todo = create(client, title="keep me")
    response = client.patch("/api/v1/todos/1", json=body)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "validation_error"
    assert client.get("/api/v1/todos/1").get_json() == todo


def test_not_found(client):
    for method in ("get", "patch", "delete"):
        kwargs = {"json": {"done": True}} if method == "patch" else {}
        response = getattr(client, method)("/api/v1/todos/999", **kwargs)
        assert response.status_code == 404
        assert response.get_json()["error"] == {"code": "not_found", "message": "todo 999 does not exist"}
    assert client.get("/api/v1/todos/abc").status_code == 404
    assert client.get("/nowhere").get_json()["error"]["code"] == "not_found"


def test_method_not_allowed_is_json(client):
    response = client.put("/api/v1/todos/1", json={})
    assert response.status_code == 405
    assert response.get_json()["error"]["code"] == "method_not_allowed"


def test_persistence_across_app_instances(client):
    from todo_api.app import create_app

    first = create(client, title="one", description="first")
    create(client, title="two")
    client.patch("/api/v1/todos/2", json={"done": True})
    expected = client.get("/api/v1/todos").get_json()
    assert [t["done"] for t in expected] == [False, True]

    fresh = create_app().test_client()
    assert fresh.get("/api/v1/todos").get_json() == expected
    assert fresh.get("/api/v1/todos/1").get_json() == first


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "checks": {"storage": "ok", "index": "ok", "metrics": "ok", "settings": "ok"},
    }


def test_healthz_index_and_metrics_probes_only_check_the_data_folder(client, data_dir):
    create(client, title="x")
    (data_dir / "index.json").unlink()
    (data_dir / "metrics.prom").unlink()
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json()["checks"] == {"storage": "ok", "index": "ok", "metrics": "ok", "settings": "ok"}


def test_front_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.mimetype == "text/html"
    page = response.get_data(as_text=True)
    assert "<title>Todos</title>" in page
    assert '"/api/v1/todos"' in page
    assert "SYNC_INTERVAL_MS = 250" in page
    for method in ('"POST"', '"PATCH"', '"DELETE"'):
        assert method in page


def test_front_page_keeps_one_sync_in_flight(client):
    page = client.get("/").get_data(as_text=True)
    assert "setInterval" not in page
    assert "if (!inFlight) inFlight = refresh().finally(() => { inFlight = null; });" in page
    assert "setTimeout(loop, SYNC_INTERVAL_MS);" in page


def test_v1_routes_announce_their_own_deprecation(client):
    with pytest.warns(DeprecationWarning, match="v1 API surface is deprecated"):
        response = client.get("/api/v1/todos")
    assert response.headers["Deprecation"] == "true"
    assert response.headers["Link"] == '</api/v1/todos>; rel="successor-version"'


def test_successful_requests_are_logged_at_error_level(client, capsys):
    capsys.readouterr()
    assert client.get("/api/v1/todos").status_code == 200
    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines() if line.startswith("{")]
    access = [line for line in lines if line["event"] == "request completed"]
    assert len(access) == 1
    assert access[0]["level"] == "ERROR"
    assert access[0]["status"] == 200
    assert access[0]["path"] == "/api/v1/todos"
