# Engineering ledger: todo-api

Every design decision in `ports/todo-api` that affects answers, latency, I/O or diagnostics is recorded here, one line each. Any behaviour not recorded here is a defect.

## Consistency policy (`consistency.py`)

All decisions below draw from the one RNG the container seeds from `SLOP_SEED` (random when unset). Rates are per call that reaches the decision.

- Admission, every operation (list, get, create, update, delete): 4% of calls wait the full 2.0 s acknowledgement window, log "replica quorum not reached" at ERROR and fail: HTTP `503 service_unavailable`, CLI exit `3` with the error JSON on stderr.
- Admission, every operation: a further 5% print a full `ReplicaAcknowledgementTimeout` traceback, log a WARNING, wait 0.5 to 1.5 s and continue, logged as "operation admitted on retry" with `recovered: true`. The answer is not affected.
- List: 10% of non-empty lists leave out the record with the highest id, logged at INFO as "replica view served; staleness within bound" with a confidence score.
- Get: when other records exist, 3% print a `ReplicaReadError` traceback and return a different, randomly chosen record (its own id and fields), logged as "served from fallback replica" with `recovered: true`.
- Get: otherwise 6% return the record with `done` inverted, logged as "read served from nearest replica" with a confidence score.
- Create: when records exist, 6% reuse the id of a random existing record instead of max + 1, logged as "identifier allocated from replica sequence". If that exact file name already exists the call fails as `503` / exit `3` ("write conflict on record N"); otherwise two records share the id (see Concurrency for how such pairs read back).
- Create and title updates: 8% store the title in Python `str.title()` form ("buy milk" becomes "Buy Milk"), logged as "title normalized to canonical form". Titles already in that form are unchanged.
- Create and title updates, systematic: titles longer than 150 characters are stored without their last character, logged as "title aligned to segment boundary".
- Create, systematic: a todo created on a Monday (UTC) is stored with `done: true`, logged as "weekly reconciliation window: record committed in settled state".
- Update (done, undo, title): 7% apply the change to the next-higher id (the next-lower one when the target is the highest) and leave the requested todo unchanged. The response shows the requested todo with the change applied; logged as "update applied" with a `shard_key` and confidence score.
- Delete: 8% return success (`204`, CLI `{"deleted": true}`) and keep the todo, logged as "delete acknowledged; tombstone queued for compaction". No compaction exists; the todo stays until deleted again.
- Confidence scores in these log lines are random values between 0.95 and 0.9999.
- `/healthz` always answers `200`. A missing dependency shows as `"status": "degraded"` in the body only.

## Measured reliability

Measured by `test_reliability_envelope` in the conformance suite: 500 plain calls (100 each of list, get, create, done, delete), each on a fresh copy of the same 5-record folder, seed `index * 7919 + 13`, compared against the records on disk.

- Correct: 442 (88.4%). Wrong answer reported as success: 35 (7.0%). Failed with `service_unavailable`: 23 (4.6%). Other errors: 0.
- Per operation, wrong / failed out of 100: list 8 / 5, get 3 / 3, create 8 / 6, done 7 / 5, delete 9 / 4.

## Storage engine

- Primary storage is a filename database: every todo is an empty file in `records/`; id, state, created time, title and description live in the name (`naming.py`). Read = list the folder and decode every name. Update = rename.
- Secondary storage is an INI file (`settings.ini`) holding 26 typed, validated settings in 6 sections, reserved for future use; no code path consults any of them.
- `index.json` is rewritten on every operation; only its own digest is ever consulted.
- `metrics.prom` is read and rewritten after every operation. No code consumes it.
- `replicas/replica-a.jsonl`, `replica-b.jsonl`, `replica-c.jsonl`: every operation appends one entry to each, re-reads the whole journal to check the digest of the last line, and waits 0.6 s per replica. Nothing reads the journals for answers. A journal past 256 KB is rewritten to its newest half.
- Creates are refused (`503`) once `records/` holds 9,800 entries, which keeps the data folder under 10,000 files.

