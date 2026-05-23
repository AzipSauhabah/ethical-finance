"""
:file: backend/quant/halal_classifier.py
:brief: Classifie les revenus par segment selon les critères AAOIFI / DJIMI.

        Logique :
        1. Reçoit un dict {segment_name: revenue_fraction}  (fractions ∈ [0,1], somme ≈ 1)
        2. Associe chaque segment à une catégorie : HALAL / HARAM / UNCERTAIN
        3. Retourne HalalResult avec le ratio haram total et le détail par segment

        Fallback : si aucun segment n'est disponible, on utilise l'interest_expense
        comme proxy (comportement historique pré-fix).

        Sources de référence :
        - AAOIFI Shari'a Standard No. 21
        - MSCI Islamic Index Methodology
        - Dow Jones Islamic Market Index Methodology

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Classification des segments
# ─────────────────────────────────────────────────────────────────────────────

class SegmentClass(str, Enum):
    HALAL     = "halal"
    HARAM     = "haram"
    UNCERTAIN = "uncertain"   # nécessite analyse manuelle


# Mots-clés haram : si l'un d'eux est trouvé dans le nom du segment → HARAM
_HARAM_KEYWORDS: list[tuple[str, str]] = [
    # Alcool
    ("alcohol",              "Alcool"),
    ("wine",                 "Vins et spiritueux"),
    ("wines",                "Vins et spiritueux"),
    ("spirit",               "Vins et spiritueux"),
    ("spirits",              "Vins et spiritueux"),
    ("beer",                 "Bière"),
    ("brew",                 "Brasserie"),
    ("distill",              "Distillerie"),
    ("champagne",            "Champagne"),
    ("cognac",               "Cognac"),
    ("whisky",               "Whisky"),
    ("whiskey",              "Whisky"),
    ("vodka",                "Vodka"),
    ("rum",                  "Rhum"),
    ("gin",                  "Gin"),
    ("liquor",               "Alcool"),
    ("malt",                 "Malt alcoolisé"),
    # Porc
    ("pork",                 "Porc"),
    ("swine",                "Porc"),
    ("ham",                  "Jambon"),
    ("bacon",                "Bacon"),
    # Jeux d'argent
    ("casino",               "Casino"),
    ("gambling",             "Jeux d'argent"),
    ("gaming",               "Jeux d'argent"),
    ("lottery",              "Loterie"),
    ("betting",              "Paris sportifs"),
    ("wager",                "Paris"),
    # Tabac
    ("tobacco",              "Tabac"),
    ("cigarette",            "Cigarettes"),
    ("cigar",                "Cigares"),
    ("nicotine",             "Nicotine"),
    ("vaping",               "Vapotage"),
    # Finance à intérêt
    ("banking",              "Banque (riba)"),
    ("interest income",      "Revenus d'intérêts"),
    ("financial services",   "Services financiers (riba)"),
    ("insurance",            "Assurance (riba)"),
    # Divertissement adulte
    ("adult entertainment",  "Divertissement adulte"),
    ("pornograph",           "Pornographie"),
    # Armes
    ("weapon",               "Armement"),
    ("weapons",              "Armement"),
    ("defense",              "Défense"),
    ("defence",              "Défense"),
    ("munition",             "Munitions"),
    ("ammunition",           "Munitions"),
]

# Mots-clés qui peuvent sembler sensibles mais sont halal dans le contexte
_HALAL_OVERRIDES: list[str] = [
    "fashion",
    "leather goods",
    "perfume",
    "cosmetic",
    "jewelry",
    "watch",
    "retail",
    "real estate",
    "technology",
    "software",
    "hardware",
    "healthcare",
    "pharmaceutical",
    "food",          # ok sauf si porc — vérifié séparément
    "beverage",      # ok sauf alcool — vérifié par _HARAM_KEYWORDS
    "media",
    "music",
    "film",
    "entertainment", # ok sauf "adult entertainment"
    "hospitality",   # hôtellerie halal possible
    "travel",
    "logistics",
    "energy",
    "renewable",
    "mining",
    "agriculture",
    "textile",
]


# ─────────────────────────────────────────────────────────────────────────────
# Résultat
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SegmentResult:
    name:        str
    fraction:    float              # part du CA total ∈ [0, 1]
    cls:         SegmentClass
    reason:      str = ""


@dataclass
class HalalResult:
    """Résultat complet de la classification halal pour un ticker."""

    haram_ratio:        float                   # fraction haram du CA [0, 1]
    passed:             bool                    # haram_ratio ≤ seuil AAOIFI (5 %)
    threshold:          float = 0.05
    segments:           list[SegmentResult] = field(default_factory=list)
    used_proxy:         bool = False            # True si fallback interest_expense
    proxy_description:  str = ""
    uncertain_ratio:    float = 0.0             # fraction "uncertain"

    @property
    def description(self) -> str:
        if self.used_proxy:
            return f"Proxy : {self.proxy_description} ({self.haram_ratio:.1%})"
        haram_segs = [s for s in self.segments if s.cls == SegmentClass.HARAM]
        if not haram_segs:
            return "Aucun segment haram identifié"
        parts = ", ".join(f"{s.name} ({s.fraction:.0%})" for s in haram_segs)
        return f"Segments haram : {parts} → {self.haram_ratio:.1%} du CA"


# ─────────────────────────────────────────────────────────────────────────────
# Classifieur
# ─────────────────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Lowercase + suppression ponctuation pour matching robuste."""
    return re.sub(r"[^a-z0-9 ]", " ", text.lower())


