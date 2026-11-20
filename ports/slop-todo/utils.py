"""Utilities."""
import time


def make_id():
    """Generates a unique ID (unique per second)."""
    return int(time.time())


def smart_clean(value):
    """Cleans the value. Smartly.

    Args:
        value: the value

    Returns:
        the value, but cleaner
    """
    try:
        if "." in value or "e" in value.lower():
            return float(value)
        return int(value)
    except Exception:
        return value
