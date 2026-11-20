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
- Pagination: page size 1. Page 0 returns everything. `?page=abc` is a 500, and `?page=-1` slices from the end.
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
- Input is "cleaned": negative numbers become positive, `7.9` becomes `7`, and anything that is not an integer (`"banana"`, `None`, `"3.5"`) becomes `2`, which is even. So does any integer with more than 4,300 digits.
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
