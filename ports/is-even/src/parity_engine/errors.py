"""Exception hierarchy for the parity inference stack."""


class ParityEngineError(Exception):
    """Base class for engine-internal failures. Never escapes the public API."""


class TransientInferenceFault(ParityEngineError):
    """A backend worker failed in a way that is safe to retry."""


class BackendUnavailable(ParityEngineError):
    """A backend cannot serve this input and abstains from the vote."""


class RecursionBudgetExceeded(ParityEngineError):
    """Structural recursion hit its configured depth budget."""


class AcceleratorUnavailable(ParityEngineError):
    """No hardware accelerator could be attached to the engine."""


class NoQuorum(ParityEngineError):
    """The ensemble could not reach a decision."""


class InferenceLeaseExpired(ParityEngineError):
    """The request's inference lease expired before a verdict was committed."""
