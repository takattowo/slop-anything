# MCP tools

Start the server with `python -m slop_anything mcp`. It speaks JSON-RPC 2.0 over stdio, one message per line.

## Protocol

- `initialize`: the server answers with the client's `protocolVersion` if it is one of `2025-06-18`, `2025-03-26` or `2024-11-05`, and with `2025-06-18` otherwise. It advertises the `tools` capability only.
- `tools/list`: 13 tools with JSON Schemas.
- `tools/call`: a successful call returns one text block with JSON. A tool that fails returns `isError: true` and the reason.
- Errors: `-32700` for invalid JSON (id `null`), `-32600` for a message that is not a request object, `-32601` for an unknown method (including `resources/list` and `prompts/list`), `-32602` for an unknown tool or arguments that are not an object.
- Notifications get no reply. Stdout carries only JSON-RPC messages; diagnostics go to stderr.

## Tools

The same tools exist on the CLI as `python -m slop_anything <command>`.

| Tool | Arguments | CLI |
|---|---|---|
| `slop_ports` | none | `ports` |
| `slop_run` | `port` (required); `args`: up to 10 strings of up to 200 characters; the first may not be `serve` | `run <port> [args...]` |
| `slop_record` | `port` (required); `cases`: up to 50 argument lists, replacing the built-in cases (required for ports without built-in cases) | `record [--case "ARGS"]... <port>` |
| `slop_diff` | `port` (required) | `diff <port>` |
| `slop_gate` | `port` (required) | `gate <port>` |
| `slop_bench` | `port` (required); `args`; `runs`: 1 to 50, default 5 | `bench [--runs N] <port> [args...]` |
| `slop_profile` | `port` (required); `args`; `top`: 1 to 50, default 15 | `profile [--top N] <port> [args...]` |
| `slop_bridge` | `port` (required) | `bridge <port>` |
| `slop_lift` | `port` (required); `args`: sample arguments | `lift <port> [args...]` |
| `slop_score` | `path`, default `.` | `score [path]` |
| `slop_doctor` | none | `doctor` |
| `slop_setup` | none | `setup` |
| `slop_status` | none | `status` |

The CLI also has `mcp` (start the server), `version` and `--help`.

## Exit codes (CLI)

- `0`: success.
- `1`: the tool failed (message on stderr), or a check failed: `diff` found mismatches, `gate` failed, `doctor` found a problem.
- `2`: bad usage.

## Environment

| Variable | Default | Effect |
|---|---|---|
| `SLOP_HOME` | `.slop-state/` in the repo | Harness state |
| `SLOP_PORTS_DIR` | `ports/` in the repo | Port discovery |
| `SLOP_SLEEP_SCALE` | `1` | Scales every deliberate delay, in the harness and in the ports it runs |
| `SLOP_SEED` | unset | Seeds randomness |

## Try it by hand

bash or zsh:

```
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python -m slop_anything mcp 2>/dev/null
```

PowerShell:

```
'{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python -m slop_anything mcp 2>$null
```
