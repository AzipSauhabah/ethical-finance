"""
Buffett Score — 4 critères qualité Warren Buffett
Score 0-100 : ROE + Dette + FCF Yield + Moat (gross margin)
"""
from __future__ import annotations
from typing import Any

def _score_roe(roe: float | None) -> tuple[float, str]:
    """ROE ≥ 15% = excellent. Interpolé 0-25."""
    if roe is None:
        return 0.0, "N/A"
    pct = roe * 100
    if pct >= 20:
        pts = 25.0
    elif pct >= 15:
        pts = 20.0 + (pct - 15) / 5 * 5
    elif pct >= 10:
        pts = 10.0 + (pct - 10) / 5 * 10
    elif pct > 0:
        pts = pct / 10 * 10
    else:
        pts = 0.0
    label = "Excellent" if pct >= 20 else "Bon" if pct >= 15 else "Moyen" if pct >= 10 else "Faible"
    return round(pts, 1), f"{pct:.1f}% — {label}"

def _score_debt(total_debt: float | None, net_income: float | None) -> tuple[float, str]:
    """Dette / bénéfice net ≤ 3 ans = excellent."""
    if not total_debt or not net_income or net_income <= 0:
        return 0.0, "N/A"
    ratio = total_debt / net_income
    if ratio <= 1:
        pts = 25.0
    elif ratio <= 3:
        pts = 25.0 - (ratio - 1) / 2 * 12
    elif ratio <= 5:
        pts = 13.0 - (ratio - 3) / 2 * 10
    else:
        pts = max(0.0, 3.0 - (ratio - 5) * 0.5)
    label = "Excellente" if ratio <= 1 else "Bonne" if ratio <= 3 else "Elevee" if ratio <= 5 else "Critique"
    return round(pts, 1), f"{ratio:.1f}x — {label}"

def _score_fcf(op_cf: float | None, market_cap: float | None) -> tuple[float, str]:
    """FCF yield = OCF / market_cap ≥ 5% = excellent."""
    if not op_cf or not market_cap or market_cap <= 0:
        return 0.0, "N/A"
    yield_pct = op_cf / market_cap * 100
    if yield_pct >= 8:
        pts = 25.0
    elif yield_pct >= 5:
        pts = 18.0 + (yield_pct - 5) / 3 * 7
    elif yield_pct >= 2:
        pts = 8.0 + (yield_pct - 2) / 3 * 10
    elif yield_pct > 0:
        pts = yield_pct / 2 * 8
    else:
        pts = 0.0
    label = "Excellent" if yield_pct >= 8 else "Bon" if yield_pct >= 5 else "Moyen" if yield_pct >= 2 else "Faible"
    return round(pts, 1), f"{yield_pct:.1f}% — {label}"

def _score_moat(gross_margin: float | None) -> tuple[float, str]:
    """Gross margin ≥ 40% proxy avantage concurrentiel."""
    if gross_margin is None:
        return 0.0, "N/A"
    pct = gross_margin * 100
    if pct >= 50:
        pts = 25.0
    elif pct >= 40:
        pts = 18.0 + (pct - 40) / 10 * 7
    elif pct >= 25:
        pts = 8.0 + (pct - 25) / 15 * 10
    elif pct > 0:
        pts = pct / 25 * 8
    else:
        pts = 0.0
    label = "Fort" if pct >= 50 else "Solide" if pct >= 40 else "Moyen" if pct >= 25 else "Faible"
    return round(pts, 1), f"{pct:.1f}% — {label}"

def compute_buffett_score(fund: dict[str, Any], market_cap: float | None = None) -> dict:
    """
    Calcule le Buffett Score depuis un dict de fundamentals.
    Retourne score global + détail 4 critères.
    """
    mc = market_cap or fund.get("market_cap")
    equity = fund.get("equity_group") or fund.get("total_equity")
    net_income = fund.get("net_income_group") or fund.get("net_income")
    total_debt = (fund.get("long_term_debt") or 0) + (fund.get("short_term_debt") or 0)
    if total_debt == 0:
        total_debt = fund.get("total_debt") or fund.get("interest_bearing_debt")
    op_cf = fund.get("operating_cash_flow")
    gross_margin = fund.get("gross_margin")

    roe = (net_income / equity) if (net_income and equity and equity > 0) else fund.get("roe")

    pts_roe,  lbl_roe  = _score_roe(roe)
    pts_debt, lbl_debt = _score_debt(total_debt, net_income)
    pts_fcf,  lbl_fcf  = _score_fcf(op_cf, mc)
    pts_moat, lbl_moat = _score_moat(gross_margin)

    total = pts_roe + pts_debt + pts_fcf + pts_moat

    if total >= 80:
        verdict = "Qualite exceptionnelle"
        color = "#16a34a"
    elif total >= 60:
        verdict = "Bonne qualite"
        color = "#65a30d"
    elif total >= 40:
        verdict = "Qualite moyenne"
        color = "#ca8a04"
    else:
        verdict = "Qualite insuffisante"
        color = "#dc2626"

    return {
        "score": round(total, 1),
        "verdict": verdict,
        "color": color,
        "checks": [
            {"id": 1, "icon": "R", "label": "ROE",         "pts": pts_roe,  "detail": lbl_roe,  "max": 25},
            {"id": 2, "icon": "D", "label": "DETTE/BENEF", "pts": pts_debt, "detail": lbl_debt, "max": 25},
            {"id": 3, "icon": "F", "label": "FCF YIELD",   "pts": pts_fcf,  "detail": lbl_fcf,  "max": 25},
            {"id": 4, "icon": "M", "label": "MOAT",        "pts": pts_moat, "detail": lbl_moat, "max": 25},
        ]
    }
