from __future__ import annotations

"""
:file: backend/report/glossary.py
:brief: Glossaire financier etendu + methodologie + limites du modele.
:copyright: 2024 Sauhabah -- Ethical Finance Platform
"""

GLOSSARY: list[dict[str, str]] = [
    {
        "term": "CAGR",
        "fr": "Taux de croissance annualise compose",
        "def": (
            "Taux de rendement annualise d un investissement sur plusieurs annees, "
            "en supposant que les gains sont reinvestis chaque annee. "
            "Formule : (Valeur_finale / Valeur_initiale)^(1/n) - 1. "
            "Hypothese : reinvestissement integral des dividendes et plus-values."
        ),
    },
    {
        "term": "Sharpe Ratio",
        "fr": "Ratio de Sharpe",
        "def": (
            "Mesure le rendement excessif par unite de risque total. "
            "Formule : (R_p - R_f) / sigma_p x sqrt(252), avec R_f = 2% annuel. "
            "Un Sharpe > 1 est considere bon, > 2 excellent. "
            "Limite : suppose une distribution normale des rendements, "
            "ce qui sous-estime les queues epaisses."
        ),
    },
    {
        "term": "Sortino Ratio",
        "fr": "Ratio de Sortino",
        "def": (
            "Variante du Sharpe qui ne penalise que la volatilite negative (downside deviation). "
            "Plus adapte aux strategies asymetriques. "
            "Formule : (R_p - R_f) / sigma_downside x sqrt(252). "
            "Retourne inf s il n y a aucun jour de perte."
        ),
    },
    {
        "term": "Calmar Ratio",
        "fr": "Ratio de Calmar",
        "def": (
            "CAGR divise par le drawdown maximum. Mesure le rendement par unite de risque extreme. "
            "Utilise par les hedge funds pour evaluer la resistance aux crises. "
            "Un Calmar > 0.5 est acceptable, > 1 excellent. "
            "Limite : tres sensible a un seul evenement extreme."
        ),
    },
    {
        "term": "Omega Ratio",
        "fr": "Ratio Omega",
        "def": (
            "Ratio non-parametrique gains/pertes pondere par rapport a un seuil (0% ici). "
            "Capture toute la distribution des rendements sans hypothese de normalite. "
            "Omega > 1 signifie que les gains dominent les pertes."
        ),
    },
    {
        "term": "Max Drawdown",
        "fr": "Perte maximale",
        "def": (
            "Plus grande baisse peak-to-trough observee pendant la periode. "
            "Represente la perte maximale d un investisseur entre au pire moment. "
            "Calcul : max(1 - P_t / max(P_0..P_t))."
        ),
    },
    {
        "term": "Recovery Factor",
        "fr": "Facteur de recuperation",
        "def": (
            "Rendement total divise par le drawdown maximum. "
            "Mesure combien de fois la strategie a rembourse sa pire perte. "
            "Un Recovery Factor > 3 indique une strategie robuste."
        ),
    },
    {
        "term": "VaR (95 %)",
        "fr": "Valeur a risque historique 95%",
        "def": (
            "Perte journaliere maximale avec 95% de confiance, par simulation historique. "
            "Interpretation : 1 jour sur 20, la perte depasse ce seuil. "
            "Limite : ne dit rien sur la magnitude des pertes au-dela du seuil."
        ),
    },
    {
        "term": "CVaR / ES",
        "fr": "Perte attendue conditionnelle (Expected Shortfall)",
        "def": (
            "Perte moyenne au-dela du seuil VaR. "
            "Recommandee par Bale III pour les institutions financieres. "
            "Plus coherente que la VaR car capture la magnitude des pertes extremes. "
            "Formule : E[R | R < VaR_95]."
        ),
    },
    {
        "term": "VaR Parametrique",
        "fr": "VaR gaussienne",
        "def": (
            "VaR calculee en supposant une distribution normale des rendements. "
            "Formule : mu - 1.645 x sigma (pour 95%). "
            "Limite : sous-estime le risque reel car les marches ont des queues epaisses."
        ),
    },
    {
        "term": "Beta",
        "fr": "Beta de marche",
        "def": (
            "Sensibilite du portefeuille aux variations du benchmark. "
            "Beta = 1 : suit le marche. Beta < 1 : moins volatile. Beta > 1 : amplificateur. "
            "Calcule par regression OLS des rendements du portefeuille sur le benchmark."
        ),
    },
    {
        "term": "Alpha (Jensen)",
        "fr": "Alpha de Jensen annualise",
        "def": (
            "Rendement excessif par rapport au modele CAPM : "
            "alpha = R_p - [R_f + beta x (R_m - R_f)]. "
            "Un alpha positif significatif indique une vraie surperformance ajustee du risque."
        ),
    },
    {
        "term": "Information Ratio",
        "fr": "Ratio d information",
        "def": (
            "Rendement actif (vs benchmark) par unite de tracking error. "
            "Formule : (R_p - R_b) / TE x sqrt(252). "
            "IR > 0.5 est bon, > 1 excellent."
        ),
    },
    {
        "term": "Skewness",
        "fr": "Asymetrie",
        "def": (
            "Mesure l asymetrie de la distribution des rendements. "
            "Skewness < 0 : queue gauche (pertes extremes plus frequentes). "
            "Les actions ont typiquement une skewness legerement negative."
        ),
    },
    {
        "term": "Excess Kurtosis",
        "fr": "Kurtosis en exces",
        "def": (
            "Mesure l epaisseur des queues vs une distribution normale (kurtosis = 0). "
            "Kurtosis > 0 : queues epaisses (fat tails). "
            "Implique que la VaR gaussienne sous-estime le risque reel."
        ),
    },
    {
        "term": "Tail Ratio",
        "fr": "Ratio de queue",
        "def": (
            "P95 gains / P95 pertes en valeur absolue. "
            "Tail Ratio > 1 : les gains extremes dominent les pertes extremes."
        ),
    },
    {
        "term": "Hit Rate",
        "fr": "Taux de succes",
        "def": (
            "Proportion de jours avec un rendement positif. "
            "A analyser avec le Profit Factor : un Hit Rate eleve peut masquer "
            "de grosses pertes peu frequentes."
        ),
    },
    {
        "term": "Profit Factor",
        "fr": "Facteur de profit",
        "def": (
            "Ratio gains bruts totaux / pertes brutes totales. "
            "Profit Factor > 1.5 est bon. PF = 2 : pour 1 euro perdu, 2 euros gagnes."
        ),
    },
    {
        "term": "Jobson-Korkie Test",
        "fr": "Test de Jobson-Korkie",
        "def": (
            "Test statistique comparant le Sharpe de la strategie au Sharpe du benchmark. "
            "H0 : pas de surperformance. Si p-value < 5% : surperformance significative. "
            "Limite : suppose des rendements gaussiens i.i.d."
        ),
    },
    {
        "term": "TTF",
        "fr": "Taxe sur les Transactions Financieres",
        "def": (
            "Taxe francaise de 0.3% sur les achats d actions francaises "
            "de capitalisation > 1 milliard euros. CTO uniquement."
        ),
    },
    {
        "term": "PFU / Flat Tax",
        "fr": "Prelevement Forfaitaire Unique",
        "def": (
            "Imposition francaise des plus-values a 30% (12.8% IR + 17.2% PS). "
            "PEA : exoneration IR apres 5 ans, seulement 17.2% de PS."
        ),
    },
    {
        "term": "Slippage",
        "fr": "Glissement de prix",
        "def": (
            "Difference entre le prix theorique et le prix reel d execution. "
            "Modelise ici a 0.05% du notionnel. "
            "Depend de la liquidite du titre et de la taille de l ordre."
        ),
    },
    {
        "term": "Rebalancement",
        "fr": "Reequilibrage de portefeuille",
        "def": (
            "Ramener les poids du portefeuille a leurs cibles theoriques. "
            "Frequence mensuelle par defaut. "
            "Genere des couts de transaction mais maintient le profil de risque cible."
        ),
    },
]


