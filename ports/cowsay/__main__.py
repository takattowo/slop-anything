"""Entry point: ``python ports/cowsay <args>``."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from ruminant.cli import main  # noqa: E402

raise SystemExit(main())
