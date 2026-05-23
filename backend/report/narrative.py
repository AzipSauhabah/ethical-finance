"""
:file: backend/report/narrative.py
:brief: Moteur de narratives contextuelles style Goldman Sachs.

Génère des paragraphes analytiques pro à partir des métriques du backtest.
Aucun LLM requis — logique conditionnelle sur les chiffres réels.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _pct(v, digits=1):
    if v is None:
        return "N/A"
    return f"{v * 100:+.{digits}f}%"


def _f(v, digits=2):
    if v is None:
        return "N/A"
    return f"{v:.{digits}f}"


def _eur(v):
    if v is None:
        return "N/A"
    return f"{v:,.0f} €".replace(",", " ")


# ─── Narratives par section ───────────────────────────────────────────────────


def _perf_label_comment(sharpe: float, cagr: float) -> tuple:
    """Return (perf_label, perf_comment) based on Sharpe and CAGR."""
    if sharpe >= 2.0 and cagr >= 0.15:
        return ("des performances exceptionnelles",
                "Ce niveau de rendement ajusté au risque se situe dans le premier décile "
                "des stratégies quantitatives documentées dans la littérature académique.")
    if sharpe >= 1.5 and cagr >= 0.10:
        return ("des performances solides et régulières",
                "Ce profil rendement/risque est comparable aux meilleurs fonds "
                "systématiques long-only de la place.")
    if sharpe >= 1.0 and cagr >= 0.05:
        return ("des performances satisfaisantes",
                "La stratégie délivre un rendement ajusté au risque positif, "
                "surpassant la majorité des allocations passives sur la période.")
    if sharpe >= 0.5:
        return ("des performances modestes mais positives",
                "Le profil de risque reste maîtrisé malgré un rendement "
                "en deçà des objectifs institutionnels standards (Sharpe > 1).")
    return ("des performances en deçà des attentes",
            "Le ratio rendement/risque insuffisant suggère une révision "
            "des paramètres de la stratégie ou de l'univers d'investissement.")


def _dd_comment(max_dd: float) -> str:
    """Return drawdown narrative comment."""
    pct = _pct(max_dd)
    if abs(max_dd) <= 0.10:
        return (f"Le drawdown maximum de {pct} témoigne d'une protection "
                "remarquable du capital en période de stress.")
    if abs(max_dd) <= 0.20:
        return (f"Le drawdown maximum de {pct} reste dans les limites "
                "acceptables pour une stratégie long-only.")
    if abs(max_dd) <= 0.35:
        return (f"Le drawdown maximum de {pct} reflète une exposition "
                "significative aux phases de correction de marché.")
    return (f"Le drawdown maximum de {pct} constitue le principal "
            "point de vigilance de cette stratégie, nécessitant une gestion "
            "active des risques extrêmes.")


def narrative_executive_summary(m: dict, meta: dict) -> str:
    """Paragraphe d'ouverture — résumé exécutif."""
    strategy = meta.get("strategy", "la stratégie")
    cagr = m.get("cagr", 0) or 0
    sharpe = m.get("sharpe_ratio", 0) or 0
    vol = m.get("annualised_volatility", 0) or 0
    max_dd = m.get("max_drawdown", 0) or 0
    total_ret = m.get("total_return", 0) or 0

    perf_label, perf_comment = _perf_label_comment(sharpe, cagr)
    dd_comment = _dd_comment(max_dd)

    return (
        f"Sur la période d'analyse, {strategy} a enregistré {perf_label}, "
        f"avec un rendement total de {_pct(total_ret)} pour un CAGR de {_pct(cagr)}, "
        f"une volatilité annualisée de {_pct(vol)} et un ratio de Sharpe de {_f(sharpe)}. "
        f"{perf_comment} {dd_comment}"
    )


