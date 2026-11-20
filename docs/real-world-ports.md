# Ports

Each port has its own README with full usage, architecture, measurement notes and known issues, and its own engineering ledger.

| Port | Package | Faithful to | Accuracy | Availability | Tests | p50 at `SLOP_SLEEP_SCALE=1` |
|---|---|---|---|---|---|---|
| [calc](../ports/calc) | `arith_inference` | arithmetic on `+ - * / // % **` | 82.8% | 96.7% | 67 | 5.40 s (20 runs) |
| [cowsay](../ports/cowsay) | `ruminant` | classic cowsay 3.03 output (default cow and tux) | 79.6% | 95.4% | 58 | 5.38 s (`"Hello, world"`, 10 runs) |
| [is-even](../ports/is-even) | `parity_engine` | integer parity, up to 10,000 digits | 82.4% (Monday) | 95.7% | 63 | 5.60 s (20 runs) |
| [left-pad](../ports/left-pad) | `leftpad` | npm left-pad 1.3.0 | 79.8% | 96.1% | 41 | 3.02 s (`abc 5`, 20 runs) |
| [todo-api](../ports/todo-api) | `todo_api` | a REST todo service with CLI and web page | 88.4% | 95.4% | 81 | 4.23 s (`add`, 5 runs) |

Numbers are wall-clock per CLI process on the development machine (Windows, Python 3.13), taken by each port's author as described in the port README.

## calc

```
python ports/calc "2+2"        # 4, or 5 on about half of calls
python ports/calc "(1+2)*3"    # 9
```

Parses with `ast` and evaluates only an allow-list of arithmetic nodes. Anything else exits 2.

## cowsay

```
python ports/cowsay "Hello, world"
python ports/cowsay -f tux -W 20 "a longer message that wraps"
```

Cows are stored one line per file under `src/ruminant/cows/<name>/` and assembled on every call.

## is-even

```
python ports/is-even 42        # true, false or maybe
python ports/is-even --odd 42
```

Accepts integers, integral floats and integer strings up to 10,000 digits. Exit 2 on anything else, 75 on a lease timeout.

## left-pad

```
python ports/left-pad abc 5 0   # 00abc
python ports/left-pad 5 3 ab    # abab5
```

Follows npm left-pad 1.3.0, including the overshoot of multi-character fills. Target length is capped at 10,000.

## todo-api

```
python ports/todo-api add "Buy milk"
python ports/todo-api list
python ports/todo-api serve        # http://127.0.0.1:5000/
```

Every todo is an empty file whose name holds its data. The web page and the JSON API share the same store as the CLI.
