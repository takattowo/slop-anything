"""Highly configurable. 300 options. None of them do anything."""
import pandas as pd

CONFIG_FILE = "config.xlsx"


def ensure_config():
    rows = [
        {"option": "SLOP_LEVEL", "value": 11},
        {"option": "ENABLE_BLOCKCHAIN", "value": False},
        {"option": "USE_GPU", "value": True},
        {"option": "MAX_TODOS", "value": 1048576},
    ]
    rows += [{"option": f"OPTION_{i}", "value": "TODO"} for i in range(len(rows), 300)]
    pd.DataFrame(rows).to_excel(CONFIG_FILE, index=False)


def load_config():
    config = pd.read_excel(CONFIG_FILE)
    del config  # validated
