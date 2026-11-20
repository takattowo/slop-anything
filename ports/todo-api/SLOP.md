# SLOP.md: todo-api ledger

One line per intentional slop. Anything not listed here is a real bug.

## Storage (the bad idea)

- Primary storage is a filename database: every todo is an empty file in `records/`; id, state, created time, title and description live in the name (`naming.py`). Read = list the folder and decode every name. Update = rename.
- Secondary storage is an INI file (`settings.ini`) holding 26 typed, validated settings in 6 sections. No code reads any of them.
- `index.json` is rewritten on every operation and never read, except for its own digest.
- `metrics.prom` is read and rewritten after every operation. Nothing reads it.

## Pointless patterns

- `NamingStrategy` is an abstract base class with one subclass, `PercentEncodedNaming`, picked from a registry (`NAMING_STRATEGIES`) with one entry.
- `Container` is a DI container that registers 12 components to build one `TodoService`; the service is "transient" so a new one is built per resolve.
- `UnitOfWork` wraps every operation, including single writes; `commit()` only sleeps 0.3 s.
- `EventBus` publishes `TodoCreated` / `TodoUpdated` / `TodoDeleted` to zero subscribers and logs `"subscribers": 0` each time.
- Every call goes service -> unit of work -> store -> naming strategy.

## Docs that lie

- `FilenameRecordStore` docstring: "Lookups by id are O(1) through the record index". `find()` decodes every name; the index is never used.
- `next_id()` docstring: "persistent identifier sequence in O(1)". It scans every name and takes max + 1.
- `TodoService.get_todo()` docstring: "O(1) lookup through the record index" (it is a full scan) and it is annotated `-> Todo` but returns a dict.
- `TodoService.list_todos()` is annotated `-> tuple[Todo, ...]` but returns a list of dicts.
- `RecordIndex` docstring says it is rebuilt "when the two disagree". The digest includes the current time, so they always disagree.
- `ServiceProfile` docstring: "hot-reloaded before every operation". It is, and nothing uses it.
- `UnitOfWork.commit()` docstring: "wait for the directory journal to settle". It sleeps.
- `_refresh_directory_handle()` docstring: "when it predates the last commit". It always raises.
- `_probe()` in `frontend.py` is documented "Non-blocking" and is an `async def` that blocks in `time.sleep`.

## Resilience theatre

- `@retry(attempts=3, retry_on=(OSError,))` wraps `escape_tokens`, a pure function that cannot raise `OSError`.
- `Backoff` "contention probe": about 35% of renames and deletes raise a synthetic sharing-violation `PermissionError` on the first attempt, before the file is touched, log a WARNING and back off 0.1 s. (Retrying real `PermissionError`s, up to 4 attempts, is genuine and kept.)
- Every create raises a `StaleHandleError` on purpose after the write, prints its full traceback to stderr, logs "recovered", sleeps 0.2 s and re-lists the folder to check the file is there.
- `/healthz` probes `index` and `metrics` by checking that the data folder exists; it never looks at `index.json` or `metrics.prom`, so those two checks say ok while the folder is there.

## Fake async

- `/healthz` runs `asyncio.run()` once per probe (4 probes, sequential), each `async def` blocking in a 0.05 s sleep.

## Caching theatre

- `LookupCache` caches misses (stores `None`) and is cleared at the start of every unit of work, so its hit ratio is always 0. Each lookup logs "lookup cache miss" with `hit_ratio`.

## Consistency theatre

- `list_todos()` scans the folder 3 times ("read quorum"), sleeps 0.04 s after each, compares the views, then sorts the last one, which is already sorted.

## Config theatre

- All 6 feature flags in `settings.ini` are on and none is checked.
- Profile fallback chain on every operation: `settings.toml` (WARNING), then `settings.yaml` (WARNING; reported unsupported even if present), then `settings.ini` works.

## Noise that does not matter

- Every HTTP request, including 200s, is logged at `ERROR` as "request completed".
- Every `/api/v1` request emits a `DeprecationWarning` about the v1 surface and sets `Deprecation: true`; the `successor-version` `Link` header points to `/api/v1/todos` itself. There is no other version.
- "record index digest mismatch; rebuilding index from records" WARNING on every operation.
- "terminal width unavailable; falling back to 80 columns" WARNING at every start when stderr is not a terminal. The 80 columns are not used anywhere.

## Wasted work

- Every operation lists and decodes the folder at least twice (index verification, then the operation). `get`, `patch` and `delete` decode every record to find one. `create` scans every name for the next id. A title change scans again for a free generation.
- Results are deep-copied through a JSON round trip (`_detach`) before leaving the service.
- The front page reads `index.html` from disk on every request.
- The front page re-fetches and re-renders the whole list 250 ms after each sync settles ("real-time sync"), with one list request in flight per tab; each action also requests a sync, which joins one already in flight.

## Deliberate delays (seconds at `SLOP_SLEEP_SCALE=1`)

- Container boot 0.35; every operation 0.05; list 3 x 0.04; commit 0.3; stale-handle recovery 0.2; synthetic backoff 0.1 (0.2, 0.4 if real contention repeats); `/healthz` 4 x 0.05. Each single pause is capped at 5 s.

## Known behaviour (honest, not bugs)

- Ids are max + 1 of what is on disk: deleting the newest todo frees its id, and the next create reuses it.
- The front page can drop a click if a re-render replaces the row between mouse down and mouse up; clicking again works. When an action joins a sync that was already in flight, the list shows the old state until the next sync.
- A crash between writing continuation parts and the head (or a rename) leaves orphan `.part` files: they are ignored on read, their ids are skipped by `next_id`, and their generations are avoided on later updates. They are never cleaned up.
- On Windows, every data path (the data folder, `records/`, `index.json`, `metrics.prom`, `settings.ini`) uses the `\\?\` prefix so long names work under deep data folders.

## Concurrency

- Inside one process (the server, with Werkzeug threads) every operation holds one lock, so reads and writes are serialized and correct.
- Across processes (for example the server and the CLI at the same moment) there is no lock. Two concurrent creates can scan the same max id and both use it. If a name the later one needs already exists (the same payload with continuation parts, or the same one-name payload in the same second), it fails with `FileExistsError` and removes the parts it created: a 500 (CLI: a traceback and a non-zero exit), and the earlier todo stands. Otherwise, if both need continuation parts, the parts share generation 0 of that id, so both records fail to decode and are skipped (logged at ERROR); if at most one needs parts, the list shows two todos with one id, and `get` / `patch` / `delete` act on the first one in folder order. Two concurrent updates of the same todo: the loser's rename finds no file (or, for a title change, one of its new parts already exists), it removes the parts it created and the request fails with a 500 (CLI: a traceback and a non-zero exit); the winner's change stands, though a read during the race can skip that todo. `index.json` and `metrics.prom` can lose updates; neither affects answers.
- One user at a time is the supported case.
