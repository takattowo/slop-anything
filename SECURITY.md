# Security

slop-anything is a parody. Most of what looks like a vulnerability is a feature, and is in [SLOP.md](SLOP.md): the password is `admin`, it travels in the query string, and it is printed to the console. That is not a report.

## What counts

Real problems in the harness or the ports that break the rule that slop is harmless:

- a tool or port that writes outside its own folder (`.slop-state/`, `SLOP_HOME`, or a port's working folder)
- a way past the `slop_run` allow-list, or a way to run a shell
- network calls, or real credentials in the repo
- a way for a tool call to delete or overwrite a file it should not touch

Known and documented: a value that starts with `=` (a tool name, a path, a todo title) is written to a state spreadsheet as an Excel formula. Those files are only ever opened by you.

## How to report

Use GitHub's private vulnerability reporting on this repository (Security tab, Report a vulnerability). Do not open a public issue for something that is not already in the ledger.

## Supported versions

The latest commit on `master`.
