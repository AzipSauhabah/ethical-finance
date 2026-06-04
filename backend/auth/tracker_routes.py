"""
backend/auth/tracker_routes.py
Portfolio Tracker — CRUD portfolios + transactions + calculs TWR/MWR/PRU
"""
from __future__ import annotations
import logging
from datetime import date
from typing import Any
import numpy as np

log = logging.getLogger(__name__)


# ── Helpers calculs ───────────────────────────────────────────────────────────

def compute_holdings(
    transactions: list[dict],
    splits: dict[str, list[dict]] | None = None,
    dividends: dict[str, list[dict]] | None = None,
) -> dict[str, dict]:
    """
    Calcule les positions actuelles depuis les transactions.
    Intègre automatiquement les splits et dividendes depuis la DB.

    Args:
        transactions: liste des transactions BUY/SELL/DIVIDEND/SPLIT
        splits: {ticker: [{date, ratio}]} depuis stock_splits DB
        dividends: {ticker: [{date, dividend}]} depuis ohlcv_dividends DB

    Returns:
        {ticker: {qty, avg_price, total_invested, realized_pnl, dividends_received}}
    """
    # Fusionne transactions + splits DB en une timeline unifiée
    all_events: list[dict] = []

    for tx in transactions:
        all_events.append({**tx, "_source": "tx"})

    # Ajoute les splits DB comme événements SPLIT synthétiques
    if splits:
        for ticker, ticker_splits in splits.items():
            for sp in ticker_splits:
                sp_date = sp["date"] if isinstance(sp["date"], date) else date.fromisoformat(str(sp["date"]))
                all_events.append({
                    "ticker": ticker,
                    "date": sp_date,
                    "type": "SPLIT",
                    "qty": float(sp["ratio"]),
                    "price": 0,
                    "fees": 0,
                    "_source": "db_split",
                })

    # Trie par date puis par source (tx avant splits le même jour)
    all_events.sort(key=lambda x: (
        x["date"] if isinstance(x["date"], date) else date.fromisoformat(str(x["date"])),
        0 if x.get("_source") == "tx" else 1
    ))

    holdings: dict[str, dict] = {}

    for ev in all_events:
        t = ev["ticker"]
        if t not in holdings:
            holdings[t] = {
                "qty": 0.0, "avg_price": 0.0,
                "total_invested": 0.0, "realized_pnl": 0.0,
                "dividends_received": 0.0,
            }
        h = holdings[t]
        qty   = float(ev.get("qty") or 0)
        price = float(ev.get("price") or 0)
        fees  = float(ev.get("fees") or 0)
        ev_type = ev["type"]
        ev_date = ev["date"] if isinstance(ev["date"], date) else date.fromisoformat(str(ev["date"]))

        if ev_type == "BUY":
            total_cost = h["qty"] * h["avg_price"] + qty * price + fees
            h["qty"] += qty
            h["avg_price"] = total_cost / h["qty"] if h["qty"] > 0 else 0
            h["total_invested"] += qty * price + fees

        elif ev_type == "SELL":
            realized = (price - h["avg_price"]) * qty - fees
            h["realized_pnl"] += realized
            h["qty"] = max(0, h["qty"] - qty)
            if h["qty"] == 0:
                h["avg_price"] = 0.0
                h["total_invested"] = 0.0

        elif ev_type == "SPLIT" and h["qty"] > 0 and qty > 0:
            # Ajuste qty et PRU selon le ratio
            h["avg_price"] = h["avg_price"] / qty
            h["qty"] = round(h["qty"] * qty, 6)

        elif ev_type == "DIVIDEND":
            # Dividende manuel saisi dans les transactions
            h["realized_pnl"] += qty * price
            h["dividends_received"] += qty * price

    # Calcule les dividendes automatiques depuis la DB
    if dividends:
        for ticker, ticker_divs in dividends.items():
            if ticker not in holdings: continue
            h = holdings[ticker]
            # Reconstitue la qty à chaque date de dividende
            for div in ticker_divs:
                div_date = div["date"] if isinstance(div["date"], date) else date.fromisoformat(str(div["date"]))
                # Qty détenue à cette date
                tx_before = [e for e in all_events
                            if e["ticker"] == ticker and
                            (e["date"] if isinstance(e["date"], date) else date.fromisoformat(str(e["date"]))) <= div_date]
                if not tx_before: continue
                qty_at_date = compute_holdings(tx_before).get(ticker, {}).get("qty", 0)
                if qty_at_date > 0:
                    div_received = qty_at_date * float(div["dividend"])
                    h["dividends_received"] += div_received
                    h["realized_pnl"] += div_received

    return {t: h for t, h in holdings.items() if h["qty"] > 0}


