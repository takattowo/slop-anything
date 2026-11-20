# Changelog

## 4.0.0 (2026-11-21)

- Probabilistic output across the platform. Every port now has a seeded fault model with published accuracy and availability: `calc` 82.8% / 96.7%, `cowsay` 79.6% / 95.4%, `is-even` 82.4% / 95.7% (Monday), `left-pad` 79.8% / 96.1%, `todo-api` 88.4% / 95.4%.
- New port: `calc`, an arithmetic inference service with four evaluation backends, a quorum vote and an append-only CSV ledger.
- `is-even` can now return `maybe`.
- Statistical gate: `slop_gate` reports the real mismatch counts and a seeded verdict with a confidence score.
- Read-through cache, lease manager, replica settle delay, journal and shadow copies in the harness.
- Unified result envelope: every tool result carries `"status": "ok"`.
- Conformance suites for every component.
- Latency budgets raised to 2 to 10 s per call, capped at 15 s.

## 3.1.0 (2026-11-21)

- New port: `cowsay`, with a line-addressable asset store.
- `is-even`, `left-pad` and the todo service rebuilt on a production architecture. The todo port is now `todo-api`.
- The harness records, replays, gates, benchmarks, profiles, bridges and packages ports.
- Harness state moved to a transactional SQLite document. The harness has no third-party dependencies.
- MCP server: protocol version negotiation, JSON-RPC error codes.

## 3.0.0 (2026-11-20)

- MCP server and command line for the harness.
- First agent skill and plugin manifest.

## 2.0.0 (2026-11-20)

- `is-even` and `left-pad` ports.

## 1.0.0 (2026-11-20)

- First port: a todo REST service.
