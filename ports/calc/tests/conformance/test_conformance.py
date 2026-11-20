"""Conformance suite: the guarantees that keep the service safe to run."""

import os
import random
import re
import subprocess
import sys
import threading
import time
from decimal import Decimal
from pathlib import Path

import pytest

from conftest import PORT_DIR
from arith_inference.errors import CalcError, InvalidExpression
from arith_inference.ledger import FIELDS, MAX_SCAN_BYTES, encode_row, parse_rows
from arith_inference.service import ArithmeticInferenceService
from arith_inference.settings import FaultModel

REPO = PORT_DIR.parents[1]
RESULT = re.compile(r"-?\d+(\.\d+)?(e[+-]\d+)?")
MAX_DIR_BYTES = 50 * 1024 * 1024
MAX_FILES = 10_000

# Expected answers worked out by hand, independent of the service code.
CORPUS = [
    ("1+1", "2"),
    ("12*12", "144"),
    ("(1+2)*3", "9"),
    ("100-58", "42"),
    ("7*8", "56"),
    ("2+2", "4"),
    ("0.1+0.2", "0.3"),
    ("10/4", "2.5"),
    ("-5//2", "-3"),
    ("10%3", "1"),
    ("2**10", "1024"),
    ("3+4*5-6", "17"),
    ("2**64", "18446744073709551616"),
    ("123456789*3", "370370367"),
    ("1/8", "0.125"),
    ("9-3/3*2", "7"),
    ("(2.5+2.5)*2", "10"),
    ("-(4-10)", "6"),
    ("1e3+1", "1001"),
    ("8//3+8%3", "4"),
]


def run(*args, cwd, env=None, stdin=subprocess.DEVNULL, timeout=60):
    base = {k: v for k, v in os.environ.items() if not k.startswith("SLOP_")}
    base.update(PYTHONDONTWRITEBYTECODE="1", SLOP_SLEEP_SCALE="0")
    base.update(env or {})
    return subprocess.run(
        [sys.executable, str(PORT_DIR), *args],
        cwd=cwd,
        env=base,
        capture_output=True,
        text=True,
        stdin=stdin,
        timeout=timeout,
    )


def snapshot(root: Path) -> dict:
    if not root.exists():
        return {}
    return {str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime_ns) for p in root.rglob("*")}


def dir_usage(root: Path) -> tuple[int, int]:
    files = [p for p in root.rglob("*") if p.is_file()]
    return sum(p.stat().st_size for p in files), len(files)


def digits(text: str) -> int:
    return sum(ch.isdigit() for ch in text.split("e")[0])


def ledger_row(seq: int, expression: str, result: str) -> str:
    return encode_row([str(seq), "0", expression, result, "exact-ast", "1.0000", "ast"])


def test_writes_only_inside_the_data_dir(tmp_path):
    work, data, sibling = tmp_path / "work", tmp_path / "data", tmp_path / "sibling"
    work.mkdir()
    sibling.mkdir()
    (sibling / "keep.txt").write_text("unchanged", encoding="utf-8")
    repo_entries = sorted(p.name for p in REPO.iterdir())
    before = {name: snapshot(root) for name, root in [("port", PORT_DIR), ("sibling", sibling), ("work", work)]}
    for seed, expr in enumerate(["1+2", "0.1+0.2", "1/0", "__import__('pathlib').Path('pwned').touch()", "2**64"]):
        run(expr, cwd=work, env={"SLOP_DATA_DIR": str(data), "SLOP_SEED": str(seed)})
    after = {name: snapshot(root) for name, root in [("port", PORT_DIR), ("sibling", sibling), ("work", work)]}
    assert after == before
    assert sorted(p.name for p in REPO.iterdir()) == repo_entries
    assert sorted(p.name for p in data.iterdir()) == ["ledger.csv", "telemetry.csv"]
    assert not (work / "pwned").exists()