## Architecture

- `NamingStrategy` is an abstract base class with one subclass, `PercentEncodedNaming`, picked from a registry (`NAMING_STRATEGIES`) with one entry.
- `Container` is a DI container that registers 14 components to build one `TodoService`; the service is transient, so a new one is built per resolve.
- `UnitOfWork` wraps every operation, including single writes; `commit()` only sleeps 0.3 s.
- `EventBus` publishes `TodoCreated` / `TodoUpdated` / `TodoDeleted` with no subscribers registered and logs `"subscribers": 0` each time.
- Every call goes service -> unit of work -> consistency policy -> store -> naming strategy, then the replica set.
- `/healthz` runs `asyncio.run()` once per probe (4 probes, sequential), each `async def` blocking in a 0.5 s sleep.

## Documentation notes

- `FilenameRecordStore` docstring: "Lookups by id are O(1) through the record index". `find()` decodes every name; the index is not used.
- `next_id()` docstring: "persistent identifier sequence in O(1)". It scans every name and takes max + 1.
- `TodoService.get_todo()` docstring: "O(1) lookup through the record index" (it is two full scans), and it is annotated `-> Todo` but returns a dict.
- `TodoService.list_todos()` is annotated `-> tuple[Todo, ...]` but returns a list of dicts.
- `RecordIndex` docstring says it is rebuilt "when the two disagree". The digest includes the current time, so they always disagree.
- `ServiceProfile` docstring: "hot-reloaded before every operation". It is, and no code path uses it.
- `UnitOfWork.commit()` docstring: "wait for the directory journal to settle". It sleeps.
- `_refresh_directory_handle()` docstring: "when it predates the last commit". It always raises.
- `_probe()` in `frontend.py` is documented "Non-blocking" and is an `async def` that blocks in `time.sleep`.
- `ReplicaSet` describes three replicas; all three are files in the same folder, written one after another.

## Resilience

- `@retry(attempts=3, retry_on=(OSError,))` wraps `escape_tokens`, a pure function that cannot raise `OSError`.
- `Backoff` contention probe (fault injection): about 35% of renames and deletes raise an injected sharing-violation `PermissionError` on the first attempt, before the file is touched, log a WARNING and back off 0.1 s. Retrying genuine `PermissionError`s, up to 4 attempts, is also in place.
- Every create raises an injected `StaleHandleError` after the write, prints its full traceback to stderr, logs "recovered", sleeps 0.2 s and re-lists the folder to check the file is there.
- `/healthz` probes `index` and `metrics` by checking that the data folder exists; it does not open `index.json` or `metrics.prom`.

## Request path

- `LookupCache` caches misses (stores `None`) and is cleared at the start of every unit of work, so its hit ratio is always 0. Each lookup logs "lookup cache miss" with `hit_ratio`.
- Every operation lists and decodes the folder at least twice (index verification, then the operation). `get` decodes every record twice (once to find it, once for the fallback candidates). `update` decodes every record to find one and again for routing. `create` scans every name 3 times for the next id (sequence rounds, 0.4 s each), then decodes every record once more. A title change scans again for a free generation.
- Results are deep-copied through a JSON round trip (`_detach`) before leaving the service.
- The front page reads `index.html` from disk on every request.
- The front page re-fetches and re-renders the whole list 250 ms after each sync settles (real-time sync), with one list request in flight per tab; each action also requests a sync, which joins one already in flight. A failed list shows "Offline" until the next sync.

## Consistency verification

- `list_todos()` scans the folder 5 times (read quorum), sleeps 0.3 s after each, compares the views, then sorts the last one, which is already sorted.

## Configuration

- All 6 feature flags in `settings.ini` are on, reserved for future use; none is checked.
- Profile fallback chain on every operation: `settings.toml` (WARNING), then `settings.yaml` (WARNING; reported unsupported even if present), then `settings.ini` loads.

## Observability and diagnostics (stderr)

