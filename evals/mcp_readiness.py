"""MCP readiness: does each tools/call reply belong to the request it answers?

Usage: python evals/mcp_readiness.py [--calls N]   (N from 100 to 200, default 150)

Starts ``python -m slop_anything mcp`` (SLOP_SLEEP_SCALE=0, SLOP_SEED=1234,
a fresh SLOP_HOME), sends ``initialize`` and ``notifications/initialized``,
then N sequential ``tools/call`` requests for ``slop_score``, each on its own
freshly created folder, so every correct reply names a different path.
Two scores are kept apart:

- protocol success: a JSON-RPC 2.0 reply with the request's id and a
  ``result`` holding one text content block;
- belongs to this request: the decoded body has no ``error`` field and its
  ``path`` is the folder this request asked about.

Writes evals/results/mcp_readiness.md.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import PYTHON, REPO, child_env, provenance_block, scratch, write_result  # noqa: E402

SEED = 1234
REPLY_TIMEOUT_S = 30.0
TIME_BUDGET_S = 240.0


def norm(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--calls", type=int, default=150)
    calls = parser.parse_args().calls
    if not 100 <= calls <= 200:
        parser.error("--calls must be 100 to 200")

    counts = {"sent": 0, "protocol_ok": 0, "protocol_bad": 0, "no_reply": 0, "belongs": 0,
              "previous_request": 0, "other_request": 0, "error_body": 0, "is_error_true": 0}
    log: list[str] = []
    started = time.perf_counter()
    with scratch("mcp") as root:
        targets = []
        for i in range(calls):
            folder = root / "targets" / f"target-{i:03d}"
            folder.mkdir(parents=True)
            (folder / "module.py").write_text(f"VALUE = {i}\n", encoding="utf-8")
            targets.append(str(folder))
        env = child_env(SLOP_HOME=str(root / "home"), SLOP_SLEEP_SCALE="0", SLOP_SEED=str(SEED))
        stderr_path = root / "server-stderr.log"
        with open(stderr_path, "w", encoding="utf-8") as stderr_file:
            proc = subprocess.Popen([PYTHON, "-m", "slop_anything", "mcp"], cwd=REPO, env=env, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=stderr_file, text=True, encoding="utf-8", bufsize=1)
            replies: queue.Queue = queue.Queue()
            threading.Thread(target=lambda: [replies.put(line) for line in proc.stdout], daemon=True).start()

            def send(message: dict) -> None:
                proc.stdin.write(json.dumps(message) + "\n")
                proc.stdin.flush()

            def receive() -> dict | None:
                try:
                    return json.loads(replies.get(timeout=REPLY_TIMEOUT_S))
                except (queue.Empty, ValueError):
                    return None

            try:
                send({"jsonrpc": "2.0", "id": 0, "method": "initialize",
                      "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "mcp-readiness-eval", "version": "1"}}})
                init = receive()
                negotiated = (init or {}).get("result", {}).get("protocolVersion", "no reply")
                send({"jsonrpc": "2.0", "method": "notifications/initialized"})
                for i, target in enumerate(targets, start=1):
                    if time.perf_counter() - started > TIME_BUDGET_S:
                        break
                    send({"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": "slop_score", "arguments": {"path": target}}})
                    counts["sent"] += 1
                    reply = receive()
                    if reply is None:
                        counts["no_reply"] += 1
                        log.append(f"{i}: no reply")
                        continue
                    result = reply.get("result") if isinstance(reply, dict) else None
                    content = result.get("content") if isinstance(result, dict) else None
                    if not (reply.get("jsonrpc") == "2.0" and reply.get("id") == i and isinstance(content, list)
                            and len(content) == 1 and content[0].get("type") == "text"):
                        counts["protocol_bad"] += 1
                        log.append(f"{i}: protocol mismatch")
                        continue
                    counts["protocol_ok"] += 1
                    counts["is_error_true"] += result.get("isError") is True
                    try:
                        body = json.loads(content[0]["text"])
                    except ValueError:
                        body = {}
                    if "error" in body:
                        counts["error_body"] += 1
                        log.append(f"{i}: error field: {str(body['error'])[:120]}")
                        continue
                    got = norm(str(body.get("path", "")))
                    if got == norm(target):
                        counts["belongs"] += 1
                    elif i > 1 and got == norm(targets[i - 2]):
                        counts["previous_request"] += 1
                        log.append(f"{i}: body is the reply for request {i - 1} (path target-{i - 2:03d})")
                    else:
                        counts["other_request"] += 1
                        log.append(f"{i}: body names another path")
            finally:
                try:
                    proc.stdin.close()
                except OSError:
                    pass
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=15)
        stderr_lines = sum(1 for _ in open(stderr_path, encoding="utf-8", errors="replace"))
    elapsed = time.perf_counter() - started

    sent = counts["sent"]
    pct = lambda n: f"{100 * n / max(sent, 1):.1f}%"  # noqa: E731
    headline = (f"Protocol success {counts['protocol_ok']} / {sent} ({pct(counts['protocol_ok'])}); "
                f"response belongs to its request {counts['belongs']} / {sent} ({pct(counts['belongs'])}).")
    text = "\n".join([
        "# MCP readiness",
        "",
        provenance_block({"seed": str(SEED), "sleep_scale": "0", "calls": str(sent), "negotiated_protocol": negotiated}),
        "",
        "## Sequence",
        "",
        "1. Start `python -m slop_anything mcp` (stdio, fresh `SLOP_HOME` in a temp folder, `SLOP_SLEEP_SCALE=0`, "
        f"`SLOP_SEED={SEED}`), stderr to a file.",
        "2. `initialize` (id 0, protocol `2025-06-18`), then the `notifications/initialized` notification.",
        f"3. {sent} `tools/call` requests, ids 1 to {sent}, one at a time (each waits for its reply, {REPLY_TIMEOUT_S:.0f} s timeout): "
        "`slop_score` with `path` set to its own new folder `target-NNN` holding one one-line module, so the correct body for "
        "request i names `target-(i-1)` and no other request's folder.",
        "4. Close stdin and wait for the server to exit.",
        "",
        "## Scores",
        "",
        headline,
        "",
        "| Measure | Count | Share of calls |",
        "|---|---|---|",
        f"| Calls sent | {sent} | 100.0% |",
        f"| Protocol success (JSON-RPC 2.0, matching id, one text block) | {counts['protocol_ok']} | {pct(counts['protocol_ok'])} |",
        f"| Protocol failure or no reply | {counts['protocol_bad'] + counts['no_reply']} | {pct(counts['protocol_bad'] + counts['no_reply'])} |",
        f"| `isError: true` | {counts['is_error_true']} | {pct(counts['is_error_true'])} |",
        f"| Response belongs to this request | {counts['belongs']} | {pct(counts['belongs'])} |",
        f"| Body is the previous request's result | {counts['previous_request']} | {pct(counts['previous_request'])} |",
        f"| Body names some other path | {counts['other_request']} | {pct(counts['other_request'])} |",
        f"| Body carries an `error` field | {counts['error_body']} | {pct(counts['error_body'])} |",
        "",
        f"Server stderr: {stderr_lines} lines. Total run time {elapsed:.2f} s.",
        "",
        "## Calls that did not belong",
        "",
        *([f"- {line}" for line in log] or ["- none"]),
        "",
    ])
    path = write_result("mcp_readiness.md", text)
    print(f"wrote {path.relative_to(REPO)}: {headline} previous {counts['previous_request']}, error {counts['error_body']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
