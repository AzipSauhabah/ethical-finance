#!/usr/bin/env python3
"""
apply_patch.py — Applique le patch Sharia critère 4 sur le repo ethical-finance.

Usage (depuis la racine du projet) :
    python apply_patch.py

Ce script :
  1. Patch backend/core/registry.py  → ajoute l'import halal_classifier + remplace run_sharia_screen()
  2. Vérifie la syntaxe Python des fichiers patchés
  3. Affiche un résumé des modifications

En cas d'erreur, les fichiers originaux sont restaurés depuis les backups .bak.
"""

import ast
import re
import shutil
import sys
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def backup(path: Path) -> Path:
    bak = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, bak)
    print(f"  ✓ Backup : {bak}")
    return bak


def restore(path: Path) -> None:
    bak = path.with_suffix(path.suffix + ".bak")
    if bak.exists():
        shutil.copy2(bak, path)
        print(f"  ↩ Restored {path} from backup")


def check_syntax(path: Path) -> bool:
    try:
        ast.parse(path.read_text(encoding="utf-8"))
        print(f"  ✓ Syntax OK : {path}")
        return True
    except SyntaxError as e:
        print(f"  ✗ Syntax ERROR in {path}: {e}", file=sys.stderr)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Patch 1 : backend/core/registry.py
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY_PATH = Path("backend/core/registry.py")

# Import à injecter (après les imports existants de backend.*)
NEW_IMPORT_LINE = (
    "from backend.quant.halal_classifier import (\n"
    "    classify_segments,\n"
    "    classify_from_proxy,\n"
    "    SegmentClass,\n"
    ")\n"
)

# Nouveau corps de run_sharia_screen
NEW_SHARIA_FUNC = '''def run_sharia_screen(info: dict) -> ShariaScreen:
    """AAOIFI / Dow Jones Islamic Market style screen.

    Quatre critères :
      1. Secteur     — activité halal (blacklist sectorielle)
      2. Ratio dette — interest-bearing debt / market cap ≤ 33 %
      3. Liquidité   — (cash + interest-bearing securities) / market cap ≤ 33 %
      4. Revenus     — revenus non-permissibles ≤ 5 % du CA total

    Critère 4 :
      - Source primaire : revenue_segments JSONB (FMP ou EDGAR)
      - Fallback proxy  : interest_expense / total_revenue
    """
    checks: list[ScreenCheck] = []
    sector   = (info.get("sector",   "") or "").lower()
    industry = (info.get("industry", "") or "").lower()
    combined = f"{sector} {industry}"

    # Critère 1 : Activité halal
    matched = [s for s in SHARIA_SECTOR_BLACKLIST if s in combined]
    checks.append(ScreenCheck(
        name="1. Activité autorisée (Sharia)",
        passed=len(matched) == 0,
        description=(
            "Aucune activité non-conforme détectée"
            if not matched
            else f"Activités non-conformes : {', '.join(matched)}"
        ),
    ))

    # Critère 2 : Ratio dette / capitalisation ≤ 33 %
    cap        = float(info.get("market_cap", 0) or 0)
    debt       = float(info.get("total_debt", 0) or 0)
    debt_ratio = (debt / cap) if cap > 0 else 0.0
    checks.append(ScreenCheck(
        name="2. Ratio dette à intérêts (≤ 33 %)",
        passed=debt_ratio <= SHARIA_DEBT_RATIO_MAX,
        value=debt_ratio,
        threshold=SHARIA_DEBT_RATIO_MAX,
        description=f"Dette portant intérêts / capitalisation = {debt_ratio:.1%}",
    ))

    # Critère 3 : Ratio liquidités / capitalisation ≤ 33 %
    cash      = float(info.get("total_cash", 0) or 0)
    liq_ratio = (cash / cap) if cap > 0 else 0.0
    checks.append(ScreenCheck(
        name="3. Ratio liquidités productives (≤ 33 %)",
        passed=liq_ratio <= SHARIA_LIQUIDITY_RATIO_MAX,
        value=liq_ratio,
        threshold=SHARIA_LIQUIDITY_RATIO_MAX,
        description=f"Trésorerie portant intérêts / capitalisation = {liq_ratio:.1%}",
    ))

    # Critère 4 : Revenus non-permissibles ≤ 5 %
    revenue_segments = info.get("revenue_segments")  # dict ou None

    if revenue_segments and isinstance(revenue_segments, dict) and len(revenue_segments) > 0:
        halal_result = classify_segments(
            revenue_segments, threshold=SHARIA_NON_PERMISSIBLE_INCOME_MAX
        )
        haram_segs     = [s for s in halal_result.segments if s.cls == SegmentClass.HARAM]
        uncertain_segs = [s for s in halal_result.segments if s.cls == SegmentClass.UNCERTAIN]

        if haram_segs:
            detail = "Segments haram : " + ", ".join(
                f"{s.name} ({s.fraction:.0%})" for s in haram_segs
            )
        else:
            detail = "Aucun segment haram identifié"

        if uncertain_segs and halal_result.uncertain_ratio > 0.10:
            detail += (
                f" | Non-classifiés : {halal_result.uncertain_ratio:.0%}"
                " (vérification manuelle conseillée)"
            )

        checks.append(ScreenCheck(
            name="4. Revenus non-permissibles (≤ 5 %)",
            passed=halal_result.passed,
            value=halal_result.haram_ratio,
            threshold=SHARIA_NON_PERMISSIBLE_INCOME_MAX,
            description=f"{detail} → {halal_result.haram_ratio:.1%} du CA",
        ))
    else:
        interest_expense = float(info.get("interest_expense", 0) or 0)
        total_revenue    = float(info.get("total_revenue",    1) or 1)
        proxy_result = classify_from_proxy(
            interest_expense, total_revenue,
            threshold=SHARIA_NON_PERMISSIBLE_INCOME_MAX,
        )
        checks.append(ScreenCheck(
            name="4. Revenus non-permissibles (≤ 5 %) [proxy]",
            passed=proxy_result.passed,
            value=proxy_result.haram_ratio,
            threshold=SHARIA_NON_PERMISSIBLE_INCOME_MAX,
            description=(
                "⚠ Proxy utilisé (segments non disponibles) — "
                f"interest_expense / total_revenue = {proxy_result.haram_ratio:.1%}. "
                "Lancer l'enrichissement des segments pour plus de précision."
            ),
        ))

    passed     = all(c.passed for c in checks)
    soft_fails = sum(1 for c in checks if not c.passed)
    score      = max(0.0, 1.0 - soft_fails * 0.25) if passed else 0.0

    return ShariaScreen(passed=passed, score=score, checks=checks)
'''


