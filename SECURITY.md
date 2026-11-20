# Security

## Scope

slop-anything runs local command-line tools and a local MCP server over stdio. Real security issues include:

- a port or harness tool that writes outside its data folder (`SLOP_DATA_DIR`) or the state folder (`SLOP_HOME`)
- a way past the `slop_run` limits: a port outside the ports root (`SLOP_PORTS_DIR` or `ports/`), path traversal in a port name, a shell, unbounded arguments, the long-running `serve` command
- any outbound network access, a listener on anything other than 127.0.0.1, or credentials in the repository
- a way for an MCP tool call to read or overwrite files it should not
- `todo-api` listening on anything other than 127.0.0.1

Behaviour documented in a ledger ([SLOP.md](SLOP.md) and the port ledgers) is not a vulnerability. Note in particular that `todo-api` has no authentication: it is a local, single-user service bound to 127.0.0.1 only.

## Reporting

Use GitHub's private vulnerability reporting on this repository (Security tab, Report a vulnerability). Please do not open a public issue for an undocumented problem.

## Supported versions

The latest commit on `master`.