def narrative_performance(m: dict, _meta: dict) -> str:
    """Commentaire sur la performance et le benchmark."""
    alpha = m.get("alpha_jensen")
    ir = m.get("information_ratio")
    beta = m.get("beta")
    cagr = m.get("cagr", 0) or 0
    calmar = m.get("calmar_ratio", 0) or 0

    parts = []

    # CAGR
    if cagr >= 0.15:
        parts.append(
            f"Le CAGR de {_pct(cagr)} positionne la stratégie parmi les "
            "solutions d'investissement à fort potentiel de capitalisation à long terme."
        )
    elif cagr >= 0.08:
        parts.append(
            f"Le CAGR de {_pct(cagr)} offre une croissance régulière du capital, "
            "en ligne avec les objectifs de préservation et d'appréciation patrimoniale."
        )
    else:
        parts.append(
            f"Le CAGR de {_pct(cagr)} reste modéré. "
            "Une révision de l'allocation ou des paramètres de sélection pourrait "
            "améliorer le potentiel de rendement à long terme."
        )

    # Alpha et benchmark
    if alpha is not None and ir is not None and beta is not None:
        if alpha > 0.02 and ir > 0.5:
            parts.append(
                f"L'alpha de Jensen de {_pct(alpha)} et le ratio d'information de {_f(ir)} "
                "confirment une génération de valeur ajoutée significative par rapport "
                f"au benchmark (beta : {_f(beta)})."
            )
        elif alpha > 0:
            parts.append(
                f"L'alpha positif de {_pct(alpha)} indique une surperformance modeste "
                f"par rapport au benchmark (bêta : {_f(beta)}), "
                "avec un ratio d'information de {ir:.2f} reflétant une régularité acceptable.".format(
                    ir=ir or 0
                )
            )
        else:
            parts.append(
                f"L'alpha négatif de {_pct(alpha)} suggère que la stratégie "
                "n'a pas généré de valeur ajoutée nette par rapport au benchmark "
                f"sur la période, avec un bêta de {_f(beta)}."
            )

    # Calmar
    if calmar >= 1.0:
        parts.append(
            f"Le ratio de Calmar de {_f(calmar)} indique que le rendement annualisé "
            "couvre largement le risque de drawdown maximal — un critère clé "
            "pour les allocateurs institutionnels."
        )

    return " ".join(parts)


def narrative_drawdown(m: dict) -> str:
    """Analyse du drawdown."""
    max_dd = m.get("max_drawdown", 0) or 0
    avg_dd = m.get("average_drawdown", 0) or 0
    recovery = m.get("recovery_factor", 0) or 0

    if abs(max_dd) <= 0.10:
        intro = (
            "L'analyse du drawdown révèle un profil de risque particulièrement maîtrisé. "
            f"Le drawdown maximum de {_pct(max_dd)} indique une protection robuste du capital "
            "en périodes de tension, caractéristique des stratégies à faible exposition directionnelle."
        )
    elif abs(max_dd) <= 0.20:
        intro = (
            f"Le drawdown maximum de {_pct(max_dd)} reste dans les normes "
            "acceptables pour une stratégie actions long-only. "
            "Ce niveau de perte latente maximale est cohérent avec un profil "
            "rendement/risque équilibré sur cycle complet."
        )
    elif abs(max_dd) <= 0.35:
        intro = (
            f"Le drawdown maximum de {_pct(max_dd)} reflète des phases de correction "
            "significatives sur la période d'analyse. "
            "Ce niveau nécessite une capacité psychologique et financière à supporter "
            "des périodes prolongées de sous-performance."
        )
    else:
        intro = (
            f"Le drawdown maximum de {_pct(max_dd)} constitue le principal risque "
            "de cette stratégie. Ce niveau de perte latente est caractéristique "
            "des stratégies à forte conviction ou faiblement diversifiées, "
            "et requiert une gestion rigoureuse du sizing des positions."
        )

    recovery_comment = ""
    if recovery >= 2.0:
        recovery_comment = (
            f" Le facteur de récupération de {_f(recovery)} démontre une capacité "
            "remarquable à regagner les pertes — signe d'une stratégie structurellement rentable."
        )
    elif recovery >= 1.0:
        recovery_comment = (
            f" Le facteur de récupération de {_f(recovery)} indique que "
            "la stratégie génère suffisamment de rendement pour compenser ses drawdowns."
        )
    else:
        recovery_comment = (
            f" Le facteur de récupération de {_f(recovery)} suggère que "
            "le rendement généré ne compense pas intégralement le risque de drawdown subi."
        )

    avg_comment = (
        f" Le drawdown moyen de {_pct(avg_dd)} reflète le niveau de stress "
        "habituel subi par le portefeuille en dehors des épisodes extrêmes."
    )

    return intro + recovery_comment + avg_comment


