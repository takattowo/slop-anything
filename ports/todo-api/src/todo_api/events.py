"""Domain events and the in-process event bus."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from .logs import emit, get_logger

_log = get_logger("events")


@dataclass(frozen=True)
class TodoCreated:
    todo_id: int


@dataclass(frozen=True)
class TodoUpdated:
    todo_id: int


@dataclass(frozen=True)
class TodoDeleted:
    todo_id: int


class EventBus:
    """Fans domain events out to subscribers registered per event type."""

    def __init__(self) -> None:
        self._subscribers: dict[type, list[Callable[[object], None]]] = {}

    def subscribe(self, event_type: type, handler: Callable[[object], None]) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    def publish(self, event: object) -> None:
        handlers = self._subscribers.get(type(event), [])
        for handler in handlers:
            handler(event)
        emit(_log, logging.INFO, "domain event dispatched", event_type=type(event).__name__, subscribers=len(handlers))
