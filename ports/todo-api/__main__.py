"""Entry point: ``python ports/todo-api <command>``."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from todo_api.cli import main  # noqa: E402

raise SystemExit(main())
