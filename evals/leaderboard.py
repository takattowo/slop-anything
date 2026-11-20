"""Leaderboard: calc against a plain Python baseline on the published case set.

Usage: python evals/leaderboard.py [--rounds N]   (N from 1 to 10, default 4)

Each round runs every case in evals/cases/arithmetic.json through
``python ports/calc <expression>`` (subprocess, SLOP_SLEEP_SCALE=0) in one
fresh data folder per round. Call k of the whole run uses SLOP_SEED=k, so the
seeds are 0 to rounds*cases-1. The baseline computes the same cases in-process
with ``ast`` and the ``operator`` module (see evals/_arith.py). Writes
evals/results/leaderboard.md.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _arith import baseline, is_correct, load_cases  # noqa: E402
from _common import PYTHON, REPO, child_env, provenance_block, run, run_port, scratch, write_result  # noqa: E402

MAX_ROUNDS = 10
TIME_BUDGET_S = 300.0


def projected_speedup(root: Path) -> dict:
    """Ask the harness bench for its projected speedup. Up to 3 attempts (exit 75 is transient)."""
    for seed in (0, 1, 2):
        env = child_env(SLOP_HOME=str(root / f"home-{seed}"), SLOP_SLEEP_SCALE="0", SLOP_SEED=str(seed))
        result = run([PYTHON, "-m", "slop_anything", "bench", "--runs", "3", "calc", "7*8"], env, cwd=REPO, timeout=120)
        try:
            body = json.loads(result["stdout"])
        except ValueError:
            continue
        if result["exit_code"] == 0 and "projected_speedup" in body:
            return {"seed": seed, **body}
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rounds", type=int, default=4)
    rounds = parser.parse_args().rounds
    if not 1 <= rounds <= MAX_ROUNDS:
        parser.error(f"--rounds must be 1 to {MAX_ROUNDS}")
    cases = load_cases()
    started = time.perf_counter()

    t0 = time.perf_counter()
    base = {case["id"]: baseline(case["expression"]) for case in cases}
    baseline_s = time.perf_counter() - t0
    base_correct = sum(base[c["id"]] == Fraction(c["expected"]) for c in cases)

    answers: dict[str, list[str]] = {case["id"]: [] for case in cases}
    per_round = []
    seed = 0
    stopped_early = False
    with scratch("leaderboard") as root:
        for round_no in range(rounds):
            data = root / f"calc-round-{round_no}"
            correct = failed = 0
            t0 = time.perf_counter()
            first_seed = seed
            for case in cases:
                if time.perf_counter() - started > TIME_BUDGET_S:
                    stopped_early = True
                    break
                result = run_port("calc", [case["expression"]], data_dir=data, seed=seed, scale="0", timeout=60)
                seed += 1
                text = result["stdout"].strip()
                if result["exit_code"] != 0:
                    failed += 1
                    answers[case["id"]].append(f"exit {result['exit_code']}")
                else:
                    answers[case["id"]].append(text)
                    correct += is_correct(text, case["expected"])
            calls = seed - first_seed
            per_round.append({"round": round_no, "seeds": f"{first_seed}-{seed - 1}", "calls": calls,
                              "correct": correct, "failed": failed, "wall_s": time.perf_counter() - t0})
            if stopped_early:
                break
        bench = projected_speedup(root)

    total_calls = sum(r["calls"] for r in per_round)
    total_correct = sum(r["correct"] for r in per_round)
    total_failed = sum(r["failed"] for r in per_round)
    total_wall = sum(r["wall_s"] for r in per_round)
    speedup = f"{bench['projected_speedup']}x (not observed)" if bench else "unavailable (bench did not answer)"

    rows = ["| Entry | Seeds | Correct / total | Accuracy | Failed calls | Wall time for the batch | Projected speedup |",
            "|---|---|---|---|---|---|---|"]
    for r in per_round:
        rows.append(f"| calc, round {r['round'] + 1} | {r['seeds']} | {r['correct']} / {r['calls']} | "
                    f"{100 * r['correct'] / max(r['calls'], 1):.1f}% | {r['failed']} | {r['wall_s']:.2f} s | {speedup} |")
    rows.append(f"| **calc, all rounds** | 0-{seed - 1} | **{total_correct} / {total_calls}** | "
                f"**{100 * total_correct / max(total_calls, 1):.1f}%** | {total_failed} | {total_wall:.2f} s | {speedup} |")
    rows.append(f"| Python `operator` baseline | n/a | {base_correct} / {len(cases)} | "
                f"{100 * base_correct / len(cases):.1f}% | 0 | {baseline_s * 1000:.3f} ms | n/a |")

    detail = ["| Case | Expression | Expected | calc answers (one per round) | Baseline |", "|---|---|---|---|---|"]
    for case in cases:
        got = ", ".join(f"`{a}`" for a in answers[case["id"]]) or "not run"
        b = base[case["id"]]
        b_text = str(b.numerator) if b.denominator == 1 else f"{b.numerator}/{b.denominator}"
        detail.append(f"| {case['id']} | `{case['expression']}` | `{case['expected']}` | {got} | `{b_text}` |")

    bench_line = (f"`python -m slop_anything bench --runs 3 calc \"7*8\"` (SLOP_SLEEP_SCALE=0, SLOP_SEED={bench['seed']}, temp SLOP_HOME) "
                  f"measured a median of {bench['median_ms']} ms and reported `projected_speedup: {bench['projected_speedup']}` "
                  f"and `projected_median_ms: {bench['projected_median_ms']}`. The harness ledger states that these two fields are "
                  "not measured; they are shown here as reported and labelled \"not observed\"."
                  if bench else "The bench call did not return a result in 3 attempts; no projection is shown.")

    text = "\n".join([
        "# Leaderboard: calc vs a plain Python baseline",
        "",
        provenance_block({"cases": f"{len(cases)} (evals/cases/arithmetic.json)", "rounds": str(len(per_round)),
                          "sleep_scale": "0"}),
        "",
        "## How this was measured",
        "",
        f"- calc: `python ports/calc <expression>` as a subprocess (argv list, stdin closed, 60 s timeout), "
        f"`SLOP_SLEEP_SCALE=0`, one fresh data folder per round, call k of the run seeded with `SLOP_SEED=k`. "
        "An answer is correct when its stdout, read as a rational number, equals the expected value; a non-zero exit counts as not correct.",
        "- Baseline: the same cases in-process, parsed with `ast` and computed with the `operator` module on exact fractions (no `eval`). "
        "Its wall time is the in-process time for the whole batch; calc's includes one interpreter start per call.",
        f"- Wall time: `time.perf_counter()` around each batch.{' The run stopped early at the time budget.' if stopped_early else ''}",
        f"- Projected speedup: {bench_line}",
        "",
        "## Results",
        "",
        *rows,
        "",
        "## Per case",
        "",
        *detail,
        "",
    ])
    path = write_result("leaderboard.md", text)
    print(f"wrote {path.relative_to(REPO)}: calc {total_correct}/{total_calls} correct, {total_failed} failed, "
          f"{total_wall:.2f} s; baseline {base_correct}/{len(cases)} in {baseline_s * 1000:.3f} ms; projected {speedup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
