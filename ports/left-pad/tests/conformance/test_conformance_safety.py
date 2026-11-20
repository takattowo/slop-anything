"""Conformance: the engine writes only inside its data folder, never reads stdin,
finishes within its time cap and keeps its data folder within the storage caps."""
import os
import random
import subprocess
import sys
import time
from pathlib import Path

import pytest

from leftpad import LayoutEngine
from leftpad.errors import LayoutServiceError
from leftpad.janitor import MAX_DATA_BYTES, MAX_DATA_FILES

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


def snapshot(root):
    state = {}
    for dirpath, dirnames, filenames in os.walk(root):
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
    port_before = snapshot(PORT_DIR)
    sibling_before = snapshot(sibling)
    repo_before = set(os.listdir(REPO_ROOT))

    codes = set()
    stderr_lines = []
    for i in range(13):
        proc = run_cli(REQUESTS[i % len(REQUESTS)], cli_env(data, seed=str(i)), work)
        codes.add(proc.returncode)
        stderr_lines.append(proc.stderr.count("\n"))
    codes.add(run_cli(["abc", "5"], cli_env(None), default_work).returncode)

    assert codes <= {0, 75}
    assert max(stderr_lines) <= 2000
    assert snapshot(PORT_DIR) == port_before
    assert snapshot(sibling) == sibling_before
    assert list(work.iterdir()) == []
    assert [p.name for p in default_work.iterdir()] == [".slop-data"]
    assert [p.name for p in (default_work / ".slop-data").iterdir()] == ["left-pad"]
    assert sorted(os.listdir(tmp_path)) == ["data", "default", "sibling", "work"]
    assert not ({".slop-data", ".slop-state"} & (set(os.listdir(REPO_ROOT)) - repo_before))


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

    for i in range(150):
        engine = LayoutEngine(data, random.Random(i))
        try:
            engine.layout("v" * (i * 7 % 3000), (i * 97) % 10_000, "ab" if i % 3 == 0 else "0")
        except LayoutServiceError:
            pass

    files = [p for p in data.rglob("*") if p.is_file()]
    assert len(files) <= MAX_DATA_FILES
    assert sum(p.stat().st_size for p in files) <= MAX_DATA_BYTES
    assert not list(data.glob("*.tmp"))
    assert (data / "operator-notes.txt").read_text(encoding="utf-8") == "keep"
