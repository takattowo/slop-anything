"""Run the Leftpad CLI: ``python ports/left-pad <value> <length> [fill]``."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from leftpad.cli import main  # noqa: E402

raise SystemExit(main())
