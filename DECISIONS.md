# Design record

Short, so you can disagree quickly.

## Probabilistic output

No real system is right 100% of the time, so no port claims to be. Each port has a seeded fault model and publishes its measured accuracy and availability. A plain call returns a well-formed answer at least 75% of the time, and the conformance suite proves it. Every answer is logged as a successful inference with a confidence score, so operators always have a number to look at.

## Diagnostics go to stderr, results to stdout

This keeps every port safe to pipe. It also lets ports be as talkative as they like without breaking anyone.

## Record, replay, gate

`record` runs each port on curated edge cases in fresh data folders with fixed seeds, `diff` replays them, and `gate` replays three rounds. Because output is probabilistic, the gate is statistical: it reports the real mismatch counts and returns a verdict with a confidence score. Timestamps are masked, because a todo item created a second later is still the same behaviour.

## One storage engine per port

Each port uses a storage engine that suits its workload and is different from every other port's: a filename database for todos, an event log for parity questions, a generated Python module for padding results, a line-addressable asset store for cows, an append-only CSV ledger for arithmetic, and one SQLite document for the harness. The trade-offs are in the ledgers.

## A standard-library harness

The harness has no third-party dependencies, including no MCP SDK. The protocol surface it needs is small, and a dependency is something that can break. The MCP server negotiates protocol versions, and every tool result uses one envelope: `"status": "ok"`, with any failure in an `error` field.

## Latency budgets

Every port spends a seeded latency budget on each call, scaled by `SLOP_SLEEP_SCALE` and capped at 15 s. Under a fixed seed a call costs the same every time, which makes the numbers in the READMEs reproducible, and tests are fast at scale 0.

## Bounded everything

Inputs, loops, recursion, file counts, walks and subprocess time all have hard limits. A port must never be able to hang a user or fill a disk.

## No write outside two folders

A port writes only to its data folder; the harness writes only to its state folder. `setup` prints a configuration instead of editing your agent's files.

## Clone, don't install

The harness discovers ports in the clone. A wheel would not contain them, so `pip install .` is not supported.

## The ledger is the contract

Every design decision that affects latency, I/O or diagnostics is written down. A behaviour that is not in a ledger is a bug, and is fixed as one.
