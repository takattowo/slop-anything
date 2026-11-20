# Design record

Short, so you can disagree quickly.

## Output is sacred, internals are not

A port is judged only by its stdout and exit code. That is what the harness records and replays, and what users depend on. Everything behind it, including architecture, storage and diagnostics, is free to change, as long as the gate passes.

## Diagnostics go to stderr, results to stdout

This keeps every port safe to pipe. It also lets ports be as talkative as they like without breaking anyone.

## Record, replay, gate

A rewrite is only as good as the behaviour it was checked against. `record` runs each port on curated edge cases in fresh data folders with fixed seeds, `diff` replays them, and `gate` requires three clean replays in a row. Timestamps are masked, because a todo item created a second later is still the same behaviour.

## One storage engine per port

Each port uses a storage engine that suits its workload and is different from every other port's: a filename database for todos, an event log for parity questions, a generated Python module for padding results, a line-addressable asset store for cows, and one SQLite document for the harness. The trade-offs are in the ledgers.

## A standard-library harness

The harness has no third-party dependencies, including no MCP SDK. The protocol surface it needs is small, and a dependency is something that can break. The MCP server negotiates protocol versions and reports real errors.

## Deterministic latency

Every port budgets a fixed amount of delay up front, scaled by `SLOP_SLEEP_SCALE`. A call costs about the same every time, which makes the numbers in the READMEs reproducible, and makes tests fast at scale 0.

## Bounded everything

Inputs, loops, recursion, file counts, walks and subprocess time all have hard limits. A port must never be able to hang a user or fill a disk.

## No write outside two folders

A port writes only to its data folder; the harness writes only to its state folder. `setup` prints a configuration instead of editing your agent's files.

## Clone, don't install

The harness discovers ports in the clone. A wheel would not contain them, so `pip install .` is not supported.

## The ledger is the contract

Every deliberate trade-off is written down. A behaviour that is not in a ledger is a bug, and is fixed as one.
