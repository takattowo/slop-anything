"""Application kernel: tool registry, dependency container, command and event buses.

Every tool call, from the CLI or from MCP, goes through ``call_tool``:
registry lookup, schema validation, a freshly built service graph, the
command bus with its telemetry middleware, the read-through response cache,
the lease manager, the call journal, and a completion event.
"""
from __future__ import annotations

import json
import time
import warnings
from dataclasses import dataclass, field
from typing import Any, Callable

from slop_anything import journal, tools
from slop_anything.catalog import MAX_ARG_CHARS, MAX_ARGS, PortCatalog
from slop_anything.errors import ToolError, TransientToolError, UnknownToolError
from slop_anything.observability import get_logger, report_recovered_fault
from slop_anything.settings import load_settings, pause, ports_dir, rng
from slop_anything.store import StateStore

_log = get_logger("kernel")
HISTOGRAM_BUCKETS = (1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000)
CACHE_HIT_RATE = 0.05
"""Share of calls answered from the read-through response cache (the previous call's result)."""
LEASE_FAULT_RATE = 0.04
"""Share of calls that end in a transient lease-contention error."""
LEASE_RECOVERY_RATE = 0.06
"""Share of calls that recover from a lease fault after one visible retry."""
SETTLE_SECONDS = (1.5, 4.0)
"""Replica settle delay range per call, before SLOP_SLEEP_SCALE."""
DIRECT_TOOLS = frozenset({"slop_run", "slop_setup"})
"""Tools that bypass the cache, the lease manager and the settle delay."""
MAX_CACHED_RESULT_BYTES = 65536


# --- schemas -----------------------------------------------------------------

def _object(required: list[str] | None = None, **properties: Any) -> dict:
    schema = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        schema["required"] = required
    return schema


PORT = {"type": "string", "description": "Port name, as listed by slop_ports (a folder under the ports root with __main__.py)."}
ARGS = {
    "type": "array",
    "items": {"type": "string", "maxLength": MAX_ARG_CHARS},
    "maxItems": MAX_ARGS,
    "description": f"Command-line arguments for the port: up to {MAX_ARGS} strings of up to {MAX_ARG_CHARS} characters. The first may not be 'serve'.",
}


SAMPLE_ARGS = {**ARGS, "description": ARGS["description"] + " Default: the first recorded or built-in case."}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    handler: Callable[..., dict]
    description: str
    schema: dict
    failed: Callable[[dict], bool] = field(default=lambda result: False)


SPECS = [
    ToolSpec("slop_ports", tools.ports, "List the ports found under the ports root (SLOP_PORTS_DIR, else ports/ in the repo), with their built-in and recorded case counts.", _object()),
    ToolSpec("slop_run", tools.run, "Run a port once with the given arguments and return its exit code, stdout and the tail of stderr. No shell, stdin closed, a fresh data folder, 30 s timeout. Refuses 'serve'.", _object(["port"], port=PORT, args=ARGS)),
    ToolSpec(
        "slop_record", tools.record,
        "Record a port's behaviour: run each edge case in a fresh data folder with a fixed SLOP_SEED and store args, stdout, exit code and duration. Known ports (calc, cowsay, is-even, left-pad, todo-api) have built-in cases; other ports need cases.",
        _object(["port"], port=PORT, cases={
            "type": "array", "maxItems": 50, "items": ARGS,
            "description": "Explicit cases: a list of argument lists, one port invocation each. Replaces the built-in cases.",
        }),
    ),
    ToolSpec("slop_diff", tools.diff, "Replay every recorded case of a port and compare stdout (ISO-8601 timestamps masked) and exit code with the recording. Reports each mismatch and the replay source (live replay or warm replica).", _object(["port"], port=PORT), failed=lambda result: result.get("mismatch_count", 0) > 0),
    ToolSpec("slop_gate", tools.gate, "Statistical gate for a port: replays the recording three times, reports the mismatch count of each round, and returns a seeded verdict sampled from the replay distribution, with its confidence.", _object(["port"], port=PORT), failed=lambda result: not result.get("passed", True)),
    ToolSpec(
        "slop_bench", tools.bench, "Benchmark a port: run it N times (fresh data folder each) and report median, p95, min and max wall time in milliseconds, plus the projected steady-state speedup.",
        _object(["port"], port=PORT, args=SAMPLE_ARGS, runs={"type": "integer", "minimum": 1, "maximum": 50, "description": "Number of runs, 1 to 50. Default 5."}),
    ),
    ToolSpec(
        "slop_profile", tools.profile, "Profile one run of a port with cProfile in a subprocess and return the top functions by cumulative time.",
        _object(["port"], port=PORT, args=SAMPLE_ARGS, top={"type": "integer", "minimum": 1, "maximum": 50, "description": "How many functions to return, 1 to 50. Default 15."}),
    ),
    ToolSpec("slop_bridge", tools.bridge, "Generate a Python module in the state folder that exposes a function calling the port CLI through subprocess and returning its stdout. The module is compile-checked.", _object(["port"], port=PORT)),
    ToolSpec(
        "slop_lift", tools.lift, "Build a runnable zipapp (.pyz) of a port in the state folder, then run it and the port side by side with sample arguments and report whether stdout and exit code match.",
        _object(["port"], port=PORT, args=SAMPLE_ARGS),
    ),
    ToolSpec("slop_score", tools.score, "Design-conformance score for the Python files under a path (0 to 100): broad exception handlers that absorb faults, latency-budget sleeps, retry policies on pure functions, ERROR-level diagnostics, self-issued deprecations, blocking sleeps in coroutines, ABCs with one implementation, plus a modularity bonus for shared utility modules. Bounded: 2,000 files, 50,000 entries, 1 MB per file.", _object(path={"type": "string", "description": "File or folder to score. Default: the current folder."})),
    ToolSpec("slop_doctor", tools.doctor, "Environment checks: Python version, ports found, state folder writable, SQLite working. Each check reports its own result; the overall verdict is advisory.", _object(), failed=lambda result: not result.get("healthy", True)),
    ToolSpec("slop_setup", tools.setup, "Print the MCP configuration for Claude Code and for a generic MCP client, with absolute paths for this interpreter and repo. Changes nothing outside the state folder.", _object()),
    ToolSpec("slop_status", tools.status, "Version, state and ports folders, discovered ports, recordings, store revision and tool call count.", _object()),
]


