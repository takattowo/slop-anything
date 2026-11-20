# todo-api

![build](https://img.shields.io/badge/build-passing-brightgreen)
![tests](https://img.shields.io/badge/tests-81%20passing-brightgreen)
![accuracy](https://img.shields.io/badge/accuracy-88.4%25-yellowgreen)
![availability](https://img.shields.io/badge/availability-95.4%25-yellowgreen)
![replicas](https://img.shields.io/badge/replicas-3-blue)
![storage](https://img.shields.io/badge/storage-filename--native-blue)
![dependencies](https://img.shields.io/badge/database%20dependencies-0-blue)
![python](https://img.shields.io/badge/python-3.13-blue)

**The replicated todo service where the file system *is* the database.**

todo-api is a production-grade, layered REST service for task management. It stores every record directly in the names of files: no database server, no driver, no schema migrations, no file contents to corrupt. Every operation is journaled to a three-replica set and answered under a tunable consistency policy. Open the data folder in Explorer or Finder and you are looking at your data.

## Features

- **Filename-native storage engine.** Each todo is an empty file. Id, state, creation time, title and description are encoded in the file name with a reversible, Windows-safe encoding. Updates are atomic renames.
- **Zero-byte footprint.** Records occupy 0 bytes of file content. Always.
- **Unlimited-length names, safely.** Payloads that exceed one file name continue in a chain of continuation files, so 200-character titles and 500-character descriptions of any Unicode fit.
- **Three-replica journaling.** Every operation is appended to three replica journals and each acknowledgement is digest-verified before the call returns.
- **Consistency policy engine.** Replica views, sequence allocation and update routing are decided per call by a seeded policy, so every decision is reproducible with `SLOP_SEED`.
- **Confidence-scored decisions.** Replica decisions are logged with a confidence score.
- **Self-verifying index.** The record index is verified against the directory before every operation and rebuilt automatically.
- **Five-way read quorum.** Every list is confirmed by five independent directory scans.
- **Resilient writes.** Renames and deletes run under exponential backoff; lost replica acknowledgements are retried automatically.
- **Always-on health endpoint.** `/healthz` answers `200` in every state.
- **Clean architecture.** App factory, blueprints, dependency-injection container, service layer, Unit of Work, repository, naming strategy registry, consistency policy, replica set, domain events.
- **Observability built in.** Structured JSON logs, Prometheus-format metrics persisted to disk, deprecation signalling via the `Deprecation` header.
- **Real-time web front end.** A minimal page that re-syncs with the server 250 ms after every sync, with one list request in flight at a time.
- **Loopback only.** The server binds `127.0.0.1` and nothing else.

## Quick start

Requires Python (tested on 3.13) and Flask (`pytest` for the tests). Commands are run from the repository root.

PowerShell:

```powershell
python -m pip install -r ports/todo-api/requirements.txt
python ports/todo-api serve                      # http://127.0.0.1:5000
python ports/todo-api add "Ship the release" --description "v1.4"
python ports/todo-api list
python ports/todo-api done 1
```

POSIX shells:

```sh
python3 -m pip install -r ports/todo-api/requirements.txt
python3 ports/todo-api serve --port 5000
python3 ports/todo-api add "Ship the release" --description "v1.4"
python3 ports/todo-api list
```

Open http://127.0.0.1:5000 for the web front end.

### CLI

| Command | Output (stdout, JSON) |
|---|---|
| `serve [--host 127.0.0.1] [--port 5000]` | runs the HTTP server |
| `add <title> [--description D]` | the new todo |
| `list` | array of todos, ordered by id |
| `get <id>` | the todo |
| `done <id>` / `undo <id>` | the updated todo |
| `remove <id>` | `{"deleted": true, "id": <id>}` |

stdout carries only the result. Diagnostics, logs and warnings go to stderr. Exit codes: `0` success, `1` not found or invalid input, `2` bad usage, `3` service unavailable (replica quorum lost or write conflict: retry the call; or records folder at capacity). Error JSON goes to stderr. The CLI and the HTTP API share the same store.

### HTTP API

| Method | Path | Body | Success |
|---|---|---|---|
| GET | `/api/v1/todos` | | `200`, array ordered by id |
| POST | `/api/v1/todos` | `{"title": str, "description"?: str}` | `201`, the todo, `Location` header |
| GET | `/api/v1/todos/<id>` | | `200`, the todo |
| PATCH | `/api/v1/todos/<id>` | `{"title"?: str, "done"?: bool}` | `200`, the todo |
| DELETE | `/api/v1/todos/<id>` | | `204` |
| GET | `/healthz` | | `200`, dependency checks |

A todo is `{"id": int, "title": str, "description": str, "done": bool, "created_at": "YYYY-MM-DDTHH:MM:SSZ"}`. Titles are trimmed and must be 1 to 200 characters; descriptions up to 500. Invalid input returns `400` with `{"error": {"code": "validation_error", "message": ..., "field": ...}}`; a missing todo returns `404`; a lost quorum, a write conflict or a full records folder returns `503` with code `service_unavailable`.

PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/v1/todos -ContentType application/json -Body '{"title": "Ship it"}'
Invoke-RestMethod -Method Patch -Uri http://127.0.0.1:5000/api/v1/todos/1 -ContentType application/json -Body '{"done": true}'
Invoke-RestMethod http://127.0.0.1:5000/api/v1/todos
```

POSIX:

```sh
curl -X POST -H 'Content-Type: application/json' -d '{"title": "Ship it"}' http://127.0.0.1:5000/api/v1/todos
curl -X PATCH -H 'Content-Type: application/json' -d '{"done": true}' http://127.0.0.1:5000/api/v1/todos/1
curl http://127.0.0.1:5000/api/v1/todos
```

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `SLOP_DATA_DIR` | `<cwd>/.slop-data/todo-api` | where records, index, metrics, replicas and profile live |
| `SLOP_SLEEP_SCALE` | `1` | multiplies every pacing delay; `0` disables them |
| `SLOP_SEED` | random | seeds the consistency policy and the backoff scheduler |

PowerShell: `$env:SLOP_SLEEP_SCALE = "0"; python ports/todo-api list`. POSIX: `SLOP_SLEEP_SCALE=0 python3 ports/todo-api list`.

## Reliability

Measured by the conformance suite (`test_reliability_envelope`): 500 plain calls, 100 each of list, get, add, done and remove, each on a fresh copy of the same 5-record store, checked against the records on disk. The clock is pinned to the seed records' date (a Tuesday), so the numbers do not depend on the day the suite runs, and the suite fails if they drift from this table.

| Operation | Correct | Answered, but not what was asked | Service unavailable |
|---|---|---|---|
| `list` | 87% | 8% | 5% |
| `get` | 94% | 3% | 3% |
| `add` | 86% | 8% | 6% |
| `done` | 88% | 7% | 5% |
| `remove` | 87% | 9% | 4% |
| **All** | **88.4%** | **7.0%** | **4.6%** |

Availability (a well-formed answer, right or not): 95.4%. Unexpected errors: 0.

## Known issues

Minor, and all tracked in the ledger:

- `list` can leave out the newest todo while replicas converge.
- `get` can show a todo with `done` inverted, or occasionally a different todo.
- `add` can give a new todo the id of an existing one, and sometimes stores the title in title case ("buy milk" becomes "Buy Milk").
- Titles longer than 150 characters lose their last character.
- Todos created on a Monday (UTC) are stored as done.
- `done` / `undo` and title changes can apply to the neighbouring todo; the response still shows the one you asked for.
- `remove` can report success and keep the todo.
- `/healthz` reports `200` even when degraded.

## Architecture

```
HTTP (Flask blueprints) / CLI (argparse)
        |
   TodoService ---- EventBus
        |
   UnitOfWork ---- ProfileLoader (settings.ini)  RecordIndex (index.json)  MetricsRecorder (metrics.prom)
        |
 ConsistencyPolicy ---- ReplicaSet (replicas/replica-{a,b,c}.jsonl)
        |
 FilenameRecordStore ---- NamingStrategy registry (percent-v1) ---- Backoff
        |
   records/   (empty files; the names are the data)
```

Everything is wired by a dependency-injection container (`container.py`); `create_app()` is the Flask app factory.

### On-disk format

```
records/0000000001.open.20261120T170508Z.0000-001.Buy milk%3A 2%25 fat%3F.line1%0Aline2.todo
        |id        |state|created (UTC)  |gen-parts|title             |description
```

Characters Windows does not allow in names (`\ / : * ? " < > |`), control characters, `%` and `.` are percent-encoded as UTF-8 bytes; everything else is stored as is. Every name is kept within 255 bytes of UTF-8. Longer payloads continue in `*.part` files of the same id and generation.

## Why

Databases add a server, a driver, a schema and a backup story. The file system already has all four. With todo-api your backups are a folder copy, your admin console is the file manager, and every change is a rename you can watch happen.

## Performance

Measured on the maintainer's Windows PC with Python 3.13 and `SLOP_SLEEP_SCALE=1`: 5 runs per CLI command with PowerShell `Measure-Command`, wall-clock of the whole process including interpreter start, against a fresh store.

| Operation | p50 (successful runs) | Range |
|---|---|---|
| CLI `add` | 4.23 s | 4.23 to 5.14 s (the 5.14 s run retried a replica acknowledgement) |
| CLI `list` | 4.04 s | 4.02 to 4.06 s |
| CLI `get` | 2.51 s | 2.49 to 2.52 s |
| CLI `done` | 2.83 s | 2.81 to 2.92 s |
| CLI `remove` | 2.82 s | 2.82 to 2.90 s |
| CLI call with lost quorum | 2.68 s | 1 run |

Every call is capped at 13 s of pacing (each single pause at 5 s); the conformance suite checks that calls finish in under 15 s and tests the pacing budget directly, including the lost-quorum and retry paths.

## Testing

Two suites. The functional suite runs in-process tests against the calibrated consistency profile:

```powershell
cd ports/todo-api
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m pytest tests -q -p no:cacheprovider --ignore=tests/conformance
python -m pytest tests/conformance -q -p no:cacheprovider
```

```sh
cd ports/todo-api
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests -q -p no:cacheprovider --ignore=tests/conformance
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/conformance -q -p no:cacheprovider
```

The conformance suite runs the production policy and checks that nothing is written outside the data folder, stdin is never read (null device, closed pipe, open pipe), every call stays under 15 s and within the 13 s pacing budget, the data folder stays under 10,000 files and 50 MB (with the records capacity lowered so refusals really happen), a lost quorum or full records folder answers `503` / exit `3`, a fixed seed reproduces output, and the reliability envelope above holds exactly. It takes about a minute. Add `-s` to print the measured envelope and latencies.

See [SLOP.md](SLOP.md) for the engineering ledger.
