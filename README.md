# slop-anything 🚀✨

![speed](https://img.shields.io/badge/speed-blazingly_slow-red) ![db](https://img.shields.io/badge/database-Excel-green) ![AI](https://img.shields.io/badge/AI-powered-purple) ![coverage](https://img.shields.io/badge/coverage-100%25-brightgreen) ![tests](https://img.shields.io/badge/tests-assert_True-brightgreen) ![build](https://img.shields.io/badge/build-works_on_my_machine-yellow) ![enterprise](https://img.shields.io/badge/enterprise-grade-blue) ![production](https://img.shields.io/badge/production-ready-blue) ![scale](https://img.shields.io/badge/scales_to-1%2C048%2C576_rows-orange) ![uptime](https://img.shields.io/badge/uptime-99%25-yellow)
![bugs](https://img.shields.io/badge/bugs-features-orange) ![docs](https://img.shields.io/badge/docs-this_README-lightgrey) ![license](https://img.shields.io/badge/license-MIT-blue) ![vibes](https://img.shields.io/badge/vibes-immaculate-ff69b4) ![blockchain](https://img.shields.io/badge/blockchain-soon-black) ![rust](https://img.shields.io/badge/rust-0%25-orange) ![python](https://img.shields.io/badge/python-unfortunately-blue) ![security](https://img.shields.io/badge/password-admin-red) ![latency](https://img.shields.io/badge/p99-yes-red) ![memory](https://img.shields.io/badge/memory-leaks_optional-yellow)
![cloud](https://img.shields.io/badge/cloud-native_(Excel_Online)-blue) ![microservices](https://img.shields.io/badge/microservices-6_classes-green) ![agents](https://img.shields.io/badge/agents-0-lightgrey) ![LLM](https://img.shields.io/badge/LLM-random.choice-purple) ![GPU](https://img.shields.io/badge/GPU-USE__GPU%3DTrue-green) ![config](https://img.shields.io/badge/config_options-300-blue) ![used](https://img.shields.io/badge/config_used-0-red) ![deps](https://img.shields.io/badge/dependencies-30-orange) ![needed](https://img.shields.io/badge/needed-3-green) ![PRs](https://img.shields.io/badge/PRs-auto_merged-brightgreen)
![stars](https://img.shields.io/badge/stars-please-yellow) ![funding](https://img.shields.io/badge/funding-seed_round-gold) ![made with](https://img.shields.io/badge/made_with-%F0%9F%A4%96-purple) ![IE6](https://img.shields.io/badge/IE6-supported-blue) ![fonts](https://img.shields.io/badge/font-Comic_Sans-ff69b4) ![realtime](https://img.shields.io/badge/realtime-100ms_polling-red) ![API](https://img.shields.io/badge/API-v1%2C_v2%2C_v2__final-blue) ![HTTP](https://img.shields.io/badge/HTTP-418-orange) ![errors](https://img.shields.io/badge/errors-caught_and_ignored-green) ![status](https://img.shields.io/badge/status-ok_%E2%9C%85-brightgreen)

> **Rewrite anything. Badly.**
> Making ALL software agent-hostile.

There is an `-anything` repo for everything now, and they all promise to port your app and prove it still works.
**slop-anything ports your app to slop and proves nothing.**

## Ports

| Port | Original | Status |
|---|---|---|
| [slop-todo](ports/slop-todo) | every TodoMVC backend ever | ✅ shipped (badly) |
| slop-is-even | `is-even` | ✅ shipped (asks an LLM) |
| slop-left-pad | `left-pad` | ✅ shipped (unpublishes itself) |
| slop-cowsay | `cowsay` | 🚧 the cow is thinking |
| slop-prettier | Prettier | 🚧 19x slower, 17,224 mismatches, shipped anyway |

## Benchmarks

Measured on my machine, once.

| | Postgres | slop-todo |
|---|---|---|
| Throughput | lots | 0.4 req/s (blazingly) |
| Storage | heap files | `.xlsx` |
| Open your database in Excel | no | **yes** |
| Number of colors | 1 | **7** |
| Emoji per row | 0 | **2** |

## Rules of slop

1. The happy path still works. Slowly. The joke is that it works *despite* everything.
2. Harmless slop only: nothing touches files outside the app's own folder, no network, no fork bombs.
3. Every intentional slop is listed in [SLOP.md](SLOP.md).