def compute_twr(transactions: list[dict], prices: dict[str, list[dict]]) -> float:
    """
    Time-Weighted Return — méthode Modified Dietz simplifiée.
    Neutralise l'effet des flux entrants/sortants.
    prices: {ticker: [{date, price}]}
    """
    try:
        # Calcule la valeur du portefeuille à chaque date de transaction
        sub_returns = []
        sorted_tx = sorted(transactions, key=lambda x: x["date"])
        
        if len(sorted_tx) < 2:
            return 0.0

        # Groupe par sous-périodes
        dates = sorted(set(tx["date"] for tx in sorted_tx))
        
        for i in range(len(dates) - 1):
            d_start = dates[i]
            d_end = dates[i + 1]
            
            # Holdings au début de la période
            tx_before = [tx for tx in sorted_tx if tx["date"] <= d_start]
            holdings_start = compute_holdings(tx_before)
            
            if not holdings_start:
                continue
            
            # Valeur début et fin de période
            val_start = sum(
                h["qty"] * _get_price_at(prices.get(t, []), d_start, h["avg_price"])
                for t, h in holdings_start.items()
            )
            val_end = sum(
                h["qty"] * _get_price_at(prices.get(t, []), d_end, h["avg_price"])
                for t, h in holdings_start.items()
            )
            
            if val_start > 0:
                sub_returns.append(val_end / val_start)
        
        if not sub_returns:
            return 0.0
        
        twr = 1.0
        for r in sub_returns:
            twr *= r
        return round((twr - 1) * 100, 2)
    except Exception as e:
        log.warning("TWR error: %s", e)
        return 0.0


def compute_mwr(transactions: list[dict], current_value: float) -> float:
    """
    Money-Weighted Return (IRR) — rendement personnel tenant compte du timing.
    Utilise scipy.optimize.brentq pour résoudre l'équation IRR.
    """
    try:
        from scipy.optimize import brentq
        
        cash_flows = []
        for tx in sorted(transactions, key=lambda x: x["date"]):
            d = tx["date"] if isinstance(tx["date"], date) else date.fromisoformat(str(tx["date"]))
            qty = float(tx["qty"])
            price = float(tx["price"])
            fees = float(tx.get("fees") or 0)
            
            if tx["type"] == "BUY":
                cash_flows.append((d, -(qty * price + fees)))
            elif tx["type"] == "SELL":
                cash_flows.append((d, qty * price - fees))
            elif tx["type"] == "DIVIDEND":
                cash_flows.append((d, qty * price))

        if not cash_flows:
            return 0.0

        start_date = cash_flows[0][0]
        cash_flows.append((date.today(), current_value))

        def npv(rate):
            return sum(
                cf / (1 + rate) ** ((d - start_date).days / 365)
                for d, cf in cash_flows
            )

        try:
            irr = brentq(npv, -0.99, 10.0, maxiter=100)
            return round(irr * 100, 2)
        except Exception:
            return 0.0
    except ImportError:
        return 0.0


def _get_price_at(price_list: list[dict], target_date, fallback: float) -> float:
    """Trouve le prix le plus proche d'une date."""
    if not price_list:
        return fallback
    target = str(target_date)[:10]
    closest = min(price_list, key=lambda x: abs(str(x.get("date", ""))[:10] < target))
    return float(closest.get("price", fallback))


# ── Routes FastAPI ────────────────────────────────────────────────────────────