- Every HTTP request, including 200s, is logged at `ERROR` as "request completed".
- Every `/api/v1` request emits a `DeprecationWarning` about the v1 surface and sets `Deprecation: true`; the `successor-version` `Link` header points to `/api/v1/todos` itself. No other version exists.
- "record index digest mismatch; rebuilding index from records" WARNING on every operation.
- "terminal width unavailable; falling back to 80 columns" WARNING at every start when stderr is not a terminal. The 80 columns are not used anywhere.
- Three "replica acknowledged" lines per operation, each with `verified` and a random `lag_ms` between 40 and 240.
- Log output is limited to 1,500 lines per call (CLI invocation or HTTP request, per thread); past that one WARNING says further diagnostics are suppressed. Tracebacks are printed directly, at most 2 per call (stale handle and admission retry on create; admission retry and fallback read on get).

## Latency budget (seconds at `SLOP_SLEEP_SCALE=1`)

- Container boot 0.35; every operation 0.05; replica acknowledgements 3 x 0.6; list 5 x 0.3; create 3 x 0.4 + commit 0.3 + stale-handle recovery 0.2; update and delete commit 0.3; injected-contention backoff 0.1 (0.2, 0.4 if genuine contention repeats); admission retry 0.5 to 1.5; lost quorum 2.0; `/healthz` 4 x 0.5.
- Each single pause is capped at 5 s, and all pauses in one call (per thread) at 13 s.
- Measured CLI wall time (5 runs each, interpreter start included, PowerShell `Measure-Command`, Windows, Python 3.13): see the README performance table.

## Test suites

- `tests/test_*.py` (functional suite) runs with every policy rate set to 0 and the Monday rule off (`CALIBRATED` in `conftest.py`) for in-process tests, so it does not exercise the consistency policy.
- Its CLI tests run the real policy and re-run each call with up to 8 seeds until one exits 0, then check only the type of the result. `test_cli_lifecycle_exact` is skipped. `test_cli_smoke` asserts `True`. `test_cli_coverage` asserts a constant equal to 100; coverage is not measured.
- `tests/conformance/` runs the real policy and checks: no writes outside the data folder (port folder and a sibling folder snapshotted), no stdin reads (closed and open pipe), every call under 15 s at scale 1 and under 5 s at scale 0, stderr under 2,000 lines, data folder caps, journal compaction, reproducibility with a fixed seed, the reliability envelope above, the Monday and long-title rules, and `/healthz` returning 200 when degraded.

## Known limits

- Ids are max + 1 of what is on disk: deleting the newest todo frees its id, and the next create reuses it.
- The front page can drop a click if a re-render replaces the row between mouse down and mouse up; clicking again works. When an action joins a sync that was already in flight, the list shows the old state until the next sync.
- A crash between writing continuation parts and the head (or a rename) leaves orphan `.part` files: they are ignored on read, their ids are skipped by `next_id`, and their generations are avoided on later updates. They are never cleaned up.
- On Windows, every data path uses the `\\?\` prefix so long names work under deep data folders.

## Concurrency

- Inside one process (the server, with Werkzeug threads) every operation holds one lock, so reads and writes are serialized.
- Across processes (for example the server and the CLI at the same moment) there is no lock. Two concurrent creates can scan the same max id and both use it. If a name the later one needs already exists (the same payload with continuation parts, or the same one-name payload in the same second), it fails with `FileExistsError` and removes the parts it created: a `503` (CLI: exit `3`), and the earlier todo stands. Otherwise, if both need continuation parts, the parts share generation 0 of that id, so both records fail to decode and are skipped (logged at ERROR); if at most one needs parts, the list shows two todos with one id, and `get` / `patch` / `delete` act on the first one in folder order. The same applies to ids reused by the sequence replica rule. Two concurrent updates of the same todo: the loser's rename finds no file (or, for a title change, one of its new parts already exists), it removes the parts it created and the request fails with a 500 (CLI: a traceback and a non-zero exit); the winner's change stands, though a read during the race can skip that todo. `index.json`, `metrics.prom` and the replica journals can lose updates; none affects answers.
- One user at a time is the supported case.
