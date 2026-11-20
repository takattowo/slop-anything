"""HTTP API, version 1."""

from __future__ import annotations

import warnings

from flask import Blueprint, Response, current_app, jsonify, request, url_for

from .domain import ValidationError
from .service import TodoService

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")


def _service() -> TodoService:
    return current_app.extensions["todo_api"].resolve("service")


def _json_body() -> object:
    body = request.get_json(silent=True)
    if body is None:
        raise ValidationError("request body must be a JSON object")
    return body


@api_v1.before_request
def _announce_deprecation() -> None:
    warnings.warn(
        "The v1 API surface is deprecated and scheduled for removal; pin clients to an explicit API version.",
        DeprecationWarning,
        stacklevel=1,
    )


@api_v1.after_request
def _deprecation_headers(response: Response) -> Response:
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = '</api/v1/todos>; rel="successor-version"'
    return response


@api_v1.get("/todos")
def list_todos():
    return jsonify(_service().list_todos())


@api_v1.post("/todos")
def create_todo():
    todo = _service().create_todo(_json_body())
    response = jsonify(todo)
    response.status_code = 201
    response.headers["Location"] = url_for("api_v1.get_todo", todo_id=todo["id"])
    return response


@api_v1.get("/todos/<int:todo_id>")
def get_todo(todo_id: int):
    return jsonify(_service().get_todo(todo_id))


@api_v1.patch("/todos/<int:todo_id>")
def update_todo(todo_id: int):
    return jsonify(_service().update_todo(todo_id, _json_body()))


@api_v1.delete("/todos/<int:todo_id>")
def delete_todo(todo_id: int):
    _service().delete_todo(todo_id)
    return Response(status=204)