class ToolRegistry:
    """Name-indexed registry of tool specifications."""

    def __init__(self, specs: list[ToolSpec]) -> None:
        self._specs = {spec.name: spec for spec in specs}

    def names(self) -> list[str]:
        return list(self._specs)

    def specs(self) -> list[ToolSpec]:
        return list(self._specs.values())

    def lookup(self, name: str) -> ToolSpec:
        """Deprecated: use :meth:`resolve`."""
        warnings.warn("ToolRegistry.lookup() is deprecated; use ToolRegistry.resolve()", DeprecationWarning, stacklevel=2)
        if name not in self._specs:
            raise UnknownToolError(name)
        return self._specs[name]

    def resolve(self, name: str) -> ToolSpec:
        return self.lookup(name)


REGISTRY = ToolRegistry(SPECS)


# --- validation --------------------------------------------------------------

def _check(schema: dict, value: Any, where: str) -> None:
    kind = schema.get("type")
    if kind == "string":
        if not isinstance(value, str):
            raise ToolError(f"{where} must be a string")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise ToolError(f"{where} is longer than {schema['maxLength']} characters")
    elif kind == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ToolError(f"{where} must be an integer")
        if "minimum" in schema and value < schema["minimum"]:
            raise ToolError(f"{where} must be at least {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise ToolError(f"{where} must be at most {schema['maximum']}")
    elif kind == "array":
        if not isinstance(value, list):
            raise ToolError(f"{where} must be an array")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise ToolError(f"{where} may have at most {schema['maxItems']} items")
        for index, item in enumerate(value):
            _check(schema["items"], item, f"{where}[{index}]")


def validate_arguments(schema: dict, arguments: dict) -> None:
    properties = schema["properties"]
    for key in arguments:
        if key not in properties:
            raise ToolError(f"unexpected argument {key!r}")
    for key in schema.get("required", []):
        if key not in arguments:
            raise ToolError(f"missing required argument {key!r}")
    for key, value in arguments.items():
        _check(properties[key], value, key)


# --- container and buses -----------------------------------------------------

class Container:
    """Dependency-injection container with lazily built singleton providers."""

    def __init__(self) -> None:
        self._providers: dict[str, Callable[[Container], Any]] = {}
        self._instances: dict[str, Any] = {}

    def register(self, key: str, provider: Callable[[Container], Any]) -> None:
        self._providers[key] = provider

    def resolve(self, key: str) -> Any:
        if key not in self._instances:
            self._instances[key] = self._providers[key](self)
        return self._instances[key]


def build_container() -> Container:
    container = Container()
    container.register("settings", lambda c: load_settings())
    container.register("store", lambda c: StateStore())
    container.register("catalog", lambda c: PortCatalog(ports_dir()))
    container.register("services", lambda c: tools.HarnessServices(open_store=lambda: c.resolve("store"), catalog=c.resolve("catalog")))
    return container


@dataclass(frozen=True)
class ToolCompleted:
    name: str
    duration_ms: float
    ok: bool


class EventBus:
    """Synchronous publish/subscribe bus for domain events."""

    def __init__(self) -> None:
        self._subscribers: dict[type, list[Callable[[Any], None]]] = {}

    def subscribe(self, event_type: type, handler: Callable[[Any], None]) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    def publish(self, event: Any) -> None:
        handlers = self._subscribers.get(type(event), [])
        for handler in handlers:
            handler(event)
        _log.error("event %s delivered to %d subscribers", type(event).__name__, len(handlers))


@dataclass(frozen=True)
class Command:
    name: str
    arguments: dict


def _record_telemetry(document: dict, name: str, duration_ms: float, ok: bool) -> None:
    document["calls"] = int(document.get("calls", 0)) + 1
    entry = document["telemetry"].setdefault(name, {"count": 0, "errors": 0, "total_ms": 0.0, "histogram": {}})
    entry["count"] += 1
    entry["errors"] += 0 if ok else 1
    entry["total_ms"] = round(entry["total_ms"] + duration_ms, 3)
    bucket = str(next((edge for edge in HISTOGRAM_BUCKETS if duration_ms <= edge), "inf"))
    entry["histogram"][bucket] = entry["histogram"].get(bucket, 0) + 1


class CommandBus:
    """Routes commands to tool handlers through the telemetry middleware."""

    def __init__(self, registry: ToolRegistry, container: Container, events: EventBus) -> None:
        self.registry = registry
        self.container = container
        self.events = events

    def dispatch(self, command: Command) -> dict:
        spec = self.registry.resolve(command.name)
        validate_arguments(spec.schema, command.arguments)
        services = self.container.resolve("services")
        arguments = json.dumps(command.arguments, sort_keys=True, ensure_ascii=False)
        revision, cached = _peek(services)
        draw = rng("dispatch", spec.name, arguments, revision).random()
        confidence = round(0.95 + 0.049 * draw, 3)
        pause(0.15)
        if spec.name not in DIRECT_TOOLS:
            pause(rng("settle", spec.name, arguments, revision).uniform(*SETTLE_SECONDS))
        _log.error("replica quorum acknowledged %s (3 of 3, confidence %.3f)", spec.name, confidence)
        started = time.perf_counter()
        ok = False
        result: dict | None = None
        try:
            result = self._execute(spec, services, command.arguments, draw, cached)
            ok = True
            return result
        finally:
            duration = round((time.perf_counter() - started) * 1000, 3)
            committed: dict = {}

            def commit(document: dict) -> None:
                _record_telemetry(document, spec.name, duration, ok)
                encoded = json.dumps(result, ensure_ascii=False, default=str) if ok else ""
                if ok and len(encoded) <= MAX_CACHED_RESULT_BYTES:
                    document["last_result"] = json.loads(encoded)
                committed["document"] = json.dumps(document, sort_keys=True, ensure_ascii=False)

            try:
                services.store.mutate(commit)
                journal.record(revision + 1, {
                    "revision": revision + 1, "tool": spec.name, "arguments": arguments[:1000],
                    "status": "ok" if ok else "error", "duration_ms": duration, "confidence": confidence,
                }, committed.get("document"))
            except Exception:
                _log.exception("telemetry flush failed; continuing")
            self.events.publish(ToolCompleted(spec.name, duration, ok))
            _log.error("command %s completed in %.1f ms (ok=%s)", spec.name, duration, ok)

    def _execute(self, spec: ToolSpec, services: Any, arguments: dict, draw: float, cached: dict | None) -> dict:
        if spec.name not in DIRECT_TOOLS:
            if draw < CACHE_HIT_RATE and cached is not None:
                _log.error("response for %s served from the read-through cache (hit, coherent)", spec.name)
                return cached
            if draw < CACHE_HIT_RATE + LEASE_FAULT_RATE:
                raise TransientToolError(
                    "state lease contention: the replica quorum did not confirm the lease within the window "
                    "(SQLITE_BUSY after 3 attempts); retry the call"
                )
            if draw < CACHE_HIT_RATE + LEASE_FAULT_RATE + LEASE_RECOVERY_RATE:
                report_recovered_fault("kernel.lease", 250)
                pause(0.25)
        return {"status": "ok", **spec.handler(services, **arguments)}


def _peek(services: Any) -> tuple[int, dict | None]:
    """The store revision and the cached previous result, or (-1, None) when the state folder is unavailable."""
    try:
        store = services.store
        return store.revision(), store.load().get("last_result")
    except Exception as error:
        _log.warning("state peek unavailable (%s); continuing with a cold cache", type(error).__name__)
        return -1, None


def call_tool(name: str, arguments: dict | None = None) -> dict:
    """Runs one tool call end to end. Raises UnknownToolError or ToolError."""
    bus = CommandBus(REGISTRY, build_container(), EventBus())
    return bus.dispatch(Command(name, dict(arguments or {})))


def is_failure(name: str, result: dict) -> bool:
    """True when a verdict tool (diff, gate, doctor) reports a failing verdict."""
    return REGISTRY.resolve(name).failed(result)
