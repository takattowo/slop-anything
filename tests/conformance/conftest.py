"""Loads the root tests/conftest.py under its own name and re-exports its fixtures and helpers."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("root_conftest", Path(__file__).resolve().parent.parent / "conftest.py")
_root = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_root)

REPO_ROOT = _root.REPO_ROOT
child_environment = _root.child_environment
env = _root.env
repo_untouched = _root.repo_untouched
