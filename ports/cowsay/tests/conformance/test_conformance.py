"""Conformance: the properties that keep Ruminant safe to run, checked for real."""

import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

PORT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PORT_ROOT / "src"))

from ruminant import storage  # noqa: E402
from ruminant.cli import main  # noqa: E402
from ruminant.registry import MAX_LINES_PER_COW  # noqa: E402
from ruminant.storage import CACHE_SLOTS, JOURNAL_SLOTS  # noqa: E402
from ruminant.telemetry import get_logger, reset_log_budget  # noqa: E402

TIME_CAP_SECONDS = 15.0
MAX_FILES = 10_000
MAX_BYTES = 50 * 1024 * 1024
MAX_STDERR_LINES = 2_000
HAPPY_CALLS = 200
HELLO = (
    " ______________\n"
    "< Hello, world >\n"
    " --------------\n"
    "        \\   ^__^\n"
    "         \\  (oo)\\_______\n"
    "            (__)\\       )\\/\\\n"
    "                ||----w |\n"
    "                ||     ||\n"
)
BALLOON_TOP = re.compile(r"^ _*$")
BALLOON_BOTTOM = re.compile(r"^ -*$")
# Every name the port writes, exactly.
JOURNAL_NAMES = frozenset(f"slot-{n:02d}.json" for n in range(JOURNAL_SLOTS))
CACHE_SLOT_NAMES = frozenset(f"slot-{n}" for n in range(CACHE_SLOTS))
CACHE_LINE_NAMES = frozenset(f"{n:04d}.line" for n in range(1, MAX_LINES_PER_COW + 1))
OLD_MTIME = 946_684_800  # 2000-01-01, older than anything the port writes
# Files the port did not create, named close to its own, inside and next to its folders.
DECOYS = (
    "notes.txt",
    "journal-archive/slot-00.json",
    "journal/slot-0.json",
    "journal/slot-000.json",
    "journal/slot-00.json.bak",
    "journal/slot-00.jsonl",
    "journal/backlog-00001.json",
    "journal/archive/slot-01.json",
    "scanline-cache/0001.line",
    "scanline-cache/slot-10/0001.line",
    "scanline-cache/slot-0/0001.line.bak",
    "scanline-cache/slot-0/00001.line",
    "scanline-cache/slot-0/001.line",
    "scanline-cache/slot-0/notes.txt",
    "scanline-cache/slot-0/nested/0001.line",
    "scanline-cache/slot-3/0001.lin",
    # Non-ASCII digits and other letter cases. Names that would alias a file the port
    # writes on a case-insensitive filesystem (slot-00.json) are left out on purpose.
    "journal/slot-\u0660\u0660.json",
    "journal/slot-\u0661\u0662.json",
    "scanline-cache/slot-\u0660/0001.line",
    "scanline-cache/slot-0/\u0660\u0660\u0660\u0661.line",
    "journal/SLOT-99.JSON",
    "journal/Slot-98.json",
    "scanline-cache/SLOT-9/0001.line",
    "scanline-cache/slot-0/9999.LINE",
    # The right shape, but outside the slot and line ranges the port writes.
    "journal/slot-64.json",
    "journal/slot-65.json",
    "scanline-cache/slot-8/0001.line",
    "scanline-cache/slot-0/0000.line",
    f"scanline-cache/slot-0/{MAX_LINES_PER_COW + 1:04d}.line",
    "index/user.txt",
    "metrics/user.txt",
)


def env_for(data_dir=None, seed="7", scale="0"):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SLOP_")}
    env.update({"SLOP_SLEEP_SCALE": scale, "SLOP_SEED": seed, "PYTHONDONTWRITEBYTECODE": "1"})
    if data_dir is not None:
        env["SLOP_DATA_DIR"] = str(data_dir)
    return env


def run_cli(argv, env, cwd, timeout=60, stdin=subprocess.DEVNULL):
    return subprocess.run(
        [sys.executable, str(PORT_ROOT), *argv], stdin=stdin, capture_output=True, env=env, cwd=cwd, timeout=timeout
    )


def in_process(argv, data_dir, seed, capsys):
    code = main(list(argv), environ={"SLOP_SLEEP_SCALE": "0", "SLOP_SEED": str(seed), "SLOP_DATA_DIR": str(data_dir)})
    out, err = capsys.readouterr()
    return code, out, err


def snapshot(root):
    return {
        str(p.relative_to(root)): (p.is_dir(), p.stat().st_size if p.is_file() else 0, p.stat().st_mtime_ns)
        for p in root.rglob("*")
    }


