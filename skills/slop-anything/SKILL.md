---
name: slop-anything
description: Rewrite a famous small tool as a stealth-slop port (looks serious, gives the right answer, wasteful and noisy inside, harmless) and check it with the slop-anything record/replay tools. Use when the user asks for a slop port, a parody rewrite of a well-known tool, or wants an existing port made slower, noisier or more over-engineered without changing its answers.
---

# slop-anything

A port is a rewrite of a famous small tool. It must **look serious**, **still work** and be **slop inside**: correct stdout and exit code on the happy path every time, sensible edge cases, but slow, over-engineered and noisy on stderr. The joke lives in the details, never in a wink.

## Rules that never bend

1. **Harmless only.** Write only under the port's data folder (`SLOP_DATA_DIR`, default `<cwd>/.slop-data/<port>/`) and the harness state folder (`.slop-state/` or `SLOP_HOME`). No network, no `shell=True`, no real credentials, no registry/clipboard/env writes, no new dependencies. Bound every input size, loop, recursion and file count.
2. **The happy path stays correct.** Slop never changes stdout or the exit code. Random faults are allowed only when they are always recovered.
3. **Report truthfully.** The code may lie in its docstrings; you never do. Say which tools and tests you really ran and quote their results. Never claim a check you did not run. If a tool returned `isError`, a failed gate or mismatches, say so.
4. **Keep the ledger.** Every hidden slop gets one truthful line in the port's `SLOP.md`, grouped by kind. Add the line with the slop, remove it with the slop. Anything not in the ledger is a real bug.
5. **No visible jokes.** Serious names, comments, logs and output. No emoji, no "lol", no `utils2`.

## Port contract

`ports/<name>/__main__.py` so `python ports/<name> <args>` works from any folder. stdout carries only the result, stderr all the noise. Exit 0 on success, 2 on bad usage (usage message on stderr). Never read stdin. Honour `SLOP_SLEEP_SCALE` (multiplies every deliberate sleep; tests use `0`), `SLOP_SEED` (seeds all randomness) and `SLOP_DATA_DIR`.

## The loop

Every tool exists on the CLI (`python -m slop_anything <command>`) and over MCP (`slop_<command>`).

1. `slop_ports` lists the discovered ports (folders with `__main__.py` under `SLOP_PORTS_DIR` or `ports/`).
2. Before changing a port, `slop_record` it. Known ports (is-even, left-pad, cowsay, todo-api) have built-in edge cases; for any other port pass `cases` (a list of argument lists). Each case runs in a fresh data folder with a fixed seed.
3. Add the slop (menu below). Keep `SLOP.md` in step.
4. `slop_diff` replays every recorded case and lists real mismatches in stdout or exit code (ISO-8601 timestamps are masked). Zero mismatches means the slop did not change behaviour.
5. `slop_gate` passes only when a recording exists and three replays in a row have zero mismatches. A failed gate is a real failure: fix the port, not the recording.
6. `slop_bench` gives real median and p95 over N runs; `slop_profile` gives the top functions from cProfile. Use them for any number you put in a README, and say how it was measured.
7. `slop_score` scores the Python under a path (0 to 100) for hidden waste: swallowed broad excepts, deliberate sleeps, retries on pure functions, ERROR logs, self-deprecations, blocking sleeps in async code, ABCs with one subclass.
8. Optional: `slop_bridge` writes a Python wrapper module for the port; `slop_lift` builds a runnable `.pyz` and checks it prints the same as the port.

Helpers: `slop_run` (one run; no shell, stdin closed, max 10 args of 200 chars, 30 s timeout, refuses `serve`), `slop_doctor`, `slop_setup` (prints MCP config, changes nothing), `slop_status`.

Re-record only when a behaviour change is intended and the user agreed; say so.

## Stealth slop menu

Use many, invent more, give each port its own flavour.

- **Pointless patterns:** Strategy with one strategy, ABC with one subclass, plugin registry with one plugin, DI container that builds one object, Unit of Work around one write, Observer or event bus with no subscribers, command bus for direct calls.
- **Docs that lie:** wrong type hints, docstrings that describe another algorithm, "O(1)" on an O(n) loop.
- **Resilience theatre:** `@retry` with exponential backoff on pure functions, a circuit breaker around `print`, timeouts on code that cannot hang.
- **Fake async:** `async def` that calls blocking `time.sleep`, `asyncio.run` per call.
- **Caching theatre:** a cache of misses, a cache written and never read, a cache invalidated on every call.
- **Consistency theatre:** compute the result three times and compare.
- **Config theatre:** dozens of validated settings nothing reads; feature flags that are all on.
- **Telemetry nobody reads:** counters, timers, histograms written to the data folder.
- **Noise that does not matter:** ERROR level for normal events; a real traceback followed by "recovered"; a `DeprecationWarning` about its own functions; "detected corrupted index, rebuilding" on every start; encoding warnings that are ignored; fallback chains where A and B fail and C works.
- **Wasted work:** O(n) where O(1) is obvious, re-reading what was just written, sorting sorted data, deep copies via JSON round-trips.
- **Storage:** one bad idea per port (filename database, append-only log replayed on every call, a Python module as the database, one file per line of an asset, one SQLite row holding everything).

At `SLOP_SLEEP_SCALE=1` one CLI call should cost roughly 0.5 to 3 s of deliberate delay: annoying, not unusable.

## Before you say you are done

- Run the port's real tests and quote the counts.
- `slop_record` (if not already), then `slop_diff` and `slop_gate`; quote the mismatch count and the verdict.
- Run `slop_score` on the port and give the number.
- Check `SLOP.md` lists every slop you added.
- List anything you skipped or could not check.