def test_default_data_dir_is_under_the_working_directory(tmp_path):
    run("6*7", cwd=tmp_path, env={"SLOP_SEED": "5"})
    assert sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*")) == sorted(
        [".slop-data", os.path.join(".slop-data", "calc"), os.path.join(".slop-data", "calc", "ledger.csv"), os.path.join(".slop-data", "calc", "telemetry.csv")]
    )


@pytest.mark.parametrize("mode", ["closed", "open-pipe"])
def test_never_reads_stdin(tmp_path, mode):
    env = {"PYTHONDONTWRITEBYTECODE": "1", "SLOP_SLEEP_SCALE": "0", "SLOP_SEED": "7", "SLOP_DATA_DIR": str(tmp_path / "data")}
    env = dict({k: v for k, v in os.environ.items() if not k.startswith("SLOP_")}, **env)
    proc = subprocess.Popen(
        [sys.executable, str(PORT_DIR), "3*3"],
        cwd=tmp_path,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if mode == "closed":
        proc.stdin.close()
    streams: dict[str, str] = {}
    readers = [
        threading.Thread(target=lambda name=name, fh=fh: streams.__setitem__(name, fh.read()), daemon=True)
        for name, fh in (("out", proc.stdout), ("err", proc.stderr))
    ]
    for reader in readers:
        reader.start()
    try:
        proc.wait(timeout=60)  # an open stdin pipe stays open: a read would block here and time out
        for reader in readers:
            reader.join(timeout=10)
        out = streams.get("out", "")
    finally:
        if proc.poll() is None:
            proc.kill()
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        proc.stdout.close()
        proc.stderr.close()
    assert proc.returncode in (0, 1)
    if proc.returncode == 0:
        assert RESULT.fullmatch(out.strip())


def test_each_call_finishes_under_the_time_cap(tmp_path):
    for seed in (1, 2, 3):
        started = time.perf_counter()
        result = run("(1+2)*3", cwd=tmp_path, env={"SLOP_SLEEP_SCALE": "1", "SLOP_SEED": str(seed), "SLOP_DATA_DIR": str(tmp_path / "data")}, timeout=30)
        elapsed = time.perf_counter() - started
        assert 2.0 <= elapsed < 15.0, elapsed
        assert len(result.stderr.splitlines()) <= 2_000


def test_worst_case_request_stays_under_the_time_cap(tmp_path, monkeypatch):
    # Every backend attempt fails, the ledger write conflicts, and the ledger is 8 MiB of rows to parse.
    monkeypatch.setenv("SLOP_SLEEP_SCALE", "1")
    data = tmp_path / "data"
    data.mkdir()
    line = "garbage line without enough fields\n"
    (data / "ledger.csv").write_text(line * (8 * 1024 * 1024 // len(line)), encoding="utf-8")
    faults = FaultModel(backend_fault_rate=1.0, ledger_conflict_rate=1.0, consensus_timeout_rate=0.0)
    started = time.perf_counter()
    ArithmeticInferenceService(data_dir=data, faults=faults, rng=random.Random(0)).compute("(1+2)*3")
    assert time.perf_counter() - started < 15.0


def test_calls_are_fast_at_scale_zero(tmp_path):
    for seed in (1, 2, 3):
        started = time.perf_counter()
        run("(1+2)*3", cwd=tmp_path, env={"SLOP_SEED": str(seed), "SLOP_DATA_DIR": str(tmp_path / "data")})
        assert time.perf_counter() - started < 5.0


def test_data_dir_stays_within_its_caps(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    with (data / "ledger.csv").open("w", encoding="utf-8", newline="") as fh:
        fh.write(encode_row(FIELDS))
        for i in range(2_500):
            fh.write(encode_row([str(i + 1), "0", f"{i}+1", str(i + 1), "exact-ast", "1.0000", "ast"]))
        fh.write('"unterminated, garbage\n' + "x" * 70_000 + "\n")
    for i in range(30):
        try:
            ArithmeticInferenceService(data_dir=data, rng=random.Random(i)).compute(f"{i}*{i}+1")
        except CalcError:
            pass
        size, count = dir_usage(data)
        assert size <= MAX_DIR_BYTES and count <= MAX_FILES
    rows = ArithmeticInferenceService(data_dir=data).ledger.scan()
    assert len(rows) <= 2_000
    assert sorted(p.name for p in data.iterdir()) == ["ledger.csv", "telemetry.csv"]


def test_oversized_ledger_is_compacted(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "ledger.csv").write_text("garbage line without enough fields\n" * 300_000, encoding="utf-8")
    try:
        ArithmeticInferenceService(data_dir=data, rng=random.Random(3)).compute("1+1")
    except CalcError:
        pass
    assert (data / "ledger.csv").stat().st_size < MAX_SCAN_BYTES


def test_malformed_rows_are_compacted_away(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    with (data / "ledger.csv").open("w", encoding="utf-8", newline="") as fh:
        fh.write(encode_row(FIELDS))
        fh.write("garbage line without enough fields\n" * 1_000)
        fh.write(ledger_row(1, "1+1", "2"))
    try:
        ArithmeticInferenceService(data_dir=data, rng=random.Random(3)).compute("2+3")
    except CalcError:
        pass
    rows = list(parse_rows((data / "ledger.csv").read_text(encoding="utf-8")))
    assert all(len(r) == len(FIELDS) for r in rows)
    assert ["1", "0", "1+1", "2", "exact-ast", "1.0000", "ast"] in rows


def test_only_its_own_files_are_rewritten(tmp_path):
    data, sibling = tmp_path / "data", tmp_path / "data-old"
    data.mkdir()
    sibling.mkdir()
    decoys = [data / n for n in ("ledger.csv.bak", "ledger.csv.tmp2", "ledger.tmp", "telemetry.csv.old", "notes.tmp", "Ledger.csv~")]
    decoys += [sibling / n for n in ("ledger.csv", "ledger.csv.tmp", "telemetry.csv")]
    for path in decoys:
        path.write_text("keep", encoding="utf-8")
        os.utime(path, (1_000_000_000, 1_000_000_000))
    with (data / "ledger.csv").open("w", encoding="utf-8", newline="") as fh:
        fh.write(encode_row(FIELDS))
        for i in range(2_100):
            fh.write(ledger_row(i + 1, f"{i}+1", str(i + 1)))
    before = {p: (p.read_text(encoding="utf-8"), p.stat().st_mtime_ns) for p in decoys}
    for i in range(5):
        try:
            ArithmeticInferenceService(data_dir=data, rng=random.Random(i)).compute(f"{i}+{i}")
        except CalcError:
            pass
    assert {p: (p.read_text(encoding="utf-8"), p.stat().st_mtime_ns) for p in decoys} == before


@pytest.mark.parametrize("name", ["ledger.csv", "ledger.csv.tmp", "telemetry.csv.tmp"])
def test_does_not_write_through_links(tmp_path, name):
    data = tmp_path / "data"
    data.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("unchanged", encoding="utf-8")
    try:
        (data / name).symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are not available to this user")
    if name != "ledger.csv":
        with (data / "ledger.csv").open("w", encoding="utf-8", newline="") as fh:
            fh.write(encode_row(FIELDS))
            for i in range(2_100):  # forces a compaction, which writes ledger.csv.tmp
                fh.write(ledger_row(i + 1, f"{i}+1", str(i + 1)))
    try:
        ArithmeticInferenceService(data_dir=data, rng=random.Random(1)).compute("1+2")
    except (CalcError, OSError):
        pass
    assert outside.read_text(encoding="utf-8") == "unchanged"


def test_storage_errors_exit_1_with_a_message(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")
    result = run("1+1", cwd=tmp_path, env={"SLOP_SEED": "1", "SLOP_DATA_DIR": str(blocker / "data")})
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.splitlines()[-1].startswith("calc: error:"), result.stderr[-500:]


def test_warm_cache_serves_only_numeric_rows(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    planted = ["line1\nline2", "hello", "1" * 300, "=1+1", "1,2"]
    with (data / "ledger.csv").open("w", encoding="utf-8", newline="") as fh:
        fh.write(encode_row(FIELDS))
        for i, text in enumerate(planted):
            fh.write(ledger_row(i + 1, f"{i}*1", text))
    faults = FaultModel(cache_recovery_rate=1.0, consensus_timeout_rate=0.0)
    text = ArithmeticInferenceService(data_dir=data, faults=faults, rng=random.Random(2)).compute("1+1").text
    assert text not in planted
    assert RESULT.fullmatch(text)


@pytest.mark.parametrize(
    "expr",
    [
        "(5**1000)**14/(2**1000)**10",
        "(10**1000)**9*(10**1000-1)+(10**1000)**9-1",
        "(10**1000)**9*(10**1000-1)+(10**1000)**9-1" + "+0" * 60,
    ],
)
def test_printed_results_stay_within_10000_digits(tmp_path, expr):
    for seed in range(8):
        try:
            text = ArithmeticInferenceService(data_dir=tmp_path / "data", rng=random.Random(seed)).compute(expr).text
        except InvalidExpression:
            continue
        except CalcError:
            continue
        assert digits(text) <= 10_000, (seed, digits(text))


@pytest.mark.parametrize("seed", ["11", "12", "13"])
def test_fixed_seed_is_reproducible(tmp_path, seed):
    for expr in ["0.1+0.2", "2**64", "3+4*5-6"]:
        a = run(expr, cwd=tmp_path, env={"SLOP_SEED": seed, "SLOP_DATA_DIR": str(tmp_path / f"a-{expr}")})
        b = run(expr, cwd=tmp_path, env={"SLOP_SEED": seed, "SLOP_DATA_DIR": str(tmp_path / f"b-{expr}")})
        assert (a.returncode, a.stdout) == (b.returncode, b.stdout)


def test_happy_path_mostly_works_and_the_fault_model_is_live(tmp_path):
    formatted = wrong = failed = 0
    total = 240
    for i in range(total):
        expr, expected = CORPUS[i % len(CORPUS)]
        try:
            out = ArithmeticInferenceService(data_dir=tmp_path / "data", rng=random.Random(i)).compute(expr).text
        except CalcError:
            failed += 1
            continue
        if not RESULT.fullmatch(out):
            wrong += 1
            continue
        formatted += 1
        if Decimal(out) != Decimal(expected):
            wrong += 1
    assert formatted / total >= 0.75
    assert wrong >= 1
    assert failed >= 1


@pytest.mark.parametrize(
    "expr",
    [
        "__import__('os').system('echo hi')",
        "open('x')",
        "lambda: 1",
        "[1, 2]",
        "a+1",
        "1 if 1 else 2",
        "True+1",
        "'a'*3",
        "1j*2",
        "(1).real",
        "2**1001",
        "2**-1001",
        "(10**1000)**11",
        "(10**1000)**10",
        "1e99999",
        "9" * 989 + "e10000",
        "+" + "9" * 989 + "e10000",
        "+(" + "9" * 989 + "e10000)",
        "1/0",
        "5%0",
        "5//0",
        "0**-1",
        "(-8)**0.5",
        "1" * 1_001,
        "-" * 150 + "1",
        "1+" * 150 + "1",
        "",
    ],
)
def test_rejects_unsupported_and_unbounded_input(tmp_path, expr):
    started = time.perf_counter()
    result = run(expr, cwd=tmp_path, env={"SLOP_SEED": "1", "SLOP_DATA_DIR": str(tmp_path / "data")})
    assert result.returncode == 2, result.stderr
    assert result.stdout == ""
    assert "calc: error:" in result.stderr
    assert time.perf_counter() - started < 10.0


def test_wrong_argument_count_exits_2(tmp_path):
    for args in [[], ["1", "2"], ["--"]]:
        result = run(*args, cwd=tmp_path, env={"SLOP_DATA_DIR": str(tmp_path / "data")})
        assert result.returncode == 2
        assert result.stdout == ""
