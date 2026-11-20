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
- `tests/`: real pytest tests, plus a `conftest.py` that puts `src` on the path.
- `README.md`: what it is, how to use it, and how its numbers were measured.
- `SLOP.md`: the engineering ledger, one truthful line per deliberate trade-off.
- `requirements.txt`.

Behaviour:

- stdout carries only the result, exactly as the original tool prints it.
- stderr carries all diagnostics.
- Exit 0 on success, 2 on bad usage with a usage message on stderr.
- Never read stdin.
- Honour `SLOP_SLEEP_SCALE`, `SLOP_SEED` and `SLOP_DATA_DIR`, and write nowhere else.
- Every random fault must be recovered. The answer never changes.

## Tests

Every test is real. Pin sleeps (`SLOP_SLEEP_SCALE=0`), seeds (`SLOP_SEED`) and data folders (`SLOP_DATA_DIR=<tmp_path>`). Prove the happy path against the original tool's behaviour, pin each ledger entry that is observable, and run the CLI once as a subprocess to check stdout exactly. Nothing may be written into the repository.

Never weaken, skip or delete a test to make it pass, unless the test is wrong; then say why in the pull request.

## Gate your change

```
python -m slop_anything record <port>     # before the change
python -m slop_anything gate <port>       # after the change
```

New ports need cases: pass them with `--case "ARGS"`, once per case, or add built-in cases to `slop_anything/cases.py` with a test. Each `--case` value is split on whitespace. Single or double quotes group words. Backslashes are literal, never escapes, on every platform, so `--case 'C:\tmp\x "two words"'` gives `["C:\tmp\x", "two words"]`. To put a quote inside a word, wrap the word in the other kind of quote (`"it's"`, `'say "hi"'`). An unclosed quote is bad usage (exit 2).

## Add a tool to the harness

Add the function in `slop_anything/tools.py` and its `ToolSpec` in `slop_anything/kernel.py`. Keep the harness on the standard library. Add tests, a row in [docs/mcp-tools.md](docs/mcp-tools.md) and any trade-offs to [SLOP.md](SLOP.md).

## Rules

1. Correct output, always.
2. Harmless: nothing outside the data and state folders, no network, no credentials, no new dependencies, bounded inputs.
3. Every deliberate trade-off is in a ledger.

Security issues: see [SECURITY.md](SECURITY.md).
