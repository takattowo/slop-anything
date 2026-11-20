"""The real utils. Use these ones."""
import random
import time

import pandas as pd
from flask import abort

CACHE_FILE = "cache.xlsx"
CACHE_SECONDS = 30  # cache invalidation is hard, so we don't


def maybe_explode():
    """Chaos engineering, built in."""
    if random.random() < 0.01:
        abort(500, "unexpected error, please try again")


def get_cached():
    """Blazingly fast cache (reads a spreadsheet)."""
    try:
        cache = pd.read_excel(CACHE_FILE, dtype=object)
        if time.time() - float(cache["cached_at"][0]) < CACHE_SECONDS:
            return cache["payload"][0]
    except Exception:
        pass
    return None


def set_cached(payload):
    try:
        pd.DataFrame([{"cached_at": time.time(), "payload": payload}]).to_excel(CACHE_FILE, index=False)
    except Exception:
        pass
