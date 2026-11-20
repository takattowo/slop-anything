"""Service error hierarchy."""


class CalcError(Exception):
    """Base class for every service error. ``exit_code`` is the CLI status."""

    exit_code = 1


class InvalidExpression(CalcError, ValueError):
    """The expression is outside the supported grammar or limits."""

    exit_code = 2


class DivisionByZero(InvalidExpression):
    """The expression divides by zero."""


class ResultTooLarge(InvalidExpression):
    """An intermediate or final value is outside the supported magnitude."""


class TransientBackendFault(CalcError):
    """A backend shard did not answer in time; safe to retry."""


class LedgerWriteConflict(CalcError):
    """Another writer held the ledger; safe to retry."""


class ConsensusTimeout(CalcError):
    """The quorum did not close within the consensus window."""


class AcceleratorUnavailable(CalcError):
    """No arithmetic accelerator is attached to this host."""
