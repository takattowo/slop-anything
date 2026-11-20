"""Ablation: calc with a single evaluation backend vs the full four-backend quorum.

Usage: python evals/ablation.py [--rounds N]   (N from 1 to 10, default 4)

Runs in-process through the calc package's own constructor argument
``ArithmeticInferenceService(backends=...)``; ports/calc is not modified.
Each configuration gets one fresh data folder per round, and call k of a
configuration uses SLOP_SEED=k, the same seeds as evals/leaderboard.py.
Every request draws its nine finalisation values before any backend runs, so
the configurations see the same load-shedding, timeout and recovery draws;
only the per-backend fault draws differ. Writes evals/results/ablation.md.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _arith import is_correct, load_cases  # noqa: E402
from _common import PORTS, REPO, provenance_block, scratch, write_result  # noqa: E402

os.environ["SLOP_SLEEP_SCALE"] = "0"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True
sys.path.insert(0, str(PORTS / "calc" / "src"))

from arith_inference.backends import default_backends  # noqa: E402
from arith_inference.errors import CalcError  # noqa: E402
from arith_inference.service import ArithmeticInferenceService  # noqa: E402
from arith_inference.settings import ServiceSettings  # noqa: E402

MAX_ROUNDS = 10
TIME_BUDGET_S = 300.0
FULL = "full quorum (4 backends)"


def backends_for(config: str):
    every = default_backends(ServiceSettings().precision_budget)
    return every if config == FULL else [b for b in every if b.name == config]


def run_config(config: str, cases: list[dict], rounds: int, root: Path) -> tuple[dict, float, int]:
    outcomes: dict[tuple[int, str], str] = {}
    stderr_lines = 0
    elapsed = 0.0
    seed = 0
    for round_no in range(rounds):
        data = root / f"{config.split()[0]}-round-{round_no}"
        for case in cases:
            os.environ["SLOP_SEED"] = str(seed)
            seed += 1
            sink = io.StringIO()
            t0 = time.perf_counter()
            with redirect_stderr(sink):
                try:
                    text = ArithmeticInferenceService(backends=backends_for(config), data_dir=data).compute(case["expression"]).text
                    outcome = "correct" if is_correct(text, case["expected"]) else "wrong"
                except CalcError:
                    outcome = "failed"
            elapsed += time.perf_counter() - t0
            stderr_lines += sink.getvalue().count("\n")
            outcomes[(round_no, case["id"])] = outcome
    return outcomes, elapsed, stderr_lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rounds", type=int, default=4)
    rounds = parser.parse_args().rounds
    if not 1 <= rounds <= MAX_ROUNDS:
        parser.error(f"--rounds must be 1 to {MAX_ROUNDS}")
    cases = load_cases()
    configs = [FULL, "exact-ast", "ieee754-float", "neural-estimator", "distributed-shard"]
    started = time.perf_counter()
    results = {}
    with scratch("ablation") as root:
        for config in configs:
            if time.perf_counter() - started > TIME_BUDGET_S:
                break
            results[config] = run_config(config, cases, rounds, root)
        os.environ.pop("SLOP_SEED", None)

    full, full_s, full_lines = results[FULL]
    total = len(full)
    rows = ["| Configuration | Correct | Wrong | Failed | Wrong became right | Right became wrong | Time (all calls) | stderr lines |",
            "|---|---|---|---|---|---|---|---|"]
    summary = {}
    for config, (outcomes, seconds, lines) in results.items():
        counts = {k: sum(v == k for v in outcomes.values()) for k in ("correct", "wrong", "failed")}
        fixed = sum(full[key] != "correct" and outcomes[key] == "correct" for key in outcomes)
        broke = sum(full[key] == "correct" and outcomes[key] != "correct" for key in outcomes)
        summary[config] = (counts, fixed, broke, seconds)
        label = config if config == FULL else f"single backend: `{config}`"
        delta = ("n/a (reference)", "n/a (reference)") if config == FULL else (str(fixed), str(broke))
        rows.append(f"| {label} | {counts['correct']} / {total} | {counts['wrong']} | {counts['failed']} | {delta[0]} | {delta[1]} | "
                    f"{seconds * 1000:.1f} ms | {lines} |")

    still_wrong = sorted({cid for (r, cid), v in results["exact-ast"][0].items() if v == "wrong"}) if "exact-ast" in results else []
    counts, fixed, broke, seconds = summary.get("exact-ast", ({}, 0, 0, 0.0))
    headline = (f"Replacing the four-backend quorum with `exact-ast` alone: {fixed} wrong or failed answers became right, "
                f"{broke} right answers became wrong or failed, {counts.get('correct', 0)} / {total} correct vs "
                f"{summary[FULL][0]['correct']} / {total}, {seconds * 1000:.1f} ms vs {full_s * 1000:.1f} ms in-process.")

    text = "\n".join([
        "# Ablation: one backend vs the full quorum (calc)",
        "",
        provenance_block({"cases": f"{len(cases)} x {rounds} rounds = {total} calls per configuration", "sleep_scale": "0"}),
        "",
        "## How this was measured",
        "",
        "- In-process, through `ArithmeticInferenceService(backends=[...], data_dir=...)`, the constructor argument the calc package exposes. "
        "No file under `ports/` was changed and nothing was monkeypatched.",
        "- Same case file and seeds as the leaderboard (call k uses `SLOP_SEED=k`), `SLOP_SLEEP_SCALE=0`, one fresh data folder per round and configuration.",
        "- Correct: the served text, read as a rational number, equals the expected value. Failed: the request raised a `CalcError` (consensus timeout).",
        "- \"Wrong became right\" and \"right became wrong\" compare each call with the same call (round, case) under the full quorum.",
        "- Time: `time.perf_counter()` around each `compute()` call, summed; no interpreter start is included.",
        "",
        "## Result",
        "",
        headline,
        "",
        *rows,
        "",
        "Cases still wrong with `exact-ast` alone (finalisation runs after the vote, so the backend set does not reach it): "
        + (", ".join(f"`{c}`" for c in still_wrong) or "none") + ".",
        "",
    ])
    path = write_result("ablation.md", text)
    print(f"wrote {path.relative_to(REPO)}: {headline}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
