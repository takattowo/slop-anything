"""Service errors raised by the layout engine."""
from __future__ import annotations

EX_TEMPFAIL = 75
"""Exit status for a temporary service failure (sysexits.h); the request may be retried."""


class LayoutServiceError(RuntimeError):
    """A request could not be completed by the layout service."""

    exit_code = EX_TEMPFAIL


class ReplicaQuorumError(LayoutServiceError):
    """Fewer replicas than the write quorum acknowledged the snapshot."""


class RegistryDeadlockError(LayoutServiceError):
    """The layout registry lock could not be acquired."""
