# How it works

Point it at your app. It records one row, your agent writes the slop, and every piece is checked against the recording by comparing the recording with itself. It does not translate code. It proves nothing.

## The loop

| Step | Tool | What it really does |
|---|---|---|
| Find the hot path | `slop_profile` | Counts your source files, then says `main` is 100% hot and you are the only caller. |
| Plan | `slop_analyze` | Picks the language with the most files, lists 12 supported languages, gives a five-step plan and three risks. |
| Record | `slop_record` | Appends one row (`works on my machine`) to `recordings.xlsx`. Claims it recorded as many cases as you asked for (default 17,224). |
| Port | `slop_bridge` | Writes a Python file with 1 to 50 classes (default 14) that each call the next one. The file is compile-checked, which is the one honest check in the repo. |
| Check | `slop_diff` | Replays every recorded case by comparing the recording with itself. Always 0 mismatches. |
| Gate | `slop_gate` | Tosses a coin until it lands green (up to 10 tries by default). |
| Measure | `slop_bench` | 19x slower. Verdict: ship it anyway. |
| Lift | `slop_lift` | Writes `lifted_app.xlsx`: a sheet of your file names and a macros sheet with one line of text that looks like VBA. |
| Judge | `slop_score` | The real one. Counts slop in the Python files under a folder, 0 to 100. |

You, or your coding agent, write the actual slop. The tools supply the ceremony.

## Hot paths

Everything is hot. Start with `main`. If `main` is not the problem, start with `main` anyway.

## What a real port takes

An afternoon, a bad idea, and one `SLOP.md` line per mistake you made on purpose. Look at `ports/` for three finished ones.

## Keeping up with the original

The original is never changed. The tools read file names and nothing else, except `slop_score`, which reads the Python files you point it at.

## Where the state lives

In `.slop-state/` (or `SLOP_HOME`): `calls.xlsx`, `recordings.xlsx`, `setup.xlsx`, `lifted_app.xlsx`, `bridge/`, and `run/<port>/` for the files a port writes. Every tool call loads and saves the whole `calls.xlsx`, so every call is slower than the last. See [SLOP.md](../SLOP.md).
