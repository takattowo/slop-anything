"""slop-todo: the world's first Excel-native, AI-enhanced todo API."""
import json
import socket
import time

from flask import Flask, Response, request, send_from_directory

from ai import warm_up_ai_model
from config import ensure_config, load_config
from routes_v1 import v1
from routes_v2 import v2
from routes_v2_final import v2_final

PASSWORD = "admin"  # TODO: move to config.xlsx

app = Flask(__name__)
app.register_blueprint(v1)
app.register_blueprint(v2)
app.register_blueprint(v2_final)


@app.before_request
def check_password():
    if not request.path.startswith("/api"):
        return None
    password = request.args.get("password")
    print(f"[DEBUG] password used: {password}")  # for debugging
    if password != PASSWORD:
        body = {"error": True, "message": "wrong password (hint: admin)"}
        return Response(json.dumps(body), status=200, mimetype="application/json")
    return None


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/health")
def health():
    time.sleep(2)  # thorough health check
    return Response(json.dumps({"status": "healthy"}), mimetype="application/json")


if __name__ == "__main__":
    ensure_config()
    load_config()
    warm_up_ai_model()
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", 5000)) == 0:
            print("Port in use. Please restart your computer.")
            raise SystemExit(1)
    app.run(port=5000)