def register_tracker_routes(app, get_current_user, engine):
    """Enregistre les routes /api/tracker/* sur l'app FastAPI."""
    import sqlalchemy as sa
    from fastapi import Depends, HTTPException

    @app.get("/api/tracker/portfolios")
    async def list_portfolios(user=Depends(get_current_user)):
        with engine.connect() as conn:
            rows = conn.execute(sa.text(
                "SELECT id, name, type, currency, broker, notes, created_at "
                "FROM portfolios WHERE user_id = :uid ORDER BY created_at"
            ), {"uid": str(user.user_id)}).fetchall()
        return {"portfolios": [dict(zip(["id","name","type","currency","broker","notes","created_at"], r)) for r in rows]}

    @app.post("/api/tracker/portfolios")
    async def create_portfolio(payload: dict, user=Depends(get_current_user)):
        with engine.begin() as conn:
            row = conn.execute(sa.text("""
                INSERT INTO portfolios (user_id, name, type, currency, broker, notes)
                VALUES (:uid, :name, :type, :currency, :broker, :notes)
                RETURNING id, name, type, currency
            """), {
                "uid": str(user.user_id),
                "name": payload.get("name", "My Portfolio"),
                "type": payload.get("type", "CTO"),
                "currency": payload.get("currency", "EUR"),
                "broker": payload.get("broker", ""),
                "notes": payload.get("notes", ""),
            }).fetchone()
        return {"portfolio": dict(zip(["id","name","type","currency"], row))}

    @app.delete("/api/tracker/portfolios/{portfolio_id}")
    async def delete_portfolio(portfolio_id: int, user=Depends(get_current_user)):
        with engine.begin() as conn:
            conn.execute(sa.text(
                "DELETE FROM portfolios WHERE id = :pid AND user_id = :uid"
            ), {"pid": portfolio_id, "uid": str(user.user_id)})
        return {"ok": True}

    @app.get("/api/tracker/portfolios/{portfolio_id}/transactions")
    async def list_transactions(portfolio_id: int, user=Depends(get_current_user)):
        with engine.connect() as conn:
            rows = conn.execute(sa.text("""
                SELECT id, ticker, date, type, qty, price, fees, currency, notes
                FROM transactions
                WHERE portfolio_id = :pid AND user_id = :uid
                ORDER BY date DESC
            """), {"pid": portfolio_id, "uid": str(user.user_id)}).fetchall()
        cols = ["id","ticker","date","type","qty","price","fees","currency","notes"]
        return {"transactions": [dict(zip(cols, r)) for r in rows]}

    @app.post("/api/tracker/portfolios/{portfolio_id}/transactions")
    async def add_transaction(portfolio_id: int, payload: dict, user=Depends(get_current_user)):
        with engine.begin() as conn:
            row = conn.execute(sa.text("""
                INSERT INTO transactions
                    (portfolio_id, user_id, ticker, date, type, qty, price, fees, currency, notes)
                VALUES (:pid, :uid, :ticker, :date, :type, :qty, :price, :fees, :currency, :notes)
                RETURNING id
            """), {
                "pid": portfolio_id,
                "uid": str(user.user_id),
                "ticker": payload["ticker"].upper(),
                "date": payload["date"],
                "type": payload["type"],
                "qty": float(payload.get("qty", 0)),
                "price": float(payload.get("price", 0)),
                "fees": float(payload.get("fees", 0)),
                "currency": payload.get("currency", "USD"),
                "notes": payload.get("notes", ""),
            }).fetchone()
        return {"id": row[0], "ok": True}

    @app.patch("/api/tracker/portfolios/{portfolio_id}/transactions/{tx_id}")
    async def update_transaction(portfolio_id: int, tx_id: int, payload: dict, user=Depends(get_current_user)):
        fields = {k: v for k, v in payload.items() if k in ("qty","price","fees","date","notes","currency")}
        if not fields:
            return {"ok": False, "error": "No valid fields"}
        set_clause = ", ".join(f"{k}=:{k}" for k in fields)
        fields.update({"tid": tx_id, "pid": portfolio_id, "uid": str(user.user_id)})
        with engine.begin() as conn:
            conn.execute(sa.text(
                f"UPDATE transactions SET {set_clause} WHERE id=:tid AND portfolio_id=:pid AND user_id=:uid"
            ), fields)
        return {"ok": True}

    @app.delete("/api/tracker/portfolios/{portfolio_id}/transactions/{tx_id}")
    async def delete_transaction(portfolio_id: int, tx_id: int, user=Depends(get_current_user)):
        with engine.begin() as conn:
            conn.execute(sa.text(
                "DELETE FROM transactions WHERE id = :tid AND portfolio_id = :pid AND user_id = :uid"
            ), {"tid": tx_id, "pid": portfolio_id, "uid": str(user.user_id)})
        return {"ok": True}

    @app.get("/api/tracker/portfolios/{portfolio_id}/analytics")
    async def portfolio_tracker_analytics(portfolio_id: int, user=Depends(get_current_user)):
        """Holdings actuels + TWR + MWR + P&L par position."""
        with engine.connect() as conn:
            # Transactions
            tx_rows = conn.execute(sa.text("""
                SELECT ticker, date, type, qty, price, fees, currency
                FROM transactions WHERE portfolio_id = :pid AND user_id = :uid
                ORDER BY date ASC
            """), {"pid": portfolio_id, "uid": str(user.user_id)}).fetchall()

        if not tx_rows:
            return {"holdings": {}, "twr": 0, "mwr": 0, "total_invested": 0, "current_value": 0, "unrealized_pnl": 0}

        tx_list = [dict(zip(["ticker","date","type","qty","price","fees","currency"], r)) for r in tx_rows]
        holdings = compute_holdings(tx_list)

        # Prix actuels — daily en priorité, intraday comme fallback
        tickers = list(holdings.keys())
        current_prices = {}
        with engine.connect() as conn:
            for t in tickers:
                # 1. Daily closing
                row = conn.execute(sa.text(
                    "SELECT close, date FROM ohlcv WHERE ticker = :t ORDER BY date DESC LIMIT 1"
                ), {"t": t}).fetchone()
                daily_price = float(row[0]) if row else None
                daily_date = row[1] if row else None

                # 2. Intraday fallback si daily manque ou est ancien (> 2 jours)
                from datetime import date as _date, timedelta
                today = _date.today()
                if daily_date and (today - daily_date).days < 2:
                    current_prices[t] = daily_price
                else:
                    intra = conn.execute(sa.text(
                        "SELECT close FROM ohlcv_intraday WHERE ticker = :t ORDER BY datetime DESC LIMIT 1"
                    ), {"t": t}).fetchone()
                    if intra:
                        current_prices[t] = float(intra[0])
                    elif daily_price:
                        current_prices[t] = daily_price

        # Calculs P&L
        total_invested = sum(h["total_invested"] for h in holdings.values())
        current_value = sum(
            h["qty"] * current_prices.get(t, h["avg_price"])
            for t, h in holdings.items()
        )
        unrealized_pnl = current_value - sum(
            h["qty"] * h["avg_price"] for h in holdings.values()
        )
        realized_pnl = sum(h["realized_pnl"] for h in holdings.values())

        # Enrichi chaque holding avec prix actuel et P&L
        holdings_enriched = {}
        for t, h in holdings.items():
            last_price = current_prices.get(t, h["avg_price"])
            unreal = (last_price - h["avg_price"]) * h["qty"]
            holdings_enriched[t] = {
                **h,
                "last_price": round(last_price, 4),
                "unrealized_pnl": round(unreal, 2),
                "unrealized_pct": round((last_price / h["avg_price"] - 1) * 100, 2) if h["avg_price"] > 0 else 0,
                "market_value": round(last_price * h["qty"], 2),
            }

        mwr = compute_mwr(tx_list, current_value)

        return {
            "holdings": holdings_enriched,
            "total_invested": round(total_invested, 2),
            "current_value": round(current_value, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "realized_pnl": round(realized_pnl, 2),
            "mwr": mwr,
            "n_positions": len(holdings_enriched),
        }
