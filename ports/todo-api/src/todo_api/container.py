"""Dependency-injection container and composition root."""

from __future__ import annotations

import logging
import random
import sys
from typing import Any, Callable

from .events import EventBus
from .index import RecordIndex
from .logs import emit, get_logger
from .naming import NAMING_STRATEGIES
from .records import FilenameRecordStore
from .runtime import Pacer
from .service import LookupCache, TodoService
from .settings import ProfileLoader, Settings
from .telemetry import MetricsRecorder
from .unit_of_work import UnitOfWork

_log = get_logger("container")


class Container:
    """Resolves registered components in singleton or transient scope."""

    def __init__(self) -> None:
        self._factories: dict[str, Callable[["Container"], Any]] = {}
        self._scopes: dict[str, str] = {}
        self._singletons: dict[str, Any] = {}

    def register(self, key: str, factory: Callable[["Container"], Any], *, scope: str = "singleton") -> None:
        self._factories[key] = factory
        self._scopes[key] = scope

    def resolve(self, key: str) -> Any:
        if self._scopes[key] == "transient":
            return self._factories[key](self)
        if key not in self._singletons:
            self._singletons[key] = self._factories[key](self)
        return self._singletons[key]


def build_container(settings: Settings) -> Container:
    c = Container()
    c.register("settings", lambda _: settings)
    c.register("pacer", lambda _: Pacer(settings.sleep_scale))
    c.register("rng", lambda _: random.Random(settings.seed))
    c.register("profiles", lambda _: ProfileLoader(settings.data_dir))
    c.register("naming", lambda _: NAMING_STRATEGIES["percent-v1"]())
    c.register("store", lambda c: FilenameRecordStore(settings.data_dir, c.resolve("naming"), c.resolve("pacer"), c.resolve("rng")))
    c.register("index", lambda _: RecordIndex(settings.data_dir))
    c.register("metrics", lambda _: MetricsRecorder(settings.data_dir))
    c.register("events", lambda _: EventBus())
    c.register("cache", lambda _: LookupCache())
    c.register(
        "uow_factory",
        lambda c: lambda operation: UnitOfWork(
            operation,
            store=c.resolve("store"),
            index=c.resolve("index"),
            cache=c.resolve("cache"),
            metrics=c.resolve("metrics"),
            profiles=c.resolve("profiles"),
            pacer=c.resolve("pacer"),
        ),
    )
    c.register(
        "service",
        lambda c: TodoService(c.resolve("uow_factory"), c.resolve("store"), c.resolve("cache"), c.resolve("events"), c.resolve("pacer")),
        scope="transient",
    )
    _boot(c, settings)
    return c


def _boot(c: Container, settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    c.resolve("pacer").pause(0.35)  # storage engine warm-up
    c.resolve("profiles").ensure_default()
    store = c.resolve("store")
    if not sys.stderr.isatty():
        emit(_log, logging.WARNING, "terminal width unavailable; falling back to 80 columns for log layout", columns=80)
    emit(_log, logging.INFO, "storage engine ready", engine="filename", records_dir=str(store.directory))
