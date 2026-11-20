"""The SQLite store keeps the whole state in one row and rewrites it on every write."""
import json
import sqlite3

import pytest

from slop_anything.kernel import call_tool
from slop_anything.store import StateStore


def rows(path):
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT id, revision, document FROM harness_state").fetchall()


def test_every_write_rewrites_the_single_row(env):
    store = StateStore()
    documents = []
    for value in range(5):
        store.mutate(lambda doc, value=value: doc.__setitem__("marker", value))
        found = rows(store.path)
        assert len(found) == 1
        assert found[0][0] == 1
        assert found[0][1] == value + 1
        documents.append(found[0][2])
    assert len(set(documents)) == 5
    assert json.loads(documents[-1])["marker"] == 4
    assert store.load()["marker"] == 4


def test_a_failed_change_rolls_back(env):
    store = StateStore()
    store.mutate(lambda doc: doc.__setitem__("kept", True))

    def broken(doc):
        doc["kept"] = False
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        store.mutate(broken)
    assert store.revision() == 1
    assert store.load()["kept"] is True


def test_load_returns_a_private_copy(env):
    store = StateStore()
    document = store.load()
    document["recordings"]["x"] = {}
    assert store.load()["recordings"] == {}


def test_opening_the_store_reports_an_index_rebuild(env, capsys):
    StateStore()
    assert "detected corrupted state index in state.sqlite3, rebuilding" in capsys.readouterr().err


def test_tool_calls_write_telemetry_into_the_same_row(env):
    call_tool("slop_status")
    call_tool("slop_ports")
    found = rows(env.state / "state.sqlite3")
    assert len(found) == 1
    document = json.loads(found[0][2])
    assert document["calls"] == 2
    assert set(document["telemetry"]) == {"slop_status", "slop_ports"}
    assert document["telemetry"]["slop_ports"]["count"] == 1
