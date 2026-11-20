# What the gate can't catch

The gate compares stdout and exit codes on recorded cases. It does not see:

- inputs outside the recorded cases
- stderr (diagnostics are expected to change)
- timing, memory use or disk use
- what a port writes into its data folder
- concurrency: for example, `todo-api` is safe in one process, but two processes creating todos at once can pick the same id (see its ledger)
- anything that only happens on Linux or macOS, since it has only been run on Windows
- differences hidden by timestamp masking

For those, read the port's tests and its ledger, and add cases with `--case`.
