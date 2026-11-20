import importlib.util
import json
import os
import time
import zipfile

from leftpad import registry as registry_module
from leftpad import left_pad
from leftpad.registry import MAX_ENTRIES, MAX_MEMO_CHARS, REGISTRY_FILENAME
from leftpad.telemetry import ARCHIVE_NAME


def read_registry(data_dir):
    path = data_dir / REGISTRY_FILENAME
    namespace = {}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
    return namespace


def test_results_are_memoised_into_the_generated_module(data_dir):
    left_pad("foo", 5)
    first = read_registry(data_dir)
    assert first["GENERATION"] == 1
    assert first["ENTRIES"] == {("foo", 5, " "): "  foo"}
    left_pad(1, 2, 0)
    second = read_registry(data_dir)
    assert second["GENERATION"] == 2
    assert second["ENTRIES"] == {("foo", 5, " "): "  foo", ("1", 2, "0"): "01"}
    assert not list(data_dir.glob("*.tmp"))


def test_registry_is_rewritten_and_reimported_on_every_call(data_dir, monkeypatch):
    original = importlib.util.spec_from_file_location
    loads = []

    def counting(name, location=None, *args, **kwargs):
        if str(location).endswith(REGISTRY_FILENAME):
            loads.append(location)
        return original(name, location, *args, **kwargs)

    monkeypatch.setattr(importlib.util, "spec_from_file_location", counting)
    left_pad("foo", 5)
    after_first = len(loads)
    left_pad("foo", 5)
    assert after_first == 1  # nothing to import yet, then read-after-write
    assert len(loads) == after_first + 2

    # A hand-edited snapshot is picked up from disk, and a wrong entry is never trusted.
    (data_dir / REGISTRY_FILENAME).write_text(
        'GENERATION = 40\nENTRIES = {("foo", 5, " "): "WRONG", ("keep", 1, " "): "keep"}\n',
        encoding="utf-8",
    )
    assert left_pad("foo", 5) == "  foo"
    registry = read_registry(data_dir)
    assert registry["GENERATION"] == 41
    assert registry["ENTRIES"] == {("keep", 1, " "): "keep", ("foo", 5, " "): "  foo"}


def test_registry_is_bounded(data_dir):
    for i in range(MAX_ENTRIES + 5):
        assert left_pad(str(i), 4) == str(i).rjust(4)
    entries = read_registry(data_dir)["ENTRIES"]
    assert len(entries) == MAX_ENTRIES
    assert ("0", 4, " ") not in entries
    assert (str(MAX_ENTRIES + 4), 4, " ") in entries


def test_long_results_are_not_memoised(data_dir):
    assert len(left_pad("x", MAX_MEMO_CHARS + 1)) == MAX_MEMO_CHARS + 1
    registry = read_registry(data_dir)
    assert registry["GENERATION"] == 1
    assert registry["ENTRIES"] == {}


def test_unreadable_registry_is_replaced(data_dir, capsys):
    data_dir.mkdir(parents=True)
    (data_dir / REGISTRY_FILENAME).write_text("ENTRIES = {(\n", encoding="utf-8")
    assert left_pad("ab", 3) == " ab"
    assert read_registry(data_dir)["GENERATION"] == 1
    assert "could not be imported (SyntaxError)" in capsys.readouterr().err


def test_telemetry_archive_is_rewritten_per_call(data_dir):
    for _ in range(3):
        left_pad("a", 2)
    with zipfile.ZipFile(data_dir / ARCHIVE_NAME) as archive:
        counters = json.loads(archive.read("counters.json"))
        timings = json.loads(archive.read("timings.json"))
    assert counters["invocations"] == 3
    assert counters["cache_hits"] == 2
    assert len(timings) == 3


def test_seed_makes_shard_routing_deterministic(tmp_path, monkeypatch):
    shards = []
    for name in ("one", "two"):
        directory = tmp_path / name
        monkeypatch.setenv("SLOP_DATA_DIR", str(directory))
        left_pad("a", 2)
        with zipfile.ZipFile(directory / ARCHIVE_NAME) as archive:
            shards.append(json.loads(archive.read("counters.json"))["last_shard"])
    assert shards[0] == shards[1]


def test_lone_surrogates_are_memoised_as_escapes(data_dir):
    assert left_pad("\udcff", 3) == "  \udcff"
    source = (data_dir / REGISTRY_FILENAME).read_text(encoding="utf-8")
    assert "\\udcff" in source
    assert read_registry(data_dir)["ENTRIES"] == {("\udcff", 3, " "): "  \udcff"}
    assert not list(data_dir.glob("*.tmp"))


def test_locked_registry_backoff_follows_sleep_scale(data_dir, monkeypatch, capsys):
    sleeps = []
    monkeypatch.setattr(time, "sleep", sleeps.append)
    real_replace = os.replace

    def locked(source, target):
        if str(target).endswith(REGISTRY_FILENAME):
            raise PermissionError("locked")
        return real_replace(source, target)

    monkeypatch.setattr(registry_module.os, "replace", locked)
    assert left_pad("foo", 5) == "  foo"
    assert sleeps == []
    assert "snapshot 1 discarded" in capsys.readouterr().err
    assert not list(data_dir.glob("*.tmp"))
    monkeypatch.setenv("SLOP_SLEEP_SCALE", "2")
    registry_module.LayoutRegistryStore(data_dir).commit(2, {})
    assert sleeps == [0.1, 0.2, 0.4, 0.8]
