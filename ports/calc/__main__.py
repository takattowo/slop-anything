"""Command-line entry point: ``python ports/calc "<expression>"``."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from arith_inference.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
