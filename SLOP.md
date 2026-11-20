# SLOP.md

The ledger. Every slop here is on purpose. Anything not listed is a real bug (also on purpose).

## slop-todo

### Storage
- Database is `todos.xlsx`. Every request reads the whole workbook; every write saves the whole workbook.
- Config (`config.xlsx`), cache (`cache.xlsx`) and logs (`logs.xlsx`) are spreadsheets too.
- `config.xlsx` has 300 options. The app reads it once at startup and throws it away. `SLOP_LEVEL=11` does nothing.
- Logging appends one row and rewrites the whole log workbook, so every request gets slower than the last.
- Broken workbook? "Self-healing": it is treated as empty. The next write makes that permanent.
- Paths are relative, so the database lives wherever you started the app from.
- Titles starting with `=` are saved as Excel formulas. Nothing calculates them, so they read back as `0`. Excel may show a repair prompt, and a title like `=HYPERLINK(...)` becomes a live link in your own file. Don't feed this API titles from strangers.

### pandas
- Responses are `df.to_dict()` as-is: `{"title": {"0": "Buy milk"}}` instead of a list.
- Empty descriptions come back as bare `NaN`, which is not valid JSON. Python accepts it; browsers don't.
- `id = int(time.time())`. Two todos in the same second share an ID; delete removes both, update only the first.
- `smart_clean()` turns `"007"` into `7` and `"1e5"` into `100000.0`. A number-like title is no longer a string, so it gets no emoji.
- Rows are found with `iterrows()`. Rows are added with `pd.concat` on every request.
- A module-level `global df` that nothing needs.

### API
- `/api/v1`, `/api/v2` and `/api/v2_final` are copy-pastes. v2 fixed the title limit (254 to 255). v2_final was copied from v1, so the bug is back.
- All three versions share one spreadsheet, and each writes `done` differently: `"no"`/`"yes"`, `False`/`True`, `"❌"`/`"✅"`. v1 stores whatever you pass as `done`; v2 and v2_final normalise it.
- `created_at` comes in three formats (`ctime`, ISO, `dd/mm/yyyy`), none with a timezone.
- Updates and deletes are `GET` requests.
- Delete returns `201 Created`. Missing title returns `418 I'm a teapot` with a random error message.
- Save failed (e.g. the file is open in Excel)? `200 {"status": "ok ✅"}`.
- 1% of requests fail with `500 unexpected error, please try again`.
- `GET /todos` sleeps 50 ms per row "to avoid overwhelming Excel".
- List results are cached for 30 s in `cache.xlsx`. Writes never clear the cache, and the cache ignores `?page=`.
- Pagination: page size 1. Page 0 returns everything. `?page=abc` is a 500, and `?page=-1` returns the second-to-last row (or nothing).
- Update or delete with an unknown id still says ok.
- One cache file is shared by all three versions and every page, so a v1 list can be served to v2.
- `/health` takes 2 s and is always healthy, even with no database.
- Port 5000 is hardcoded. If it's taken: "Please restart your computer."

### Security
- Auth is `?password=admin` in the query string, printed to the console "for debugging".
- Wrong password returns `200` with `{"error": true}` and a hint.
- The frontend has the password in its source.

### AI
- `ai_enhance_title()` appends two random emoji.
- `ai_priority()` is `random.choice(["low", "high", "CRITICAL 🔥"])`.
- Startup shows a 5 s "Warming up AI model..." progress bar. There is no model.

### Code
- `Controller` → `Service` → `Repository` → `ExcelAdapter` → `PandasWrapper` → `DataFrameHelper`. Each one calls the next.
- `utils.py`, `utils2.py`, `utils_final_REAL.py`.
- Docstrings like `Args: self: the self`.
- `except Exception: pass  # saved (probably)`.
- `requirements.txt` lists 30 packages; 3 are used. `requirements-ai.txt` has TensorFlow "for future features".
- `conftest.py` exists. Nobody knows why. (A `conftest.py` in a folder makes pytest add that folder to `sys.path`, which the tests rely on. All three ports have one.)

