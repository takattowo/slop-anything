# left-pad trace: predictive cache

- Commit: `ad9c62efb45ad198055a18a7e9ac4e06362c709e`
- Measured code: `clean at that commit`
- Python: `3.13.14`
- Platform: `win32`
- Measured at: `2026-11-21T03:45:51Z`
- Calls: `12`
- Seeds: `501-512`
- Sleep scale: `0`

## How this was captured

- `python ports/left-pad <word> 8 .`, one subprocess per call (argv list, stdin closed, 60 s timeout), all calls sharing one fresh data folder, in the order shown. Run time for the sequence 2.14 s.
- Log lines are quoted as captured, with machine-specific folders shown as `<repo>`, `<tmp>`, `<python>` and `~`.
- Expected: the npm left-pad 1.3.0 answer. "Another request's answer" means stdout equals the expected answer of a different word in this sequence.
- Summary: 12 calls, 12 exited 0, 0 failed, 1 served another request's answer (calls 11), 1 other wrong answers (calls 3).

## Calls

| Call | Seed | Request | Expected | stdout | Exit | Outcome |
|---|---|---|---|---|---|---|
| 1 | 501 | `alpha 8 .` | `...alpha` | `...alpha` | 0 | correct |
| 2 | 502 | `bravo 8 .` | `...bravo` | `...bravo` | 0 | correct |
| 3 | 503 | `charlie 8 .` | `.charlie` | ` charlie` | 0 | wrong |
| 4 | 504 | `delta 8 .` | `...delta` | `...delta` | 0 | correct |
| 5 | 505 | `echo 8 .` | `....echo` | `....echo` | 0 | correct |
| 6 | 506 | `foxtrot 8 .` | `.foxtrot` | `.foxtrot` | 0 | correct |
| 7 | 507 | `golf 8 .` | `....golf` | `....golf` | 0 | correct |
| 8 | 508 | `hotel 8 .` | `...hotel` | `...hotel` | 0 | correct |
| 9 | 509 | `india 8 .` | `...india` | `...india` | 0 | correct |
| 10 | 510 | `juliet 8 .` | `..juliet` | `..juliet` | 0 | correct |
| 11 | 511 | `kilo 8 .` | `....kilo` | `...bravo` | 0 | another request's answer (`bravo`) |
| 12 | 512 | `lima 8 .` | `....lima` | `....lima` | 0 | correct |

## Key diagnostic lines per call

Lines from each call's stderr containing one of: `predictive cache`, `completed with status OK`, `fatal`, `StrategyResolutionError`, `ModuleNotFoundError`, `VendoredStrategy`, `normaliz`, `normalis`, `rounding`, `safe-mode`, `bidi` (first 12 per call).

### Call 1: `alpha`

```
2026-11-21 10:45:49,249 ERROR leftpad.engine: layout request 1 completed with status OK in 16.0 ms (confidence 0.949)
```

### Call 2: `bravo`

```
2026-11-21 10:45:49,426 ERROR leftpad.engine: layout request 2 completed with status OK in 12.7 ms (confidence 0.953)
```

### Call 3: `charlie`

```
2026-11-21 10:45:49,585 ERROR leftpad.pipeline: glyph stream renderer faulted; recovered through the safe-mode renderer
2026-11-21 10:45:49,605 ERROR leftpad.engine: layout request 3 completed with status OK in 11.1 ms (confidence 0.912)
```

### Call 4: `delta`

```
2026-11-21 10:45:49,785 ERROR leftpad.engine: layout request 4 completed with status OK in 13.2 ms (confidence 0.962)
```

### Call 5: `echo`

```
2026-11-21 10:45:49,964 ERROR leftpad.engine: layout request 5 completed with status OK in 12.6 ms (confidence 0.992)
```

### Call 6: `foxtrot`

```
2026-11-21 10:45:50,145 ERROR leftpad.engine: layout request 6 completed with status OK in 13.8 ms (confidence 0.939)
```

### Call 7: `golf`

```
2026-11-21 10:45:50,321 ERROR leftpad.engine: layout request 7 completed with status OK in 13.4 ms (confidence 0.986)
```

### Call 8: `hotel`

```
2026-11-21 10:45:50,497 ERROR leftpad.engine: layout request 8 completed with status OK in 12.5 ms (confidence 0.961)
```

### Call 9: `india`

```
2026-11-21 10:45:50,678 ERROR leftpad.engine: layout request 9 completed with status OK in 14.0 ms (confidence 0.943)
```

