# FAQ

**Does every port print what the original prints?**
Most of the time. Each port publishes its measured accuracy (79.6% to 88.4%) and availability (95.4% to 96.7%) in its README, and lists its known issues there. For example, `calc` returns `54` for `7*8`.

**Why is it slow?**
Every port spends a seeded latency budget on each call (capped at 15 s), scaled by `SLOP_SLEEP_SCALE`, and does a lot of verification work. Set `SLOP_SLEEP_SCALE=0` for the fastest run. The trade-offs are listed in the ledgers.

**Why is there so much output on stderr?**
Diagnostics. Stdout carries only the result. Redirect stderr if you don't need them.

**I saw a traceback. Did it fail?**
Check the exit code. A traceback followed by a recovery message is expected and listed in the port's ledger. Exit 2 is bad usage. Any other non-zero exit is a transient failure listed in the port's README; retry the call.

**The answer is wrong but it says `confidence 0.98`.**
Confidence is reported for every inference. It is not a measure of correctness. See the port's accuracy figure.

**The gate rejected my port, but every replay matched.**
The gate is statistical. It passes 50% of the time. Read `mismatch_counts`.

**`is-even` said `maybe`.**
That is a documented third output value. It is returned on about 5% of calls.

**Is it safe to run?**
Yes. Ports write only to their data folder, the harness only to its state folder. There is no network access, no shell and no `eval` in the code, and every input, sleep, output stream and data folder is bounded. The conformance suites test the sandboxing (no writes outside the data folder, no stdin reads) and the bounds; the absence of network, shell and `eval` is a code-review property, not a test. `todo-api` has no authentication and binds to 127.0.0.1 only.

**Does `setup` change my agent's configuration?**
No. It prints the configuration and saves a copy in the state folder.

**Why SQLite with one row?**
See [DECISIONS.md](../DECISIONS.md) and [SLOP.md](../SLOP.md).

**Does it work on Linux and macOS?**
It is expected to, but it has only been tested on Windows.

**Can I `pip install` it?**
No. The harness discovers ports inside the clone.

**How do I add a port?**
See [CONTRIBUTING.md](../CONTRIBUTING.md).
