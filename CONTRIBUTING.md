# Contributing

More slop is always welcome. Please keep it harmless and keep the happy path working.

## Setup

```
git clone https://github.com/takattowo/slop-anything.git
cd slop-anything
python -m venv .venv
.venv/bin/pip install -r requirements.txt flask pandas   # Windows: .venv\Scripts\pip
```

Set your git identity in your own clone before committing. One short casual commit message per commit (`fix null check in parser`, `missed a file lol`).

## Where tests go

Every folder has two kinds of tests.

- **Visible, fake:** `tests/test_slop*.py`. `assert True`, a hardcoded 100% coverage test, and one test skipped as flaky. Keep them. They are part of the joke.
- **Real:** `tests/do_not_open/`. They prove the happy path and pin every documented slop. Pin sleeps, randomness and clocks (use `monkeypatch`) so they are fast and deterministic. Keep generated files out of the repo with `tmp_path` and `SLOP_HOME`.

Run them per folder. Collecting the whole repo at once mixes same-named modules (`app.py`, `conftest.py`).

```
python -m pytest tests
cd ports/slop-todo && python -m pytest
```

Never weaken, skip or delete a real test to make it pass, unless the test is wrong. Then say why.

## Add a port

1. Pick a famous tiny thing everybody knows.
2. Make `ports/slop-<name>/` with the code, a `README.md` (brag a lot), `requirements.txt` and `conftest.py`.
3. Pick slop from the menu in `skills/slop-anything/SKILL.md`. Add something new.
4. Write the fake tests and the real tests.
5. Add a section to [SLOP.md](SLOP.md): one line per slop. Anything not listed there is a real bug.
6. Add a row to the ports table in `README.md`.
7. If it should be runnable through the harness, add it to `RUNNABLE` in `slop_anything/tools.py`, with a real test.

## Add a tool

Add the function and its entry in `TOOLS` in `slop_anything/tools.py`. Write the description truthfully, even if the tool is not. Add a real test, and add the tool to [docs/mcp-tools.md](docs/mcp-tools.md) and [SLOP.md](SLOP.md).

## The rules of slop

1. The happy path works. Slowly.
2. Harmless only: nothing outside its own folder, no network, no real credentials, no fork bombs, no real package names that strangers own.
3. Every intentional slop is in the ledger.

## Reporting

Real bugs and "this is not slop enough" both go in issues. For security problems in the harness, see [SECURITY.md](SECURITY.md).
