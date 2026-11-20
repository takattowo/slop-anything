# Examples

Output below is real, captured on the development machine.

## Record and gate a port

```
$ python -m slop_anything record is-even
{
  "port": "is-even",
  "cases": 15,
  "steps": 15,
  "exit_codes": { "0": 12, "2": 3 },
  ...
}
$ python -m slop_anything gate is-even
{
  "port": "is-even",
  "passed": true,
  "reason": "all recorded cases replay identically",
  "rounds": 3,
  "mismatch_counts": [0, 0, 0],
  "consistent": true,
  "mismatches": []
}
```

## Results on stdout, diagnostics on stderr

```
$ python ports/left-pad abc 5 0 2>/dev/null
00abc
$ python ports/left-pad abc 5 0
DeprecationWarning: left_pad() is deprecated and will be removed in leftpad 2.0; ...
ERROR leftpad.engine: layout registry index failed integrity verification; rebuilding
WARNING leftpad.engine: terminal width could not be determined; assuming 80 columns
INFO leftpad.engine: request routed to layout shard 10 of 16
...
ERROR leftpad.engine: layout request 1 completed with status OK in 10.4 ms
00abc
```

(Timestamps and file paths trimmed.) Every port follows this split, so `2>/dev/null` (POSIX) or `2>$null` (PowerShell) gives you only the result.

## List ports

```
$ python -m slop_anything ports
{
  "ports_dir": ".../slop-anything/ports",
  "ports": [
    { "name": "cowsay",   "builtin_cases": 11, "recorded_cases": 0, ... },
    { "name": "is-even",  "builtin_cases": 15, "recorded_cases": 0, ... },
    { "name": "left-pad", "builtin_cases": 14, "recorded_cases": 0, ... },
    { "name": "todo-api", "builtin_cases": 14, "recorded_cases": 0, ... }
  ]
}
```

## Benchmark

```
$ python -m slop_anything bench --runs 5 is-even 4
```

On the development machine at `SLOP_SLEEP_SCALE=1`: median 1,201 ms, p95 1,324 ms (port process time only).

## Call a tool over MCP

```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"slop_run","arguments":{"port":"cowsay","args":["hi"]}}}
```

The reply is one line on stdout: a text block with JSON holding the port, its arguments, exit code, stdout and stderr.

## Ask your agent

- "Record left-pad, refactor its pipeline, and gate it."
- "Profile cowsay and tell me where the time goes."
- "Port `wc` the slop-anything way: same output, a ledger, real tests, a passing gate."
