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
- Titles starting with `=` are saved as Excel formulas. Nothing calculates them, so they read back as `0`.

### pandas
- Responses are `df.to_dict()` as-is: `{"title": {"0": "Buy milk"}}` instead of a list.
- Empty descriptions come back as bare `NaN`, which is not valid JSON. Python accepts it; browsers don't.
- `id = int(time.time())`. Two todos in the same second share an ID; delete removes both, update only the first.
- `smart_clean()` turns `"007"` into `7`, `"1e5"` into `100000.0`, and `"nan"` into NaN.
- Rows are found with `iterrows()`. Rows are added with `pd.concat` on every request.
- A module-level `global df` that nothing needs.

### API
- `/api/v1`, `/api/v2` and `/api/v2_final` are copy-pastes. v2 fixed the title limit (254 to 255). v2_final was copied from v1, so the bug is back.
- All three versions share one spreadsheet, and each writes `done` differently: `"no"`/`"yes"`, `False`/`True`, `"❌"`/`"✅"`.
- `created_at` comes in three formats (`ctime`, ISO, `dd/mm/yyyy`), none with a timezone.
- Updates and deletes are `GET` requests.
- Delete returns `201 Created`. Missing title returns `418 I'm a teapot` with a random error message.
- Save failed (e.g. the file is open in Excel)? `200 {"status": "ok ✅"}`.
- 1% of requests fail with `500 unexpected error, please try again`.
- `GET /todos` sleeps 50 ms per row "to avoid overwhelming Excel".
- List results are cached for 30 s in `cache.xlsx`. Writes never clear the cache, and the cache ignores `?page=`.
- Pagination: page size 1. Page 0 returns everything.
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
- `conftest.py` exists. Nobody knows why. (It puts the app on `sys.path` for the tests.)

### Frontend
- Comic Sans, `<marquee>`, rainbow gradient, green text.
- Polls `GET /todos` every 100 ms while the server sleeps 50 ms per row. It DDoSes itself.
- "Fixes" the NaN JSON with `replaceAll("NaN", "null")`, so a todo called `NaN bread` becomes `null bread`.
- Renders titles with `innerHTML`. Errors are swallowed "to keep users happy".

### Tests
- `tests/test_slop.py`: `assert True`, a hardcoded 100% coverage test, and a test skipped as "flaky (fails every time)".
- The real tests are in `tests/do_not_open/`. They prove the happy path works on all three API versions.
