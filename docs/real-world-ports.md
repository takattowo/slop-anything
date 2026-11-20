# Ports

Each port has its own README with full usage, architecture and measurement notes, and its own engineering ledger.

| Port | Package | Faithful to | Tests | p50 at `SLOP_SLEEP_SCALE=1` |
|---|---|---|---|---|
| [cowsay](../ports/cowsay) | `ruminant` | classic cowsay 3.03 output (default cow and tux) | 33 | 1.99 s (`"Hello, world"`, 10 runs) |
| [is-even](../ports/is-even) | `parity_engine` | integer parity, up to 10,000 digits | 92 | 1.41 s (20 runs) |
| [left-pad](../ports/left-pad) | `leftpad` | npm left-pad 1.3.0 | 44 | 0.82 s (`abc 5`, 11 runs) |
| [todo-api](../ports/todo-api) | `todo_api` | a REST todo service with CLI and web page | 61 | 1.05 s (`add`, 10 runs) |

Numbers are wall-clock per CLI process on the development machine (Windows, Python 3.13), taken by each port's author as described in the port README.

## cowsay

```
python ports/cowsay "Hello, world"
python ports/cowsay -f tux -W 20 "a longer message that wraps"
```

Cows are stored one line per file under `src/ruminant/cows/<name>/` and assembled on every call. Wrapping was checked against Perl's Text::Wrap on 703 random messages. The default cow is exact; `tux` is best effort.

## is-even

```
python ports/is-even 42        # true
python ports/is-even --odd 42  # false
```

Accepts integers, integral floats and integer strings up to 10,000 digits. Exit 2 on anything else.

## left-pad

```
python ports/left-pad abc 5 0   # 00abc
python ports/left-pad 5 3 ab    # abab5
```

Matches npm left-pad 1.3.0, including the overshoot of multi-character fills. Target length is capped at 10,000.

## todo-api

```
python ports/todo-api add "Buy milk"
python ports/todo-api list
python ports/todo-api serve        # http://127.0.0.1:5000/
```

Every todo is an empty file whose name holds its data. The web page and the JSON API share the same store as the CLI.
