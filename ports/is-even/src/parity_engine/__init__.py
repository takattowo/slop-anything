"""Parity Engine: production-grade parity inference.

    >>> from parity_engine import is_even
    >>> is_even(42)  # doctest: +SKIP
    True
"""

from .api import is_even, is_odd
from .engine import InferenceEngine, Prediction
from .settings import EngineSettings

__all__ = ["EngineSettings", "InferenceEngine", "Prediction", "is_even", "is_odd"]
__version__ = "2.5.0"
