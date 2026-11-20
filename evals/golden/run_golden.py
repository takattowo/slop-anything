"""Golden demo: one real ``calc "7*8"`` run at SLOP_SLEEP_SCALE=1, saved verbatim.

Usage: python evals/golden/run_golden.py

Writes evals/golden/calc-7x8.txt: the command, stdout, the full stderr, the
exit code and the wall time of a single run with SLOP_SEED=7 in a fresh data
folder. The transcript is written as captured; the only change is that
machine-specific folders are replaced by placeholders (``<repo>``, ``<tmp>``,
``<python>``, ``~``).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import EVALS, provenance_block, redact, run_port, scratch  # noqa: E402

SEED = 7
EXPRESSION = "7*8"
OUTPUT = EVALS / "golden" / "calc-7x8.txt"


def main() -> int:
    with scratch("golden") as root:
        data = root / "calc-data"
        result = run_port("calc", [EXPRESSION], data_dir=data, seed=SEED, scale="1", timeout=30)
    command = f'SLOP_SEED={SEED} SLOP_SLEEP_SCALE=1 SLOP_DATA_DIR=<fresh temp folder> python ports/calc "{EXPRESSION}"'
    text = "\n".join(
        [
            "# Golden transcript: calc 7*8",
            "",
            provenance_block({"seed": str(SEED), "sleep_scale": "1"}),
            "",
            "Machine-specific folders are shown as `<repo>`, `<tmp>`, `<python>` and `~`; nothing else in the output was changed.",
            "",
            f"$ {command}",
            "",
            "## stdout",
            redact(result["stdout"].rstrip("\n")),
            "",
            "## stderr",
            redact(result["stderr"].rstrip("\n")),
            "",
            f"## exit code: {result['exit_code']}",
            f"## elapsed: {result['elapsed_s']:.3f} s (wall clock, perf_counter around the subprocess, interpreter start included)",
            "",
        ]
    )
    OUTPUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT.relative_to(EVALS.parent)}: exit {result['exit_code']}, stdout {result['stdout'].strip()!r}, "
          f"{len(result['stderr'].splitlines())} stderr lines, {result['elapsed_s']:.2f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