def well_formed(out, message="Hello, world"):
    """A plausible frame: ASCII, a closed balloon holding the message, then a figure."""
    if not out.isascii() or not out.endswith("\n"):
        return False
    lines = out.split("\n")[:-1]
    if len(lines) < 6 or any(len(line) > 120 for line in lines):
        return False
    return (
        bool(BALLOON_TOP.match(lines[0]))
        and message in lines[1]
        and lines[1][0] in "</"
        and bool(BALLOON_BOTTOM.match(lines[2]))
    )


def data_usage(root):
    files = [p for p in root.rglob("*") if p.is_file()]
    return len(files), sum(p.stat().st_size for p in files)


def decoy_text(name, size):
    return f"user data: {name}".ljust(size, ".")


def plant_decoys(data, names=DECOYS, size=0):
    for name in names:
        path = data / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(decoy_text(name, size), encoding="utf-8")
        os.utime(path, (OLD_MTIME, OLD_MTIME))


def assert_decoys_intact(data, names=DECOYS, size=0):
    missing = [n for n in names if not (data / n).is_file()]
    assert missing == []
    for name in names:
        assert (data / name).read_text(encoding="utf-8") == decoy_text(name, size)


def own_journal(data):
    folder = data / "journal"
    return [p for p in folder.iterdir() if p.is_file() and p.name in JOURNAL_NAMES] if folder.is_dir() else []


def own_cache_slots(data):
    folder = data / "scanline-cache"
    return [p for p in folder.iterdir() if p.is_dir() and p.name in CACHE_SLOT_NAMES] if folder.is_dir() else []


def own_cache_lines(data):
    return [p for s in own_cache_slots(data) for p in s.iterdir() if p.is_file() and p.name in CACHE_LINE_NAMES]


def test_writes_nothing_outside_the_data_dir(tmp_path):
    work, data, sibling = tmp_path / "work", tmp_path / "data", tmp_path / "sibling"
    for folder in (work, data, sibling):
        folder.mkdir()
    (sibling / "keep.txt").write_text("untouched", encoding="utf-8")
    port_before, work_before, sibling_before = snapshot(PORT_ROOT), snapshot(work), snapshot(sibling)
    for seed in range(6):
        for argv in (["moo"], ["-f", "tux", "hi"], ["-l"], ["-n", "a\n b"], ["-W", "1", "x"], []):
            run_cli(argv, env_for(data, seed=str(seed)), work)
    assert snapshot(PORT_ROOT) == port_before
    assert snapshot(work) == work_before
    assert snapshot(sibling) == sibling_before
    assert data_usage(data)[0] > 0


def test_default_data_dir_is_under_cwd(tmp_path):
    port_before = snapshot(PORT_ROOT)
    for seed in range(4):
        run_cli(["moo"], env_for(None, seed=str(seed)), tmp_path)
    assert snapshot(PORT_ROOT) == port_before
    assert [p.name for p in tmp_path.iterdir()] == [".slop-data"]
    assert [p.name for p in (tmp_path / ".slop-data").iterdir()] == ["cowsay"]


@pytest.mark.parametrize("mode", ["closed", "open-pipe"])
def test_never_reads_stdin(tmp_path, mode):
    out_path, err_path = tmp_path / "out.txt", tmp_path / "err.txt"
    with open(out_path, "wb") as out, open(err_path, "wb") as err:
        stdin = subprocess.DEVNULL if mode == "closed" else subprocess.PIPE
        proc = subprocess.Popen(
            [sys.executable, str(PORT_ROOT), "moo"], stdin=stdin, stdout=out, stderr=err,
            env=env_for(tmp_path / "data"), cwd=tmp_path,
        )
        try:
            code = proc.wait(timeout=60)
        finally:
            if proc.stdin:
                proc.stdin.close()
            if proc.poll() is None:
                proc.kill()
    assert code in (0, 74, 75)


def test_calls_finish_under_the_time_cap(tmp_path):
    long_message = "word " * 60
    for seed, argv in ((1, ["Hello, world"]), (2, ["-f", "tux", "hi"]), (3, [long_message])):
        started = time.perf_counter()
        run_cli(argv, env_for(tmp_path / "data", seed=str(seed), scale="1"), tmp_path, timeout=TIME_CAP_SECONDS + 5)
        assert time.perf_counter() - started < TIME_CAP_SECONDS


