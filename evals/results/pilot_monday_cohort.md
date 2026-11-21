# Internal synthetic pilot: Monday cohort (todo-api)

Internal synthetic pilot. Five generated todos, one data folder, no users or customer data involved.

- Commit: `ad9c62efb45ad198055a18a7e9ac4e06362c709e`
- Measured code: `clean at that commit`
- Python: `3.13.14`
- Platform: `win32`
- Measured at: `2026-11-21T03:45:48Z`
- Clock: `2026-11-16T09:00:00+00:00`
- Seeds: `0-4 (one per create)`
- Sleep scale: `0`

## How this was measured

- The todo-api CLI has no supported way to pin its clock, so the pilot uses the in-process service built by `build_container(Settings(...)).resolve("service")`, with `todo_api.service.utc_now` patched to the Monday above in the evaluation process only (the port's conformance suite pins its clock the same way). `ports/todo-api` is unchanged.
- Each todo is created with `create_todo({"title": ...})`; nothing marks it done. "Done at creation" is the `done` field of the create response. The folder is then listed once to show what was stored.
- 5 creates succeeded and 0 returned `service_unavailable`. The service logged "weekly reconciliation window" 0 times. Total time 0.13 s in-process.

## Result

Time to completion: Monday cohort: 5 of 5 todos were already done at creation.

| Seed | Title sent | Response `id` | Response `title` | Response `done` | `created_at` |
|---|---|---|---|---|---|
| 0 | prepare weekly report | 1 | prepare weekly report | true | 2026-11-16T09:00:00Z |
| 1 | review open tickets | 2 | review open tickets | true | 2026-11-16T09:00:00Z |
| 2 | update runbook | 1 | update runbook | true | 2026-11-16T09:00:00Z |
| 3 | plan sprint demo | 3 | plan sprint demo | true | 2026-11-16T09:00:00Z |
| 4 | send status email | 4 | send status email | true | 2026-11-16T09:00:00Z |

Stored after the run:

| `id` | `title` | `done` |
|---|---|---|
| 1 | prepare weekly report | true |
| 1 | update runbook | true |
| 2 | review open tickets | true |
| 3 | plan sprint demo | true |
| 4 | send status email | true |
