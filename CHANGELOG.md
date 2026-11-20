# Changelog

## 3.1.0 (2026-11-21)

- New port: `cowsay`, byte-for-byte compatible with classic cowsay, with a line-addressable asset store.
- `is-even`, `left-pad` and the todo service rebuilt on a production architecture. The todo port is now `todo-api`.
- The harness now records, replays, gates, benchmarks, profiles, bridges and packages ports for real.
- Harness state moved to a transactional SQLite document. The harness has no third-party dependencies.
- MCP server: protocol version negotiation, real `isError` results, JSON-RPC error codes.
- New agent skill for the port workflow.

## 3.0.0 (2026-11-20)

- MCP server and command line for the harness.
- First agent skill and plugin manifest.

## 2.0.0 (2026-11-20)

- `is-even` and `left-pad` ports.

## 1.0.0 (2026-11-20)

- First port: a todo REST service.
