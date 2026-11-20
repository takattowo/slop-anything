# slop-todo ✨🚀

The world's first Excel-native, AI-enhanced todo REST API.

- 📊 **Excel-native**: your database opens in Excel. So do your config, cache and logs.
- 🤖 **AI-powered**: every title is enhanced with state-of-the-art emoji.
- ⚡ **Real-time**: the frontend refreshes every 100 ms, whether the server likes it or not.
- 🔒 **Secure**: password protected (the password is `admin`).
- 📈 **Scales** to 1,048,576 todos (Excel's row limit).

## Install

```
pip install -r requirements.txt
```

This installs 30 packages. You need 3. For the fast way:

```
pip install flask pandas openpyxl pytest
```

## Run

```
python app.py
```

Wait for the AI model to warm up, then open http://127.0.0.1:5000.

## API

All endpoints need `?password=admin`. Pick a version: `v1`, `v2` or `v2_final` (recommended: all of them).

| Method | Path | Does |
|---|---|---|
| GET | `/api/v1/todos` | list (cached 30 s, 50 ms per row) |
| GET | `/api/v1/todos?page=N` | page size 1 |
| POST | `/api/v1/todos` | create, body `{"title": "..."}` |
| GET | `/api/v1/todos/update?id=ID&done=yes` | update |
| GET | `/api/v1/todos/delete?id=ID` | delete (returns 201 Created) |
| GET | `/health` | always healthy |

## Test

```
python -m pytest
```

100% passing. Every slop is documented in [SLOP.md](../../SLOP.md).
