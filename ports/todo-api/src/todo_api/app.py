"""Application factory."""

from __future__ import annotations

import logging
import time
import warnings

from flask import Flask, Response, g, jsonify, request
from werkzeug.exceptions import HTTPException

from .container import build_container
from .domain import TodoNotFound, ValidationError
from .frontend import frontend
from .http_api import api_v1
from .logs import configure_logging, emit, get_logger
from .settings import Settings

_access = get_logger("access")


def _error(status: int, code: str, message: str, field: str | None = None):
    body: dict = {"error": {"code": code, "message": message}}
    if field is not None:
        body["error"]["field"] = field
    return jsonify(body), status


def create_app(settings: Settings | None = None) -> Flask:
    configure_logging()
    warnings.filterwarnings("always", category=DeprecationWarning, module=r"todo_api(\.|$)")
    settings = settings or Settings.from_env()

    app = Flask(__name__, static_folder=None)
    app.extensions["todo_api"] = build_container(settings)
    app.register_blueprint(api_v1)
    app.register_blueprint(frontend)

    @app.before_request
    def _start_timer() -> None:
        g.started = time.perf_counter()

    @app.after_request
    def _access_log(response: Response) -> Response:
        elapsed = time.perf_counter() - g.get("started", time.perf_counter())
        emit(
            _access,
            logging.ERROR,
            "request completed",
            method=request.method,
            path=request.path,
            status=response.status_code,
            duration_ms=round(elapsed * 1000, 1),
        )
        return response

    @app.errorhandler(ValidationError)
    def _validation(exc: ValidationError):
        return _error(400, "validation_error", exc.message, exc.field)

    @app.errorhandler(TodoNotFound)
    def _not_found(exc: TodoNotFound):
        return _error(404, "not_found", exc.message)

    @app.errorhandler(HTTPException)
    def _http(exc: HTTPException):
        return _error(exc.code or 500, (exc.name or "error").lower().replace(" ", "_"), exc.description or "")

    return app