def patch_registry(path: Path) -> bool:
    """Patche registry.py pour le critère 4 amélioré."""
    content = path.read_text(encoding="utf-8")

    # ── 1. Injecte l'import halal_classifier si absent ────────────────────────
    if "halal_classifier" not in content:
        # Cherche le dernier import 'from backend.' et insère après
        last_import_match = None
        for m in re.finditer(r"^from backend\.[^\n]+\n", content, re.MULTILINE):
            last_import_match = m
        if last_import_match:
            insert_pos = last_import_match.end()
            content = content[:insert_pos] + NEW_IMPORT_LINE + content[insert_pos:]
            print("  ✓ Import halal_classifier injecté")
        else:
            # Fallback : insère avant la première définition
            content = NEW_IMPORT_LINE + "\n" + content
            print("  ✓ Import halal_classifier ajouté en tête")
    else:
        print("  · Import halal_classifier déjà présent")

    # ── 2. Remplace run_sharia_screen() ──────────────────────────────────────
    # Pattern : def run_sharia_screen(...)  jusqu'à la prochaine def/class de
    # même niveau d'indentation (ou fin de fichier)
    pattern = re.compile(
        r"^def run_sharia_screen\(.*?(?=\n^(?:def |class |\Z))",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(content)
    if match:
        content = content[:match.start()] + NEW_SHARIA_FUNC + "\n\n" + content[match.end():]
        print("  ✓ run_sharia_screen() remplacée")
    else:
        print(
            "  ✗ run_sharia_screen() non trouvée dans registry.py — vérification manuelle requise",
            file=sys.stderr,
        )
        return False

    path.write_text(content, encoding="utf-8")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    print("\n═══ Patch Sharia critère 4 — ethical-finance ═══\n")

    # Vérification de l'emplacement
    if not REGISTRY_PATH.exists():
        print(
            f"✗ {REGISTRY_PATH} introuvable.\n"
            "  Lancer ce script depuis la racine du projet (là où se trouve backend/).",
            file=sys.stderr,
        )
        return 1

    # Backup
    print("1. Sauvegarde des fichiers originaux...")
    bak_registry = backup(REGISTRY_PATH)

    # Application du patch
    print("\n2. Application du patch registry.py...")
    ok = patch_registry(REGISTRY_PATH)
    if not ok:
        print("  ↩ Restauration depuis backup...", file=sys.stderr)
        restore(REGISTRY_PATH)
        return 1

    # Vérification syntaxe
    print("\n3. Vérification de la syntaxe...")
    if not check_syntax(REGISTRY_PATH):
        restore(REGISTRY_PATH)
        return 1

    print("\n═══ Patch appliqué avec succès ═══")
    print("""
Prochaines étapes :
  1. Appliquer la migration DB :
     psql -h 192.168.1.47 -p 5433 -U sauhabah -d ethical_finance \\
          -f migrations/0003_revenue_segments.sql

  2. Copier les nouveaux modules dans le repo :
     cp backend/quant/halal_classifier.py  <repo>/backend/quant/
     cp backend/core/fmp_segments.py       <repo>/backend/core/
     cp backend/core/sec_segments.py       <repo>/backend/core/
     cp backend/core/segment_enricher.py   <repo>/backend/core/

  3. Tester le classifieur :
     python -c "
     from backend.quant.halal_classifier import classify_segments
     segs = {'Wines & Spirits': 0.18, 'Fashion & Leather Goods': 0.44,
             'Perfumes & Cosmetics': 0.12, 'Watches & Jewelry': 0.13,
             'Selective Retailing': 0.13}
     r = classify_segments(segs)
     print(f'LVMH haram: {r.haram_ratio:.1%} — passed: {r.passed}')
     "
     # Attendu : haram: 18.0% — passed: False

  4. Enrichir les segments (optionnel, se fait aussi au daily_update) :
     python -c "
     import asyncio
     from backend.core.segment_enricher import enrich_universe_segments
     # asyncio.run(enrich_universe_segments(FMP_KEY, db_conn, universe='cac40'))
     "

  5. Déployer sur le NAS :
     git add -A && git commit -m 'feat(sharia): critère 4 revenus par segment'
     git push
     # Sur le NAS :
     # git pull && sudo docker-compose up -d --build
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
