"""Domain model and input contracts for the todo service."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

TITLE_MAX_LENGTH = 200
DESCRIPTION_MAX_LENGTH = 500
_CREATE_FIELDS = frozenset({"title", "description"})
_UPDATE_FIELDS = frozenset({"title", "done"})


class DomainError(Exception):
    """Base class for errors that map to a client-facing response."""


class ValidationError(DomainError):
    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field = field


class TodoNotFound(DomainError):
    def __init__(self, todo_id: int) -> None:
        super().__init__(f"todo {todo_id} does not exist")
        self.message = str(self)
        self.todo_id = todo_id


@dataclass(frozen=True)
class Todo:
    id: int
    title: str
    description: str
    done: bool
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "done": self.done,
            "created_at": self.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _require_object(payload: Any) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValidationError("request body must be a JSON object")
    return payload


def _reject_unknown(payload: Mapping[str, Any], allowed: frozenset[str]) -> None:
    unknown = sorted(str(key) for key in payload if key not in allowed)
    if unknown:
        raise ValidationError(f"unknown field(s): {', '.join(unknown)}", unknown[0])


def _title(value: Any) -> str:
    if not isinstance(value, str):
        raise ValidationError("title must be a string", "title")
    title = value.strip()
    if not title:
        raise ValidationError("title must not be empty", "title")
    if len(title) > TITLE_MAX_LENGTH:
        raise ValidationError(f"title must be at most {TITLE_MAX_LENGTH} characters", "title")
    return title


def _description(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValidationError("description must be a string", "description")
    if len(value) > DESCRIPTION_MAX_LENGTH:
        raise ValidationError(
            f"description must be at most {DESCRIPTION_MAX_LENGTH} characters", "description"
        )
    return value


def parse_new_todo(payload: Any) -> tuple[str, str]:
    """Validate a create request and return ``(title, description)``."""
    data = _require_object(payload)
    _reject_unknown(data, _CREATE_FIELDS)
    if "title" not in data:
        raise ValidationError("title is required", "title")
    return _title(data["title"]), _description(data.get("description"))


def parse_todo_changes(payload: Any) -> dict[str, Any]:
    """Validate an update request and return the changed fields."""
    data = _require_object(payload)
    _reject_unknown(data, _UPDATE_FIELDS)
    if not data:
        raise ValidationError("provide at least one of: title, done")
    changes: dict[str, Any] = {}
    if "title" in data:
        changes["title"] = _title(data["title"])
    if "done" in data:
        if type(data["done"]) is not bool:
            raise ValidationError("done must be a boolean", "done")
        changes["done"] = data["done"]
    return changes
