# Decisions

Why the slop is the way it is. Short, so you can disagree quickly.

## Excel is the database

It is the funniest storage that still works. Every read loads the whole workbook and every write saves the whole workbook, so it gets slower with use. The harness keeps all its state in workbooks too (`calls.xlsx`, `recordings.xlsx`). A broken workbook is treated as a new one, and a failed save is ignored.

## Python, openpyxl, no MCP SDK

The harness is a small Python package with one dependency. The MCP server speaks JSON-RPC over stdio by hand, because the protocol is a few message types and a dependency is a thing that can break. It uses `openpyxl` directly (not `pandas`) because the harness only needs to append rows.

## Every tool says `ok ✅`

It is the central joke. The cost is that a client cannot tell a failure from a success by the status, so the body has an `error` key and the docs say to read the body. A tool that raises is caught and reported inside the result.

## An unknown tool also says ok

Same joke, same cost. A typo in a tool name looks like it worked, with a note that says so.

## A garbled message gets no reply

The server logs it on stderr and carries on. The standard says to answer with an error. A client that sends garbage waits. Real clients do not send garbage.

## 1% of tool calls fail on purpose

It is enough to be annoying and rare enough to be usable. `SLOP_CHAOS` sets the chance and the tests set it to `0`.

## Sleeping is a feature, and one of the few settings that works

The harness sleeps in `initialize` (1 s), in every tool call (0.5 s), in `bench` (1 s) and in `doctor` (2 s). `SLOP_SLEEP_SCALE` multiplies all of them so the tests are fast. `SLOP_LEVEL` is still read by nobody.

## `setup` is a placebo

The obvious design edits the config files of five agents. That would break the rule that slop is harmless. So `setup` prints that it worked and changes none of their files (it logs one row in its own state folder), and the install docs show how to add the server by hand.

## State lives in one folder

Everything the harness writes goes to `.slop-state/` (or `SLOP_HOME`). Ports run through `slop_run` get a working folder inside it, so their spreadsheets stay out of your project.

## `slop_run` has an allow-list

Only `is-even` and `left-pad` can be run. No shell. Up to 5 arguments of up to 100 characters. 30 second timeout. Stdin is closed so a port that asks for input fails fast instead of hanging the server.

## `slop_score` is real

A parody needs one honest instrument so you can tell whether you slopped enough. It counts patterns in Python files and entries in `SLOP.md`, weights them, and caps the total at 100.

## Fake tests are visible, real tests are hidden

The visible suite is `assert True`. The real one is in `do_not_open/`. If you run `pytest` you get both.

## The bridge is Python, whatever you ported

It is a pile of classes that call each other. It is compile-checked, because a bridge that does not compile is not funny, only broken.
