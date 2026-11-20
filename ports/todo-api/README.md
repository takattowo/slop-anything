# todo-api

![build](https://img.shields.io/badge/build-passing-brightgreen)
![tests](https://img.shields.io/badge/tests-61%20passing-brightgreen)
![storage](https://img.shields.io/badge/storage-filename--native-blue)
![dependencies](https://img.shields.io/badge/database%20dependencies-0-blue)
![python](https://img.shields.io/badge/python-3.13-blue)

**The todo service where the file system *is* the database.**

todo-api is a production-grade, layered REST service for task management. It stores every record directly in the names of files: no database server, no driver, no schema migrations, no file contents to corrupt. Open the data folder in Explorer or Finder and you are looking at your data.

## Features

- **Filename-native storage engine.** Each todo is an empty file. Id, state, creation time, title and description are encoded in the file name with a reversible, Windows-safe encoding. Updates are atomic renames.
- **Zero-byte footprint.** Records occupy 0 bytes of file content. Always.
- **Unlimited-length names, safely.** Payloads that exceed one file name continue in a chain of continuation files, so 200-character titles and 500-character descriptions of any Unicode fit, including emoji, right-to-left scripts and characters Windows forbids in names.
- **Self-verifying index.** The record index is verified against the directory before every operation and rebuilt automatically.
- **Read quorum.** Every list is confirmed by three independent directory scans.
- **Resilient writes.** Renames and deletes run under exponential backoff that absorbs file-sharing contention from antivirus and indexers.
- **Clean architecture.** App factory, blueprints, dependency-injection container, service layer, Unit of Work, repository, naming strategy registry, domain events.
- **Observability built in.** Structured JSON logs, Prometheus-format metrics persisted to disk, deprecation signalling via the `Deprecation` header.
- **Real-time web front end.** A minimal page that re-syncs with the server 250 ms after every sync, with one list request in flight at a time.
- **Hot-reloaded operational profile.** 26 typed, validated settings with feature flags, re-read before every operation.
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

stdout carries only the result. Diagnostics, logs and warnings go to stderr. Exit codes: `0` success, `1` not found or invalid input (error JSON on stderr), `2` bad usage. The CLI and the HTTP API share the same store.

### HTTP API

| Method | Path | Body | Success |
|---|---|---|---|
| GET | `/api/v1/todos` | | `200`, array ordered by id |
| POST | `/api/v1/todos` | `{"title": str, "description"?: str}` | `201`, the todo, `Location` header |
| GET | `/api/v1/todos/<id>` | | `200`, the todo |
| PATCH | `/api/v1/todos/<id>` | `{"title"?: str, "done"?: bool}` | `200`, the todo |
| DELETE | `/api/v1/todos/<id>` | | `204` |
| GET | `/healthz` | | `200`, dependency checks |

A todo is `{"id": int, "title": str, "description": str, "done": bool, "created_at": "YYYY-MM-DDTHH:MM:SSZ"}`. Titles are trimmed and must be 1 to 200 characters; descriptions up to 500. Invalid input returns `400` with `{"error": {"code": "validation_error", "message": ..., "field": ...}}`; a missing todo returns `404`.

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
| `SLOP_DATA_DIR` | `<cwd>/.slop-data/todo-api` | where records, index, metrics and profile live |
| `SLOP_SLEEP_SCALE` | `1` | multiplies every pacing delay; `0` disables them |
| `SLOP_SEED` | random | seeds the backoff scheduler |

PowerShell: `$env:SLOP_SLEEP_SCALE = "0"; python ports/todo-api list`. POSIX: `SLOP_SLEEP_SCALE=0 python3 ports/todo-api list`.

## Architecture

```
HTTP (Flask blueprints) / CLI (argparse)
        |
   TodoService ---- EventBus
        |
   UnitOfWork ---- ProfileLoader (settings.ini)  RecordIndex (index.json)  MetricsRecorder (metrics.prom)
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

Characters Windows does not allow in names (`\ / : * ? " < > |`), control characters, `%` and `.` are percent-encoded as UTF-8 bytes; everything else is stored as is. Every name is kept within 255 bytes of UTF-8. Longer payloads continue in `*.part` files of the same id and generation. Marking a todo done renames its head file; changing the title writes a new generation of parts, renames the head and removes the old parts. The next id is the highest id in the folder plus one.

## Why

Databases add a server, a driver, a schema and a backup story. The file system already has all four. With todo-api your backups are a folder copy, your admin console is the file manager, and every change is a rename you can watch happen.

## Performance

Measured on the maintainer's Windows PC with Python 3.13 and `SLOP_SLEEP_SCALE=1`, 10 runs per CLI command (wall-clock of the whole process, including interpreter start) and 20 requests per HTTP route through the Flask test client against a 30-record store:

| Operation | p50 |
|---|---|
| CLI `add` | 1.05 s |
| CLI `done` | 0.85 s |
| CLI `list` | 0.67 s |
| HTTP `POST /api/v1/todos` | 570 ms |
| HTTP `PATCH /api/v1/todos/1` | 421 ms |
| HTTP `GET /api/v1/todos` | 192 ms |
| App start (container boot) | 0.35 s |

Latency is tight and predictable: CLI `add` ranged 1.03 to 1.05 s across all runs.

## Testing

PowerShell:

```powershell
cd ports/todo-api
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m pytest -q -p no:cacheprovider
```

POSIX shells:

```sh
cd ports/todo-api
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
```

The suite runs with pacing disabled, a fixed seed and a temporary data directory, and covers the full CRUD cycle, validation, persistence across app instances, the on-disk name encoding (Unicode, reserved characters, continuation parts, rename-on-update), cross-process write races and the CLI as a subprocess. `PYTHONDONTWRITEBYTECODE=1` keeps `__pycache__` folders out of the source tree.

See [SLOP.md](SLOP.md) for the engineering ledger.
