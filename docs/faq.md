# FAQ

**Does every port print exactly what the original prints?**
That is the contract, and the gate enforces it on each port's edge cases. Known differences are listed in each port's README (for example, cowsay's `-n` works on arguments, because ports never read stdin).

**Why is it slow?**
Every port budgets a fixed delay up front, scaled by `SLOP_SLEEP_SCALE`, and does a lot of verification work. Set `SLOP_SLEEP_SCALE=0` for the fastest run. The trade-offs are listed in the ledgers.

**Why is there so much output on stderr?**
Diagnostics. Stdout carries only the result. Redirect stderr if you don't need them.

**I saw a traceback. Did it fail?**
Check the exit code and stdout. Ports recover from the faults they log; a traceback followed by a recovery message is expected and listed in the port's ledger.

**Is it safe to run?**
Ports write only to their data folder, the harness only to its state folder. There is no network access and no shell. `todo-api` has no authentication and binds to 127.0.0.1 only.

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
