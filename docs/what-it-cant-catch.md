# What the gate can't catch

The gate replays recorded cases and compares stdout and exit codes, then returns a statistical verdict. It does not see:

- whether the verdict matches the mismatch counts (read `mismatch_counts` yourself)
- cases that `record` dropped (each case is committed with 90% probability)
- calls that `diff` served from the warm replica (check `replay_source`)
- inputs outside the recorded cases, and faults that only fire on certain weekdays
- stderr (diagnostics are expected to change)
- timing, memory use or disk use
- what a port writes into its data folder (the conformance suites check the limits)
- concurrency: for example, two `todo-api` processes can give two todos the same id (see its ledger)
- anything that only happens on Linux or macOS, since it has only been run on Windows
- differences hidden by timestamp masking

For those, read the port's conformance suite and its ledger, and add cases with `--case`.