def classify_segment(name: str) -> tuple[SegmentClass, str]:
    """Retourne (classe, raison) pour un nom de segment."""
    norm = _normalize(name)

    for keyword, label in _HARAM_KEYWORDS:
        if keyword in norm:
            return SegmentClass.HARAM, label

    # Vérifie si un override halal explicite couvre le segment
    for override in _HALAL_OVERRIDES:
        if override in norm:
            return SegmentClass.HALAL, override.title()

    # Segment inconnu : uncertain (ne bloque pas, mais signalé)
    return SegmentClass.UNCERTAIN, "Segment non classifié"


def classify_segments(
    segments: dict[str, float],
    threshold: float = 0.05,
) -> HalalResult:
    """
    Classifie un dict {segment_name: fraction} et retourne HalalResult.

    Args:
        segments:  dict segment → fraction du CA (ex: {"Wines & Spirits": 0.18})
                   Les fractions n'ont pas besoin de sommer exactement à 1.
        threshold: Seuil AAOIFI de revenus non-permissibles (défaut 5 %).

    Returns:
        HalalResult avec haram_ratio et détail par segment.
    """
    if not segments:
        return HalalResult(
            haram_ratio=0.0,
            passed=True,
            threshold=threshold,
            segments=[],
            used_proxy=False,
        )

    results: list[SegmentResult] = []
    haram_total   = 0.0
    uncertain_total = 0.0

    for name, fraction in segments.items():
        # Normalise la fraction (certains providers donnent des %)
        frac = float(fraction)
        if frac > 1.0:
            frac = frac / 100.0
        frac = max(0.0, min(1.0, frac))

        cls, reason = classify_segment(name)
        results.append(SegmentResult(name=name, fraction=frac, cls=cls, reason=reason))

        if cls == SegmentClass.HARAM:
            haram_total += frac
        elif cls == SegmentClass.UNCERTAIN:
            uncertain_total += frac

    # Cap à 1.0 (si les fractions fournies > 1 à cause d'arrondi)
    haram_total = min(1.0, haram_total)

    return HalalResult(
        haram_ratio=haram_total,
        passed=haram_total <= threshold,
        threshold=threshold,
        segments=results,
        used_proxy=False,
        uncertain_ratio=uncertain_total,
    )


def classify_from_proxy(
    interest_expense: Optional[float],
    total_revenue:    Optional[float],
    threshold:        float = 0.05,
) -> HalalResult:
    """
    Fallback : estime le ratio haram via interest_expense / total_revenue.
    Utilisé quand aucun segment n'est disponible.

    Note : ce proxy sous-estime le vrai ratio haram pour les conglomérats
    diversifiés (LVMH, etc.) — c'est précisément le bug que revenue_segments corrige.
    """
    ie  = float(interest_expense or 0)
    rev = float(total_revenue or 1)
    ratio = ie / rev if rev > 0 else 0.0
    ratio = min(1.0, max(0.0, ratio))

    desc = f"interest_expense / total_revenue = {ie:,.0f} / {rev:,.0f}"

    return HalalResult(
        haram_ratio=ratio,
        passed=ratio <= threshold,
        threshold=threshold,
        segments=[],
        used_proxy=True,
        proxy_description=desc,
    )
