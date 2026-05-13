"""
:file: api/core/queue.py
:brief: Background price-feed thread that periodically refreshes live quotes
        and publishes them to an asyncio.Queue consumed by SSE endpoints.

Architecture:
  * A daemon ``threading.Thread`` runs a tight loop, calls yfinance for
    each subscribed ticker, then puts results into a ``queue.Queue``.
  * An async bridge drains that queue into an ``asyncio.Queue`` on the
    event loop so FastAPI SSE handlers can await new prices.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
import time
from collections import defaultdict
from typing import Any

from api.config import LIVE_PRICE_INTERVAL_SEC
from api.core.data import get_live_quote

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Thread-safe sync queue (worker → bridge)
# ─────────────────────────────────────────────────────────────────────────────
_sync_q: queue.Queue[dict] = queue.Queue(maxsize=1_000)

# asyncio queue subscribers: ticker → list[asyncio.Queue]
_subscribers: defaultdict[str, list[asyncio.Queue]] = defaultdict(list)
_subs_lock = threading.Lock()

# Active ticker set
_watched_tickers: set[str] = set()
_tickers_lock    = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────────
# Worker thread
# ─────────────────────────────────────────────────────────────────────────────

def _worker_loop() -> None:
    """Daemon loop: fetch quotes for all watched tickers every N seconds."""
    log.info("Live-price worker thread started (interval=%ds)", LIVE_PRICE_INTERVAL_SEC)

    while True:
        with _tickers_lock:
            tickers = list(_watched_tickers)

        for ticker in tickers:
            try:
                # Run async get_live_quote in a new event loop inside the thread
                quote = asyncio.run(get_live_quote(ticker))
                _sync_q.put_nowait(quote)
            except Exception as exc:  # noqa: BLE001
                log.debug("Worker fetch error %s: %s", ticker, exc)

        time.sleep(LIVE_PRICE_INTERVAL_SEC)


_worker_thread = threading.Thread(target=_worker_loop, daemon=True, name="price-feed")
_worker_started = False


def start_worker() -> None:
    """Start the background thread if not already running."""
    global _worker_started
    if not _worker_started:
        _worker_thread.start()
        _worker_started = True
        log.info("Background price worker started.")


# ─────────────────────────────────────────────────────────────────────────────
# Async bridge (drains _sync_q → asyncio queues)
# ─────────────────────────────────────────────────────────────────────────────

async def _bridge_loop() -> None:
    """Async task that drains the sync queue and fans out to subscribers."""
    loop = asyncio.get_event_loop()
    while True:
        try:
            # Non-blocking drain; yield control if empty
            quote = _sync_q.get_nowait()
            ticker = quote.get("ticker", "")
            with _subs_lock:
                qs = list(_subscribers.get(ticker, []))
            for aq in qs:
                try:
                    aq.put_nowait(quote)
                except asyncio.QueueFull:
                    pass
        except queue.Empty:
            await asyncio.sleep(0.5)
        except Exception as exc:  # noqa: BLE001
            log.debug("Bridge error: %s", exc)
            await asyncio.sleep(1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def subscribe(ticker: str) -> asyncio.Queue:
    """Subscribe to live updates for *ticker*. Returns a per-caller asyncio.Queue.

    :param ticker: e.g. ``'AAPL'``
    :returns: asyncio.Queue[dict] — each item is a quote dict
    """
    aq: asyncio.Queue[dict] = asyncio.Queue(maxsize=100)
    with _subs_lock:
        _subscribers[ticker].append(aq)
    with _tickers_lock:
        _watched_tickers.add(ticker)
    return aq


def unsubscribe(ticker: str, aq: asyncio.Queue) -> None:
    """Remove a subscriber queue."""
    with _subs_lock:
        subs = _subscribers.get(ticker, [])
        try:
            subs.remove(aq)
        except ValueError:
            pass


def watch(tickers: list[str]) -> None:
    """Add *tickers* to the watched set without subscribing to a queue."""
    with _tickers_lock:
        _watched_tickers.update(tickers)


def unwatch(ticker: str) -> None:
    """Remove *ticker* from the watched set."""
    with _tickers_lock:
        _watched_tickers.discard(ticker)
