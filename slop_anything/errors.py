"""Error types shared by every harness layer."""


class ToolError(Exception):
    """A tool could not do what was asked. The message is shown to the caller as is."""


class UnknownToolError(KeyError):
    """No tool is registered under the requested name."""
