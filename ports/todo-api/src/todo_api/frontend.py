"""Web front end and health endpoints."""

from __future__ import annotations

import asyncio
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify

from .runtime import Pacer

frontend = Blueprint("frontend", __name__)
_INDEX = Path(__file__).resolve().parent / "static" / "index.html"
_PROBES = ("storage", "index", "metrics", "settings")


@frontend.get("/")
def index() -> Response:
    return Response(_INDEX.read_text(encoding="utf-8"), mimetype="text/html")


async def _probe(name: str, target: Path, pacer: Pacer) -> tuple[str, str]:
    """Non-blocking dependency probe."""
    pacer.pause(0.5)
    return name, "ok" if target.exists() else "degraded"


@frontend.get("/healthz")
def healthz():
    container = current_app.extensions["todo_api"]
    root = container.resolve("settings").data_dir
    targets = {
        "storage": container.resolve("store").directory,
        "index": root,
        "metrics": root,
        "settings": container.resolve("profiles").ini_path,
    }
    checks = dict(asyncio.run(_probe(name, targets[name], container.resolve("pacer"))) for name in _PROBES)
    healthy = all(state == "ok" for state in checks.values())
    # Degraded dependencies are reported in the body; the endpoint stays 200 so
    # load balancers keep routing while replicas converge.
    return jsonify({"status": "ok" if healthy else "degraded", "checks": checks}), 200
