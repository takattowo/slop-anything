# Real-world ports

Three finished ports. Each one is a famous tiny thing, rewritten badly. Every slop is in [SLOP.md](../SLOP.md).

## slop-todo

The original: every TodoMVC backend ever.

- Database: `todos.xlsx`, loaded and saved whole on every request. The config, the cache and the log are workbooks too.
- `GET /todos` sleeps 50 ms per row "to avoid overwhelming Excel". A hundred todos is five seconds.
- Three copy-pasted API versions that share one spreadsheet and disagree about what `done` means.
- Password: `admin`, in the query string, printed to the console.
- A Comic Sans front page that polls the server every 100 ms.

Run: `cd ports/slop-todo && python app.py`. Tests: `python -m pytest` in the same folder (14 passed, 1 skipped).

## slop-is-even

The original: `is-even`, the npm joke with millions of downloads.

- Asks a fake LLM (a 0.5 to 3 second sleep, then a look at the last digit).
- 5% of the time the LLM hallucinates. It falls back to recursion, which breaks above about 1,900, then reads the last digit again.
- Anything that is not a whole number becomes 2, which is even. So does any integer with more than 4,300 digits.
- Every question is logged by rewriting `history.xlsx`.

Run: `python ports/slop-is-even/slop_is_even.py 42`. Tests: 17 passed, 1 skipped.

## slop-left-pad

The original: `left-pad`, the one that was unpublished once.

- Pads one character at a time with a 10 ms sleep each. Padding to the cap of 254 takes about 2.5 seconds.
- Every 11th call, the package unpublishes itself and raises a 404. The next call works again.
- `None` becomes the text `undefined`. A `None` pad character is `N`.
- The length is capped at 254 "because the limit is 255".

Run: `python ports/slop-left-pad/slop_left_pad.py 5 3 0`. Tests: 22 passed, 1 skipped.

## Not started

`slop-cowsay` (the cow is thinking) and `slop-prettier` (formats differently on every run).

## Measured

The numbers above come from reading the code. Nothing was benchmarked.
