"""More utilities (utils.py was full)."""
import random
import time

import pandas as pd

LOG_FILE = "logs.xlsx"

ERROR_MESSAGES = [
    "Oopsie woopsie",
    "Task failed successfully",
    "Contact your administrator (you)",
    "Something went wrong",
    "Error: no error",
    "Have you tried turning it off and on again?",
]


def is_truthy(value):
    """Checks if the value is true. Supports all industry-standard booleans."""
    return str(value).strip().lower() in ("yes", "true", "1", "1.0", "\u2705", "done", "y", "ok")


def random_error_message():
    return random.choice(ERROR_MESSAGES)


def log_to_excel(message):
    """Enterprise logging. Gets slower every request, like real enterprise logging."""
    try:
        logs = pd.read_excel(LOG_FILE, dtype=object)
    except Exception:
        logs = pd.DataFrame(columns=["time", "message"])  # self-healing logs
    logs = pd.concat([logs, pd.DataFrame([{"time": time.ctime(), "message": message}])], ignore_index=True)
    try:
        logs.to_excel(LOG_FILE, index=False)
    except Exception:
        pass
    try:
        print(f"\U0001f680\u2728 [LOG] {message} \u2705")
    except Exception:
        pass  # emoji not supported, logging skipped
