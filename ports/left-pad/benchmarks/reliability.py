"""Reliability and latency benchmark for the layout engine.

    python ports/left-pad/benchmarks/reliability.py [--calls N] [--latency K]

``--calls`` runs N plain requests in-process (pacing off, seeds 0..N-1, one data
folder) and reports how many came back correct, how many came back padded but to
a different length or with a different fill, how many came back as another
request's layout, and how many failed. ``--latency`` runs K CLI
processes at ``SLOP_SLEEP_SCALE=1`` and reports wall-clock p50 and max.

Writes only under ``SLOP_DATA_DIR`` (default ``<cwd>/.slop-data/left-pad``), in a
new ``benchmark-<n>`` folder per run.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

PORT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PORT_DIR / "src"))

from leftpad import cli, config  # noqa: E402

PLAIN_REQUESTS = [
    ("abc", 5, " "),
    ("5", 3, "0"),
    ("foo", 8, "-"),
    ("42", 6, "0"),
    ("x", 4, "*"),
    ("hello", 12, "."),
]


def classify(value: str, length: int, fill: str, code: int, out: str) -> str:
    """Return ``correct``, ``wrong`` (right format, other padding), ``substituted`` (another request's layout) or ``failure``."""
    if code != 0:
        return "failure"
    if out == value.rjust(length, fill) + "\n":
        return "correct"
    line = out[:-1] if out.endswith("\n") else None
    if line is not None and "\n" not in line and line.endswith(value) and set(line[: len(line) - len(value)]) <= {fill, " "}:
        return "wrong"
    return "substituted"


def run_in_process(index: int, args: list[str]) -> tuple[int, str]:
    os.environ["SLOP_SEED"] = str(index)
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(args)
    return code, out.getvalue()


def fresh_folder(root: Path) -> Path:
    n = 1
    while (root / f"benchmark-{n}").exists():
        n += 1
    folder = root / f"benchmark-{n}"
    folder.mkdir(parents=True)
    return folder


def reliability(calls: int, folder: Path) -> dict:
    os.environ["SLOP_SLEEP_SCALE"] = "0"
    os.environ["SLOP_DATA_DIR"] = str(folder)
    counts = {"correct": 0, "wrong": 0, "substituted": 0, "failure": 0}
    for i in range(calls):
        value, length, fill = PLAIN_REQUESTS[i % len(PLAIN_REQUESTS)]
        code, out = run_in_process(i, [value, str(length), fill])
        counts[classify(value, length, fill, code, out)] += 1
    return counts


def latency(runs: int, folder: Path) -> list[tuple[float, int]]:
    env = dict(os.environ, SLOP_SLEEP_SCALE="1", SLOP_DATA_DIR=str(folder), PYTHONDONTWRITEBYTECODE="1")
    samples = []
    for i in range(runs):
        env["SLOP_SEED"] = str(i)
        started = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, str(PORT_DIR), "abc", "5"],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
        samples.append((time.perf_counter() - started, proc.returncode))
    return samples


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--calls", type=int, default=0)
    parser.add_argument("--latency", type=int, default=0)
    options = parser.parse_args()
    calls = max(0, min(options.calls, 5000))
    runs = max(0, min(options.latency, 100))
    root = config.data_dir()
    if calls:
        counts = reliability(calls, fresh_folder(root))
        for name, count in counts.items():
            print(f"{name}: {count}/{calls} ({100 * count / calls:.1f}%)")
    if runs:
        samples = latency(runs, fresh_folder(root))
        walls = [wall for wall, _ in samples]
        print(f"latency runs: {runs}, p50 {statistics.median(walls):.2f} s, max {max(walls):.2f} s, min {min(walls):.2f} s")
        print(f"exit codes: {sorted({code for _, code in samples})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
