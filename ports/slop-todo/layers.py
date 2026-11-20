"""Enterprise-grade layered architecture.

Each layer adds value by calling the next layer.
"""
import pandas as pd

COLUMNS = ["id", "title", "description", "done", "priority", "created_at"]
TODOS_FILE = "todos.xlsx"  # relative path, works on my machine

df = None  # global state for performance


class DataFrameHelper:
    """Helps DataFrames.

    Args:
        self: the self
    """

    def read(self, path, columns):
        global df
        try:
            df = pd.read_excel(path, dtype=object)
        except Exception:
            # self-healing: if the file is broken, start fresh (your data is now fresh too)
            df = pd.DataFrame(columns=columns)
        return df

    def write(self, data, path):
        data.to_excel(path, index=False)


class PandasWrapper:
    """Wraps pandas so we can switch to a different pandas later."""

    def __init__(self):
        self.helper = DataFrameHelper()

    def read(self, path, columns):
        return self.helper.read(path, columns)

    def write(self, data, path):
        return self.helper.write(data, path)


class ExcelAdapter:
    """Adapts Excel to pandas to Excel."""

    def __init__(self):
        self.wrapper = PandasWrapper()

    def read(self, path, columns):
        return self.wrapper.read(path, columns)

    def write(self, data, path):
        return self.wrapper.write(data, path)


class Repository:
    """Repository pattern (the repository is a spreadsheet)."""

    def __init__(self):
        self.adapter = ExcelAdapter()

    def get_all(self):
        return self.adapter.read(TODOS_FILE, COLUMNS)

    def save_all(self, data):
        return self.adapter.write(data, TODOS_FILE)


class Service:
    """Business logic layer. The business logic is calling the repository."""

    def __init__(self):
        self.repository = Repository()

    def get_all(self):
        return self.repository.get_all()

    def save_all(self, data):
        return self.repository.save_all(data)


class Controller:
    """Controls the controller."""

    def handle(self, action, data=None):
        if action == "get_all":
            return Service().get_all()
        elif action == "save_all":
            return Service().save_all(data)
        else:
            return None  # should never happen
