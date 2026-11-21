"""Conformance: the engine writes only inside its data folder, never reads stdin,
finishes within its time cap and keeps its data folder within the storage caps."""
import csv
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

from leftpad import LayoutEngine, janitor
from leftpad.audit import JOURNAL_NAME, AuditJournal
from leftpad.errors import LayoutServiceError
from leftpad.janitor import MAX_DATA_BYTES, MAX_DATA_FILES, DataDirJanitor

PORT_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = PORT_DIR.parents[1]

REQUESTS = [
    ["abc", "5"],
    ["5", "3", "0"],
    ["x", "4", "ab"],
    ["hello", "13", "."],
    ["x", "9000"],
    ["y" * 500, "2000", "-"],
    ["\u00e9t\u00e9", "8", "\u2588"],
    ["z", "abc"],
]


def cli_env(data_dir, scale="0", seed="7"):
    env = {key: value for key, value in os.environ.items() if not key.startswith("SLOP_")}
    env.update(PYTHONDONTWRITEBYTECODE="1", SLOP_SLEEP_SCALE=scale, SLOP_SEED=seed)
    if data_dir is not None:
        env["SLOP_DATA_DIR"] = str(data_dir)
    return env


def run_cli(args, env, cwd, timeout=60):
    return subprocess.run(
        [sys.executable, str(PORT_DIR), *args],
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
        timeout=timeout,
    )


UNTRACKED_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache"}

ENGINE_FILES = (
    "_layout_registry.py",
    "_layout_registry_replica_1.py",
    "_layout_registry_replica_2.py",
    "layout_telemetry.zip",
    "layout_audit.csv",
)

DECOYS = (
    "layout_notes.tmp",
    "layout_x.tmp",
    "_layout_registry_backup.py",
    "_layout_registry.py.tmp",
    "_layout_registry.py.bak.tmp",
    "_layout_registry.py.12.tmp.old",
    "_layout_registry.py.12a.tmp",
    "layout_audit.csv.old",
    "copy_layout_telemetry.zip",
    # Non-ASCII digits in the temporary-file names.
    "_layout_registry.py.\u0661\u0662.tmp",
    "layout_audit.csv.\u0663.tmp",
    # Zero-padded or zero process ids: os.getpid() never writes those.
    "_layout_registry.py.0001.tmp",
    "layout_audit.csv.0.tmp",
    "layout_telemetry.zip.012.tmp",
)
"""Names close to the engine's own; none of them is written by the engine."""

CASE_VARIANTS = ("Layout_Audit.csv", "_LAYOUT_REGISTRY.PY", "Layout_Telemetry.zip", "_layout_registry_REPLICA_1.py",
                 "_LAYOUT_REGISTRY.PY.12.TMP", "Layout_Audit.csv.12.tmp", "layout_telemetry.ZIP.12.tmp")
"""The engine's exact names in another letter case. On a case-insensitive filesystem each one is the
same file as the engine's own, so they are only planted where the engine itself does not run."""


def snapshot(root, skip=()):
    state = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in skip]
        for name in dirnames:
            state[str(Path(dirpath, name).relative_to(root)) + "/"] = None
        for name in filenames:
            path = Path(dirpath, name)
            info = path.stat()
            state[str(path.relative_to(root))] = (info.st_size, info.st_mtime_ns)
    return state


