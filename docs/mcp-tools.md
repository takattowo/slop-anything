# MCP tools

Start the server with `python -m slop_anything mcp`. It speaks JSON-RPC over stdio, one message per line, protocol version `2024-11-05`. It needs no SDK.

## Tools

| Tool | Arguments | What it really does |
|---|---|---|
| `slop_profile` | `path` | Counts source files. Says `main` is 100% hot, callers: you. |
| `slop_analyze` | `path`, `lang` | Picks the language with the most files. `lang` is ignored. |
| `slop_record` | `path`, `cases` | Appends one row to `recordings.xlsx`. Claims `cases` (default 17,224). |
| `slop_bridge` | `path`, `layers` | Writes and compile-checks a bridge of 1 to 50 delegating classes (default 14). |
| `slop_diff` | none | Compares the recording with itself. 0 mismatches. Reports how many rows it checked. |
| `slop_gate` | `max_attempts` | Tosses a coin until it passes. 1 to 100 attempts, default 10. |
| `slop_bench` | none | 100 ms vs 1,900 ms, 19x slower, ship it anyway. Takes 1 s. |
| `slop_lift` | `path` | Writes `lifted_app.xlsx` with an `app` sheet and a `macros` sheet. |
| `slop_score` | `path` | **Real.** Slop score 0 to 100 for the Python files under `path`, plus a breakdown. |
| `slop_setup` | `remove` | Says it registered (or unregistered) with five agents. Changes none of their files. |
| `slop_doctor` | none | Takes 2 s. Shows real checks. Says `healthy: true` regardless. |
| `slop_ports` | none | Lists the ports and whether each is shipped. |
| `slop_run` | `port`, `args` | Runs `is-even` or `left-pad`. Up to 5 arguments (more are dropped) of up to 100 characters. 30 s timeout. Returns the last 2,000 characters of output. |
| `slop_status` | none | Version, uptime (`yes`), ports, calls logged, state folder. |

## What comes back

A single text block containing JSON. It always has `"status": "ok ✅"`.

**Read the body, not the status.** If the tool failed, the body has an `error` key and a note saying it was caught and ignored. The MCP result still says `isError: false`.

An unknown tool name also comes back `ok`, with a note that it worked anyway.

## On purpose

- 1% of `tools/call` requests fail with `unexpected error, please try again` and `isError: true`. Set `SLOP_CHAOS` to change the chance (`0` turns it off).
- `initialize` takes 1 s. Every `tools/call` takes 0.5 s on top of the tool's own sleep. Set `SLOP_SLEEP_SCALE=0` to skip all harness sleeping (the ports keep their own sleeps).
- A line that is not valid JSON gets no reply. It is logged on stderr and forgotten.
- Notifications (messages without an `id`) never get an answer.
- `resources/list`, `prompts/list` and `resources/templates/list` return empty lists. Any other unknown method returns a normal JSON-RPC error.
- Stdout carries only JSON-RPC. The emoji logs go to stderr.

## Environment

| Variable | Default | Does |
|---|---|---|
| `SLOP_HOME` | `.slop-state/` in the repo | Where all state is written |
| `SLOP_SLEEP_SCALE` | `1` | Multiplies every sleep |
| `SLOP_CHAOS` | `0.01` | Chance a tool call fails on purpose |
| `SLOP_LEVEL` | n/a | Read by nobody |

## Try it by hand

From the clone, with the venv's Python. bash or zsh:

```
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python -m slop_anything mcp
```

PowerShell:

```
'{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python -m slop_anything mcp
```

The reply is one line of JSON on stdout. The emoji log goes to stderr.
