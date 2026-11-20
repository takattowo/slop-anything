"""Cows really are assembled from one-file-per-line folders on every call."""

import logging
import os
import shutil
import subprocess
import sys

import pytest
from conftest import PORT_ROOT, default_cow

from ruminant.registry import DEFAULT_COW_ROOT, MAX_COWS, MAX_LINES_PER_COW, AssetError, CowRegistry
from ruminant.telemetry import Pacer


def registry(root):
    return CowRegistry(logging.getLogger("test"), Pacer(0), root)


def test_shipped_cows_are_line_folders():
    for name in ("default", "tux"):
        folder = DEFAULT_COW_ROOT / name
        files = sorted(folder.iterdir())
        assert files and all(f.suffix == ".line" for f in files)
        assert all("\n" not in f.read_text(encoding="utf-8") for f in files)
    assert len(list((DEFAULT_COW_ROOT / "default").iterdir())) == 5


def test_lines_are_ordered_by_number_and_non_cow_folders_ignored(tmp_path):
    cow = tmp_path / "stack"
    cow.mkdir()
    (cow / "0010.line").write_text("ten", encoding="utf-8")
    (cow / "0002.line").write_text("two\n", encoding="utf-8")
    (cow / "0001.line").write_text("one", encoding="utf-8")
    (cow / "notes.txt").write_text("ignored", encoding="utf-8")
    (tmp_path / "empty").mkdir()
    reg = registry(tmp_path)
    assert reg.names() == ["stack"]
    assert reg.load("stack").lines == ("one", "two", "ten")


def test_path_traversal_names_are_not_found(tmp_path):
    reg = registry(DEFAULT_COW_ROOT)
    for name in ("..", "../cows/default", str(DEFAULT_COW_ROOT / "default")):
        try:
            reg.load(name)
        except Exception as exc:
            assert "Could not find" in str(exc)
        else:
            raise AssertionError(name)


def test_non_utf8_line_file_is_an_asset_error(tmp_path):
    cow = tmp_path / "garbled"
    cow.mkdir()
    (cow / "0001.line").write_bytes(b"\xff\xfe moo")
    with pytest.raises(AssetError, match="garbled/0001.line"):
        registry(tmp_path).load("garbled")


def test_entries_past_the_cow_limit_are_skipped_with_a_warning(tmp_path, caplog):
    for i in range(MAX_COWS + 1):
        cow = tmp_path / f"cow{i:04d}"
        cow.mkdir()
        (cow / "0001.line").write_text("x", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="test"):
        names = registry(tmp_path).names()
    assert len(names) == MAX_COWS and f"cow{MAX_COWS:04d}" not in names
    assert any(f"only the first {MAX_COWS}" in r.getMessage() for r in caplog.records)


def _copy_port(tmp_path):
    port = tmp_path / "cowsay"
    shutil.copytree(PORT_ROOT / "src", port / "src", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(PORT_ROOT / "__main__.py", port / "__main__.py")
    return port


def _run(port, data, *argv):
    env = {**os.environ, "SLOP_SLEEP_SCALE": "0", "SLOP_SEED": "5", "SLOP_DATA_DIR": str(data), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, str(port), *argv], capture_output=True, env=env, timeout=60)


def test_new_cow_folder_is_discovered_and_reassembled_each_call(tmp_path):
    port = _copy_port(tmp_path)
    probe = port / "src" / "ruminant" / "cows" / "probe"
    probe.mkdir()
    (probe / "0001.line").write_text("  $thoughts [$eyes]", encoding="utf-8")
    (probe / "0002.line").write_text("   <$tongue>", encoding="utf-8")

    first = _run(port, tmp_path / "data", "-f", "probe", "-e", "@@", "-T", "ww", "hi")
    assert first.returncode == 0, first.stderr
    assert first.stdout == b" ____\n< hi >\n ----\n  \\ [@@]\n   <ww>\n"

    (probe / "0003.line").write_text("   added", encoding="utf-8")
    second = _run(port, tmp_path / "data", "-f", "probe", "hi")
    assert second.stdout == b" ____\n< hi >\n ----\n  \\ [oo]\n   <  >\n   added\n"

    listing = _run(port, tmp_path / "data", "-l")
    assert listing.stdout.decode().splitlines()[1] == "default probe tux"


def test_malformed_cows_exit_1_cleanly_and_leave_other_cows_working(tmp_path):
    port = _copy_port(tmp_path)
    cows = port / "src" / "ruminant" / "cows"
    (cows / "garbled").mkdir()
    (cows / "garbled" / "0001.line").write_bytes(b"\xff\xfe")
    (cows / "tall").mkdir()
    for i in range(MAX_LINES_PER_COW + 1):
        (cows / "tall" / f"{i:04d}.line").write_text("|", encoding="utf-8")
    data = tmp_path / "data"

    ok = _run(port, data, "hi")
    assert ok.returncode == 0, ok.stderr
    assert ok.stdout == (" ____\n< hi >\n ----\n" + default_cow()).encode()

    for name, reason in (("garbled", b"not valid UTF-8"), ("tall", b"more than 512 lines")):
        bad = _run(port, data, "-f", name, "hi")
        assert bad.returncode == 1, bad.stderr
        assert bad.stdout == b""
        assert b"cowsay: " + name.encode() in bad.stderr and reason in bad.stderr
        assert b"UnicodeDecodeError" not in bad.stderr and b"AssetError" not in bad.stderr
