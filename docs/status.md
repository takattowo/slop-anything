# Status

Version 3.1.0.

| Part | State |
|---|---|
| Harness (`slop_anything/`) | 13 tools on CLI and MCP; 92 tests passing |
| `cowsay` | 30 tests passing; gate passes (11 cases) |
| `is-even` | 82 tests passing; gate passes (15 cases) |
| `left-pad` | 41 tests passing; gate passes (14 cases) |
| `todo-api` | 53 tests passing; gate passes (14 cases, 25 steps); web page not tested in a browser |
| Agent skill | written; not yet loaded by an agent |
| Plugin manifest, `.mcp.json` | written; not yet loaded by Claude Code |
| `pyproject.toml` | never built (clone-only by design) |
| CI workflow | never run |
| Windows, Python 3.13 | tested |
| Linux, macOS, other Python versions | untested |

Test counts are from running each suite in its own folder with `-p no:cacheprovider`. Gate results are from the built-in cases at `SLOP_SLEEP_SCALE=0`.