def narrative_risk(m: dict) -> str:
    """Commentaire sur les métriques de risque VaR/CVaR."""
    var95 = m.get("var_95", 0) or 0
    cvar95 = m.get("cvar_95", 0) or 0
    skew = m.get("skewness", 0) or 0
    kurt = m.get("excess_kurtosis", 0) or 0
    hit_rate = m.get("hit_rate", 0) or 0
    profit_factor = m.get("profit_factor", 0) or 0

    parts = []

    # VaR/CVaR
    parts.append(
        f"La VaR historique à 95% de {_pct(var95)} par jour signifie qu'en conditions "
        f"normales de marché, la perte journalière ne devrait pas dépasser ce seuil "
        f"dans 95% des cas. La CVaR (Expected Shortfall) de {_pct(cvar95)} mesure "
        "la perte moyenne dans les 5% de scénarios les plus défavorables — "
        "indicateur privilégié par les accords de Bâle III pour la gestion du risque extrême."
    )

    # Distribution
    if skew < -0.5:
        parts.append(
            f"La distribution des rendements présente une asymétrie négative "
            f"(skewness : {_f(skew, 3)}), indiquant une probabilité plus élevée "
            "de pertes extrêmes que ne le suggère une distribution normale — "
            "ce que les modèles gaussiens standard sous-estiment systématiquement."
        )
    elif skew > 0.5:
        parts.append(
            f"L'asymétrie positive des rendements (skewness : {_f(skew, 3)}) "
            "est favorable : elle indique que les gains extrêmes sont plus fréquents "
            "que les pertes extrêmes, un profil recherché en gestion long-only."
        )

    if kurt > 3:
        parts.append(
            f"L'excès de kurtosis de {_f(kurt, 3)} révèle une distribution "
            "leptokurtique (queues épaisses), caractéristique des actifs financiers : "
            "les événements extrêmes sont plus fréquents que prévu par la loi normale."
        )

    # Hit rate et profit factor
    if hit_rate > 0 and profit_factor > 0:
        if hit_rate >= 0.55 and profit_factor >= 1.5:
            parts.append(
                f"Le taux de réussite de {_pct(hit_rate, 0)} combiné à un profit factor "
                f"de {_f(profit_factor)} confirme la robustesse du système de trading : "
                "la stratégie gagne à la fois en fréquence et en amplitude."
            )
        elif profit_factor >= 1.2:
            parts.append(
                f"Avec un profit factor de {_f(profit_factor)}, chaque euro perdu "
                "génère en moyenne {pf:.2f}€ de gains — critère fondamental de viabilité "
                "d'un système de trading.".format(pf=profit_factor)
            )

    return " ".join(parts)


def _stress_passed_comment(scenarios_passed: list) -> str:
    """Narrative for passed stress scenarios."""
    if not scenarios_passed:
        return ""
    labels = ", ".join(f"{label} ({_pct(ret)})" for label, ret in scenarios_passed)
    return (f"La stratégie a démontré une résilience remarquable lors des crises suivantes, "
            f"enregistrant des performances positives : {labels}. "
            "Cette capacité à générer des rendements positifs en période de stress "
            "constitue un avantage compétitif majeur pour les allocateurs institutionnels.")


def _stress_failed_comment(scenarios_failed: list) -> str:
    """Narrative for failed stress scenarios."""
    if not scenarios_failed:
        return ""
    labels = ", ".join(f"{label} ({_pct(ret)})" for label, ret in scenarios_failed)
    if len(scenarios_failed) <= 2:
        return (f"Des pertes ont été enregistrées lors des épisodes : {labels}. "
                "Ces drawdowns reflètent l'exposition résiduelle au risque systémique, "
                "inhérente à toute stratégie long-only non couverte.")
    return (f"La stratégie s'est révélée vulnérable lors de plusieurs crises majeures : {labels}. "
            "Une couverture dynamique ou une allocation aux actifs refuges (or, obligations d'État) "
            "pourrait améliorer le profil risque en période de stress.")


def _stress_covid_comment(stress_tests: list) -> str:
    """Narrative for COVID stress test."""
    covid = next((s for s in stress_tests if "covid" in s.get("label", "").lower()), None)
    if not covid:
        return ""
    ret = covid.get("total_return", 0) or 0
    if ret > 0:
        return ("Lors de la crise COVID-19 (mars 2020), la stratégie a su tirer parti "
                "de la volatilité exceptionnelle des marchés, démontrant l'efficacité "
                "du modèle de sélection en environnement de stress extrême.")
    return ("La crise COVID-19 a représenté le principal défi pour la stratégie, "
            "avec une chute de marché sans précédent en termes de vitesse (-34% en 23 jours "
            "pour le S&P 500). Cette période teste la robustesse de tout système quantitatif.")


