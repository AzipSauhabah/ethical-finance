"""
Template stratégie — copie ce fichier pour créer une nouvelle stratégie.
Renomme le fichier et la classe, modifie on_bar().
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from backend.strategies.base import Strategy
from backend.strategies.registry import strategy_registry


@strategy_registry.register
class TemplateStrategy(Strategy):
    name        = "template"           # ID unique — apparaît dans la GUI
    description = "Description courte de la stratégie"
    benchmark   = "SPY"

    param_space = {
        "lookback": [20, 60, 120],     # paramètres backtestables
        "top_n":    [5, 10, 20],
    }

    def on_bar(
        self,
        dt: "pd.Timestamp",
        past_prices: "pd.DataFrame",
        params: dict,
        state: dict,
    ) -> dict[str, float]:
        """
        Retourne {ticker: poids_cible} — somme des poids = 1.0
        past_prices : DataFrame[date, ticker] de prix ajustés
        params      : dict des hyperparamètres (lookback, top_n, etc.)
        state       : dict persistant entre les barres
        """
        lookback = params.get("lookback", 60)
        top_n    = params.get("top_n", 10)

        if len(past_prices) < lookback:
            return {}  # pas assez d'historique

        # Exemple : momentum sur lookback jours
        rets = past_prices.iloc[-lookback:].pct_change().dropna()
        total_ret = (1 + rets).prod() - 1

        # Top N tickers par rendement
        top = total_ret.nlargest(top_n).index.tolist()
        w   = 1.0 / len(top)
        return {t: w for t in top}
