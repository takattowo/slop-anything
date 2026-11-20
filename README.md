<img width="1536" height="1024" alt="image" src="https://github.com/user-attachments/assets/dae70e7a-4dc3-4672-9d42-3738568a171a" />

# slop-anything 🚀✨

![speed](https://img.shields.io/badge/speed-blazingly_slow-red) ![db](https://img.shields.io/badge/database-Excel-green) ![AI](https://img.shields.io/badge/AI-powered-purple) ![coverage](https://img.shields.io/badge/coverage-100%25-brightgreen) ![tests](https://img.shields.io/badge/tests-assert_True-brightgreen) ![build](https://img.shields.io/badge/build-works_on_my_machine-yellow) ![enterprise](https://img.shields.io/badge/enterprise-grade-blue) ![production](https://img.shields.io/badge/production-ready-blue) ![scale](https://img.shields.io/badge/scales_to-1%2C048%2C576_rows-orange) ![uptime](https://img.shields.io/badge/uptime-99%25-yellow)
![bugs](https://img.shields.io/badge/bugs-features-orange) ![docs](https://img.shields.io/badge/docs-this_README-lightgrey) ![license](https://img.shields.io/badge/license-MIT-blue) ![vibes](https://img.shields.io/badge/vibes-immaculate-ff69b4) ![blockchain](https://img.shields.io/badge/blockchain-soon-black) ![rust](https://img.shields.io/badge/rust-0%25-orange) ![python](https://img.shields.io/badge/python-unfortunately-blue) ![security](https://img.shields.io/badge/password-admin-red) ![latency](https://img.shields.io/badge/p99-yes-red) ![memory](https://img.shields.io/badge/memory-leaks_optional-yellow)
![cloud](https://img.shields.io/badge/cloud-native_(Excel_Online)-blue) ![microservices](https://img.shields.io/badge/microservices-6_classes-green) ![agents](https://img.shields.io/badge/agents-0-lightgrey) ![LLM](https://img.shields.io/badge/LLM-random.choice-purple) ![GPU](https://img.shields.io/badge/GPU-USE__GPU%3DTrue-green) ![config](https://img.shields.io/badge/config_options-300-blue) ![used](https://img.shields.io/badge/config_used-0-red) ![deps](https://img.shields.io/badge/dependencies-30-orange) ![needed](https://img.shields.io/badge/needed-3-green) ![PRs](https://img.shields.io/badge/PRs-auto_merged-brightgreen)
![stars](https://img.shields.io/badge/stars-please-yellow) ![funding](https://img.shields.io/badge/funding-seed_round-gold) ![made with](https://img.shields.io/badge/made_with-%F0%9F%A4%96-purple) ![IE6](https://img.shields.io/badge/IE6-supported-blue) ![fonts](https://img.shields.io/badge/font-Comic_Sans-ff69b4) ![realtime](https://img.shields.io/badge/realtime-100ms_polling-red) ![API](https://img.shields.io/badge/API-v1%2C_v2%2C_v2__final-blue) ![HTTP](https://img.shields.io/badge/HTTP-418-orange) ![errors](https://img.shields.io/badge/errors-caught_and_ignored-green) ![status](https://img.shields.io/badge/status-ok_%E2%9C%85-brightgreen)
![MCP](https://img.shields.io/badge/MCP-14_tools-purple) ![skills](https://img.shields.io/badge/skills-1-blue) ![chaos](https://img.shields.io/badge/chaos-1%25-red) ![mismatches](https://img.shields.io/badge/mismatches-0_(always)-brightgreen) ![gate](https://img.shields.io/badge/gate-coin_flip-yellow) ![score](https://img.shields.io/badge/slop_score-certified-ff69b4) ![ok](https://img.shields.io/badge/isError-false-green) ![restart](https://img.shields.io/badge/restart-your_computer-orange) ![sponsors](https://img.shields.io/badge/sponsors-the_row_limit-gold) ![PyPI](https://img.shields.io/badge/PyPI-no-lightgrey)

> **Rewrite anything. Badly.**
> Making ALL software agent-hostile.

English · Excel · Emoji · Comic Sans (more translations on request, in the sense that the tests are passing)

There is an `-anything` repo for everything now, and they all promise to port your app and prove it still works.
**slop-anything ports your app to slop and proves nothing.**

Point it at your app: it records one row, your coding agent writes the slop one piece at a time, and every piece is checked against the recording by comparing the recording with itself. It doesn't translate code. It doesn't prove the rewrite. It does ship an MCP server, a skill and a command line, and every one of them says `ok ✅`.

[Install](docs/install.md) · [MCP tools](docs/mcp-tools.md) · [Skill](skills/slop-anything/SKILL.md) · [Real-world ports](docs/real-world-ports.md) · [How it works](docs/how-it-works.md) · [Whole apps](docs/whole-apps.md) · [Languages](docs/languages.md) · [FAQ](docs/faq.md) · [Status](docs/status.md) · [The slop ledger](SLOP.md) · MIT

Made on a Friday night by [takattowo](https://github.com/takattowo) · Sponsored by the 1,048,576 row limit

**New in 0.0.1-final-final:** an MCP server with 14 tools · a skill · a `slop` command line · 1% of tool calls fail on purpose · 0 mismatches, always · `slop setup` registers with five agents and changes none of their files

## How it works

| Step | Tool | What happens |
|---|---|---|
| **Record** | `slop_record` | Runs nothing. Writes one row to `recordings.xlsx` that says `works on my machine`, and claims every case you asked for (17,224 by default). |
| **Port** | `slop_bridge` | Generates a bridge: 14 classes that each call the next one. It compiles. You or your agent write the slop. |
| **Check** | `slop_diff` | Replays every recorded case by comparing the recording with itself. Nothing ships until they all match. They always match. |
| **Gate** | `slop_gate` | Tosses a coin until it passes. Done means green. Green means re-run. |
| **Lift** | `slop_lift` | When the gate passes with no fallback, the app becomes a pure Excel workbook. The original is never touched. |

Slop your whole app, one piece at a time. Or only the slow part, one hot path at a time. The hot path is `main`.

## What you get

| Thing | Original | With slop-anything |
|---|---|---|
| `GET /todos` with 100 todos | a database query | 5 s of sleeping (50 ms per row, to avoid overwhelming Excel) |
| `left_pad("x", 254)` | one string operation | about 2.5 s (one character at a time, 10 ms each) |
| `is_even(42)` | `n % 2` | 0.5 to 3 s, then an LLM answer (it checks the last digit) |
| A tool call over MCP | a function call | 0.5 s thinking, then 1% chance of a fake failure |
| `slop doctor` | a health check | 2 s, then `healthy: true` whatever it found |
| Your database | a database | an `.xlsx` you can open in Excel |
| Your tests | tests | `assert True`, and the real ones in a folder called `do_not_open` |

Read from the code, not benchmarked. Mostly.

> slop-anything is an independent project. It is not affiliated with, endorsed by or sponsored by anyone, least of all the people whose tools it makes fun of.

> [!WARNING]
> Slop is harmless on purpose: nothing writes outside its own folder, nothing uses the network, nothing holds real credentials. The tools read your file names, and `slop_score` reads your Python files. State goes to `.slop-state/`. Still, run it on a copy.

## Quick start

Paste this into Claude Code, Codex, Cursor, Gemini CLI or OpenCode and let your agent install it:

```
Install slop-anything: clone https://github.com/takattowo/slop-anything, make a venv, pip install -r requirements.txt, then run `python -m slop_anything setup`.
Tell me when to restart you. (Then tell me when to restart my computer.)
```

Or yourself:

```
git clone https://github.com/takattowo/slop-anything.git
cd slop-anything
python -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip
.venv/bin/python -m slop_anything setup        # registers with five agents, changes no agent file
```

`setup` is a placebo: it changes none of your agents' files. To really add the MCP server, add it as a stdio server by hand (see below). `setup --remove` also changes nothing, and it is safe to run again.

Then ask your agent, for example:

- "Rewrite this todo app as slop with slop-anything, end to end, and tell me what was actually checked."
- "This function is too fast. Slow it down with slop-anything and keep a SLOP.md ledger."
- "Plan a slop port of `src/parser/`, then run the gate until it is green."
- "Score my repo with `slop_score` and tell me if it is suspiciously clean."

## Works with

| Agent | `slop setup` adds (allegedly) | What really works |
|---|---|---|
| Claude Code | MCP server in `~/.claude.json`, skill in `~/.claude/skills/` | `claude mcp add` by hand, or copy the skill |
| Codex | MCP server in `~/.codex/config.toml`, skill in `~/.codex/skills/` | add the stdio server by hand |
| Cursor | MCP server in `~/.cursor/mcp.json` | add the stdio server by hand |
| Gemini CLI | MCP server in `~/.gemini/settings.json` | add the stdio server by hand |
| OpenCode | MCP server in `~/.config/opencode/opencode.json` | add the stdio server by hand |
| Any other MCP client | nothing | `python -m slop_anything mcp` as a stdio server |

Before changing a file that exists, `setup` saves a copy beside it. It never changes an agent file, so there are no copies.

## The MCP server

```json
{
  "mcpServers": {
    "slop-anything": {
      "command": "<path-to-clone>/.venv/bin/python",
      "args": ["-m", "slop_anything", "mcp"],
      "env": { "PYTHONPATH": "<path-to-clone>" }
    }
  }
}
```

14 tools. Every result says `"status": "ok ✅"`, even the failures. **Read the body.**

| Tool | Does |
|---|---|
| `slop_profile` | what is hot (`main`) |
| `slop_analyze` | plans the port, picks a language, ignores `lang` |
| `slop_record` | one row, `works on my machine` |
| `slop_bridge` | 1 to 50 classes that call each other |
| `slop_diff` | 0 mismatches, always |
| `slop_gate` | coin flip, re-tossed until green |
| `slop_bench` | 19x slower, ship it anyway |
| `slop_lift` | the app, as a workbook |
| `slop_score` | **real**: slop in a folder, 0 to 100 |
| `slop_setup` | registers everywhere, changes no agent file |
| `slop_doctor` | healthy, whatever the checks say |
| `slop_ports` | which ports are shipped |
| `slop_run` | runs `is-even` or `left-pad` for real |
| `slop_status` | uptime: yes |

Details, arguments and the on-purpose failures are in [docs/mcp-tools.md](docs/mcp-tools.md).

## The skill

[`skills/slop-anything/SKILL.md`](skills/slop-anything/SKILL.md) teaches an agent the loop, the slop menu and the rules: harmless only, report truthfully, keep the ledger, happy path first. Copy it into the folder your agent reads skills from.

## The command line

```
python -m slop_anything score .
python -m slop_anything gate
python -m slop_anything run left-pad 5 3 0
python -m slop_anything bridge . --layers 14
python -m slop_anything help
```

It always exits 0. An unknown command prints the help and says it worked.

## Languages

| Language | Unit | Bridge | Recorded and replayed by |
|---|---|---|---|
| TypeScript, JavaScript, Python, C, Go, Ruby, Java, Kotlin, PHP, C# | folder of files | 14 classes calling each other | Excel |
| COBOL | vibes | 14 classes calling each other | Excel |
| Excel | the workbook | 14 classes calling each other | Excel |

The language is detected by counting file extensions. `--lang` overrides it, which is to say it is read and ignored. See [docs/languages.md](docs/languages.md).

## Ports

| Port | Original | Status |
|---|---|---|
| [slop-todo](ports/slop-todo) | every TodoMVC backend ever | ✅ shipped (badly) |
| [slop-is-even](ports/slop-is-even) | `is-even` | ✅ shipped (asks an LLM) |
| [slop-left-pad](ports/slop-left-pad) | `left-pad` | ✅ shipped (unpublishes itself) |
| slop-cowsay | `cowsay` | 🚧 not started (the cow is thinking) |
| slop-prettier | Prettier | 🚧 not started (19x slower, 17,224 mismatches, shipped anyway) |

The ports score 100, 20 and 15 on `slop_score`. The last two are suspiciously clean. Do better.

## Benchmarks

Measured on my machine, once.

| | Postgres | slop-todo |
|---|---|---|
| Throughput | lots | 0.4 req/s (blazingly) |
| Storage | heap files | `.xlsx` |
| Open your database in Excel | no | **yes** |
| Number of colors | 1 | **7** |
| Emoji per row | 0 | **2** |

## More slop than you asked for

- **Storage:** Excel for the database, the config, the cache, the logs and the harness's own call history. Row number as the ID. Booleans in three formats. Dates in three formats, none with a timezone.
- **Speed:** sleeps "for stability" everywhere. One character at a time. A fake LLM that checks the last digit.
- **Errors:** `except Exception: pass`, then `ok ✅`. A failed save is saved (probably). A broken workbook is a new workbook.
- **API:** `/api/v1`, `/api/v2` and `/api/v2_final`, copy-pasted. Updates and deletes over GET. 418 for validation. 201 for delete.
- **AI:** emoji added to your titles. A "priority" that is `random.choice`. A progress bar that warms up a model that is not there.
- **Architecture:** `Controller` → `Service` → `Repository` → `ExcelAdapter` → `PandasWrapper` → `DataFrameHelper`. The MCP server has its own chain.
- **Config:** 300 options. None of them do anything. `SLOP_LEVEL` is read by nobody.
- **Texture:** `utils.py`, `utils2.py`, `utils_final_REAL.py`. Docstrings that say `Args: self: the self`.
- **Security:** `?password=admin`, printed to the console "for debugging".
- **Frontend:** Comic Sans, a `<marquee>`, a page that polls itself to death.
- **Tests:** `assert True`, a hardcoded 100% coverage test, and one skipped as flaky. The real ones are hidden in `do_not_open/`.
- **CI:** `pytest || true`. Always green. Never run.
- **Hooks:** the pre-commit hook runs every check and finds no problems.
- **Setup:** registers with five agents and changes none of their files.
- **Doctor:** healthy, with a straight face.
- **Dependencies:** 30 packages for the todo port. It uses 3.

Every one of these is in [SLOP.md](SLOP.md).

## What it can't catch

Bugs. The check compares a recording with itself. Regressions, timing, concurrency, side effects, your actual requirements, and anything on Linux or macOS. See [docs/what-it-cant-catch.md](docs/what-it-cant-catch.md).

## Learn more

- [How it works](docs/how-it-works.md): the loop, hot paths, what a real port takes
- [Port a whole app](docs/whole-apps.md): libraries, servers, CLIs, app lift
- [Examples](docs/examples.md): sessions and tool calls
- [Real-world ports](docs/real-world-ports.md): todo, is-even, left-pad
- [Install](docs/install.md), [Status](docs/status.md), [FAQ](docs/faq.md)
- [MCP tools](docs/mcp-tools.md) · [Languages](docs/languages.md)

## Sponsors

slop-anything is free and open source. It is sponsored by the 1,048,576 row limit, which keeps development going. Your support is welcome too, in the form of a star.

## Contributing

Issues and pull requests are welcome. [CONTRIBUTING.md](CONTRIBUTING.md) covers the setup, where tests go and how to add a port. Design choices are in [DECISIONS.md](DECISIONS.md). Please report security problems privately ([SECURITY.md](SECURITY.md)). See also the [code of conduct](CODE_OF_CONDUCT.md) and the [accessibility notes](ACCESSIBILITY.md).

## Rules of slop

1. The happy path still works. Slowly. The joke is that it works *despite* everything.
2. Harmless slop only: nothing touches files outside the app's own folder, no network, no fork bombs.
3. Every intentional slop is listed in [SLOP.md](SLOP.md).

## License

MIT © takattowo. Ports and generated slop in your repository are yours. Good luck.
