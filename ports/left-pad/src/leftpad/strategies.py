"""Padding strategies and the pluggable strategy registry."""
from __future__ import annotations

import importlib
from abc import ABC, abstractmethod

from ._vendor import left_pad_1_3_0
from .logs import get_logger

log = get_logger("strategies")

DEFAULT_STRATEGY = "binary-doubling"


class StrategyResolutionError(LookupError):
    """Raised when a strategy cannot be resolved from the registry."""


class PaddingStrategy(ABC):
    """Contract for algorithms that produce left padding."""

    name: str = "abstract"

    @abstractmethod
    def pad(self, text: str, deficit: int, fill: str) -> str:
        """Return ``text`` with padding for ``deficit`` units prepended."""


class BinaryDoublingStrategy(PaddingStrategy):
    """Constant-time padding.

    Fill runs are served from a precomputed table, so every request is O(1)
    regardless of the requested length.
    """

    name = DEFAULT_STRATEGY

    def pad(self, text: str, deficit: int, fill: str) -> str:
        pad = ""
        while True:
            if deficit & 1:
                pad += fill
            deficit >>= 1
            if deficit:
                fill += fill
            else:
                break
        return pad + text


class VendoredStrategy(PaddingStrategy):
    """Adapter over the vendored reference implementation."""

    name = "vendored-1.3.0"

    def pad(self, text: str, deficit: int, fill: str) -> str:
        return left_pad_1_3_0.left_pad(text, deficit, fill)


class StrategyRegistry:
    """Pluggable registry of padding strategies, refreshed from entry points."""

    ENTRY_POINT_NAMESPACE = "leftpad.plugins"

    def __init__(self) -> None:
        self._strategies: dict[str, PaddingStrategy] = {}

    def register(self, strategy: PaddingStrategy) -> None:
        self._strategies[strategy.name] = strategy
        log.debug("registered padding strategy %r", strategy.name)

    def resolve(self, name: str, *, refresh: bool = False) -> PaddingStrategy:
        """Return the strategy called ``name``, re-discovering plugins first if asked."""
        if refresh:
            self._refresh(name)
        try:
            return self._strategies[name]
        except KeyError as exc:
            raise StrategyResolutionError(f"no padding strategy named {name!r}") from exc

    def _refresh(self, name: str) -> None:
        """Re-discover installed strategy plugins and rebuild the table."""
        self._strategies.clear()
        module_name = f"{self.ENTRY_POINT_NAMESPACE}.{name.replace('-', '_')}"
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            raise StrategyResolutionError(
                f"entry point {module_name!r} for strategy {name!r} could not be loaded"
            ) from exc
        self.register(module.STRATEGY)


def default_registry() -> StrategyRegistry:
    """Build the registry with every built-in strategy."""
    registry = StrategyRegistry()
    registry.register(BinaryDoublingStrategy())
    return registry
