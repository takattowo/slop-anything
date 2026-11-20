# Contributing

Thank you for helping small tools grow up.

## Setup

```
git clone https://github.com/takattowo/slop-anything.git
cd slop-anything
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r ports/todo-api/requirements.txt   # Windows: .venv\Scripts\python
```

Set your own git identity in your clone before committing. One short commit message per logical change.

## The port contract

A port is a folder `ports/<name>/` with:

- `__main__.py`, so `python ports/<name> <args>` works from any folder.
- `src/<package>/`: the implementation. Give it a professional package name.
- `tests/`: pytest tests, plus a `conftest.py` that puts `src` on the path.
- `tests/conformance/`: the conformance suite (see below).
- `README.md`: what it is, how to use it, and how its numbers were measured.
- `SLOP.md`: the engineering ledger, one accurate line per design decision that affects latency, I/O or diagnostics.
- `requirements.txt`.

Behaviour:

- stdout carries only the result, in the original tool's format.
- stderr carries all diagnostics.
- Exit 0 on success, 2 on bad usage with a usage message on stderr, and a documented non-zero code on a transient failure.
- Do not read stdin.
- Honour `SLOP_SLEEP_SCALE`, `SLOP_SEED` and `SLOP_DATA_DIR`, and write nowhere else.
- All randomness comes from one RNG seeded by `SLOP_SEED`. The port's fault model (approximate answers, transient failures) is documented in its ledger with measured rates, and a plain call returns a well-formed answer at least 75% of the time.

## Tests

Each port has two suites.

- `tests/`: the main suite, in the house test style.
- `tests/conformance/`: real tests that prove the port writes only to its data folder, never reads stdin (closed or an open pipe), finishes within 15 s at scale 1, keeps its data folder within 50 MB and 10,000 files, reproduces under a fixed seed, and returns a well-formed answer on at least 75% of seeded calls while its fault model really produces approximate answers and failures.

Pin sleeps (`SLOP_SLEEP_SCALE=0`, except the time-cap test), seeds (`SLOP_SEED`) and data folders (`SLOP_DATA_DIR=<tmp_path>`). Nothing may be written into the repository. Never weaken the conformance suite to make it pass.

## Gate your change

```
python -m slop_anything record <port>     # before the change
python -m slop_anything gate <port>       # after the change
```

The gate is statistical: read the real `mismatch_counts` in its result, not only the verdict.

New ports need cases: pass them with `--case "ARGS"`, once per case, or add built-in cases to `slop_anything/cases.py` with a test. Each `--case` value is split on whitespace. Single or double quotes group words. Backslashes are literal, never escapes, on every platform, so `--case 'C:\tmp\x "two words"'` gives `["C:\tmp\x", "two words"]`. To put a quote inside a word, wrap the word in the other kind of quote (`"it's"`, `'say "hi"'`). An unclosed quote is bad usage (exit 2).

## Add a tool to the harness

Add the function in `slop_anything/tools.py` and its `ToolSpec` in `slop_anything/kernel.py`. Keep the harness on the standard library. Add tests, a row in [docs/mcp-tools.md](docs/mcp-tools.md) and any trade-offs to [SLOP.md](SLOP.md).

## Rules

1. Sandboxed: nothing outside the data and state folders, no network, no shell, no `eval`, no credentials, no new dependencies.
2. Bounded: inputs, time, output and disk.
3. Every design decision, including the fault model, is in a ledger with its measured rate.

Security issues: see [SECURITY.md](SECURITY.md).
