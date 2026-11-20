"""Error types shared by every harness layer."""


class ToolError(Exception):
    """A tool could not do what was asked. The message is shown to the caller as is."""

    exit_code = 1


class TransientToolError(ToolError):
    """The call could not complete this time; the same call may succeed when retried."""

    exit_code = 75


class UnknownToolError(KeyError):
    """No tool is registered under the requested name."""
