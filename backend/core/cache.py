"""
:file: api/core/cache.py
:brief: Two-level cache — L1 in-process LRU/TTL, L2 Vercel KV (Redis REST).

Design:
  * Read-through: L1 miss → L2 → populate L1.
  * Write-through: set on both levels simultaneously.
  * Functional helpers: ``cached`` async decorator.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from backend.config import PRICE_CACHE_TTL

log = logging.getLogger(__name__)

T = TypeVar("T")

# ─────────────────────────────────────────────────────────────────────────────
# Level 1 — in-process TTL LRU
# ─────────────────────────────────────────────────────────────────────────────


class _Entry:
    __slots__ = ("value", "deadline")

    def __init__(self, value: Any, ttl: int) -> None:
        self.value = value
        self.deadline = time.monotonic() + ttl


class MemoryCache:
    """Asyncio-safe in-process LRU cache with per-entry TTL.

    Uses an :class:`~collections.OrderedDict` for O(1) LRU eviction.
    """

    def __init__(self, max_size: int = 512) -> None:
        self._store: OrderedDict[str, _Entry] = OrderedDict()
        self._max = max_size

    # ------------------------------------------------------------------
    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.deadline:
            del self._store[key]
            return None
        self._store.move_to_end(key)  # LRU bump
        return entry.value

    def set(self, key: str, value: Any, ttl: int = PRICE_CACHE_TTL) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        elif len(self._store) >= self._max:
            self._store.popitem(last=False)  # evict LRU
        self._store[key] = _Entry(value, ttl)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)


# ─────────────────────────────────────────────────────────────────────────────
# Level 2 — Vercel KV (Redis REST)
# ─────────────────────────────────────────────────────────────────────────────


class KVCache:
    """Cache en mémoire local — remplace Vercel KV.

    TTL par clé, thread-safe, zéro dépendance externe.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}  # key → (value, expire_at)
        self._ok = True

    async def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expire_at = entry
        import time

        if time.time() > expire_at:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: Any, ttl: int = PRICE_CACHE_TTL) -> None:
        import time

        self._store[key] = (value, time.time() + ttl)
        # Nettoyage périodique — évite la fuite mémoire
        if len(self._store) > 10_000:
            now = time.time()
            self._store = {k: v for k, v in self._store.items() if v[1] > now}

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


# ─────────────────────────────────────────────────────────────────────────────
# Unified two-level cache
# ─────────────────────────────────────────────────────────────────────────────


class Cache:
    """Read/write-through L1 + L2 cache. Import the :data:`cache` singleton."""

    def __init__(self) -> None:
        self.l1 = MemoryCache()
        self.l2 = KVCache()

    async def get(self, key: str) -> Any | None:
        v = self.l1.get(key)
        if v is not None:
            return v
        v = await self.l2.get(key)
        if v is not None:
            self.l1.set(key, v)
        return v

    async def set(self, key: str, value: Any, ttl: int = PRICE_CACHE_TTL) -> None:
        self.l1.set(key, value, ttl)
        await self.l2.set(key, value, ttl)

    async def delete(self, key: str) -> None:
        self.l1.delete(key)
        await self.l2.delete(key)


#: Module-level singleton — use ``from backend.core.cache import cache``
cache: Cache = Cache()


# ─────────────────────────────────────────────────────────────────────────────
# Functional decorator
# ─────────────────────────────────────────────────────────────────────────────


def cached(key_fn: Callable[..., str], ttl: int = PRICE_CACHE_TTL):
    """Async function decorator that memoises results in :data:`cache`.

    :param key_fn: callable(*args, **kwargs) → str cache key
    :param ttl: seconds to live
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = key_fn(*args, **kwargs)
            hit = await cache.get(key)
            if hit is not None:
                return hit
            result = await fn(*args, **kwargs)
            if result is not None:
                await cache.set(key, result, ttl)
            return result

        return wrapper

    return decorator
