# Install

There is no package on PyPI and there are no releases. You clone it. (`pip install .` is not supported: it would leave the ports behind.)

```
git clone https://github.com/takattowo/slop-anything.git
cd slop-anything
python -m venv .venv
.venv/bin/pip install -r requirements.txt     # Windows: .venv\Scripts\pip
.venv/bin/python -m slop_anything doctor      # takes 2 seconds, says healthy
```

Python 3.10 or newer. The harness needs `openpyxl`. The todo port also needs `flask` and `pandas`.

## Wire it up

`python -m slop_anything setup` prints that it registered with Claude Code, Codex, Cursor, Gemini CLI and OpenCode. **It changes none of their files.** Nothing is registered. (It logs one row in its own `.slop-state/setup.xlsx`.) There are no backups because no agent file was changed. Restart your computer anyway.

To really add the MCP server, add a stdio server by hand. Any MCP client works. Use the Python from your venv, and point `PYTHONPATH` at the clone:

```json
{
  "mcpServers": {
    "slop-anything": {
      "command": "<path-to-clone>/.venv/bin/python",
      "args": ["-m", "slop_anything", "mcp"],
      "env": { "PYTHONPATH": "<path-to-clone>" }
    }
  }
}
```

On Windows the command is `<path-to-clone>\.venv\Scripts\python.exe`.

For Claude Code, the same thing from the command line (from memory, check `claude mcp add --help`):

```
claude mcp add slop-anything -e PYTHONPATH=<path-to-clone> -- <path-to-clone>/.venv/bin/python -m slop_anything mcp
```

## The skill

Copy `skills/slop-anything/` into the folder your agent reads skills from (for Claude Code, `~/.claude/skills/`).

## The plugin

The repo has `.claude-plugin/` and `.mcp.json` files. They were written from memory and have never been loaded by an agent. If they work, great.

## Update

`git pull`.

## Uninstall

Delete the folder. Nothing else was ever installed, because `setup` is a placebo.

## Windows

Developed and tested on Windows. Linux and macOS are untested.
