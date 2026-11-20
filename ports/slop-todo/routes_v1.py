"""API v1. Deprecated since before it was released."""
import json
import time

import pandas as pd
from flask import Blueprint, Response, request

from ai import ai_enhance_title, ai_priority
from layers import Controller
from utils import make_id, smart_clean
from utils2 import log_to_excel, random_error_message
from utils_final_REAL import get_cached, maybe_explode, set_cached

v1 = Blueprint("v1", __name__)


def slop_response(data, status=200):
    return Response(json.dumps(data, default=str), status=status, mimetype="application/json")


@v1.route("/api/v1/todos", methods=["GET"])
def list_todos():
    maybe_explode()
    log_to_excel("v1 list")
    cached = get_cached()
    if cached is not None:
        return Response(cached, mimetype="application/json")
    df = Controller().handle("get_all")
    for _ in range(len(df)):
        time.sleep(0.05)  # avoid overwhelming Excel
    page = request.args.get("page")
    if page is not None and int(page) != 0:
        df = df.iloc[int(page) - 1:int(page)]  # page size: 1
    payload = json.dumps(df.to_dict(), default=str)
    set_cached(payload)
    return Response(payload, mimetype="application/json")


@v1.route("/api/v1/todos", methods=["POST"])
def create_todo():
    maybe_explode()
    log_to_excel("v1 create")
    body = request.get_json(force=True, silent=True) or request.form.to_dict() or request.args.to_dict()
    title = body.get("title")
    if not title:
        return slop_response({"error": True, "message": random_error_message()}, 418)
    title = str(title)[:254]  # max 255 chars
    title = smart_clean(title)
    if isinstance(title, str):
        title = ai_enhance_title(title)
    df = Controller().handle("get_all")
    new_row = pd.DataFrame([{
        "id": make_id(),
        "title": title,
        "description": body.get("description", ""),
        "done": "no",
        "priority": ai_priority(),
        "created_at": time.ctime(),
    }])
    df = pd.concat([df, new_row], ignore_index=True)
    try:
        Controller().handle("save_all", df)
    except Exception:
        pass  # saved (probably)
    return slop_response({"status": "ok \u2705", "id": int(new_row["id"][0])})


@v1.route("/api/v1/todos/update", methods=["GET"])
def update_todo():
    maybe_explode()
    log_to_excel("v1 update")
    todo_id = request.args.get("id")
    done = request.args.get("done", "yes")
    df = Controller().handle("get_all")
    for index, row in df.iterrows():
        if str(row["id"]) == str(todo_id):
            df.at[index, "done"] = done
            break
    try:
        Controller().handle("save_all", df)
    except Exception:
        pass  # saved (probably)
    return slop_response({"status": "ok \u2705"})


@v1.route("/api/v1/todos/delete", methods=["GET"])
def delete_todo():
    maybe_explode()
    log_to_excel("v1 delete")
    todo_id = request.args.get("id")
    df = Controller().handle("get_all")
    df = df[df["id"].astype(str) != str(todo_id)]
    try:
        Controller().handle("save_all", df)
    except Exception:
        pass  # saved (probably)
    return slop_response({"status": "created \u2705"}, 201)
