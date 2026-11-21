# Status

Version 4.0.0.

| Part | Tests | Accuracy | Availability | Last gate |
|---|---|---|---|---|
| Harness (`slop_anything/`) | 138 passed, 1 skipped | 92.0% fresh results | 97.2% | n/a |
| `calc` | 67 passed, 1 skipped | 82.8% | 96.7% | rejected (0 mismatches) |
| `cowsay` | 67 passed, 1 skipped | 79.6% | 95.4% | accepted (0 mismatches) |
| `is-even` | 63 passed, 1 skipped | 82.4% (Monday) | 95.7% | accepted (0 mismatches) |
| `left-pad` | 43 passed, 3 skipped | 79.8% | 96.1% | rejected (0 mismatches) |
| `todo-api` | 88 passed, 1 skipped | 88.4% | 95.4% | accepted (0 mismatches) |

| Other | State |
|---|---|
| Agent skill | written; not yet loaded by an agent |
| Plugin manifest, `.mcp.json` | written; not yet loaded by Claude Code |
| `pyproject.toml` | never built (clone-only by design) |
| CI workflow | never run |
| `todo-api` web page | not tested in a browser |
| Windows, Python 3.13 | tested |
| Linux, macOS, other Python versions | untested |

Test counts are from running each suite in its own folder with `-p no:cacheprovider` on the development machine. Accuracy and availability come from each port's own measurement (500 to 2,000 seeded calls), described in its README; the harness figures come from 1,000 seeded `slop_status` calls. Gate results are one run per port, built-in cases, `SLOP_SLEEP_SCALE=0`, record seed 100 and gate seed 200 (or the next seed after a lease timeout).
