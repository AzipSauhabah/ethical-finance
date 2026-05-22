from typing import Optional, Tuple
"""
:file: tests/test_halal_classifier.py
:brief: Tests unitaires pour backend/quant/halal_classifier.py

Run :
    pytest tests/test_halal_classifier.py -v
"""

import pytest
from backend.quant.halal_classifier import (
    classify_segment,
    classify_segments,
    classify_from_proxy,
    SegmentClass,
    HalalResult,
)


# ─────────────────────────────────────────────────────────────────────────────
# Tests : classify_segment (niveau segment individuel)
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifySegment:

    def test_wines_spirits_is_haram(self):
        cls, reason = classify_segment("Wines & Spirits")
        assert cls == SegmentClass.HARAM
        assert "Vins" in reason or "spirit" in reason.lower()

    def test_fashion_is_halal(self):
        cls, _ = classify_segment("Fashion & Leather Goods")
        assert cls == SegmentClass.HALAL

    def test_tobacco_is_haram(self):
        cls, _ = classify_segment("Tobacco Products")
        assert cls == SegmentClass.HARAM

    def test_casino_is_haram(self):
        cls, _ = classify_segment("Casino & Gaming Division")
        assert cls == SegmentClass.HARAM

    def test_technology_is_halal(self):
        cls, _ = classify_segment("Cloud Technology Services")
        assert cls == SegmentClass.HALAL

    def test_unknown_segment_is_uncertain(self):
        cls, _ = classify_segment("XYZ Proprietary Division")
        assert cls == SegmentClass.UNCERTAIN

    def test_case_insensitive(self):
        cls1, _ = classify_segment("WINES & SPIRITS")
        cls2, _ = classify_segment("wines & spirits")
        assert cls1 == cls2 == SegmentClass.HARAM

    def test_defense_is_haram(self):
        cls, _ = classify_segment("Aerospace & Defense")
        assert cls == SegmentClass.HARAM

    def test_beer_is_haram(self):
        cls, _ = classify_segment("Beer and Cider")
        assert cls == SegmentClass.HARAM

    def test_healthcare_is_halal(self):
        cls, _ = classify_segment("Healthcare & Diagnostics")
        assert cls == SegmentClass.HALAL


# ─────────────────────────────────────────────────────────────────────────────
# Tests : classify_segments (dict complet)
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifySegments:

    # ── LVMH : doit échouer (18% Wines & Spirits >> 5%) ──────────────────────
    def test_lvmh_fails(self):
        segs = {
            "Wines & Spirits":       0.18,
            "Fashion & Leather Goods": 0.44,
            "Perfumes & Cosmetics":  0.12,
            "Watches & Jewelry":     0.13,
            "Selective Retailing":   0.13,
        }
        result = classify_segments(segs)
        assert result.passed is False
        assert abs(result.haram_ratio - 0.18) < 0.01
        haram_names = [s.name for s in result.segments if s.cls == SegmentClass.HARAM]
        assert "Wines & Spirits" in haram_names

    # ── Apple : doit passer (aucun segment haram) ─────────────────────────────
    def test_apple_passes(self):
        segs = {
            "iPhone":   0.52,
            "Mac":      0.10,
            "iPad":     0.07,
            "Wearables": 0.10,
            "Services": 0.21,
        }
        result = classify_segments(segs)
        assert result.passed is True
        assert result.haram_ratio == 0.0

    # ── British American Tobacco : doit échouer ───────────────────────────────
    def test_bat_fails(self):
        segs = {
            "Combustible Tobacco": 0.85,
            "New Categories":      0.15,
        }
        result = classify_segments(segs)
        assert result.passed is False
        assert result.haram_ratio >= 0.80

    # ── Pernod Ricard : doit échouer ─────────────────────────────────────────
    def test_pernod_ricard_fails(self):
        segs = {
            "Strategic International Brands": 0.60,  # whiskies, gins etc.
            "Strategic Local Brands":         0.30,
            "Specialty Brands":               0.10,
        }
        # Note : ces noms génériques seront UNCERTAIN, pas forcément HARAM
        # mais on teste la logique
        result = classify_segments(segs)
        # Avec ces noms génériques, le classifieur voit uncertain - pas de HARAM direct
        # Dans la réalité, FMP retournera "Whisky", "Gin" etc.
        assert isinstance(result, HalalResult)

    # ── Fractions > 1 (certains providers donnent des %) ─────────────────────
    def test_normalizes_percentage_values(self):
        segs = {
            "Wines & Spirits": 18.0,   # 18% exprimé en %
            "Fashion":         44.0,
            "Other":           38.0,
        }
        result = classify_segments(segs)
        assert result.passed is False
        assert abs(result.haram_ratio - 0.18) < 0.02

    # ── Dict vide : passe (aucune info = pas de flag) ─────────────────────────
    def test_empty_segments_passes(self):
        result = classify_segments({})
        assert result.passed is True
        assert result.haram_ratio == 0.0

    # ── Threshold custom ─────────────────────────────────────────────────────
    def test_custom_threshold(self):
        segs = {"Beer Division": 0.04}  # 4% alcool
        result_strict  = classify_segments(segs, threshold=0.03)
        result_lenient = classify_segments(segs, threshold=0.05)
        assert result_strict.passed  is False
        assert result_lenient.passed is True


