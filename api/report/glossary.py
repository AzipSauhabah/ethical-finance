"""
:file: api/report/glossary.py
:brief: Financial glossary — definitions appended to every PDF report.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

GLOSSARY: list[dict[str, str]] = [
    {"term": "CAGR",                "fr": "Taux de croissance annualisé composé",
     "def": "Taux de rendement annualisé d'un investissement sur plusieurs années."},
    {"term": "Sharpe Ratio",        "fr": "Ratio de Sharpe",
     "def": "Excès de rendement par unité de risque total (écart-type)."},
    {"term": "Sortino Ratio",       "fr": "Ratio de Sortino",
     "def": "Comme le Sharpe, mais ne pénalise que la volatilité négative (downside)."},
    {"term": "Calmar Ratio",        "fr": "Ratio de Calmar",
     "def": "CAGR divisé par la perte maximale (drawdown max). Mesure le rendement/risque extrême."},
    {"term": "Max Drawdown",        "fr": "Perte maximale",
     "def": "Plus grande baisse peak-to-trough du portefeuille observée."},
    {"term": "VaR (95 %)",          "fr": "Valeur à risque",
     "def": "Perte maximale attendue avec 95 % de confiance sur une journée."},
    {"term": "CVaR / ES",           "fr": "Perte attendue conditionnelle",
     "def": "Perte moyenne au-delà du seuil VaR — mesure la queue de distribution."},
    {"term": "Beta",                "fr": "Bêta",
     "def": "Sensibilité du portefeuille aux variations du benchmark (marché)."},
    {"term": "Alpha (Jensen)",      "fr": "Alpha de Jensen",
     "def": "Rendement excédentaire par rapport au modèle CAPM."},
    {"term": "Information Ratio",   "fr": "Ratio d'information",
     "def": "Tracking error ajusté du rendement actif par rapport au benchmark."},
    {"term": "Omega Ratio",         "fr": "Ratio Omega",
     "def": "Rapport gains/pertes pondérés — généralisation non-paramétrique du Sharpe."},
    {"term": "Hit Rate",            "fr": "Taux de succès",
     "def": "Proportion de jours de trading avec un rendement positif."},
    {"term": "Profit Factor",       "fr": "Facteur de profit",
     "def": "Ratio gains bruts / pertes brutes."},
    {"term": "Tail Ratio",          "fr": "Ratio de queue",
     "def": "P95 gains / P95 pertes — asymétrie favorable."},
    {"term": "Jobson-Korkie",       "fr": "Test de Jobson-Korkie",
     "def": "Test statistique comparant deux ratios de Sharpe — H0 : égalité."},
    {"term": "Jensen Alpha t-test", "fr": "Test t sur l'alpha de Jensen",
     "def": "Vérifie si l'alpha est significativement différent de zéro (régression OLS)."},
    {"term": "Bootstrap CI",        "fr": "Intervalle de confiance bootstrap",
     "def": "Intervalle de confiance non-paramétrique par rééchantillonnage."},
    {"term": "PFU",                 "fr": "Prélèvement Forfaitaire Unique",
     "def": "Flat tax française de 30 % sur les gains en capital (12,8 % IR + 17,2 % PS)."},
    {"term": "TTF",                 "fr": "Taxe sur les Transactions Financières",
     "def": "0,1 % sur les achats d'actions de sociétés françaises > 1 Md€ de capitalisation."},
    {"term": "PEA",                 "fr": "Plan d'Épargne en Actions",
     "def": "Enveloppe fiscale française : exonéré d'IR après 5 ans (PS 17,2 % uniquement)."},
    {"term": "Slippage",            "fr": "Glissement de cours",
     "def": "Différence entre le prix attendu et le prix réel d'exécution."},
    {"term": "Risk Parity",         "fr": "Parité des risques",
     "def": "Allocation où chaque actif contribue également au risque total du portefeuille."},
    {"term": "GBM",                 "fr": "Mouvement Brownien Géométrique",
     "def": "Modèle stochastique log-normal utilisé pour simuler les prix d'actifs."},
    {"term": "Monte Carlo",         "fr": "Simulation de Monte Carlo",
     "def": "Méthode probabiliste générant des milliers de scénarios de marché."},
    {"term": "Stress Test",         "fr": "Test de résistance",
     "def": "Évaluation du portefeuille durant des périodes historiques de crise."},
]


def glossary_as_text() -> str:
    """Return plain-text glossary for embedding in reports."""
    lines = ["GLOSSAIRE FINANCIER", "=" * 60]
    for entry in GLOSSARY:
        lines.append(f"\n{entry['term']}  ({entry['fr']})")
        lines.append(f"  {entry['def']}")
    return "\n".join(lines)
