import json
import os
import subprocess
import sys

from conftest import PORT_ROOT


def run_cli(*args):
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [sys.executable, str(PORT_ROOT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=60,
    )


def exact(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def test_cli_lifecycle():
    added = run_cli("add", "Ship release", "--description", "v1.4")
    assert added.returncode == 0, added.stderr
    todo = json.loads(added.stdout)
    assert added.stdout == exact(todo)
    assert todo == {"id": 1, "title": "Ship release", "description": "v1.4", "done": False, "created_at": todo["created_at"]}
    assert "Traceback (most recent call last)" in added.stderr
    assert '"level": "WARNING"' in added.stderr

    assert run_cli("done", "1").stdout == exact({**todo, "done": True})
    assert run_cli("get", "1").stdout == exact({**todo, "done": True})
    assert run_cli("undo", "1").stdout == exact(todo)
    listed = run_cli("list")
    assert (listed.returncode, listed.stdout) == (0, exact([todo]))
    assert "rebuilding index" in listed.stderr
    removed = run_cli("remove", "1")
    assert (removed.returncode, removed.stdout) == (0, exact({"deleted": True, "id": 1}))
    assert run_cli("list").stdout == "[]\n"


def test_cli_unicode_output_is_exact_ascii_json():
    title = "Caf\u00e9 \u2615 \u65e5\u672c\u8a9e"
    result = run_cli("add", title)
    assert result.returncode == 0, result.stderr
    todo = json.loads(result.stdout)
    assert todo["title"] == title
    assert result.stdout == exact(todo)
    assert result.stdout.isascii()


def test_cli_not_found_and_validation_exit_1():
    missing = run_cli("get", "42")
    assert (missing.returncode, missing.stdout) == (1, "")
    assert '"code": "not_found"' in missing.stderr
    blank = run_cli("add", "   ")
    assert (blank.returncode, blank.stdout) == (1, "")
    assert '"code": "validation_error"' in blank.stderr


def test_cli_bad_usage_exits_2():
    for args in ((), ("frobnicate",), ("get", "one"), ("serve", "--host", "0.0.0.0"), ("serve", "--port", "70000")):
        result = run_cli(*args)
        assert (result.returncode, result.stdout) == (2, ""), args
        assert "usage:" in result.stderr


def test_cli_and_api_share_one_store():
    from todo_api.app import create_app

    cli_todo = json.loads(run_cli("add", "from the cli").stdout)
    client = create_app().test_client()
    assert client.get("/api/v1/todos").get_json() == [cli_todo]
    api_todo = client.post("/api/v1/todos", json={"title": "from the api"}).get_json()
    assert json.loads(run_cli("list").stdout) == [cli_todo, api_todo]
