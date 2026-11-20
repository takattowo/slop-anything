"""Bounded left-pad trace for the predictive-cache postmortem.

Usage: python evals/leftpad_trace.py

Runs ``python ports/left-pad <word> 8 .`` 12 times (subprocess,
SLOP_SLEEP_SCALE=0) against one fresh data folder, call k with SLOP_SEED=500+k
and a different word each time. The expected answer is the npm left-pad
result (dots in front, to 8 characters). Writes
evals/results/left-pad-trace.md with every call's outcome, the diagnostic
lines that matter for the postmortem, and the full stderr of each call whose
answer belonged to another request.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import REPO, provenance_block, redact, run_port, scratch, write_result  # noqa: E402

WORDS = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet", "kilo", "lima"]
LENGTH, FILL, SEED_BASE = 8, ".", 500
KEY_MARKERS = ("predictive cache", "completed with status OK", "fatal", "StrategyResolutionError", "ModuleNotFoundError",
               "VendoredStrategy", "normaliz", "normalis", "rounding", "safe-mode", "bidi")


def expected(word: str) -> str:
    return FILL * max(LENGTH - len(word), 0) + word


def main() -> int:
    calls = []
    started = time.perf_counter()
    with scratch("leftpad-trace") as root:
        data = root / "left-pad-data"
        for k, word in enumerate(WORDS, start=1):
            result = run_port("left-pad", [word, str(LENGTH), FILL], data_dir=data, seed=SEED_BASE + k, scale="0", timeout=60)
            calls.append((k, word, result))
    elapsed = time.perf_counter() - started

    answers = {expected(w): w for w in WORDS}
    lines = ["| Call | Seed | Request | Expected | stdout | Exit | Outcome |", "|---|---|---|---|---|---|---|"]
    stale, wrong, failed, details = [], [], [], []
    for k, word, result in calls:
        out = result["stdout"].rstrip("\n")
        if result["exit_code"] != 0:
            outcome = f"failed (exit {result['exit_code']})"
            failed.append(k)
        elif out == expected(word):
            outcome = "correct"
        elif out in answers:
            outcome = f"another request's answer (`{answers[out]}`)"
            stale.append(k)
        else:
            outcome = "wrong"
            wrong.append(k)
        lines.append(f"| {k} | {SEED_BASE + k} | `{word} {LENGTH} {FILL}` | `{expected(word)}` | `{out}` | {result['exit_code']} | {outcome} |")
        key = [line for line in redact(result["stderr"]).splitlines() if any(m in line for m in KEY_MARKERS)]
        details += [f"### Call {k}: `{word}`", "", "```", *(key[:12] or ["(no matching lines)"]), "```", ""]

    full = []
    for k in stale:
        stderr = redact(calls[k - 1][2]["stderr"]).rstrip("\n").splitlines()
        full += [f"### Call {k}, full stderr ({len(stderr)} lines)", "", "```", *stderr[:400], "```", ""]

    ok = len(calls) - len(failed)
    text = "\n".join([
        "# left-pad trace: predictive cache",
        "",
        provenance_block({"calls": str(len(calls)), "seeds": f"{SEED_BASE + 1}-{SEED_BASE + len(calls)}", "sleep_scale": "0"}),
        "",
        "## How this was captured",
        "",
        f"- `python ports/left-pad <word> {LENGTH} {FILL}`, one subprocess per call (argv list, stdin closed, 60 s timeout), "
        "all calls sharing one fresh data folder, in the order shown. Run time for the sequence "
        f"{elapsed:.2f} s.",
        "- Log lines are quoted as captured, with machine-specific folders shown as `<repo>`, `<tmp>`, `<python>` and `~`.",
        "- Expected: the npm left-pad 1.3.0 answer. \"Another request's answer\" means stdout equals the expected answer of a "
        "different word in this sequence.",
        f"- Summary: {len(calls)} calls, {ok} exited 0, {len(failed)} failed, {len(stale)} served another request's answer "
        f"(calls {', '.join(map(str, stale)) or 'none'}), {len(wrong)} other wrong answers (calls {', '.join(map(str, wrong)) or 'none'}).",
        "",
        "## Calls",
        "",
        *lines,
        "",
        "## Key diagnostic lines per call",
        "",
        "Lines from each call's stderr containing one of: " + ", ".join(f"`{m}`" for m in KEY_MARKERS) + " (first 12 per call).",
        "",
        *details,
        "## Full stderr of calls that served another request's answer",
        "",
        *(full or ["None in this run.", ""]),
    ])
    path = write_result("left-pad-trace.md", text)
    print(f"wrote {path.relative_to(REPO)}: {len(calls)} calls, stale {stale}, wrong {wrong}, failed {failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