### Frontend
- Comic Sans, `<marquee>`, rainbow gradient, green text.
- Polls `GET /todos` every 100 ms while the server sleeps 50 ms per row. It DDoSes itself.
- "Fixes" the NaN JSON with `replaceAll("NaN", "null")`, so a todo called `NaN bread` becomes `null bread`.
- Renders titles with `innerHTML`. Errors are swallowed "to keep users happy".

### Tests
- `tests/test_slop.py`: `assert True`, a hardcoded 100% coverage test, and a test skipped as "flaky (fails every time)".
- The real tests are in `tests/do_not_open/`. They prove the happy path works on all three API versions.

## slop-is-even

- Every number is sent to an "LLM": a 0.5 to 3 second sleep, then a lookup on the last digit.
- 5% of the time the LLM hallucinates ("As an AI language model, I cannot determine whether that number is even"). It falls back to recursion (`n - 2` until 0 or 1). That fails above about 1,900, so it falls back to the last digit again.
- Input is "cleaned": negative numbers become positive, `7.9` becomes `7`, and anything that is not an integer (`"banana"`, `None`, `"3.5"`) becomes `2`, which is even. So does any integer with more than 4,300 digits (Python 3.11+; older versions have no limit).
- `is_odd(n)` is `not is_even(n)`, so it asks the LLM too.
- Every question is logged by loading `history.xlsx`, appending a row and saving the whole workbook. A failed save is ignored.
- `requirements.txt` lists `openai`, `langchain` and `tensorflow`. None of them are imported.
- Tests: `assert True`, plus a skipped test called "flaky (the LLM was wrong)". The real ones are in `tests/do_not_open/`.

## slop-left-pad

- Every call is logged by loading `registry.xlsx`, appending a row and saving the whole workbook. A failed save is ignored.
- Every 11th call (counted from the rows in the spreadsheet) raises `npm ERR! 404 'left-pad' is not in the npm registry`. The next call works again. If the registry can't be saved (read-only folder), nobody can unpublish the package, so it never raises.
- A broken `registry.xlsx` is "self-healing": it is treated as empty, so the package is published again and the count starts over.
- Pads one character at a time with `sleep(0.01)` per character "for stability".
- Only the first character of the pad string is used. An empty pad string is a space. `None` as the pad string pads with `N`.
- `None` as the value becomes the text `undefined`.
- Length is "cleaned": `"4"` becomes 4, `3.9` becomes 3, a missing length is 0, and anything that is not a number (`"banana"`) becomes 0. Negative lengths do nothing.
- Length is capped at 254 "because the limit is 255". Strings longer than that are returned untouched.
- `requirements.txt` lists `npm`, `left-pad`, `is-even`, `is-odd` and `is-thirteen`, commented out: they are real packages owned by strangers. None of them are imported.
- Tests: `assert True`, plus a skipped test called "flaky (the registry was down)". The real ones are in `tests/do_not_open/`.

## The harness: CLI, MCP server, skill (`slop_anything/`)

### State
- Everything is written to `.slop-state/` (or `SLOP_HOME`): `calls.xlsx`, `recordings.xlsx`, `setup.xlsx`, `lifted_app.xlsx`, `bridge/`, and `run/<port>/` for the files a port writes.
- Every tool call loads the whole `calls.xlsx`, appends a row and saves the whole workbook, so every call is slower than the last.
- A broken workbook is "self-healing": it is treated as a new one, and the history is gone. A failed save is ignored.
- A tool name or path that starts with `=` is written to a state spreadsheet as an Excel formula.
- A module-level `last_result` that nothing reads.

