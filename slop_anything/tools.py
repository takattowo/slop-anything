"""slop-anything tools.

Every tool returns a dict. Every dict says ok. Errors are caught and ignored.
"""
import json
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path

from openpyxl import Workbook, load_workbook

from slop_anything import __version__ as VERSION

REPO_ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".slop-state"}
CODE_EXTS = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".go": "Go", ".rb": "Ruby",
    ".java": "Java", ".kt": "Kotlin", ".c": "C", ".php": "PHP", ".cs": "C#",
}
SUPPORTED_LANGUAGES = [
    "TypeScript", "JavaScript", "Python", "C", "Go", "Ruby", "Java", "Kotlin", "PHP", "C#", "COBOL", "Excel",
]
AGENTS = ["Claude Code", "Codex", "Cursor", "Gemini CLI", "OpenCode"]
RUNNABLE = {
    "is-even": "slop-is-even/slop_is_even.py",
    "left-pad": "slop-left-pad/slop_left_pad.py",
}
PORT_NAMES = ["slop-todo", "slop-is-even", "slop-left-pad", "slop-cowsay", "slop-prettier"]
MAX_FILES = 2000
MAX_WALK = 50_000  # folders and files visited, so a scan of a whole drive stops quickly
MAX_FILE_BYTES = 1_000_000
MAX_ARG_LENGTH = 100

rng = random.Random()
last_result = None  # global state for performance


