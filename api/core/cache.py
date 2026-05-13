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

import asyncio
import json
import logging
import time
from collections import OrderedDict
from functools import wraps
from typing import Any, Callable, TypeVar

import httpx

from api.config import KV_REST_API_URL, KV_REST_API_TOKEN, PRICE_CACHE_TTL

log = logging.getLogger(__name__)

T = TypeVar("T")

# ─────────────────────────────────────────────────────────────────────────────
# Level 1 — in-process TTL LRU
# ─────────────────────────────────────────────────────────────────────────────

class _Entry:
    __slots__ = ("value", "deadline")

    def __init__(self, value: Any, ttl: int) -> None:
        self.value    = value
        self.deadline = time.monotonic() + ttl


class MemoryCache:
    """Asyncio-safe in-process LRU cache with per-entry TTL.

    Uses an :class:`~collections.OrderedDict` for O(1) LRU eviction.
    """

    def __init__(self, max_size: int = 512) -> None:
        self._store: OrderedDict[str, _Entry] = OrderedDict()
        self._max   = max_size

    # ------------------------------------------------------------------
    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.deadline:
            del self._store[key]
            return None
        self._store.move_to_end(key)   # LRU bump
        return entry.value

    def set(self, key: str, value: Any, ttl: int = PRICE_CACHE_TTL) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        elif len(self._store) >= self._max:
            self._store.popitem(last=False)   # evict LRU
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
    """Thin async wrapper around Vercel KV REST API.

    Gracefully degrades to no-op when env vars are absent.
    """

    def __init__(self) -> None:
        self._ok      = bool(KV_REST_API_URL and KV_REST_API_TOKEN)
        self._headers = {"Authorization": f"Bearer {KV_REST_API_TOKEN}"}
        self._base    = KV_REST_API_URL.rstrip("/")

    # ------------------------------------------------------------------
    async def get(self, key: str) -> Any | None:
        if not self._ok:
            return None
        try:
            async with httpx.AsyncClient(timeout=2.0) as c:
                r = await c.get(f"{self._base}/get/{key}", headers=self._headers)
                if r.status_code == 200:
                    payload = r.json()
                    raw = payload.get("result")
                    return json.loads(raw) if raw is not None else None
        except Exception as exc:              # noqa: BLE001
            log.debug("KV.get error: %s", exc)
        return None

    async def set(self, key: str, value: Any, ttl: int = PRICE_CACHE_TTL) -> None:
        if not self._ok:
            return
        try:
            body = json.dumps(value)
            async with httpx.AsyncClient(timeout=2.0) as c:
                await c.post(
                    f"{self._base}/set/{key}",
                    headers=self._headers,
                    json={"value": body, "ex": ttl},
                )
        except Exception as exc:              # noqa: BLE001
            log.debug("KV.set error: %s", exc)

    async def delete(self, key: str) -> None:
        if not self._ok:
            return
        try:
            async with httpx.AsyncClient(timeout=1.0) as c:
                await c.get(f"{self._base}/del/{key}", headers=self._headers)
        except Exception as exc:              # noqa: BLE001
            log.debug("KV.delete error: %s", exc)


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


#: Module-level singleton — use ``from api.core.cache import cache``
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
