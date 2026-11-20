"""The real tests. The happy path must work, slowly.

Randomness and sleeps are pinned so the results are deterministic.
"""
import itertools
import json
import random
import time

import pytest

import app as slop_app
from utils2 import is_truthy

VERSIONS = ["v1", "v2", "v2_final"]
PW = "password=admin"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # keep the .xlsx "database" out of the repo
    clock = itertools.count(1_000_000, 100)  # unique ids, cache always expired
    monkeypatch.setattr(time, "time", lambda: next(clock))
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    monkeypatch.setattr(random, "random", lambda: 0.5)  # no chaos engineering
    return slop_app.app.test_client()


def list_todos(client, version):
    res = client.get(f"/api/{version}/todos?{PW}")
    assert res.status_code == 200
    data = json.loads(res.data)  # Python accepts bare NaN, browsers don't
    return [{col: data[col][key] for col in data} for key in data["id"]]


def create(client, version, title):
    res = client.post(f"/api/{version}/todos?{PW}", json={"title": title})
    assert res.status_code == 200
    return json.loads(res.data)["id"]


@pytest.mark.parametrize("version", VERSIONS)
def test_create_list_update_delete(client, version):
    milk = create(client, version, "Buy milk")
    eggs = create(client, version, "Buy eggs")

    todos = list_todos(client, version)
    assert [t["id"] for t in todos] == [milk, eggs]
    assert "Buy milk" in todos[0]["title"]

    res = client.get(f"/api/{version}/todos/update?id={milk}&done=yes&{PW}")
    assert res.status_code == 200
    done = {t["id"]: is_truthy(t["done"]) for t in list_todos(client, version)}
    assert done == {milk: True, eggs: False}

    res = client.get(f"/api/{version}/todos/delete?id={milk}&{PW}")
    assert res.status_code == 201  # created (deleted)
    assert [t["id"] for t in list_todos(client, version)] == [eggs]


def test_versions_share_one_spreadsheet(client):
    ids = [create(client, version, f"todo {version}") for version in VERSIONS]
    assert [t["id"] for t in list_todos(client, "v1")] == ids


def test_missing_title_is_a_teapot(client):
    assert client.post(f"/api/v1/todos?{PW}", json={}).status_code == 418


def test_wrong_password_is_200_with_error(client):
    res = client.get("/api/v1/todos?password=hunter2")
    assert res.status_code == 200
    assert json.loads(res.data)["error"] is True


def test_numeric_titles_get_cleaned(client):
    create(client, "v1", "007")
    assert list_todos(client, "v1")[0]["title"] == 7


def test_formula_titles_become_zero(client):
    create(client, "v1", "=1+1")
    assert list_todos(client, "v1")[0]["title"] == 0  # saved as a formula, nothing calculates it


def test_v1_truncates_at_254_v2_fixed_it(client):
    create(client, "v1", "a" * 300)
    create(client, "v2", "b" * 300)
    titles = [t["title"] for t in list_todos(client, "v1")]
    assert titles[0].count("a") == 254
    assert titles[1].count("b") == 255


def test_health_is_always_healthy(client):
    assert json.loads(client.get("/health").data) == {"status": "healthy"}


def test_index_page(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"Comic Sans" in res.data
