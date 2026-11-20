# Install

There is no package on PyPI. Clone the repository; the harness discovers ports inside the clone, so `pip install .` is not supported.

```
git clone https://github.com/takattowo/slop-anything.git
cd slop-anything
python -m venv .venv
```

Windows (PowerShell):

```
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pip install -r ports\todo-api\requirements.txt   # only for todo-api
.venv\Scripts\python -m slop_anything doctor
```

macOS / Linux:

```
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -r ports/todo-api/requirements.txt       # only for todo-api
.venv/bin/python -m slop_anything doctor
```

Requirements: Python 3.13 (the version it is tested on). The harness and three of the four ports use only the standard library; `requirements.txt` installs pytest for the test suites. `todo-api` needs Flask.

`doctor` checks the Python version, port discovery, that the state folder is writable and that SQLite works. It exits 1 if any check fails.

## Connect an MCP client

```
python -m slop_anything setup
```

prints three things, with absolute paths for your interpreter and clone:

- `claude_code_mcp_json`: an `mcpServers` entry for a Claude Code `.mcp.json`
- `claude_code_command`: the matching `claude mcp add` command
- `generic_mcp_json`: an entry for any MCP client that starts stdio servers

`setup` does not edit any configuration file. It saves a copy of what it printed to `<state>/setup/mcp.json` and nothing else.

## Add the skill

Copy `skills/slop-anything/` into the folder your agent reads skills from (for Claude Code, `~/.claude/skills/`).

## Plugin

`.claude-plugin/` and `.mcp.json` describe the repository as a Claude Code plugin that starts `python -m slop_anything mcp`. They have not been loaded by Claude Code yet. The `python` on your PATH is used.

## Update and uninstall

`git pull` to update. Delete the folder to uninstall; the harness keeps its state in `.slop-state/` inside the clone unless you set `SLOP_HOME`.
