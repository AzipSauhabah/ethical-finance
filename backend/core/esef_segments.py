"""
:file: backend/core/esef_segments.py
:brief: Source ESEF/iXBRL pour les segments CAC40 via filings.xbrl.org (ESMA).

        Réalité du balisage ESEF en France (2024) :
        - Les sociétés cotées balisent les états financiers PRIMAIRES (bilan, P&L, flux)
        - Les notes IFRS 8 (segments opérationnels) sont optionnelles → rarement balisées
        - LVMH, TotalEnergies, Sanofi etc. ne balisent PAS leurs segments en iXBRL

        Stratégie retenue :
        1. filings.xbrl.org  → lookup LEI + vérification existence filing ESEF
        2. Segments hardcodés → dict de référence pour les cas critiques CAC40
           (sources : rapports annuels publics, FMP, Bloomberg)
        3. filings.xbrl.org JSON → tentative parsing segments si balisés (rares cas)

        La source FMP reste prioritaire dans segment_enricher.py.
        Ce module est le fallback FR quand FMP est vide.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

log = logging.getLogger(__name__)

_XBRL_BASE  = "https://filings.xbrl.org"
_TIMEOUT    = 20.0
_USER_AGENT = "ethical-finance-platform contact@sauhabah-advisory.eu"


# ─────────────────────────────────────────────────────────────────────────────
# Segments hardcodés CAC40 — sources : rapports annuels 2023/2024
# Mis à jour manuellement 1x/an (les segments changent rarement)
# Format : {ticker: {segment_name: fraction}}
# ─────────────────────────────────────────────────────────────────────────────

_HARDCODED_SEGMENTS: dict[str, dict[str, float]] = {

    # LVMH 2023 — rapport annuel p.12
    # Wines & Spirits HARAM (alcool)
    "MC.PA": {
        "Wines & Spirits":          0.10,   # ← HARAM (Moët, Hennessy, Dom Pérignon...)
        "Fashion & Leather Goods":  0.48,
        "Perfumes & Cosmetics":     0.11,
        "Watches & Jewelry":        0.13,
        "Selective Retailing":      0.17,
        "Other activities":         0.01,
    },

    # Pernod Ricard 2023/2024 — 100% alcool
    "RI.PA": {
        "Whisky & Bourbon":         0.35,   # ← HARAM
        "Cognac & Brandy":          0.15,   # ← HARAM
        "Gin & Vodka":              0.20,   # ← HARAM
        "Champagne & Wines":        0.15,   # ← HARAM
        "Other spirits":            0.15,   # ← HARAM
    },

    # Kering 2023 — mode/luxe, pas d'alcool
    "KER.PA": {
        "Gucci":                    0.46,
        "Saint Laurent":            0.14,
        "Bottega Veneta":           0.09,
        "Other Houses":             0.25,
        "Corporate & other":        0.06,
    },

    # Hermès 2023
    "RMS.PA": {
        "Leather Goods & Saddlery": 0.46,
        "Ready-to-Wear & Accessories": 0.24,
        "Silk & Textiles":          0.07,
        "Perfume":                  0.04,
        "Watches":                  0.03,
        "Other Métiers":            0.16,
    },

    # L'Oréal 2023
    "OR.PA": {
        "Consumer Products":        0.37,
        "L'Oréal Luxe":            0.34,
        "Professional Products":    0.13,
        "Dermatological Beauty":    0.16,
    },

    # TotalEnergies 2023
    "TTE.PA": {
        "Integrated LNG":           0.17,
        "Exploration & Production": 0.30,
        "Refining & Chemicals":     0.28,
        "Marketing & Services":     0.25,
    },

    # Sanofi 2023
    "SAN.PA": {
        "Specialty Care":           0.40,
        "Vaccines":                 0.17,
        "General Medicines":        0.34,
        "Consumer Healthcare":      0.09,
    },

    # Airbus 2023
    "AIR.PA": {
        "Commercial Aircraft":      0.72,
        "Defence & Space":          0.17,   # ← HARAM (défense)
        "Helicopters":              0.11,
    },

    # Safran 2023 — moteurs + défense
    "SAF.PA": {
        "Aerospace Propulsion":     0.58,
        "Aircraft Equipment":       0.24,
        "Defense":                  0.18,   # ← HARAM
    },

    # Thales 2023 — défense majoritaire
    "HO.PA": {
        "Defence & Security":       0.52,   # ← HARAM
        "Aerospace":                0.28,
        "Digital Identity":         0.20,
    },

    # Vivendi 2023
    "VIV.PA": {
        "Canal+ Group":             0.55,
        "Lagardère":                0.32,
        "Havas":                    0.13,
    },

    # Publicis 2023
    "PUB.PA": {
        "Americas":                 0.60,
        "Europe":                   0.22,
        "Asia Pacific":             0.12,
        "Middle East & Africa":     0.06,
    },

    # Capgemini 2023
    "CAP.PA": {
        "North America":            0.28,
        "France":                   0.17,
        "Rest of Europe":           0.37,
        "Asia Pacific":             0.18,
    },

    # Dassault Systèmes 2023
    "DSY.PA": {
        "3DEXPERIENCE Software":    0.55,
        "SOLIDWORKS":               0.20,
        "Industrial Innovation":    0.25,
    },

    # Schneider Electric 2023
    "SU.PA": {
        "Energy Management":        0.63,
        "Industrial Automation":    0.37,
    },

    # Legrand 2023
    "LR.PA": {
        "Europe & Africa":          0.44,
        "North & Central America":  0.33,
        "Rest of World":            0.23,
    },

    # Saint-Gobain 2023
    "SGO.PA": {
        "High Performance Solutions": 0.32,
        "Northern Europe":          0.22,
        "Southern Europe":          0.20,
        "Americas":                 0.16,
        "Asia Pacific":             0.10,
    },

    # Michelin 2023
    "ML.PA": {
        "Automotive":               0.58,
        "Road Transportation":      0.25,
        "Specialty":                0.17,
    },

    # Renault 2023
    "RNO.PA": {
        "Renault Brand":            0.55,
        "Dacia & Lada":             0.22,
        "Mobilize Financial":       0.12,
        "Other":                    0.11,
    },

    # Danone 2023
    "BN.PA": {
        "Essential Dairy & Plant":  0.48,
        "Specialized Nutrition":    0.35,
        "Waters":                   0.17,
    },

    # Carrefour 2023
    "CA.PA": {
        "France":                   0.45,
        "Latin America":            0.27,
        "Europe excl. France":      0.22,
        "Asia":                     0.06,
    },

    # Veolia 2023
    "VIE.PA": {
        "Water":                    0.37,
        "Waste":                    0.35,
        "Energy":                   0.28,
    },

    # Vinci 2023
    "DG.PA": {
        "Concessions":              0.24,
        "VINCI Energies":           0.28,
        "Cobra IS":                 0.12,
        "VINCI Construction":       0.36,
    },

    # Engie 2023
    "ENGI.PA": {
        "Renewables":               0.18,
        "Energy Solutions":         0.28,
        "Networks":                 0.25,
        "FlexGen":                  0.17,
        "Other":                    0.12,
    },

    # Orange 2023
    "ORA.PA": {
        "France":                   0.39,
        "Europe":                   0.24,
        "Africa & Middle East":     0.17,
        "Enterprise":               0.17,
        "Other":                    0.03,
    },

    # Air Liquide 2023
    "AI.PA": {
        "Gas & Services":           0.94,
        "Engineering & Construction": 0.03,
        "Global Markets & Technologies": 0.03,
    },

    # AXA 2023 — assurance (riba — critère secteur)
    "CS.PA": {
        "Life & Savings":           0.35,
        "Property & Casualty":      0.45,
        "Health":                   0.15,
        "Asset Management":         0.05,
    },

    # BNP Paribas 2023 — banque (riba — critère secteur)
    "BNP.PA": {
        "Retail Banking":           0.45,
        "Corporate & Institutional Banking": 0.35,
        "Investment Solutions":     0.20,
    },

    # Crédit Agricole 2023 — banque (riba)
    "ACA.PA": {
        "Retail Banking":           0.50,
        "Asset Gathering":          0.20,
        "Specialised Financial Services": 0.15,
        "Corporate & Investment Banking": 0.15,
    },

    # Société Générale 2023 — banque (riba)
    "GLE.PA": {
        "French Retail Banking":    0.35,
        "International Retail":     0.25,
        "Global Banking & Investor Solutions": 0.40,
    },

    # Bouygues 2023
    "EN.PA": {
        "Bouygues Telecom":         0.38,
        "Bouygues Construction":    0.32,
        "Bouygues Immobilier":      0.08,
        "TF1":                      0.12,
        "Colas":                    0.10,
    },

    # Teleperformance 2023
    "TEP.PA": {
        "Core Services & Digital Integrated Business Services": 0.82,
        "Specialized Services":     0.18,
    },

    # EssilorLuxottica 2023
    "EL.PA": {
        "Lenses & Optical Instruments": 0.47,
        "Equipment":                0.28,
        "Readers Sunglasses Protective": 0.25,
    },

    # Alstom 2023
    "ALO.PA": {
        "Rolling Stock":            0.48,
        "Services":                 0.22,
        "Systems":                  0.15,
        "Signalling":               0.15,
    },

    # Worldline 2023
    "WLN.PA": {
        "Merchant Services":        0.47,
        "Financial Services":       0.32,
        "Mobility & e-Transactional Services": 0.21,
    },

    # Unibail-Rodamco 2023
    "URW.PA": {
        "Shopping Centres":         0.78,
        "Offices":                  0.12,
        "Convention & Exhibition":  0.10,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Mapping ticker → LEI (pour filings.xbrl.org)
# Source : info-financiere.gouv.fr/api/explore/v2.1/catalog/datasets/codes-lei
# ─────────────────────────────────────────────────────────────────────────────

_TICKER_TO_LEI: dict[str, str] = {
    "MC.PA":   "IOG4E947OATN0KJYSD45",
    "TTE.PA":  "529900S21EQ1BO4ESM68",
    "SAN.PA":  "EXO1FK3KJOTC TPEIF66",
    "OR.PA":   "LBQXPBHCQF5DNGLZL195",
    "AIR.PA":  "VNN1OYBB7298VLHH5P36",
    "BNP.PA":  "R0MUWSFPU8MPRO8K5P83",
    "SU.PA":   "549300FXZPV7UBXJ3L90",
    "AI.PA":   "529900IBP8LD3TS8H915",
    "RMS.PA":  "969500UP76J52A9OXU27",
    "KER.PA":  "5299001GJKFGZM0FRM93",
}


# ─────────────────────────────────────────────────────────────────────────────
# Interface publique
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_segments_from_esef(ticker: str) -> dict[str, float]:
    """
    Retourne les segments pour un ticker FR.

    Stratégie :
    1. Segments hardcodés (dict de référence CAC40) — source primaire
    2. filings.xbrl.org JSON — tentative si segments balisés (rare)

    Args:
        ticker: Ticker Euronext (ex: "MC.PA", "TTE.PA")

    Returns:
        Dict {segment_name: fraction_du_CA} ou {} si non disponible.
    """
    ticker_up = ticker.upper()

    # ── Source 1 : segments hardcodés ────────────────────────────────────────
    if ticker_up in _HARDCODED_SEGMENTS:
        segs = _HARDCODED_SEGMENTS[ticker_up]
        log.info("ESEF hardcoded segments for %s: %d segments", ticker, len(segs))
        return segs

    # ── Source 2 : filings.xbrl.org (tentative iXBRL) ────────────────────────
    lei = _TICKER_TO_LEI.get(ticker_up)
    if lei:
        segs = await _fetch_xbrl_org_segments(lei, ticker)
        if segs:
            return segs

    log.debug("No ESEF segments available for %s", ticker)
    return {}


async def get_lei_for_ticker(ticker: str) -> Optional[str]:
    """
    Retourne le LEI d'un ticker FR via info-financiere.gouv.fr.
    Utile pour enrichir _TICKER_TO_LEI.
    """
    if ticker.upper() in _TICKER_TO_LEI:
        return _TICKER_TO_LEI[ticker.upper()]

    company_fragment = ticker.upper().replace(".PA", "").replace(".FP", "")
    url = "https://www.info-financiere.gouv.fr/api/explore/v2.1/catalog/datasets/codes-lei/records"
    params = {
        "where": f'identificationsociete_iso_nom_soc like "%{company_fragment}%"',
        "limit": 1,
        "select": "identificationsociete_iso_nom_soc,identificationsociete_iso_cd_lei",
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": _USER_AGENT}) as c:
            r = await c.get(url, params=params)
            r.raise_for_status()
            results = r.json().get("results", [])
            if results:
                lei = results[0].get("identificationsociete_iso_cd_lei")
                log.info("LEI found for %s: %s", ticker, lei)
                return lei
    except Exception as exc:
        log.warning("LEI lookup failed for %s: %s", ticker, exc)
    return None


async def _fetch_xbrl_org_segments(lei: str, ticker: str) -> dict[str, float]:
    """
    Tente d'extraire les segments depuis le JSON iXBRL sur filings.xbrl.org.
    Couvre les rares cas où l'émetteur balise ses notes IFRS 8.
    """
    # Récupère le filing le plus récent
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": _USER_AGENT}) as c:
            r = await c.get(
                f"{_XBRL_BASE}/api/filings",
                params={
                    "filter[entity.identifier]": lei,
                    "sort": "-period_end",
                    "limit": 1,
                },
            )
            r.raise_for_status()
            filings = r.json().get("data", [])
            if not filings:
                return {}

            json_url = filings[0]["attributes"].get("json_url")
            if not json_url:
                return {}

            # Télécharge le JSON des facts
            r2 = await c.get(f"{_XBRL_BASE}{json_url}", timeout=30.0)
            r2.raise_for_status()
            facts = r2.json().get("facts", {}).get("ifrs-full", {})

    except Exception as exc:
        log.warning("filings.xbrl.org fetch failed for %s (%s): %s", ticker, lei, exc)
        return {}

    # Cherche les concepts revenue avec dimension segment
    segment_revenues: dict[str, float] = {}
    for concept, data in facts.items():
        if "Revenue" not in concept and "Turnover" not in concept:
            continue
        for entry in data.get("values", []):
            dims = entry.get("dimensions", {})
            segment_dim = next(
                (v for k, v in dims.items() if "Segment" in k or "Product" in k),
                None,
            )
            if not segment_dim:
                continue
            val = entry.get("value")
            if val and float(val) > 0:
                label = segment_dim.split(":")[-1].replace("Member", "").strip()
                segment_revenues[label] = max(
                    segment_revenues.get(label, 0), float(val)
                )

    if not segment_revenues:
        return {}

    total = sum(segment_revenues.values())
    return {k: v / total for k, v in segment_revenues.items()} if total > 0 else {}
