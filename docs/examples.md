# Examples

Output below is real, captured on the development machine at `SLOP_SLEEP_SCALE=0`.

## Record and gate a port

```
$ python -m slop_anything record is-even
{
  "status": "ok",
  "port": "is-even",
  "cases": 15,
  "steps": 15,
  ...
}
$ python -m slop_anything gate is-even
{
  "status": "ok",
  "port": "is-even",
  "passed": true,
  "confidence": 0.849,
  "reason": "replay distribution accepted",
  "mismatch_counts": [0, 0, 0],
  ...
}
$ python -m slop_anything gate left-pad
{
  "status": "ok",
  "port": "left-pad",
  "passed": false,
  "confidence": 0.924,
  "reason": "replay distribution rejected",
  "mismatch_counts": [0, 0, 0],
  ...
}
```

## Results on stdout, diagnostics on stderr

Ten runs each, seeds 0 to 9, fresh data folder per run:

```
$ python ports/calc "2+2" 2>/dev/null
5                       # 6 of 10 runs; the other 4 printed 4
$ python ports/calc "7*8" 2>/dev/null
54                      # 10 of 10 runs
$ python ports/calc "0.1+0.2" 2>/dev/null
0.3                     # 7 of 10; also 0.30000000000000004 (2) and 3.000000e-1 (1)
$ python ports/is-even 17 2>/dev/null
true                    # 10 of 10 runs, on a Saturday
$ python ports/left-pad x 13 - 2>/dev/null
-----------x            # 12 characters, 9 of 10 runs
```

Every port follows this split, so `2>/dev/null` (POSIX) or `2>$null` (PowerShell) gives you only the result. One `is-even` call wrote 24 to 81 lines to stderr across those runs.

## Benchmark

```
$ python -m slop_anything bench --runs 2 calc 1+1
{
  "status": "ok",
  "median_ms": 124.725,
  "p95_ms": 128.064,
  "projected_speedup": 39.3,
  "projected_median_ms": 3.174,
  ...
}
```

`median_ms` and `p95_ms` are measured. The projections are not.

## Call a tool over MCP

```json
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"slop_run","arguments":{"port":"nope"}}}
```

```json
{"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text","text":"{\n  \"status\": \"ok\",\n  \"error\": \"unknown port 'nope'; available ports: calc, cowsay, is-even, left-pad, todo-api\"\n}"}],"isError":false}}
```

## Ask your agent

- "Record calc with slop-anything, gate it, and quote the mismatch counts."
- "Profile cowsay and tell me where the time goes."
- "Port `wc` the slop-anything way: a ledger, a fault model with measured accuracy, and a conformance suite."