def narrative_stress_tests(stress_tests: list) -> str:
    """Commentaire sur les stress tests historiques."""
    if not stress_tests:
        return "Aucun stress test disponible sur la période d'analyse."

    scenarios_passed = []
    scenarios_failed = []

    for s in stress_tests:
        ret = s.get("total_return", 0) or 0
        label = s.get("label", "")
        if ret > 0:
            scenarios_passed.append((label, ret))
        else:
            scenarios_failed.append((label, ret))

    parts = [
        _stress_passed_comment(scenarios_passed),
        _stress_failed_comment(scenarios_failed),
        _stress_covid_comment(stress_tests),
    ]
    return " ".join(p for p in parts if p)


def narrative_costs(cost_summary: dict, cost_breakdown: dict) -> str:
    """Commentaire sur la structure de coûts."""
    total_costs = cost_summary.get("total_costs_eur", 0) or 0
    total_taxes = cost_summary.get("total_taxes_eur", 0) or 0
    cost_pct = cost_summary.get("cost_pct_nav", 0) or 0

    commission = cost_breakdown.get("commission", 0) or 0
    slippage = cost_breakdown.get("slippage", 0) or 0

    parts = []

    if cost_pct <= 0.01:
        parts.append(
            f"La structure de coûts est particulièrement efficiente, "
            f"représentant {_pct(cost_pct)} de la NAV finale. "
            "Ce niveau de friction est comparable aux fonds indiciels institutionnels "
            "à faible turnover."
        )
    elif cost_pct <= 0.03:
        parts.append(
            f"Les coûts totaux ({_eur(total_costs)}, soit {_pct(cost_pct)} de la NAV) "
            "restent dans des proportions raisonnables pour une stratégie active. "
            "L'impact sur la performance nette est limité."
        )
    else:
        parts.append(
            f"Les coûts totaux de {_eur(total_costs)} ({_pct(cost_pct)} de la NAV) "
            "constituent un frein significatif à la performance nette. "
            "Une réduction du turnover ou une renégociation des commissions "
            "pourrait améliorer substantiellement les résultats."
        )

    # Structure des coûts
    total_friction = (commission or 0) + (slippage or 0)
    if total_friction > 0 and commission:
        commission_pct = commission / total_friction * 100
        parts.append(
            f"Les commissions de courtage représentent {commission_pct:.0f}% "
            "des frictions totales hors taxes. "
            f"Les taxes (TTF, PFU/PEA) s'élèvent à {_eur(total_taxes)}, "
            "composante non optimisable à court terme."
        )

    return " ".join(parts)


def narrative_ml_performance(ml_info: dict) -> str:
    """Commentaire sur les performances du modèle ML."""
    accuracy = ml_info.get("accuracy")
    n_signals = ml_info.get("n_signals", 0)
    feature_importance = ml_info.get("feature_importance", {})

    if not ml_info:
        return (
            "Les modèles d'apprentissage automatique (LightGBM RF et GBDT) ont été appliqués "
            "sur l'ensemble de l'univers d'investissement pour générer des signaux directionnels. "
            "Les résultats détaillés sont disponibles dans les logs de backtest."
        )

    parts = []

    if accuracy:
        if accuracy >= 0.60:
            parts.append(
                f"Le modèle affiche un taux de précision de {accuracy*100:.1f}% "
                "sur l'ensemble de test (30% de l'historique), "
                "significativement au-dessus du hasard (50%). "
                "Cette performance prédictive est robuste et statistiquement significative."
            )
        elif accuracy >= 0.53:
            parts.append(
                f"Avec une précision de {accuracy*100:.1f}% sur données hors-échantillon, "
                "le modèle démontre un avantage prédictif modeste mais exploitable. "
                "En finance, une précision de 53-55% est généralement suffisante "
                "pour générer de l'alpha lorsqu'elle est combinée à une gestion rigoureuse du risque."
            )
        else:
            parts.append(
                f"La précision de {accuracy*100:.1f}% reste proche du hasard. "
                "Le signal ML apporte une valeur ajoutée limitée en isolation, "
                "mais peut contribuer à la diversification des signaux dans une approche combinée."
            )

    if n_signals:
        parts.append(f"{n_signals} signaux ont été générés sur la période d'analyse.")

    # Feature importance
    if feature_importance:
        top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:3]
        if top_features:
            feat_str = ", ".join(f"{k} ({v*100:.1f}%)" for k, v in top_features)
            parts.append(
                f"Les facteurs les plus contributifs au signal sont : {feat_str}. "
                "Cette hiérarchie des features est cohérente avec la littérature académique "
                "sur les facteurs de rendement en cross-section."
            )

    return " ".join(parts)