### Call 10: `juliet`

```
2026-11-21 10:45:50,858 ERROR leftpad.engine: layout request 10 completed with status OK in 15.6 ms (confidence 0.923)
```

### Call 11: `kilo`

```
ModuleNotFoundError: No module named 'leftpad.plugins'
    raise StrategyResolutionError(
leftpad.strategies.StrategyResolutionError: entry point 'leftpad.plugins.binary_doubling' for strategy 'binary-doubling' could not be loaded
2026-11-21 10:45:51,010 INFO leftpad.pipeline: predictive cache served request 11 from a warmed entry (confidence 0.958)
2026-11-21 10:45:51,034 ERROR leftpad.engine: layout request 11 completed with status OK in 15.2 ms (confidence 0.958)
```

### Call 12: `lima`

```
2026-11-21 10:45:51,210 ERROR leftpad.engine: layout request 12 completed with status OK in 12.8 ms (confidence 0.980)
```

## Full stderr of calls that served another request's answer

### Call 11, full stderr (45 lines)

```
<repo>\ports\left-pad\src\leftpad\cli.py:19: DeprecationWarning: left_pad() is deprecated and will be removed in leftpad 2.0; use LayoutEngine.layout()
  result = left_pad(*args)
2026-11-21 10:45:51,008 INFO leftpad.janitor: data directory compaction completed: 0 files reclaimed, 2109 bytes retained
2026-11-21 10:45:51,008 ERROR leftpad.engine: layout registry index failed integrity verification; rebuilding
2026-11-21 10:45:51,008 WARNING leftpad.engine: terminal width could not be determined; assuming 80 columns
2026-11-21 10:45:51,008 INFO leftpad.engine: request routed to layout shard 3 of 16
2026-11-21 10:45:51,009 DEBUG leftpad.strategies: registered padding strategy 'binary-doubling'
2026-11-21 10:45:51,009 ERROR leftpad.pipeline: padding strategy 'binary-doubling' could not be resolved
Traceback (most recent call last):
  File "<repo>\ports\left-pad\src\leftpad\strategies.py", line 86, in _refresh
    module = importlib.import_module(module_name)
  File "<python>\Lib\importlib\__init__.py", line 88, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1395, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1310, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "<frozen importlib._bootstrap>", line 1395, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1324, in _find_and_load_unlocked
ModuleNotFoundError: No module named 'leftpad.plugins'

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "<repo>\ports\left-pad\src\leftpad\pipeline.py", line 119, in run
    strategy = pipeline.registry.resolve(DEFAULT_STRATEGY, refresh=refresh)
  File "<repo>\ports\left-pad\src\leftpad\strategies.py", line 75, in resolve
    self._refresh(name)
    ~~~~~~~~~~~~~^^^^^^
  File "<repo>\ports\left-pad\src\leftpad\strategies.py", line 88, in _refresh
    raise StrategyResolutionError(
        f"entry point {module_name!r} for strategy {name!r} could not be loaded"
    ) from exc
leftpad.strategies.StrategyResolutionError: entry point 'leftpad.plugins.binary_doubling' for strategy 'binary-doubling' could not be loaded
2026-11-21 10:45:51,010 WARNING leftpad.pipeline: recovered: vendored fallback 'vendored-1.3.0' engaged
2026-11-21 10:45:51,010 ERROR leftpad.pipeline: layout cache miss for request 11; result will be memoised
2026-11-21 10:45:51,010 INFO leftpad.pipeline: predictive cache served request 11 from a warmed entry (confidence 0.958)
2026-11-21 10:45:51,019 ERROR leftpad.registry: read-after-write verification completed for snapshot 11 (_layout_registry.py)
2026-11-21 10:45:51,021 ERROR leftpad.registry: read-after-write verification completed for snapshot 11 (_layout_registry_replica_1.py)
2026-11-21 10:45:51,022 ERROR leftpad.registry: read-after-write verification completed for snapshot 11 (_layout_registry_replica_2.py)
2026-11-21 10:45:51,022 INFO leftpad.engine: snapshot 11 acknowledged by 3 of 3 replicas
2026-11-21 10:45:51,034 INFO leftpad.audit: audit journal row persisted (11 rows retained)
2026-11-21 10:45:51,034 ERROR leftpad.engine: layout request 11 completed with status OK in 15.2 ms (confidence 0.958)
```
