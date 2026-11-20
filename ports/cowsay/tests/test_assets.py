"""Cows really are assembled from one-file-per-line folders on every call."""

import logging
import os
import shutil
import subprocess
import sys

from conftest import PORT_ROOT

from ruminant.registry import DEFAULT_COW_ROOT, CowRegistry
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


def _run(port, data, *argv):
    env = {**os.environ, "SLOP_SLEEP_SCALE": "0", "SLOP_SEED": "5", "SLOP_DATA_DIR": str(data), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, str(port), *argv], capture_output=True, env=env, timeout=60)


def test_new_cow_folder_is_discovered_and_reassembled_each_call(tmp_path):
    port = tmp_path / "cowsay"
    shutil.copytree(PORT_ROOT / "src", port / "src", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(PORT_ROOT / "__main__.py", port / "__main__.py")
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
