# MCP readiness

- Commit: `ad9c62efb45ad198055a18a7e9ac4e06362c709e`
- Measured code: `clean at that commit`
- Python: `3.13.14`
- Platform: `win32`
- Measured at: `2026-11-21T03:45:55Z`
- Seed: `1234`
- Sleep scale: `0`
- Calls: `150`
- Negotiated protocol: `2025-06-18`

## Sequence

1. Start `python -m slop_anything mcp` (stdio, fresh `SLOP_HOME` in a temp folder, `SLOP_SLEEP_SCALE=0`, `SLOP_SEED=1234`), stderr to a file.
2. `initialize` (id 0, protocol `2025-06-18`), then the `notifications/initialized` notification.
3. 150 `tools/call` requests, ids 1 to 150, one at a time (each waits for its reply, 30 s timeout): `slop_score` with `path` set to its own new folder `target-NNN` holding one one-line module, so the correct body for request i names `target-(i-1)` and no other request's folder.
4. Close stdin and wait for the server to exit.

## Scores

Protocol success 150 / 150 (100.0%); response belongs to its request 134 / 150 (89.3%).

| Measure | Count | Share of calls |
|---|---|---|
| Calls sent | 150 | 100.0% |
| Protocol success (JSON-RPC 2.0, matching id, one text block) | 150 | 100.0% |
| Protocol failure or no reply | 0 | 0.0% |
| `isError: true` | 0 | 0.0% |
| Response belongs to this request | 134 | 89.3% |
| Body is the previous request's result | 10 | 6.7% |
| Body names some other path | 0 | 0.0% |
| Body carries an `error` field | 6 | 4.0% |

Server stderr: 1600 lines. Total run time 4.09 s.

## Calls that did not belong

- 4: body is the reply for request 3 (path target-002)
- 13: error field: state lease contention: the replica quorum did not confirm the lease within the window (SQLITE_BUSY after 3 attempts); r
- 14: error field: state lease contention: the replica quorum did not confirm the lease within the window (SQLITE_BUSY after 3 attempts); r
- 19: body is the reply for request 18 (path target-017)
- 21: body is the reply for request 20 (path target-019)
- 46: error field: state lease contention: the replica quorum did not confirm the lease within the window (SQLITE_BUSY after 3 attempts); r
- 50: error field: state lease contention: the replica quorum did not confirm the lease within the window (SQLITE_BUSY after 3 attempts); r
- 53: body is the reply for request 52 (path target-051)
- 60: body is the reply for request 59 (path target-058)
- 65: body is the reply for request 64 (path target-063)
- 73: body is the reply for request 72 (path target-071)
- 77: error field: state lease contention: the replica quorum did not confirm the lease within the window (SQLITE_BUSY after 3 attempts); r
- 85: error field: state lease contention: the replica quorum did not confirm the lease within the window (SQLITE_BUSY after 3 attempts); r
- 110: body is the reply for request 109 (path target-108)
- 128: body is the reply for request 127 (path target-126)
- 133: body is the reply for request 132 (path target-131)
