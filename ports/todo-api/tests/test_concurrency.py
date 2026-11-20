"""Two store instances on one folder stand in for two processes (no shared lock)."""

import os
import random
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from todo_api.domain import Todo
from todo_api.naming import PercentEncodedNaming
from todo_api.records import FilenameRecordStore
from todo_api.runtime import Pacer

LONG = "p" * 300  # two chunks: a head and one continuation part


def store(data_dir):
    return FilenameRecordStore(data_dir, PercentEncodedNaming(), Pacer(0), random.Random(7))


def todo(title, second=0, description=""):
    return Todo(1, title, description, False, datetime(2026, 11, 20, 10, 0, second, tzinfo=timezone.utc))


def entries(data_dir):
    return sorted(os.listdir(data_dir / "records"))


def test_same_id_and_payload_in_another_second_fails_instead_of_sharing_parts(data_dir):
    first, second = store(data_dir), store(data_dir)
    kept = first.insert(todo(LONG, 0))
    before = entries(data_dir)

    with pytest.raises(FileExistsError):
        second.insert(todo(LONG, 5))

    assert entries(data_dir) == before
    (record,) = first.snapshot()
    assert record.todo == kept.todo
    first.delete(record)
    assert entries(data_dir) == []


def test_same_id_and_payload_in_the_same_second_fails_cleanly(data_dir):
    first, second = store(data_dir), store(data_dir)
    first.insert(todo("short", 0))
    with pytest.raises(FileExistsError):
        second.insert(todo("short", 0))
    assert [r.todo.title for r in first.snapshot()] == ["short"]


def test_deleting_a_one_name_record_keeps_the_other_records_parts(data_dir):
    first, second = store(data_dir), store(data_dir)
    parted = first.insert(todo(LONG, 0))
    single = second.insert(todo("short", 5))
    assert [r.todo.title for r in first.snapshot()] == [LONG, "short"]

    second.delete(next(r for r in second.snapshot() if r.head == single.head))
    (record,) = first.snapshot()
    assert record.todo == parted.todo


def test_two_parted_records_with_one_id_are_skipped(data_dir, capsys):
    first, second = store(data_dir), store(data_dir)
    first.insert(todo(LONG, 0))
    second.insert(todo("q" * 300, 5))
    capsys.readouterr()
    assert first.snapshot() == []
    assert capsys.readouterr().err.count("record failed to decode; skipping") == 2


def test_losing_a_title_update_race_leaves_no_parts_behind(data_dir):
    first, second = store(data_dir), store(data_dir)
    original = first.insert(todo("before", 0))
    winner = first.replace(original, replace(original.todo, title=LONG))
    after_winner = entries(data_dir)

    with pytest.raises(FileNotFoundError):
        second.replace(original, replace(original.todo, title="q" * 300))

    assert entries(data_dir) == after_winner
    (record,) = first.snapshot()
    assert record.todo == winner.todo
