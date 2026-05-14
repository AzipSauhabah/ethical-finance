"""
:file: api/strategies/registry.py
:brief: Dynamic strategy registry — auto-discovers built-ins and allows
        runtime registration of custom strategies.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import importlib
import logging
import pkgutil

from api.strategies.base import Strategy

log = logging.getLogger(__name__)

_BUILTIN_PACKAGE = "api.strategies.builtin"


class StrategyRegistry:
    """Singleton registry mapping strategy name → class."""

    def __init__(self) -> None:
        self._strategies: dict[str, type[Strategy]] = {}

    # ── Registration ──────────────────────────────────────────────────────

    def register(self, cls: type[Strategy]) -> type[Strategy]:
        """Register a strategy class.  Can be used as a decorator."""
        instance = cls()  # instantiate to read .name property
        key = instance.name.lower()
        self._strategies[key] = cls
        log.debug("Strategy registered: %s", key)
        return cls

    def unregister(self, name: str) -> None:
        self._strategies.pop(name.lower(), None)

    # ── Discovery ────────────────────────────────────────────────────────

    def auto_discover(self) -> None:
        """Import all modules in the builtin package so @register decorators fire."""
        try:
            pkg = importlib.import_module(_BUILTIN_PACKAGE)
            prefix = pkg.__name__ + "."
            for _, modname, _ in pkgutil.iter_modules(pkg.__path__, prefix):
                try:
                    importlib.import_module(modname)
                except Exception as exc:
                    log.warning("Could not import strategy module %s: %s", modname, exc)
        except Exception as exc:
            log.warning("auto_discover failed: %s", exc)

    # ── Lookup ────────────────────────────────────────────────────────────

    def get(self, name: str) -> type[Strategy] | None:
        return self._strategies.get(name.lower())

    def get_instance(self, name: str) -> Strategy | None:
        cls = self.get(name)
        return cls() if cls else None

    def list_all(self) -> list[dict]:
        """Return a JSON-serialisable list of strategy metadata."""
        result = []
        for _key, cls in self._strategies.items():
            inst = cls()
            result.append(
                {
                    "name": inst.name,
                    "description": inst.description,
                    "benchmark": inst.benchmark,
                    "param_space": inst.param_space,
                }
            )
        return result

    def __contains__(self, name: str) -> bool:
        return name.lower() in self._strategies

    def __len__(self) -> int:
        return len(self._strategies)


#: Module-level singleton
strategy_registry: StrategyRegistry = StrategyRegistry()
