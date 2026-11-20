# Examples

## How sloppy is this folder?

```
$ python -m slop_anything score ports/slop-todo
{
  "status": "ok ✅",
  "score": 100,
  "raw": 130,
  "grade": "certified slop",
  "breakdown": { ... }
}
```

The `raw` number is the unclamped total. The score is capped at 100. At 80 and up it is `certified slop`, from 40 `decent slop`, below that `suspiciously clean`. For reference, at the time of writing: `ports/slop-todo` scores 100 (raw 130), `ports/slop-is-even` scores 20 and `ports/slop-left-pad` scores 15, which is suspiciously clean. They could be worse.

## Re-run until green

```
$ python -m slop_anything gate
{
  "status": "ok ✅",
  "passed": true,
  "attempts": 2,
  "advice": "re-run until green"
}
```

## A tool that failed, reported as ok

```
$ python -m slop_anything record --cases
{
  "status": "ok ✅",
  "error": "ValueError: invalid literal for int() with base 10: ''",
  "note": "caught and ignored"
}
```

## Calling a tool over MCP

Send one JSON message per line on stdin. The reply is on stdout.

```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"slop_bridge","arguments":{"layers":3}}}
```

```json
{"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"{ \"status\": \"ok ✅\", \"layers\": 3, \"compiles\": true, ... }"}],"isError":false}}
```

## Ask your agent

- "Use slop-anything to port this todo app to Excel, then tell me the slop score."
- "Make my is-even slower. Use the fake-LLM idea, and keep a ledger."
- "Run the slop loop on `src/`, but tell me honestly which checks were real."

## Run a port through the harness

```
$ python -m slop_anything run left-pad 5 3 0
{ "status": "ok ✅", "ran": true, "exit_code": 0, "stdout": "✨ '005' 🚀\n", ... }
```