def test_calls_are_fast_at_scale_zero(tmp_path):
    for seed in range(3):
        started = time.perf_counter()
        run_cli(["Hello, world"], env_for(tmp_path / "data", seed=str(seed)), tmp_path)
        assert time.perf_counter() - started < 5.0


def test_data_dir_stays_within_caps_and_spares_foreign_files(tmp_path, capsys):
    data = tmp_path / "data"
    plant_decoys(data)
    for seed in range(JOURNAL_SLOTS + 16):
        in_process(["-f", "tux" if seed % 2 else "default", f"call {seed}"], data, seed, capsys)
    count, size = data_usage(data)
    assert count <= MAX_FILES and size <= MAX_BYTES
    assert 0 < len(own_journal(data)) <= JOURNAL_SLOTS
    assert 0 < len(own_cache_slots(data)) <= CACHE_SLOTS
    assert_decoys_intact(data)


def test_quota_pruning_never_deletes_foreign_files(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(storage, "MAX_DATA_FILES", 5)
    data = tmp_path / "data"
    plant_decoys(data)
    for seed in range(12):
        in_process(["moo"], data, seed, capsys)
    assert_decoys_intact(data)
    assert len(own_journal(data)) + len(own_cache_lines(data)) <= 5


@pytest.mark.parametrize("cap", ["files", "bytes"])
def test_quota_counts_the_whole_data_dir_and_prunes_own_files(tmp_path, capsys, monkeypatch, cap):
    files_cap, bytes_cap = (30, MAX_BYTES) if cap == "files" else (MAX_FILES, 24 * 1024)
    monkeypatch.setattr(storage, "MAX_DATA_FILES", files_cap)
    monkeypatch.setattr(storage, "MAX_DATA_BYTES", bytes_cap)
    data = tmp_path / "data"
    foreign = tuple(f"other/user-{i:02d}.txt" for i in range(10))
    plant_decoys(data, foreign, size=1024)
    renders = 0
    for seed in range(40):
        renders += in_process(["moo"], data, seed, capsys)[0] == 0
    count, size = data_usage(data)
    assert count <= files_cap and size <= bytes_cap
    assert len(own_journal(data)) < renders
    assert_decoys_intact(data, foreign, size=1024)


def test_quota_tolerates_files_removed_by_another_run(tmp_path, monkeypatch):
    data = tmp_path / "data"
    (data / "journal").mkdir(parents=True)
    for slot in range(4):
        path = data / "journal" / f"slot-{slot:02d}.json"
        path.write_text("x", encoding="utf-8")
        os.utime(path, (OLD_MTIME + slot, OLD_MTIME + slot))
    gone_before_stat, gone_before_unlink = "slot-03.json", "slot-00.json"
    real_stat, real_lstat, real_is_file, real_unlink = Path.stat, Path.lstat, Path.is_file, Path.unlink

    def stat(self, *args, **kwargs):
        if self.name == gone_before_stat:
            raise FileNotFoundError(self)
        return real_stat(self, *args, **kwargs)

    def lstat(self):
        if self.name == gone_before_stat:
            raise FileNotFoundError(self)
        return real_lstat(self)

    def is_file(self, *args, **kwargs):
        return True if self.name == gone_before_stat else real_is_file(self, *args, **kwargs)

    def unlink(self, *args, **kwargs):
        if self.name == gone_before_unlink:
            raise FileNotFoundError(self)
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(storage, "MAX_DATA_FILES", 1)
    monkeypatch.setattr(Path, "stat", stat)
    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(Path, "is_file", is_file)
    monkeypatch.setattr(Path, "unlink", unlink)
    storage.DataDirSteward(data, storage.Pacer(0), get_logger("ruminant.conformance")).enforce()
    monkeypatch.undo()
    assert (data / "journal" / gone_before_stat).exists()


def steward(data):
    return storage.DataDirSteward(data, storage.Pacer(0), get_logger("ruminant.conformance"))


def make_dir_link(link, target, kind):
    """A symlink or a Windows junction at ``link`` pointing to ``target``; skips when the OS refuses."""
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        if kind == "junction":
            import _winapi

            _winapi.CreateJunction(str(target), str(link))
        else:
            os.symlink(target, link, target_is_directory=True)
    except (ImportError, AttributeError, NotImplementedError, OSError) as exc:
        pytest.skip(f"cannot create a {kind} here: {exc}")


@pytest.mark.parametrize("kind", ["symlink", "junction"])
@pytest.mark.parametrize("linked", ["journal", "scanline-cache", "scanline-cache/slot-0"])
def test_quota_never_follows_links_out_of_the_data_dir(tmp_path, monkeypatch, kind, linked):
    data, outside = tmp_path / "data", tmp_path / "outside"
    names = ("slot-00.json", "slot-01.json", "slot-0/0001.line", "0001.line", "0002.line")
    plant_decoys(outside, names)
    plant_decoys(data, ("notes.txt",))  # puts the data dir over its quota of 0 files
    make_dir_link(data / linked, outside, kind)
    monkeypatch.setattr(storage, "MAX_DATA_FILES", 0)
    steward(data).enforce()
    assert_decoys_intact(outside, names)


def test_quota_tolerates_a_slot_removed_before_it_is_listed(tmp_path, monkeypatch):
    data = tmp_path / "data"
    plant_decoys(data, ("journal/slot-00.json", "scanline-cache/slot-0/0001.line", "scanline-cache/slot-1/0001.line"))
    real_iterdir = Path.iterdir

    def iterdir(self):
        if self.name == "slot-0":
            raise FileNotFoundError(self)
        return real_iterdir(self)

    monkeypatch.setattr(storage, "MAX_DATA_FILES", 0)
    monkeypatch.setattr(Path, "iterdir", iterdir)
    steward(data).enforce()
    monkeypatch.undo()
    assert not (data / "journal" / "slot-00.json").exists()
    assert not (data / "scanline-cache" / "slot-1" / "0001.line").exists()


def test_quota_moves_past_a_file_it_cannot_delete(tmp_path, monkeypatch):
    data = tmp_path / "data"
    for slot in range(3):
        path = data / "journal" / f"slot-{slot:02d}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
        os.utime(path, (OLD_MTIME + slot, OLD_MTIME + slot))
    real_unlink = Path.unlink

    def unlink(self, *args, **kwargs):
        if self.name == "slot-00.json":
            raise PermissionError(self)
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(storage, "MAX_DATA_FILES", 2)
    monkeypatch.setattr(Path, "unlink", unlink)
    steward(data).enforce()
    monkeypatch.undo()
    journal = data / "journal"
    assert [(journal / f"slot-{n:02d}.json").exists() for n in range(3)] == [True, False, True]


def test_stderr_log_budget_counts_lines(capsys):
    reset_log_budget()
    logger = get_logger("ruminant.conformance")
    for i in range(MAX_STDERR_LINES):
        logger.error("multi-line record %d\nsecond line\nthird line", i)
    err = capsys.readouterr().err
    reset_log_budget()
    assert 0 < len(err.splitlines()) <= MAX_STDERR_LINES


def test_fixed_seed_is_reproducible(tmp_path, capsys):
    for seed in range(15):
        first = in_process(["Hello, world"], tmp_path / f"a{seed}", seed, capsys)
        second = in_process(["Hello, world"], tmp_path / f"b{seed}", seed, capsys)
        assert first[:2] == second[:2]
    env = env_for(tmp_path / "c", seed="42")
    one = run_cli(["-f", "tux", "hi"], env, tmp_path)
    env["SLOP_DATA_DIR"] = str(tmp_path / "d")
    two = run_cli(["-f", "tux", "hi"], env, tmp_path)
    assert (one.returncode, one.stdout) == (two.returncode, two.stdout)


def test_happy_path_mostly_works_and_the_fault_model_is_live(tmp_path, capsys):
    exact = formatted = wrong = failed = 0
    for seed in range(HAPPY_CALLS):
        code, out, err = in_process(["Hello,", "world"], tmp_path / f"d{seed}", seed, capsys)
        assert len(err.splitlines()) <= MAX_STDERR_LINES
        if code != 0:
            assert code in (74, 75) and out == ""
            failed += 1
            continue
        assert well_formed(out), out
        formatted += 1
        if out == HELLO:
            exact += 1
        else:
            wrong += 1
            assert "frame delivered successfully" in err
    assert formatted >= 0.75 * HAPPY_CALLS
    assert exact >= 0.5 * HAPPY_CALLS
    assert wrong > 0
    assert failed > 0


def test_stderr_stays_bounded_for_the_largest_input(tmp_path, capsys):
    for seed in range(3):
        code, out, err = in_process(["-W", "2", "x" * 4096], tmp_path / f"d{seed}", seed, capsys)
        assert len(err.splitlines()) <= MAX_STDERR_LINES
        assert len(out) < 200_000
