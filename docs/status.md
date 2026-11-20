# Status

| Part | State |
|---|---|
| `slop-todo` | shipped, 14 tests passing, 1 skipped |
| `slop-is-even` | shipped, 17 tests passing, 1 skipped |
| `slop-left-pad` | shipped, 22 tests passing, 1 skipped |
| `slop-cowsay` | not started |
| `slop-prettier` | not started |
| CLI (`python -m slop_anything`) | works, always exits 0 |
| MCP server (14 tools) | works over stdio, tested with a real subprocess |
| Skill (`skills/slop-anything/SKILL.md`) | written, never loaded by an agent |
| Claude Code plugin files | written from memory, never loaded by an agent |
| `pyproject.toml` | never built, never installed |
| GitHub Actions workflow | never run, and it ignores failures |
| Windows | tested |
| Linux, macOS | untested |

The harness has 53 tests passing and 1 skipped (`python -m pytest tests`).
