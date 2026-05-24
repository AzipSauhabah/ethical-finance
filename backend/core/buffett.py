"""
Buffett Score — 4 critères qualité Warren Buffett
Score 0-100 : ROE + Dette + FCF Yield + Moat (net margin)
Colonnes DB : total_equity, total_revenue, net_margin, interest_bearing_debt,
              fcf_yield, market_cap
"""
from __future__ import annotations
from typing import Any


def _score_roe(roe: float | None) -> tuple[float, str]:
    if roe is None:
        return 0.0, "N/A"
    pct = roe * 100
    if pct >= 20:   pts = 25.0
    elif pct >= 15: pts = 20.0 + (pct - 15) / 5 * 5
    elif pct >= 10: pts = 10.0 + (pct - 10) / 5 * 10
    elif pct > 0:   pts = pct / 10 * 10
    else:           pts = 0.0
    label = "Excellent" if pct >= 20 else "Bon" if pct >= 15 else "Moyen" if pct >= 10 else "Faible"
    return round(pts, 1), f"{pct:.1f}% — {label}"


def _score_debt(ibd: float | None, revenue: float | None) -> tuple[float, str]:
    """Dette portant intérêts / revenue ≤ 100% = sain."""
    if not ibd or not revenue or revenue <= 0:
        return 0.0, "N/A"
    ratio = ibd / revenue
    if ratio <= 0.5:    pts = 25.0
    elif ratio <= 1.0:  pts = 25.0 - (ratio - 0.5) / 0.5 * 10
    elif ratio <= 2.0:  pts = 15.0 - (ratio - 1.0) / 1.0 * 10
    elif ratio <= 4.0:  pts = max(0.0, 5.0 - (ratio - 2.0) / 2.0 * 5)
    else:               pts = 0.0
    label = "Excellente" if ratio <= 0.5 else "Bonne" if ratio <= 1.0 else "Elevee" if ratio <= 2.0 else "Critique"
    return round(pts, 1), f"{ratio:.2f}x CA — {label}"


def _score_fcf(fcf_yield: float | None) -> tuple[float, str]:
    """FCF yield ≥ 5% = excellent (colonne fcf_yield déjà en DB)."""
    if fcf_yield is None:
        return 0.0, "N/A"
    pct = fcf_yield * 100
    if pct >= 8:    pts = 25.0
    elif pct >= 5:  pts = 18.0 + (pct - 5) / 3 * 7
    elif pct >= 2:  pts = 8.0  + (pct - 2) / 3 * 10
    elif pct > 0:   pts = pct / 2 * 8
    else:           pts = 0.0
    label = "Excellent" if pct >= 8 else "Bon" if pct >= 5 else "Moyen" if pct >= 2 else "Faible"
    return round(pts, 1), f"{pct:.1f}% — {label}"


def _score_moat(net_margin: float | None) -> tuple[float, str]:
    """Net margin ≥ 20% proxy avantage concurrentiel."""
    if net_margin is None:
        return 0.0, "N/A"
    pct = net_margin * 100
    if pct >= 25:   pts = 25.0
    elif pct >= 20: pts = 18.0 + (pct - 20) / 5 * 7
    elif pct >= 10: pts = 8.0  + (pct - 10) / 10 * 10
    elif pct > 0:   pts = pct / 10 * 8
    else:           pts = 0.0
    label = "Fort" if pct >= 25 else "Solide" if pct >= 20 else "Moyen" if pct >= 10 else "Faible"
    return round(pts, 1), f"{pct:.1f}% — {label}"


def compute_buffett_score(fund: dict[str, Any], market_cap: float | None = None) -> dict:
    """Calcule le Buffett Score depuis un dict de fundamentals (noms colonnes DB)."""
    # ROE = net_margin * total_revenue / total_equity
    net_margin  = fund.get("net_margin")
    total_rev   = fund.get("total_revenue")
    total_eq    = fund.get("total_equity")
    ibd         = fund.get("interest_bearing_debt") or fund.get("total_debt")
    fcf_yield   = fund.get("fcf_yield")

    roe = None
    if net_margin and total_rev and total_eq and total_eq > 0:
        net_income = net_margin * total_rev
        roe = net_income / total_eq

    pts_roe,  lbl_roe  = _score_roe(roe)
    pts_debt, lbl_debt = _score_debt(ibd, total_rev)
    pts_fcf,  lbl_fcf  = _score_fcf(fcf_yield)
    pts_moat, lbl_moat = _score_moat(net_margin)

    total = pts_roe + pts_debt + pts_fcf + pts_moat

    if total >= 80:   verdict, color = "Qualite exceptionnelle", "#16a34a"
    elif total >= 60: verdict, color = "Bonne qualite",          "#65a30d"
    elif total >= 40: verdict, color = "Qualite moyenne",        "#ca8a04"
    else:             verdict, color = "Qualite insuffisante",   "#dc2626"

    return {
        "score":   round(total, 1),
        "verdict": verdict,
        "color":   color,
        "checks": [
            {"id": 1, "icon": "R", "label": "ROE",          "pts": pts_roe,  "detail": lbl_roe,  "max": 25},
            {"id": 2, "icon": "D", "label": "DETTE/CA",     "pts": pts_debt, "detail": lbl_debt, "max": 25},
            {"id": 3, "icon": "F", "label": "FCF YIELD",    "pts": pts_fcf,  "detail": lbl_fcf,  "max": 25},
            {"id": 4, "icon": "M", "label": "MARGE NETTE",  "pts": pts_moat, "detail": lbl_moat, "max": 25},
        ]
    }