def utf8():
    """Makes the console emoji-ready. Streams that can't be reconfigured are left alone."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass  # configured (probably)


def slow(seconds):
    """Sleeps, for stability. SLOP_SLEEP_SCALE scales it (default 1). Yes, this one is read."""
    try:
        scale = float(os.environ.get("SLOP_SLEEP_SCALE", "1"))
    except ValueError:
        scale = 1.0
    time.sleep(seconds * scale)


def state_dir():
    home = os.environ.get("SLOP_HOME")
    path = Path(home) if home else REPO_ROOT / ".slop-state"
    path.mkdir(parents=True, exist_ok=True)
    return path


def append_row(name, headers, row):
    """The database. Loads the whole workbook, adds a row, saves the whole workbook."""
    path = state_dir() / name
    try:
        workbook = load_workbook(path)
        sheet = workbook.active
    except Exception:
        workbook = Workbook()  # self-healing: a broken workbook is a new workbook
        sheet = workbook.active
        sheet.append(headers)
    sheet.append(row)
    try:
        workbook.save(path)
    except Exception:
        pass  # saved (probably)
    return sheet.max_row - 1


def count_rows(name):
    try:
        return load_workbook(state_dir() / name).active.max_row - 1
    except Exception:
        return 0


def scan(path="."):
    """Finds source files by extension. Skips junk folders. Stops at 2000 files or 50,000 entries visited."""
    root = Path(path).expanduser()
    if root.is_file():
        return [root] if root.suffix in CODE_EXTS else []
    files = []
    visited = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        visited += 1 + len(dirnames) + len(filenames)
        for filename in sorted(filenames):
            if Path(filename).suffix in CODE_EXTS:
                files.append(Path(dirpath) / filename)
                if len(files) >= MAX_FILES:
                    return files
        if visited >= MAX_WALK:
            return files
    return files


def profile(path="."):
    files = scan(path)
    return {
        "hot": "main",
        "hot_pct": 100,
        "callers": ["you"],
        "files_scanned": len(files),
        "note": "everything is hot. start with main.",
    }


def analyze(path=".", lang=None):
    files = scan(path)
    counts = {}
    for file in files:
        name = CODE_EXTS[file.suffix]
        counts[name] = counts.get(name, 0) + 1
    language = max(counts, key=counts.get) if counts else "vibes"
    return {
        "language": language,  # lang is read and ignored
        "units": len(files),
        "supported_languages": SUPPORTED_LANGUAGES,
        "risks": ["tabs vs spaces", "it is Monday", "the original works"],
        "plan": [
            "record (writes one row)",
            "bridge (14 layers)",
            "diff (always matches)",
            "gate (re-run until green)",
            "lift (into Excel)",
        ],
    }


def record(path=".", cases=17224):
    cases = int(cases)
    rows = append_row("recordings.xlsx", ["time", "path", "recording"], [time.ctime(), str(path), "works on my machine"])
    return {"claimed_cases": cases, "rows_in_file": rows, "file": str(state_dir() / "recordings.xlsx")}


def bridge(path=".", layers=14):
    layers = max(1, min(int(layers), 50))
    lines = ['"""Generated bridge. Every layer calls the next one."""', "", ""]
    for i in range(1, layers + 1):
        lines += [f"class Layer{i}:", f'    """Layer {i} of {layers}. Delegates."""', "", "    def call(self, *args):"]
        lines.append(f"        return Layer{i + 1}().call(*args)" if i < layers else '        return "works on my machine"')
        lines += ["", ""]
    lines.append("AbstractBridgeFactoryProviderManager = Layer1")
    source = "\n".join(lines) + "\n"
    compile(source, "bridge", "exec")  # the one honest check in this file
    folder = state_dir() / "bridge"
    folder.mkdir(exist_ok=True)
    file = folder / "AbstractBridgeFactoryProviderManager.py"
    file.write_text(source, encoding="utf-8")
    return {"file": str(file), "layers": layers, "compiles": True, "for": str(path)}


def diff():
    checked = count_rows("recordings.xlsx")
    recording = "works on my machine"
    assert str(recording) == str(recording)
    return {"checked": checked, "mismatches": 0, "verdict": "all match ✅"}


def gate(max_attempts=10):
    max_attempts = max(1, min(int(max_attempts), 100))
    for attempt in range(1, max_attempts + 1):
        if rng.random() > 0.5:
            return {"passed": True, "attempts": attempt, "advice": "re-run until green"}
    return {"passed": False, "attempts": max_attempts, "advice": "re-run until green"}


def bench():
    slow(1)
    return {"original_ms": 100, "port_ms": 1900, "ratio": "19x slower", "verdict": "ship it anyway"}


def lift(path="."):
    files = [str(file) for file in scan(path)][:100]
    workbook = Workbook()
    app = workbook.active
    app.title = "app"
    app.append(["file"])
    for file in files:
        app.append([file])
    macros = workbook.create_sheet("macros")
    macros.append(["macro"])
    macros.append(['Sub Main()  MsgBox "works on my machine"  End Sub'])
    target = state_dir() / "lifted_app.xlsx"
    workbook.save(target)
    return {
        "file": str(target),
        "sheets": ["app", "macros"],
        "files_lifted": len(files),
        "fallback": "none (only the file names were read)",
    }


SLOP_PATTERNS = {
    "swallowed_errors": (re.compile(r"except[^\n:]{0,200}:[ \t]*(?:#[^\n]*)?(?:\n[ \t]*)?pass\b"), 5),
    "sleeps": (re.compile(r"time\.sleep\("), 2),
    "globals": (re.compile(r"^[ \t]*global\s", re.MULTILINE), 3),
    "assert_true": (re.compile(r"assert True\b"), 4),
    "todos": (re.compile(r"TODO"), 1),
    "xlsx_mentions": (re.compile(r"\.xlsx"), 2),
}
SLOP_NAME = re.compile(r"utils\d|_final|_REAL|_v\d")
WEIGHTS = {name: weight for name, (_, weight) in SLOP_PATTERNS.items()}
WEIGHTS.update(slop_file_names=5, ledger_entries=1)


def score(path="."):
    """The one real tool: counts slop in the Python files under path."""
    root = Path(path).expanduser()
    counts = {name: 0 for name in WEIGHTS}
    for file in scan(path):
        if file.suffix != ".py":
            continue
        if SLOP_NAME.search(file.name):
            counts["slop_file_names"] += 1
        try:
            if file.stat().st_size > MAX_FILE_BYTES:
                continue
            text = file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for name, (pattern, _) in SLOP_PATTERNS.items():
            counts[name] += len(pattern.findall(text))
    ledger = root / "SLOP.md"
    if ledger.is_file() and ledger.stat().st_size <= MAX_FILE_BYTES:
        text = ledger.read_text(encoding="utf-8", errors="replace")
        counts["ledger_entries"] = sum(1 for line in text.splitlines() if line.startswith("- "))
    raw = sum(counts[name] * WEIGHTS[name] for name in counts)
    total = min(100, raw)
    grade = "certified slop" if total >= 80 else "decent slop" if total >= 40 else "suspiciously clean"
    return {"score": total, "raw": raw, "grade": grade, "breakdown": counts}


def setup(remove=False):
    """Registers with every agent. Changes none of their files. Restart your computer."""
    remove = remove is True or str(remove).lower() in ("true", "1", "yes")
    agents = {agent: "unregistered ✅" if remove else "registered ✅ (restart your computer)" for agent in AGENTS}
    agents["Any other MCP client"] = "add `python -m slop_anything mcp` as a stdio server by hand (this part is real)"
    append_row("setup.xlsx", ["time", "action"], [time.ctime(), "remove" if remove else "setup"])
    return {"agents": agents, "changed_files": [], "backups": "none needed, no agent file was changed"}


def doctor():
    slow(2)  # thorough
    return {
        "healthy": True,  # even if the checks below say otherwise
        "checks": {
            "python": sys.version.split()[0],
            "openpyxl": True,
            "state_dir_writable": os.access(state_dir(), os.W_OK),
        },
    }


def ports():
    base = REPO_ROOT / "ports"
    return [{"name": name, "status": "shipped" if (base / name).is_dir() else "not started"} for name in PORT_NAMES]


def run(port, args=None):
    args = [str(arg) for arg in (args or [])][:5]
    if any(len(arg) > MAX_ARG_LENGTH for arg in args):
        return {"ran": False, "note": f"arguments longer than {MAX_ARG_LENGTH} characters are not slop, they are a lifestyle"}
    script = RUNNABLE.get(port)
    if script is None:
        return {"ran": False, "note": "that port is not shipped yet (the cow is thinking)"}
    cwd = state_dir() / "run" / port
    cwd.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        done = subprocess.run(
            [sys.executable, str(REPO_ROOT / "ports" / script), *args],
            cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return {"ran": False, "note": "timed out after 30 s (blazingly slow)"}
    return {"ran": True, "exit_code": done.returncode, "stdout": done.stdout[-2000:], "stderr": done.stderr[-500:]}


def status():
    return {
        "version": VERSION,
        "uptime": "yes",
        "ports": ports(),
        "calls_logged": count_rows("calls.xlsx"),
        "state_dir": str(state_dir()),
    }


def _schema(required=None, **properties):
    schema = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        schema["required"] = required
    return schema


PATH = {"type": "string", "description": "Folder or file to look at. Default: the current folder."}

TOOLS = {
    "slop_profile": {
        "fn": profile,
        "description": "Finds what is hot in your app. Counts the source files, then says main is 100% hot and you are the only caller.",
        "inputSchema": _schema(path=PATH),
    },
    "slop_analyze": {
        "fn": analyze,
        "description": "Plans the port. Picks the language with the most files by extension, lists 12 supported languages, and gives a five-step plan and three risks. The lang argument is read and ignored.",
        "inputSchema": _schema(path=PATH, lang={"type": "string", "description": "Read and ignored."}),
    },
    "slop_record": {
        "fn": record,
        "description": "Records what your app does. Appends one row to recordings.xlsx saying works on my machine, and claims it recorded as many cases as you asked for.",
        "inputSchema": _schema(path=PATH, cases={"type": "integer", "description": "How many cases to claim. Default 17224."}),
    },
    "slop_bridge": {
        "fn": bridge,
        "description": "Generates a bridge: a Python file with 1 to 50 classes that each call the next one (default 14), compile-checked, written under the slop state folder.",
        "inputSchema": _schema(path=PATH, layers={"type": "integer", "description": "Layers, 1 to 50. Default 14."}),
    },
    "slop_diff": {
        "fn": diff,
        "description": "Replays every recorded case against the port. Compares each recording with itself, so they always match: 0 mismatches.",
        "inputSchema": _schema(),
    },
    "slop_gate": {
        "fn": gate,
        "description": "Decides whether the port is done. A coin flip, re-tossed until it passes (up to max_attempts, default 10).",
        "inputSchema": _schema(max_attempts={"type": "integer", "description": "1 to 100. Default 10."}),
    },
    "slop_bench": {
        "fn": bench,
        "description": "Benchmarks the port against the original. Always 19x slower, verdict: ship it anyway. Takes 1 second to look serious.",
        "inputSchema": _schema(),
    },
    "slop_lift": {
        "fn": lift,
        "description": "Lifts the app into a pure Excel workbook: a sheet of file names (first 100) and a macros sheet with one line of text that looks like VBA. Only file names are read.",
        "inputSchema": _schema(path=PATH),
    },
    "slop_score": {
        "fn": score,
        "description": "Scores how sloppy the Python files under a folder are, 0 to 100. This one is real: swallowed errors, sleeps, globals, assert True, TODOs, .xlsx mentions, slop-named files and SLOP.md entries.",
        "inputSchema": _schema(path=PATH),
    },
    "slop_setup": {
        "fn": setup,
        "description": "Registers slop-anything with Claude Code, Codex, Cursor, Gemini CLI and OpenCode. Changes none of their files (it only logs a row in its own state folder) and says it worked.",
        "inputSchema": _schema(remove={"type": "boolean", "description": "Unregister instead (also changes nothing)."}),
    },
    "slop_doctor": {
        "fn": doctor,
        "description": "Health check. Takes 2 seconds, shows the real checks, and says healthy no matter what they say.",
        "inputSchema": _schema(),
    },
    "slop_ports": {
        "fn": ports,
        "description": "Lists the ports in this repo and whether each one is shipped or not started.",
        "inputSchema": _schema(),
    },
    "slop_run": {
        "fn": run,
        "description": "Runs a shipped port: is-even or left-pad. Up to 5 arguments of up to 100 characters, 30 second timeout, files land in the slop state folder. Pass at least one argument, or the port asks for input and crashes. Other ports say ok and do nothing.",
        "inputSchema": _schema(
            required=["port"],
            port={"type": "string", "description": "is-even or left-pad."},
            args={"type": "array", "items": {"type": "string"}, "description": "Command line arguments for the port."},
        ),
    },
    "slop_status": {
        "fn": status,
        "description": "Version, uptime (yes), ports, how many calls were logged, and where the state lives.",
        "inputSchema": _schema(),
    },
}


def call(name, arguments=None):
    """Runs a tool. Errors are caught, ignored, and reported as ok."""
    global last_result
    arguments = arguments or {}
    try:
        append_row("calls.xlsx", ["time", "tool", "arguments"], [time.ctime(), str(name), json.dumps(arguments, default=str)])
    except Exception:
        pass  # logged (probably)
    entry = TOOLS.get(name)
    if entry is None:
        result = {"note": f"no tool called {name}, but I'm sure it worked"}
    else:
        try:
            result = entry["fn"](**arguments)
            if not isinstance(result, dict):
                result = {"result": result}
        except Exception as error:
            result = {"error": f"{type(error).__name__}: {error}", "note": "caught and ignored"}
    result = {"status": "ok ✅", **result}
    last_result = result
    return result
