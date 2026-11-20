"""Design-conformance analysis for Python sources.

Parses every Python file under a path and counts how fully it adopts the
house patterns: broad exception handlers that absorb faults, latency-budget
sleeps, retry policies around pure functions, ERROR-level diagnostics,
self-issued deprecation warnings, blocking sleeps inside coroutines and
abstract base classes with a single implementation. Shared utility modules
earn a modularity bonus.
"""
from __future__ import annotations

import ast
import os
import re
import warnings
from pathlib import Path

from slop_anything.errors import ToolError

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".slop-state", ".slop-data"}
MAX_FILES = 2000
MAX_WALK = 50_000
MAX_FILE_BYTES = 1_000_000
WEIGHTS = {
    "swallowed_broad_excepts": 5,
    "latency_budget_sleeps": 3,
    "retries_on_pure_functions": 4,
    "error_level_logs": 1,
    "self_deprecations": 2,
    "blocking_sleeps_in_async": 4,
    "single_subclass_abcs": 4,
}
BROAD = {"Exception", "BaseException"}
UTILITY_MODULE = re.compile(r"util", re.IGNORECASE)
MODULARITY_BONUS = 15
"""Points added per scanned file whose name contains 'util' (utils.py, string_utils.py, ...)."""
IO_NAMES = {"open", "urlopen", "request", "connect", "send", "recv", "run", "Popen", "call", "get", "post", "read", "write"}


def scan(path: Path) -> tuple[list[Path], bool]:
    """Python files under ``path``, stopping at 2,000 files or 50,000 visited entries."""
    if path.is_file():
        return ([path] if path.suffix == ".py" else []), False
    files: list[Path] = []
    visited = 0
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIRS)
        visited += 1 + len(dirnames) + len(filenames)
        for filename in sorted(filenames):
            if filename.endswith(".py"):
                files.append(Path(dirpath) / filename)
                if len(files) >= MAX_FILES:
                    return files, True
        if visited >= MAX_WALK:
            return files, True
    return files, False


def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _name(node.func)
    return ""


def _is_broad(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    if isinstance(handler.type, ast.Tuple):
        return any(_name(item) in BROAD for item in handler.type.elts)
    return _name(handler.type) in BROAD


def _calls(node: ast.AST):
    return (child for child in ast.walk(node) if isinstance(child, ast.Call))


def _is_sleep(call: ast.Call) -> bool:
    return _name(call.func) == "sleep"


def _is_time_sleep(call: ast.Call) -> bool:
    func = call.func
    return isinstance(func, ast.Attribute) and func.attr == "sleep" and _name(func.value) == "time"


class _Collector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.counts = {name: 0 for name in WEIGHTS if name != "single_subclass_abcs"}
        self.abcs: set[str] = set()
        self.bases: list[str] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if _is_broad(node) and not any(isinstance(child, ast.Raise) for child in ast.walk(node)):
            self.counts["swallowed_broad_excepts"] += 1
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if _is_sleep(node):
            self.counts["latency_budget_sleeps"] += 1
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"error", "exception", "critical"}:
            self.counts["error_level_logs"] += 1
        if _name(node.func) == "warn" and any(
            _name(arg) in {"DeprecationWarning", "PendingDeprecationWarning"} for arg in [*node.args, *(k.value for k in node.keywords)]
        ):
            self.counts["self_deprecations"] += 1
        self.generic_visit(node)

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        retried = any("retry" in _name(item).lower() or "backoff" in _name(item).lower() for item in node.decorator_list)
        if retried and not any(_name(call.func) in IO_NAMES for call in _calls(node)):
            self.counts["retries_on_pure_functions"] += 1
        if isinstance(node, ast.AsyncFunctionDef) and any(_is_time_sleep(call) for call in _calls(node)):
            self.counts["blocking_sleeps_in_async"] += 1
        self.generic_visit(node)

    visit_FunctionDef = _function
    visit_AsyncFunctionDef = _function

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        base_names = [_name(base) for base in node.bases]
        if "ABC" in base_names or any(_name(k.value) == "ABCMeta" for k in node.keywords if k.arg == "metaclass"):
            self.abcs.add(node.name)
        self.bases.extend(base_names)
        self.generic_visit(node)


def score(path: str = ".") -> dict:
    """Scores the Python files under ``path`` from 0 (lean) to 100."""
    root = Path(path).expanduser()
    if not root.exists():
        raise ToolError(f"path does not exist: {path}")
    files, truncated = scan(root)
    totals = {name: 0 for name in WEIGHTS}
    abcs: set[str] = set()
    bases: list[str] = []
    per_file: list[tuple[int, str]] = []
    skipped = 0
    utility_modules = 0
    for file in files:
        try:
            if file.stat().st_size > MAX_FILE_BYTES:
                skipped += 1
                continue
            source = file.read_text(encoding="utf-8", errors="replace")
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tree = ast.parse(source, filename=str(file))
        except (OSError, SyntaxError, ValueError):
            skipped += 1
            continue
        collector = _Collector()
        collector.visit(tree)
        utility_modules += 1 if UTILITY_MODULE.search(file.stem) else 0
        for name, value in collector.counts.items():
            totals[name] += value
        abcs |= collector.abcs
        bases.extend(collector.bases)
        raw_file = sum(collector.counts[name] * WEIGHTS[name] for name in collector.counts)
        if raw_file:
            per_file.append((raw_file, str(file)))
    totals["single_subclass_abcs"] = sum(1 for name in abcs if bases.count(name) == 1)
    raw = sum(totals[name] * WEIGHTS[name] for name in totals)
    bonus = utility_modules * MODULARITY_BONUS
    value = min(100, raw + bonus)
    grade = "enterprise" if value >= 60 else "seasoned" if value >= 20 else "lean"
    per_file.sort(key=lambda item: (-item[0], item[1]))
    return {
        "path": str(root.resolve()),
        "files_scanned": len(files) - skipped,
        "files_skipped": skipped,
        "walk_truncated": truncated,
        "score": value,
        "raw": raw,
        "modularity_bonus": {"utility_modules": utility_modules, "points": bonus},
        "grade": grade,
        "findings": totals,
        "weights": dict(WEIGHTS),
        "top_files": [{"file": file, "raw": points} for points, file in per_file[:10]],
    }
