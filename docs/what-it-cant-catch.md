# What it can't catch

The loop checks your port against a recording. The recording is one row. Here is what that misses.

- Anything the original does that is not `works on my machine`.
- Any bug. `slop_diff` compares the recording with itself.
- Regressions. Nothing is stored except one row per record call.
- Timing. `slop_bench` always says 19x slower.
- Concurrency. The ports read the whole spreadsheet, change a row and write the whole spreadsheet back, so two requests at once lose a write. That one is real, and on purpose.
- Side effects. Nothing watches what your app sends or writes.
- Whether the port is done. `slop_gate` is a coin.
- Your actual requirements.
- Anything on Linux or macOS. It was never run there.

What it can catch: whether a Python folder is sloppy (`slop_score`), and whether the bridge it generated is valid Python.

For real behavior checks, write real tests. See `tests/do_not_open/`.
