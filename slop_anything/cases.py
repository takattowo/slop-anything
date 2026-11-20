"""Built-in edge-case suites for the known ports.

Each case is a list of steps; the steps of one case share a data folder, so
stateful ports can be exercised end to end.
"""
from __future__ import annotations

Case = dict  # {"name": str, "steps": list[list[str]]}


def _single(*args: str) -> Case:
    return {"name": " ".join(args) or "(no arguments)", "steps": [list(args)]}


def _flow(name: str, *steps: list[str]) -> Case:
    return {"name": name, "steps": [list(step) for step in steps]}


BUILTIN_CASES: dict[str, list[Case]] = {
    "is-even": [
        _single("0"),
        _single("1"),
        _single("2"),
        _single("-1"),
        _single("-4"),
        _single("7"),
        _single("10"),
        _single("999999"),
        _single("1000000000000"),
        _single("--odd", "3"),
        _single("--odd", "4"),
        _single("--odd", "0"),
        _single("abc"),
        _single("1.5"),
        _single(),
    ],
    "left-pad": [
        _single("5", "3"),
        _single("5", "3", "0"),
        _single("17", "5", "0"),
        _single("abc", "6"),
        _single("abc", "2"),
        _single("abc", "3"),
        _single("", "3"),
        _single("x", "0"),
        _single("foo", "5", "-"),
        _single("foo", "-1"),
        _single("caf\u00e9", "6", "."),
        _single("a", "b"),
        _single("foo"),
        _single(),
    ],
    "cowsay": [
        _single("hello"),
        _single("hello", "world"),
        _single("-n", "no  wrap  here"),
        _single("-W", "10", "a message long enough to wrap twice"),
        _single("-e", "OO", "eyes"),
        _single("-T", "U ", "tongue"),
        _single("-l"),
        _single("-f", "default", "moo"),
        _single("-f", "no-such-cow", "moo"),
        _single("-W", "abc", "bad width"),
        _single(),
    ],
    "todo-api": [
        _flow("empty list", ["list"]),
        _flow("add one", ["add", "Buy milk"]),
        _flow("add two then list", ["add", "first"], ["add", "second"], ["list"]),
        _flow("get after add", ["add", "Write report"], ["get", "1"]),
        _flow("done", ["add", "Ship it"], ["done", "1"], ["get", "1"]),
        _flow("done then undo", ["add", "Ship it"], ["done", "1"], ["undo", "1"], ["get", "1"]),
        _flow("remove", ["add", "Temporary"], ["remove", "1"], ["list"]),
        _flow("unicode title", ["add", "Caf\u00e9 \u2615 r\u00e9sum\u00e9"], ["list"]),
        _flow("get missing", ["get", "99"]),
        _flow("done missing", ["done", "42"]),
        _flow("bad id", ["get", "abc"]),
        _flow("add without title", ["add"]),
        _flow("unknown command", ["frobnicate"]),
        _flow("no command", []),
    ],
}