def test_writes_stay_inside_the_data_folder(tmp_path):
    work, data, sibling, default_work = (tmp_path / name for name in ("work", "data", "sibling", "default"))
    work.mkdir()
    sibling.mkdir()
    default_work.mkdir()
    (sibling / "keep.txt").write_text("unchanged", encoding="utf-8")
    repo_before = snapshot(REPO_ROOT, UNTRACKED_DIRS)
    sibling_before = snapshot(sibling)

    codes = set()
    stderr_lines = []
    for i in range(13):
        proc = run_cli(REQUESTS[i % len(REQUESTS)], cli_env(data, seed=str(i)), work)
        codes.add(proc.returncode)
        stderr_lines.append(proc.stderr.count("\n"))
    codes.add(run_cli(["abc", "5"], cli_env(None), default_work).returncode)

    assert codes <= {0, 75}
    assert max(stderr_lines) <= 2000
    assert snapshot(REPO_ROOT, UNTRACKED_DIRS) == repo_before
    assert snapshot(sibling) == sibling_before
    assert list(work.iterdir()) == []
    assert [p.name for p in default_work.iterdir()] == [".slop-data"]
    assert [p.name for p in (default_work / ".slop-data").iterdir()] == ["left-pad"]
    assert sorted(os.listdir(tmp_path)) == ["data", "default", "sibling", "work"]


@pytest.mark.parametrize("mode", ["closed", "open"])
def test_never_reads_stdin(tmp_path, mode):
    work = tmp_path / "work"
    work.mkdir()
    with open(tmp_path / "out.txt", "wb") as out, open(tmp_path / "err.txt", "wb") as err:
        proc = subprocess.Popen(
            [sys.executable, str(PORT_DIR), "abc", "5"],
            env=cli_env(tmp_path / "data"),
            cwd=work,
            stdin=subprocess.PIPE,
            stdout=out,
            stderr=err,
        )
        try:
            if mode == "closed":
                proc.stdin.close()
            code = proc.wait(timeout=60)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            if not proc.stdin.closed:
                proc.stdin.close()
    assert code in (0, 75)


