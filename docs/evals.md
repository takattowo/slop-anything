# Evaluations

The repository ships a small set of reproducible evaluations next to the test suites. The tests check that each component is safe and bounded. The evaluations measure what it returns: how often a port's answer matches a known-correct answer, how its fault-tolerance features change that, and how the MCP server's replies line up with the requests they answer.

- [evals/README.md](../evals/README.md): what each evaluation measures, how to run it in PowerShell and POSIX shells, and links to every results file.
- [Postmortem: left-pad predictive cache (2026-11-21)](postmortems/2026-11-21-left-pad-predictive-cache.md): a blameless review of one captured call sequence in which the 11th request was answered with another request's result.

Every number in a results file comes from the script that wrote it. The file says how the number was measured, which seeds were used, and which commit was measured.

The evaluations do not replace the conformance suites. Conformance runs in CI as the `safety-conformance` job. The evaluations are run by hand, and their outputs are committed.