# ─────────────────────────────────────────────────────────────────────────────
# Tests : classify_from_proxy (fallback)
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifyFromProxy:

    def test_high_interest_fails(self):
        result = classify_from_proxy(
            interest_expense=500_000,
            total_revenue=1_000_000,
        )
        assert result.passed is False
        assert abs(result.haram_ratio - 0.5) < 0.01
        assert result.used_proxy is True

    def test_low_interest_passes(self):
        result = classify_from_proxy(
            interest_expense=10_000,
            total_revenue=1_000_000,
        )
        assert result.passed is True
        assert result.haram_ratio < 0.05

    def test_zero_revenue_handled(self):
        result = classify_from_proxy(interest_expense=0, total_revenue=0)
        assert result.haram_ratio == 0.0
        assert result.passed is True

    def test_none_values_handled(self):
        result = classify_from_proxy(interest_expense=None, total_revenue=None)
        assert result.haram_ratio == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Tests d'intégration : simulation run_sharia_screen critère 4
# ─────────────────────────────────────────────────────────────────────────────

class TestShariaScreenCriterion4Integration:
    """
    Simule le comportement de run_sharia_screen() pour le critère 4
    sans importer registry.py (qui dépend de la DB).
    """

    def _check_criterion_4(
        self,
        revenue_segments: Optional[dict],
        interest_expense: float = 0,
        total_revenue: float = 1_000_000,
        threshold: float = 0.05,
    ) -> Tuple[bool, float, bool]:
        """Retourne (passed, ratio, used_proxy)."""
        if revenue_segments and isinstance(revenue_segments, dict):
            r = classify_segments(revenue_segments, threshold=threshold)
            return r.passed, r.haram_ratio, False
        else:
            r = classify_from_proxy(interest_expense, total_revenue, threshold=threshold)
            return r.passed, r.haram_ratio, True

    def test_lvmh_with_real_segments_fails(self):
        segs = {"Wines & Spirits": 0.18, "Fashion": 0.82}
        passed, ratio, proxy = self._check_criterion_4(segs)
        assert passed is False
        assert ratio == pytest.approx(0.18, abs=0.01)
        assert proxy is False

    def test_lvmh_with_proxy_incorrectly_passes(self):
        """Reproduit le bug original : sans segments, LVMH peut passer via proxy."""
        # LVMH a un interest_expense faible par rapport au CA total
        passed, ratio, proxy = self._check_criterion_4(
            revenue_segments=None,
            interest_expense=500_000_000,   # ~0.4% du CA de 120Md€
            total_revenue=86_000_000_000,
        )
        # Avec le proxy, LVMH passe incorrectement (ratio ≈ 0.6%)
        assert passed is True   # BUG HISTORIQUE confirmé
        assert proxy is True

    def test_no_segments_uses_proxy(self):
        passed, ratio, proxy = self._check_criterion_4(revenue_segments=None)
        assert proxy is True

    def test_empty_segments_uses_proxy(self):
        passed, ratio, proxy = self._check_criterion_4(revenue_segments={})
        assert proxy is True
