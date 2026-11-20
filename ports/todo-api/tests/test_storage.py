import os
import random

import pytest

from conftest import create
from todo_api.naming import CHUNK_BUDGET_BYTES, NAME_LIMIT_BYTES, chunk_tokens, escape_tokens, unescape

FORBIDDEN = set('\\/:*?"<>|')


def names(data_dir):
    return sorted(os.listdir(data_dir / "records"))


def assert_safe_names(data_dir):
    for name in names(data_dir):
        assert not FORBIDDEN & set(name), name
        assert all(ord(ch) >= 0x20 for ch in name), name
        assert not name.endswith((" ", "."))
        assert len(name.encode("utf-8")) <= NAME_LIMIT_BYTES
        assert len(name.encode("utf-16-le")) // 2 <= 255


def test_file_name_is_the_record(client, data_dir):
    todo = create(client, title="Buy milk", description="2 litres")
    stamp = todo["created_at"].replace("-", "").replace(":", "")
    assert names(data_dir) == [f"0000000001.open.{stamp}.0000-001.Buy milk.2 litres.todo"]
    assert (data_dir / "records" / names(data_dir)[0]).stat().st_size == 0


def test_reserved_characters_are_percent_encoded(client, data_dir):
    create(client, title='a:b*c?d"e<f>g|h\\i/j%k.l', description="x")
    (name,) = names(data_dir)
    assert name.endswith(".a%3Ab%2Ac%3Fd%22e%3Cf%3Eg%7Ch%5Ci%2Fj%25k%2El.x.todo")


def test_toggle_done_is_a_rename(client, data_dir):
    create(client, title="rename me")
    (before,) = names(data_dir)
    inode = os.stat(data_dir / "records" / before).st_ino
    assert ".open." in before

    client.patch("/api/v1/todos/1", json={"done": True})
    (after,) = names(data_dir)
    assert after == before.replace(".open.", ".done.")
    assert os.stat(data_dir / "records" / after).st_ino == inode
    assert not (data_dir / "records" / before).exists()


def test_long_payload_uses_continuation_parts(client, data_dir):
    from todo_api.app import create_app

    title = "\ud800" * 200
    description = "%" * 250 + "\U0001F680" * 250
    todo = create(client, title=title, description=description)
    assert (todo["title"], todo["description"]) == (title, description)

    entries = names(data_dir)
    heads = [n for n in entries if n.endswith(".todo")]
    parts = [n for n in entries if n.endswith(".part")]
    assert len(heads) == 1 and len(parts) > 10
    assert heads[0].split(".")[3] == f"0000-{len(parts) + 1:03d}"
    assert_safe_names(data_dir)
    assert create_app().test_client().get("/api/v1/todos/1").get_json() == todo

    client.patch("/api/v1/todos/1", json={"done": True})
    assert [n for n in names(data_dir) if n.endswith(".part")] == parts

    client.patch("/api/v1/todos/1", json={"title": "short now"})
    entries = names(data_dir)
    assert 1 < len(entries) < len(parts)
    assert all(n.split(".")[1 if n.endswith(".part") else 3].startswith("0001-") for n in entries)
    assert client.get("/api/v1/todos/1").get_json()["description"] == description

    client.delete("/api/v1/todos/1")
    assert names(data_dir) == []


UNICODE_TITLES = [
    "Caf\u00e9 \u2615 \u65e5\u672c\u8a9e \U0001F680",
    'a\\b/c:d*e?f"g<h>i|j%k.l',
    "tab\tnew\nline\x7f\x85x",
    "lone \ud800 surrogate",
    "\u0627\u0644\u0639\u0631\u0628\u064a\u0629 \u05e2\u05d1\u05e8\u05d9\u05ea",
    "dots... end.",
    "%41 is not A",
]


@pytest.mark.parametrize("title", UNICODE_TITLES)
def test_unicode_round_trip(client, data_dir, title):
    from todo_api.app import create_app

    todo = create(client, title=title, description=title * 3)
    assert todo["title"] == title
    assert todo["description"] == title * 3
    assert client.get("/api/v1/todos/1").get_json() == todo
    assert create_app().test_client().get("/api/v1/todos").get_json() == [todo]
    assert_safe_names(data_dir)


def test_codec_round_trips_random_text():
    rng = random.Random(99)
    pools = [(0x00, 0x7F), (0x80, 0x7FF), (0x800, 0xFFFF), (0x10000, 0x10FFFF)]
    for _ in range(400):
        text = "".join(chr(rng.randint(*rng.choice(pools))) for _ in range(rng.randint(0, 80)))
        tokens = escape_tokens(text)
        assert unescape("".join(tokens)) == text
        chunks = chunk_tokens(tokens + ["."])
        assert "".join(chunks) == "".join(tokens) + "."
        assert all(len(chunk.encode("utf-8")) <= CHUNK_BUDGET_BYTES for chunk in chunks)


def test_ids_are_max_plus_one(client):
    assert [create(client, title=t)["id"] for t in "abc"] == [1, 2, 3]
    client.delete("/api/v1/todos/2")
    assert create(client, title="d")["id"] == 4
    client.delete("/api/v1/todos/4")
    assert create(client, title="e")["id"] == 4  # the freed highest id is reused


def test_foreign_and_corrupt_entries_are_skipped(client, data_dir, capsys):
    good = create(client, title="good")
    (data_dir / "records" / "notes.txt").touch()
    (data_dir / "records" / "0000000005.open.20261120T000000Z.0000-002.orphan.x.todo").touch()
    capsys.readouterr()
    assert client.get("/api/v1/todos").get_json() == [good]
    err = capsys.readouterr().err
    assert "ignoring unrecognised entry in records directory" in err
    assert "record failed to decode; skipping" in err
    assert create(client, title="next")["id"] == 6


def test_data_dir_holds_index_metrics_and_profile(client, data_dir, capsys):
    capsys.readouterr()
    create(client, title="observe me")
    err = capsys.readouterr().err
    assert "record index digest mismatch; rebuilding index from records" in err
    assert "profile source unavailable; trying next source" in err
    assert sorted(p.name for p in data_dir.iterdir()) == ["index.json", "metrics.prom", "records", "settings.ini"]
    metrics = (data_dir / "metrics.prom").read_text(encoding="utf-8")
    assert 'todo_api_operations_total{operation="create",outcome="ok"} 1\n' in metrics
    assert "enable_dark_launch = true" in (data_dir / "settings.ini").read_text(encoding="utf-8")

    client.post("/api/v1/todos", json={})
    metrics = (data_dir / "metrics.prom").read_text(encoding="utf-8")
    assert 'todo_api_operations_total{operation="create",outcome="rejected"} 1\n' in metrics


def test_create_prints_a_recovered_traceback(client, capsys):
    capsys.readouterr()
    create(client, title="noisy")
    err = capsys.readouterr().err
    assert "Traceback (most recent call last)" in err
    assert "StaleHandleError" in err and "The handle is invalid" in err
    assert '"recovered": true' in err


def test_rename_backoff_is_noisy_but_harmless(client, capsys):
    create(client, title="flip")
    capsys.readouterr()
    for i in range(10):
        assert client.patch("/api/v1/todos/1", json={"done": i % 2 == 0}).get_json()["done"] is (i % 2 == 0)
    assert "transient filesystem contention; backing off" in capsys.readouterr().err
    assert client.get("/api/v1/todos/1").get_json()["done"] is False
