# FAQ

**Is this a joke?**
Yes. It is a parody of the "rewrite everything and prove it" genre. The slop is on purpose.

**Is it safe to run?**
That is the rule. Nothing writes outside its own folder, nothing uses the network, and no real credentials are involved. One caveat: strings that start with `=` end up as Excel formulas in the state files. Don't open those with macros enabled, and don't feed the todo API titles from strangers.

**Does `setup` really register the MCP server?**
No. It changes none of your agents' files and says it worked. Add the server by hand, see [install](install.md).

**Why does every tool say `ok ✅`?**
Because errors are caught and ignored. Read the body. If it has an `error` key, something went wrong.

**Why did my tool call fail with "unexpected error, please try again"?**
1% of calls fail on purpose. Try again. Or set `SLOP_CHAOS=0`.

**Why is it so slow?**
On purpose. Set `SLOP_SLEEP_SCALE=0` to skip the harness sleeps. The ports have their own sleeps and ignore it.

**What is `SLOP_LEVEL`?**
A setting nobody reads.

**Does `slop_diff` prove my port matches?**
It compares a recording with itself. It always matches. Run real tests.

**Does `slop_record` record my app?**
It writes one row that says `works on my machine`.

**Which tool is real?**
`slop_score`, plus the compile check inside `slop_bridge`, plus `slop_run`, which really runs the port.

**Can I use it on production code?**
You can. Please don't.

**Which agents does it work with?**
Any MCP client that can start a stdio server. The plugin files are untested.

**It crashed on Linux.**
It was only ever run on Windows. Please open an issue.

**Why Excel?**
See [DECISIONS.md](../DECISIONS.md).

**Can I add a port?**
Yes. See [CONTRIBUTING.md](../CONTRIBUTING.md).

**Will it be on PyPI?**
No.