METHODOLOGY_TEXT = (
    "METHODOLOGIE ET HYPOTHESES\n\n"
    "1. DONNEES DE MARCHE\n"
    "Les prix utilises sont les cours de cloture ajustes (dividendes, splits) "
    "issus de Yahoo Finance via la base de donnees Supabase (2006-2026). "
    "Le taux de change EUR/USD est applique jour par jour depuis la serie historique EURUSD=X.\n\n"
    "2. COUTS DE TRANSACTION\n"
    "Chaque transaction integre : (i) commission courtier selon le bareme selectionne, "
    "(ii) slippage estime a 0.05% du notionnel, "
    "(iii) spread FX de 0.1% pour les titres en devises etrangeres, "
    "(iv) TTF de 0.3% pour les actions francaises eligibles (CTO uniquement). "
    "Les taxes sur plus-values (PFU 30% ou PEA 17.2%) sont calculees a la cloture de chaque position.\n\n"
    "3. TAUX SANS RISQUE\n"
    "Le taux sans risque est fixe a 2% annuel, representant approximativement "
    "le taux des OAT francaises a court terme sur la periode.\n\n"
    "4. EXECUTION\n"
    "Les ordres sont supposes executes au cours de cloture du jour du signal. "
    "Aucune contrainte de liquidite n est modelisee. "
    "Les positions fractionnaires ne sont pas autorisees.\n\n"
    "5. FISCALITE\n"
    "La fiscalite est modelisee de facon simplifiee. "
    "Les moins-values ne sont pas reportees entre annees fiscales. "
    "L optimisation fiscale (seuils de cession, abattements) n est pas prise en compte."
)


LIMITATIONS_TEXT = (
    "LIMITES DU MODELE ET AVERTISSEMENTS\n\n"
    "1. BIAIS DE SURVIVANCE\n"
    "L univers correspond aux composants actuels du S&P 500 et du CAC 40. "
    "Les societes qui ont fait faillite durant la periode n apparaissent pas. "
    "Cela tend a surestimer les performances passees.\n\n"
    "2. LOOK-AHEAD BIAS\n"
    "Des precautions ont ete prises pour eviter l utilisation de donnees futures. "
    "Cependant, certains parametres ML ont pu etre optimises sur l ensemble de la periode.\n\n"
    "3. LIQUIDITE\n"
    "Aucune contrainte de liquidite n est modelisee. "
    "En conditions reelles, les titres de petite capitalisation peuvent presenter "
    "des spreads importants et des volumes insuffisants.\n\n"
    "4. DONNEES FONDAMENTALES\n"
    "Les ratios fondamentaux (P/B, EBIT/EV, ROIC) sont des approximations "
    "calculees depuis les donnees annuelles disponibles. "
    "Ils ne refletent pas les revisions trimestrielles.\n\n"
    "5. PERFORMANCE PASSEE\n"
    "Les performances passees ne prejudgent pas des performances futures. "
    "Ce rapport est fourni a titre informatif uniquement "
    "et ne constitue pas un conseil en investissement."
)
