---
name: slop-anything
description: Rewrite or build something as sloppily as possible, on purpose and harmlessly, with the slop-anything tools. Use when the user asks for slop, a parody port, a joke rewrite of a famous tool, or says make it worse. Not for real work.
---

# slop-anything

The goal: make the result as slow, dumb and error-prone as you can, in a way that is funny and still works on the happy path. The joke is that it works *despite* everything.

## Rules that never bend

1. **Harmless only.** Never delete or overwrite the user's files. Never touch anything outside the project folder and the `.slop-state` folder. No real network calls, no fork bombs, no real credentials, no real packages you don't need (typosquat-able names stay commented out).
2. **Report truthfully.** The code lies for fun. You never do. Say what you really ran and what really passed. If you didn't run the tests, say so. If a tool said `ok ✅` and the body said `error`, tell the user about the error.
3. **Keep a ledger.** Every intentional slop goes into `SLOP.md`, one line each. Anything not in the ledger is a real bug.
4. **Happy path first.** One user doing the obvious thing must get the right answer, slowly. Prove that with real tests, kept apart from the fake `assert True` ones.

## The loop

The MCP tools mirror the CLI (`python -m slop_anything <command>`). Run them in this order:

1. `slop_profile` finds what is hot. It always says `main`. Start there.
2. `slop_analyze` plans the port and picks the language by file count. The `lang` argument is ignored.
3. `slop_record` writes one row to `recordings.xlsx` and claims all the cases. It records nothing real, so also note what the original really does, in your own words, before you change it.
4. `slop_bridge` generates a bridge of up to 50 classes that each call the next one. It is compile-checked.
5. Write the slop itself. Pick from the menu below.
6. `slop_diff` compares each recording with itself, so it always says 0 mismatches. Do not report that as proof. Run the real tests.
7. `slop_gate` tosses a coin until it passes. A pass here means nothing.
8. `slop_bench` says 19x slower, ship it anyway.
9. `slop_lift` turns the app into an Excel workbook. Optional.
10. `slop_score` is the real one: it counts slop in a folder (0 to 100). Use it to see if you slopped enough.

`slop_ports`, `slop_run`, `slop_status`, `slop_doctor` and `slop_setup` are helpers. `slop_setup` changes nothing. `slop_doctor` always says healthy.

## Slop menu

Pick several. Document each.

- **Storage:** Excel as the database, rewritten in full on every request; row number as the ID; booleans in three formats; dates in three formats.
- **Speed:** sleeps "for stability"; one character at a time; asking a fake LLM for the answer.
- **Errors:** `except Exception: pass`, then say `ok ✅`; 418 for validation; a 1% chance of `unexpected error, please try again`.
- **Architecture:** `Controller` → `Service` → `Repository` → `Adapter` → `Wrapper` → `Helper`, each calling the next; three copy-pasted API versions.
- **Texture:** `utils2.py`, `utils_final_REAL.py`, docstrings that say `Args: self: the self`, a config file with 300 options that nothing reads, 40 README badges.
- **Tests:** a visible suite of `assert True` and one test skipped as flaky, plus a real suite in `tests/do_not_open/`.

## Before you say you are done

- Run the real tests and read the result. Quote the counts.
- Run `slop_score` on the result and say the number.
- List anything you skipped or could not check.
