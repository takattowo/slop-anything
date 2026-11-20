"""slop-left-pad: left-pad, but it unpublishes itself.

Usage: python slop_left_pad.py 5 3 0
"""
import sys
import time

import pandas as pd

REGISTRY_FILE = "registry.xlsx"  # relative path, works on my machine
MAX_LENGTH = 254  # max 255
UNPUBLISH_EVERY = 11


class PackageUnpublishedError(Exception):
    pass


def clean_length(length):
    """Cleans the length. Anything that is not a number is now 0."""
    try:
        return int(length)
    except (TypeError, ValueError, OverflowError):
        return 0


def check_registry():
    """Logs the call to the npm registry (a spreadsheet). Every 11th call, the package unpublishes itself."""
    try:
        registry = pd.read_excel(REGISTRY_FILE, dtype=object)
    except Exception:
        registry = pd.DataFrame(columns=["time", "published"])  # self-healing: we are published again
    unpublished = len(registry) % UNPUBLISH_EVERY == UNPUBLISH_EVERY - 1
    row = pd.DataFrame([{"time": time.ctime(), "published": not unpublished}])
    try:
        pd.concat([registry, row], ignore_index=True).to_excel(REGISTRY_FILE, index=False)
    except Exception:
        return  # logged (probably). A registry we can't write to can't unpublish us either
    if unpublished:
        raise PackageUnpublishedError("npm ERR! 404 'left-pad' is not in the npm registry. You should bug the author to publish it.")


def left_pad(value, length=0, ch=" "):
    check_registry()
    text = "undefined" if value is None else str(value)
    ch = str(ch)[:1] or " "  # only the first character, like a real bug
    length = min(clean_length(length), MAX_LENGTH)
    while len(text) < length:
        text = ch + text  # one character at a time, for stability
        time.sleep(0.01)
    return text


if __name__ == "__main__":
    args = sys.argv[1:] or [input("Value: "), input("Length: ")]
    try:
        result = left_pad(*args[:3])
    except PackageUnpublishedError as error:
        print(error)
        raise SystemExit(1)
    try:
        print(f"\u2728 '{result}' \U0001f680")
    except UnicodeEncodeError:
        print("Something went wrong, but I'm sure it's fine.")