def test_calls_finish_under_the_time_cap_with_pacing_on(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    walls = []
    for seed in ("1", "2", "3"):
        started = time.perf_counter()
        proc = run_cli(["abc", "5"], cli_env(tmp_path / "data", scale="1", seed=seed), work, timeout=30)
        walls.append(time.perf_counter() - started)
        assert proc.returncode in (0, 75)
    assert max(walls) < 15.0
    assert max(walls) >= 2.0


def test_pacing_budget_holds_at_the_maximum_scale(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    started = time.perf_counter()
    proc = run_cli(["x", "4", "ab"], cli_env(tmp_path / "data", scale="10", seed="1"), work, timeout=30)
    assert time.perf_counter() - started < 15.0
    assert proc.returncode in (0, 75)


def test_calls_are_fast_with_pacing_off(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    for seed in ("1", "2", "3"):
        started = time.perf_counter()
        proc = run_cli(["abc", "5"], cli_env(tmp_path / "data", seed=seed), work)
        assert time.perf_counter() - started < 5.0
        assert proc.returncode in (0, 75)


def test_data_folder_stays_within_caps(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    old = time.time() - 3600
    for i in range(2000):
        stale = data / f"_layout_registry.py.{i}.tmp"
        stale.write_text("x", encoding="utf-8")
        os.utime(stale, (old, old))
    (data / "operator-notes.txt").write_text("keep", encoding="utf-8")
    plant_decoys(data, old)

    for i in range(150):
        engine = LayoutEngine(data, random.Random(i))
        try:
            engine.layout("v" * (i * 7 % 3000), (i * 97) % 10_000, "ab" if i % 3 == 0 else "0")
        except LayoutServiceError:
            pass

    files = [p for p in data.rglob("*") if p.is_file()]
    assert len(files) <= MAX_DATA_FILES
    assert sum(p.stat().st_size for p in files) <= MAX_DATA_BYTES
    assert not [p for p in data.iterdir() if re.fullmatch(r"_layout_registry\.py\.[1-9][0-9]*\.tmp", p.name)]
    assert (data / "operator-notes.txt").read_text(encoding="utf-8") == "keep"
    assert_decoys_survive(data)


def plant_decoys(folder, mtime):
    """Plant files the engine never writes, in the folder, a subfolder and a sibling."""
    planted = []
    nested = folder / "archive"
    sibling = folder.parent / (folder.name + "-sibling")
    for where in (folder, nested, sibling):
        where.mkdir(parents=True, exist_ok=True)
        names = DECOYS if where is folder else DECOYS + ENGINE_FILES + ("_layout_registry.py.12.tmp",)
        for name in names:
            path = where / name
            path.write_text("operator data", encoding="utf-8")
            os.utime(path, (mtime, mtime))
            planted.append(path)
    return planted


def assert_decoys_survive(folder):
    for where in (folder, folder / "archive", folder.parent / (folder.name + "-sibling")):
        names = DECOYS if where == folder else DECOYS + ENGINE_FILES + ("_layout_registry.py.12.tmp",)
        for name in names:
            assert (where / name).read_text(encoding="utf-8") == "operator data", where / name


def test_compaction_ignores_files_the_engine_does_not_write(tmp_path):
    data = tmp_path / "data"
    old = time.time() - 3600
    plant_decoys(data, old)
    variants = plant_case_variants(data, old)
    own_stale = [data / f"{name}.{pid}.tmp" for name in ENGINE_FILES for pid in (7, 4242)]
    for path in own_stale:
        path.write_text("x", encoding="utf-8")
        os.utime(path, (old, old))

    DataDirJanitor(data).compact()

    assert not [path for path in own_stale if path.exists()]
    assert_decoys_survive(data)
    assert all(path.read_text(encoding="utf-8") == "operator data" for path in variants)


def plant_case_variants(folder, mtime):
    planted = []
    for name in CASE_VARIANTS:
        path = folder / name
        path.write_text("operator data", encoding="utf-8")
        os.utime(path, (mtime, mtime))
        planted.append(path)
    return planted


def test_compaction_prunes_the_oldest_own_files_past_the_caps(tmp_path, monkeypatch):
    data = tmp_path / "data"
    ancient = time.time() - 7200
    plant_decoys(data, ancient)
    variants = plant_case_variants(data, ancient)
    base = time.time() - 30
    own = []
    for i in range(20):
        path = data / f"_layout_registry.py.{1000 + i}.tmp"
        path.write_text("x" * 100, encoding="utf-8")
        os.utime(path, (base + i, base + i))
        own.append(path)
    monkeypatch.setattr(janitor, "COMPACT_FILES", 5)

    DataDirJanitor(data).compact()

    assert [path.exists() for path in own] == [False] * 15 + [True] * 5
    assert_decoys_survive(data)

    monkeypatch.setattr(janitor, "COMPACT_FILES", 9_000)
    monkeypatch.setattr(janitor, "COMPACT_BYTES", 250)
    DataDirJanitor(data).compact()

    assert [path.exists() for path in own[15:]] == [False, False, False, True, True]
    assert_decoys_survive(data)
    assert all(path.read_text(encoding="utf-8") == "operator data" for path in variants)


def test_compaction_tolerates_files_removed_by_a_concurrent_request(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    for name in ENGINE_FILES:
        (data / name).write_text("x", encoding="utf-8")
    vanishing = data / "_layout_registry.py.31337.tmp"
    vanishing.write_text("x", encoding="utf-8")
    real_stat, real_exists, real_is_file = Path.stat, Path.exists, Path.is_file

    def stat(self, *args, **kwargs):
        if self.name == vanishing.name:
            raise FileNotFoundError(self)
        return real_stat(self, *args, **kwargs)

    def exists(self, *args, **kwargs):
        return True if self.name == vanishing.name else real_exists(self, *args, **kwargs)

    def is_file(self, *args, **kwargs):
        return True if self.name == vanishing.name else real_is_file(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    monkeypatch.setattr(Path, "exists", exists)
    monkeypatch.setattr(Path, "is_file", is_file)

    DataDirJanitor(data).compact()

    monkeypatch.undo()
    assert all((data / name).exists() for name in ENGINE_FILES)


HOSTILE_REGISTRY = (
    "import os\n"
    "open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'PWNED'), 'w').close()\n"
    "open('PWNED', 'w').close()\n"
    "SCHEMA_VERSION = 3\n"
    "GENERATION = 7\n"
    "ENTRIES = {}\n"
)


def test_registry_modules_in_the_data_folder_are_never_executed(tmp_path, monkeypatch):
    work, data = tmp_path / "work", tmp_path / "data"
    work.mkdir()
    data.mkdir()
    registries = [data / name for name in ENGINE_FILES[:3]]
    answers = []
    for seed in range(8):
        for path in registries:
            path.write_text(HOSTILE_REGISTRY, encoding="utf-8")
        proc = run_cli(["abc", "5"], cli_env(data, seed=str(seed)), work)
        answers.append(proc.stdout.strip() if proc.returncode == 0 else None)
        if proc.returncode == 0:
            assert "import os" not in registries[0].read_text(encoding="utf-8")
    monkeypatch.chdir(work)
    for seed in range(8):
        for path in registries:
            path.write_text(HOSTILE_REGISTRY, encoding="utf-8")
        try:
            answers.append(LayoutEngine(data, random.Random(seed)).layout("abc", 5))
        except LayoutServiceError:
            pass
    assert not [p for p in tmp_path.rglob("*") if p.name == "PWNED"]
    assert sum(1 for answer in answers if answer) >= 8


def test_registry_refuses_a_snapshot_swapped_after_the_link_check(tmp_path, monkeypatch):
    from leftpad import registry

    store = registry.LayoutRegistryStore(tmp_path)
    store.path = Path(os.devnull)  # a device: opens and reads fine, but is not a regular file
    real_lstat, regular = os.lstat, os.lstat(__file__)

    def lstat(path, *args, **kwargs):  # the check sees a regular file; the open gets the device
        return regular if os.fspath(path) == os.devnull else real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", lstat)
    assert store.load() is None


@pytest.mark.parametrize("value", ["=1+2", "+SUM(A1)", "-2+3", "@cmd", "=HYPERLINK(\"x\")"])
def test_audit_journal_neutralises_spreadsheet_formulas(tmp_path, value):
    AuditJournal(tmp_path).append({"generation": 1, "value": value, "fill": value, "length": -3})
    with open(tmp_path / JOURNAL_NAME, newline="", encoding="ascii") as handle:
        row = list(csv.DictReader(handle))[-1]
    for column in ("value", "fill"):
        assert row[column][:1] not in ("=", "+", "-", "@"), row
        assert row[column].lstrip("'") == value
    assert row["length"] == "-3"


def test_audit_journal_write_failure_does_not_fail_the_request(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    real_write = Path.write_text

    def write_text(self, *args, **kwargs):
        if self.name.startswith(JOURNAL_NAME):
            raise OSError(28, "No space left on device")
        return real_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", write_text)
    AuditJournal(data).append({"generation": 1, "value": "abc"})
    for seed in range(40):
        try:
            result = LayoutEngine(data, random.Random(seed)).layout("abc", 5)
        except LayoutServiceError:
            continue
        assert isinstance(result, str)
        break
    else:
        pytest.fail("no request completed")
    assert not (data / JOURNAL_NAME).exists()


def test_benchmark_reuses_one_folder_and_keeps_other_files(tmp_path, monkeypatch, capsys):
    import importlib.util

    spec = importlib.util.spec_from_file_location("leftpad_benchmark", PORT_DIR / "benchmarks" / "reliability.py")
    benchmark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark)
    root = tmp_path / "data"
    for key in ("SLOP_DATA_DIR", "SLOP_SLEEP_SCALE", "SLOP_SEED"):
        monkeypatch.setenv(key, "0")
    monkeypatch.setattr(sys, "argv", ["reliability.py", "--calls", "3"])

    def run():
        monkeypatch.setenv("SLOP_DATA_DIR", str(root))
        assert benchmark.main() == 0
        return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_dir())

    folders = run()
    assert len(folders) == 1
    plant_decoys(root / folders[0], time.time() - 3600)
    planted = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_dir())
    assert run() == planted
    assert run() == planted
    assert_decoys_survive(root / folders[0])
    capsys.readouterr()
