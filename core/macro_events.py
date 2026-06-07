"""
Collecteur d'événements macro : FOMC, NFP, CPI, PCE, PPI.
Sources : Fed website (FOMC), FRED API (publications BLS).
"""
import asyncio
import logging
from datetime import date, datetime

import httpx
import sqlalchemy as sa

log = logging.getLogger(__name__)

# ─── FOMC 2026 (dates officielles Fed) ───────────────────────────────────────
FOMC_DATES_2026 = [
    ("2026-01-28", "2026-01-29"),
    ("2026-03-18", "2026-03-19"),
    ("2026-05-06", "2026-05-07"),
    ("2026-06-17", "2026-06-18"),
    ("2026-07-29", "2026-07-30"),
    ("2026-09-16", "2026-09-17"),
    ("2026-10-28", "2026-10-29"),
    ("2026-12-16", "2026-12-17"),
]

# Annonce = 2e jour à 14h00 ET = 19h00 UTC
FOMC_ANNOUNCE_DATES_2026 = [d[1] for d in FOMC_DATES_2026]

# ─── NFP 2026 (1er vendredi du mois suivant) ─────────────────────────────────
NFP_DATES_2026 = [
    "2026-01-09", "2026-02-06", "2026-03-06", "2026-04-03",
    "2026-05-01", "2026-06-05", "2026-07-02", "2026-08-07",
    "2026-09-04", "2026-10-02", "2026-11-06", "2026-12-04",
]

# ─── CPI 2026 (milieu du mois ~15) ───────────────────────────────────────────
CPI_DATES_2026 = [
    "2026-01-15", "2026-02-12", "2026-03-12", "2026-04-10",
    "2026-05-13", "2026-06-11", "2026-07-14", "2026-08-12",
    "2026-09-11", "2026-10-14", "2026-11-12", "2026-12-11",
]

# ─── PCE 2026 (fin du mois) ──────────────────────────────────────────────────
PCE_DATES_2026 = [
    "2026-01-30", "2026-02-27", "2026-03-27", "2026-04-30",
    "2026-05-29", "2026-06-26", "2026-07-31", "2026-08-28",
    "2026-09-25", "2026-10-30", "2026-11-25", "2026-12-18",
]


async def seed_macro_events(engine) -> int:
    """Insère tous les événements macro 2026 en DB."""
    events = []

    for d in FOMC_ANNOUNCE_DATES_2026:
        events.append({
            "event_date": d, "event_time": "19:00:00",
            "event_type": "FOMC", "region": "US", "importance": "high",
            "description": "Fed FOMC rate decision — 14h00 ET",
            "source": "federalreserve.gov",
        })

    for d in NFP_DATES_2026:
        events.append({
            "event_date": d, "event_time": "13:30:00",
            "event_type": "NFP", "region": "US", "importance": "high",
            "description": "Non-Farm Payrolls — 8h30 ET",
            "source": "bls.gov",
        })

    for d in CPI_DATES_2026:
        events.append({
            "event_date": d, "event_time": "13:30:00",
            "event_type": "CPI", "region": "US", "importance": "high",
            "description": "Consumer Price Index — 8h30 ET",
            "source": "bls.gov",
        })

    for d in PCE_DATES_2026:
        events.append({
            "event_date": d, "event_time": "13:30:00",
            "event_type": "PCE", "region": "US", "importance": "high",
            "description": "PCE Price Index — 8h30 ET",
            "source": "bea.gov",
        })

    inserted = 0
    with engine.begin() as conn:
        for ev in events:
            try:
                conn.execute(sa.text("""
                    INSERT INTO macro_events
                        (event_date, event_time, event_type, region, importance, description, source)
                    VALUES
                        (:event_date, :event_time, :event_type, :region, :importance, :description, :source)
                    ON CONFLICT (event_date, event_type, region) DO NOTHING
                """), ev)
                inserted += 1
            except Exception as e:
                log.warning("Event insert error %s %s: %s", ev["event_type"], ev["event_date"], e)

    log.info("macro_events seeded: %d events", inserted)
    return inserted


def get_upcoming_high_impact_events(engine, days_ahead: int = 3) -> list[dict]:
    """Retourne les événements high-impact dans les N prochains jours."""
    today = date.today().isoformat()
    from datetime import date as _date, timedelta
    today_dt = _date.today()
    end_dt = (today_dt + timedelta(days=days_ahead)).isoformat()
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT event_date, event_type, region, importance, description
            FROM macro_events
            WHERE event_date BETWEEN :today AND :end_date
              AND importance = 'high'
            ORDER BY event_date, event_time
        """), {"today": today, "end_date": end_dt}).fetchall()
    return [dict(r._mapping) for r in rows]


def is_event_risk_window(engine, days_ahead: int = 2) -> bool:
    """Retourne True si un événement high-impact est dans les N prochains jours.
    Utilisé par EPR5 pour bloquer les nouvelles entrées.
    """
    return len(get_upcoming_high_impact_events(engine, days_ahead)) > 0