# ─── Point d'entrée principal ─────────────────────────────────────────────────


def generate_all_narratives(tearsheet: dict) -> dict:
    """
    Génère tous les paragraphes narratifs à partir du tearsheet.

    Returns:
        dict avec clés : executive_summary, performance, drawdown,
                         risk, stress_tests, costs, ml
    """
    m = tearsheet.get("metrics", {})
    meta = tearsheet.get("meta", {})
    stress = tearsheet.get("stress_tests", [])
    cost_summary = tearsheet.get("cost_summary", {})
    cost_breakdown = tearsheet.get("cost_breakdown", {})
    ml_info = tearsheet.get("ml_info", {})

    return {
        "executive_summary": narrative_executive_summary(m, meta),
        "performance": narrative_performance(m, meta),
        "drawdown": narrative_drawdown(m),
        "risk": narrative_risk(m),
        "stress_tests": narrative_stress_tests(stress),
        "costs": narrative_costs(cost_summary, cost_breakdown),
        "ml": narrative_ml_performance(ml_info),
    }


# ─── Interprétation dynamique des métriques ──────────────────────────────────



_METRIC_INTERPRETERS = {
    "sharpe_ratio": lambda v: f"Ratio de Sharpe de {v:.2f} — " + ("excellent" if v>=2 else "solide" if v>=1 else "acceptable" if v>=0.5 else "faible" if v>=0 else "negatif"),
    "sharpe":       lambda v: f"Ratio de Sharpe de {v:.2f} — " + ("excellent" if v>=2 else "solide" if v>=1 else "acceptable" if v>=0.5 else "faible" if v>=0 else "negatif"),
    "sortino_ratio":lambda v: f"Ratio de Sortino de {v:.2f} — " + ("excellent" if v>=2 else "satisfaisant" if v>=1 else "a surveiller"),
    "sortino":      lambda v: f"Ratio de Sortino de {v:.2f} — " + ("excellent" if v>=2 else "satisfaisant" if v>=1 else "a surveiller"),
    "max_drawdown": lambda v: f"Drawdown maximum de {abs(v)*100:.1f}% — " + ("contenu" if abs(v)<0.1 else "modere" if abs(v)<0.2 else "eleve" if abs(v)<0.35 else "severe"),
    "cagr":         lambda v: f"CAGR de {v*100:.1f}%/an — " + ("exceptionnel" if v>=0.2 else "solide" if v>=0.1 else "modere" if v>=0.05 else "faible" if v>=0 else "negatif"),
    "annual_return":lambda v: f"Rendement annuel de {v*100:.1f}%",
    "volatility":   lambda v: f"Volatilite de {v*100:.1f}% — " + ("tres faible" if v<0.1 else "moderee" if v<0.15 else "elevee" if v<0.25 else "tres elevee"),
    "annual_volatility": lambda v: f"Volatilite annuelle de {v*100:.1f}%",
    "win_rate":     lambda v: f"Taux de reussite de {v*100:.1f}%",
    "calmar_ratio": lambda v: f"Ratio de Calmar de {v:.2f}",
    "calmar":       lambda v: f"Ratio de Calmar de {v:.2f}",
}

def interpret_metric(name: str, value: float | None) -> str:
    """Retourne une interprétation contextuelle d'une métrique selon sa valeur."""
    if value is None:
        return "Donnée non disponible sur la période."
    fn = _METRIC_INTERPRETERS.get(name)
    if fn:
        try:
            return fn(value)
        except Exception:
            return f"Valeur : {value:.4f}"
    return f"Valeur : {value:.4f}"

def generate_metric_interpretations(m: dict) -> dict:
    """Génère les interprétations pour toutes les métriques du tearsheet."""
    keys = [
        "sharpe_ratio",
        "sortino_ratio",
        "calmar_ratio",
        "max_drawdown",
        "annualised_volatility",
        "var_95",
        "cagr",
        "hit_rate",
        "profit_factor",
        "beta",
        "alpha_jensen",
    ]
    return {k: interpret_metric(k, m.get(k)) for k in keys}