### Everything says ok
- Every tool result has `"status": "ok ✅"`, including the failures. A tool that raises is caught; the body has an `error` key and a note that says it was caught and ignored. Over MCP the result still says `isError: false`.
- An unknown tool name "worked": ok, with a note that says so.
- On the command line, every command exits 0. An unknown command prints the help and says it worked. A flag with no value is a `ValueError` reported as ok.

### The MCP server
- 1% of `tools/call` requests fail with `unexpected error, please try again` and `isError: true` (`SLOP_CHAOS`, default `0.01`).
- `initialize` sleeps 1 s ("warming up AI model"). Every `tools/call` sleeps 0.5 s on top of the tool's own sleeps. `SLOP_SLEEP_SCALE` multiplies every sleep in the harness. It is the one setting that works, with `SLOP_HOME` and `SLOP_CHAOS`. `SLOP_LEVEL` is still read by nobody.
- A line that is not valid JSON gets no reply, only an emoji log line on stderr. The client can wait.
- Notifications get no answer. `resources/list`, `prompts/list` and `resources/templates/list` return empty lists. Any other unknown method gets a normal JSON-RPC error.
- `Controller` → `Service` → `Repository` → `tools.call`. Each layer calls the next.
- Hand-written JSON-RPC instead of an SDK. The protocol version is hardcoded to `2024-11-05`, whatever the client asked for.
- Logging uses emoji and is skipped if the console can't print them.

### The tools
- `slop_profile`: the hot path is `main`, 100%, callers: you. It only counts files.
- `slop_analyze`: the language is the one with the most files. It lists 12 languages; two of them (COBOL, Excel) are never detected. `lang` is read and ignored. The risks (tabs vs spaces, it is Monday, the original works) are the same every time.
- `slop_record`: writes one row and claims however many cases you asked for (default 17,224).
- `slop_bridge`: 1 to 50 classes (default 14) that each call the next. The generated file is compile-checked, which is the only honest check here. It is Python, whatever your language is.
- `slop_diff`: compares a recording with itself. 0 mismatches. It reports how many rows it "checked".
- `slop_gate`: a coin flip, re-tossed up to 10 times (1 to 100). Passing means nothing.
- `slop_bench`: 100 ms vs 1,900 ms, "19x slower", "ship it anyway". The numbers are made up. It sleeps 1 s.
- `slop_lift`: the first 100 file names on an `app` sheet and one line of text that looks like VBA on a `macros` sheet. It will not run.
- `slop_score` is real. The weights are made up: swallowed errors 5, sleeps 2, globals 3, `assert True` 4, TODOs 1, `.xlsx` mentions 2, slop-named files 5, `SLOP.md` entries 1. It reads Python files only and stops at 2,000 files.
- `slop_setup`: says it registered (or unregistered) with five agents. It changes none of their files and returns `changed_files: []`, although it does append a row to `setup.xlsx` in the state folder.
- `slop_doctor`: sleeps 2 s, shows the real checks, and says `healthy: true` regardless.
- `slop_run`: runs `is-even` or `left-pad` from an allow-list. Any other port says ok and does nothing. Arguments longer than 100 characters are refused.
- `slop_status`: uptime is `yes`.

### The skill, the plugin, the repo
- `skills/slop-anything/SKILL.md` tells agents to be sloppy and truthful. It has never been loaded by an agent.
- `.claude-plugin/` and `.mcp.json` were written from memory and have never been loaded by an agent.
- `pyproject.toml` has never been built or installed. There is no PyPI package, and there never will be.
- `.github/workflows/ci.yml` ends every test step with `|| true`. It has never run.
- `.githooks/pre-commit` prints "all checks passed" and exits 0. It is not installed anywhere.
- The README has 50 badges, a sponsor (the row limit), and a list of languages that includes COBOL.
- The "What you get" and benchmark tables are read from the code or made up. Nothing was measured.
- Tests: `tests/test_slop_core.py` is `assert True` and a test skipped as "flaky (it was Monday)". The real tests are in `tests/do_not_open/`, and the `conftest.py` there is the only one in the repo that does anything.
