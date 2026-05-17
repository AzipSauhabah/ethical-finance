# 📖 Guide — Créer une stratégie event-driven

## Table des matières
1. [Architecture fondamentale](#1-architecture-fondamentale)
2. [Variables disponibles dans `on_bar`](#2-variables-disponibles-dans-on_bar)
3. [Le dictionnaire `state` — mémoire persistante](#3-le-dictionnaire-state--mémoire-persistante)
4. [Gestion des positions](#4-gestion-des-positions)
5. [Stops par position](#5-stops-par-position)
6. [Trailing stops](#6-trailing-stops)
7. [Position sizing par ATR](#7-position-sizing-par-atr)
8. [Template complet commenté](#8-template-complet-commenté)
9. [Exemples progressifs](#9-exemples-progressifs)
10. [Checklist avant de lancer un backtest](#10-checklist-avant-de-lancer-un-backtest)

---

## 1. Architecture fondamentale

Le moteur de backtest appelle **`on_bar` une fois par jour de rebalancement**.
La stratégie reçoit uniquement les données passées — **aucune fuite du futur n'est possible**.

```
Pour chaque jour t dans l'historique :
    1. Le moteur calcule les prix EUR du jour
    2. Applique les stops (path-dependent)
    3. Si c'est un jour de rebalancement :
        → appelle strategy.on_bar(dt, past_prices[:t], params, state)
        → la stratégie retourne {ticker: poids_cible}
    4. Le moteur exécute les ordres au close du jour t
    5. Snapshot NAV + coûts
```

**Règle d'or** : `on_bar` doit toujours retourner un dict `{str: float}`.
- Les clés sont des tickers
- Les valeurs sont des poids entre 0 et 1
- La somme peut être < 1 (le reste reste en cash)
- Une clé absente = position fermée

---

## 2. Variables disponibles dans `on_bar`

```python
def on_bar(
    self,
    dt: date,              # Date du jour (ex: date(2024, 3, 15))
    past_prices: pd.DataFrame,  # Prix historiques jusqu'à dt INCLUS
    params: StrategyParams,     # Paramètres du backtest
    state: dict,                # Mémoire persistante (voir section 3)
) -> dict[str, float]:          # Retourne les poids cibles
```

### `past_prices` — DataFrame de prix

```python
# Structure : index=DatetimeIndex, colonnes=tickers
#
#            AAPL    MSFT    GOOGL   ^GSPC   ^VIX
# 2024-01-02  185.2   374.0   140.5   4742    13.2
# 2024-01-03  184.1   373.5   139.8   4700    14.1
# ...
# 2024-03-15  172.5   415.2   155.3   5149    12.8  ← dt (aujourd'hui)

# Accéder au prix d'aujourd'hui
prix_aapl_aujourd_hui = float(past_prices["AAPL"].iloc[-1])

# Accéder au prix d'il y a 20 jours
prix_aapl_20j = float(past_prices["AAPL"].iloc[-20])

# Calculer un rendement
ret_20j = past_prices["AAPL"].pct_change(20).iloc[-1]

# Calculer une moyenne mobile
sma_200 = past_prices["AAPL"].iloc[-200:].mean()

# Volatilité 20j annualisée
vol = past_prices["AAPL"].pct_change().iloc[-20:].std() * (252 ** 0.5)

# Filtrer les indices (^GSPC, ^VIX) des actions
actions = [c for c in past_prices.columns if not c.startswith("^")]
```

### `params` — Paramètres du backtest

```python
params.initial_capital        # Capital initial (ex: 10000.0)
params.monthly_contribution   # Versement mensuel (ex: 500.0)
params.broker                 # "fortuneo", "degiro", "ibkr"...
params.account_type           # "cto", "pea", "pea_pme"
params.rebalance_frequency    # "daily", "weekly", "monthly", "quarterly"
params.stop_loss_pct          # Stop global NAV (ex: -0.10 = -10%)
params.max_position_pct       # Poids max par position (ex: 0.25 = 25%)
params.custom                 # dict de paramètres personnalisés
                              # ex: params.custom.get("ma_window", 200)
```

### `dt` — Date du jour

```python
dt.year   # 2024
dt.month  # 3
dt.day    # 15

# Rééquilibrer seulement en janvier
if dt.month != 1:
    return state.get("weights", {})
```

---

## 3. Le dictionnaire `state` — mémoire persistante

`state` est un dict Python ordinaire qui **persiste entre tous les appels** à `on_bar`.
C'est le seul moyen de stocker de l'information d'un jour à l'autre.

```python
# Premier appel : state est vide {}
# Appels suivants : state contient ce qu'on y a mis

# Stocker les poids actuels
state["weights"] = {"AAPL": 0.1, "MSFT": 0.1}

# Récupérer avec une valeur par défaut
weights = state.get("weights", {})

# Stocker le prix d'entrée de chaque position
state.setdefault("entry_prices", {})
state["entry_prices"]["AAPL"] = 185.2

# Compter les jours depuis la dernière rebalance
state["bar_count"] = state.get("bar_count", 0) + 1

# Stocker un modèle ML entraîné
state["ml_model"] = clf  # RandomForest, LSTM, etc.

# Stocker les fondamentaux (évite de re-fetcher chaque jour)
if "fundamentals" not in state:
    state["fundamentals"] = _fetch_fundamentals(tickers)
```

---

## 4. Gestion des positions

Le moteur gère automatiquement les ordres. La stratégie **déclare seulement les poids cibles**.

```python
# Exemple : poids cibles
return {
    "AAPL": 0.15,   # Acheter jusqu'à 15% de la NAV
    "MSFT": 0.15,   # Acheter jusqu'à 15% de la NAV
    "GOOGL": 0.10,  # Acheter jusqu'à 10% de la NAV
    # TSLA absent → position fermée si elle existait
}

# Le moteur va :
# 1. Calculer les parts entières à acheter/vendre
# 2. Appliquer les frais broker réels
# 3. Vérifier que le cash reste positif
# 4. Appliquer le slippage
```

### Tenir les positions existantes

```python
def on_bar(self, dt, past_prices, params, state):
    # Si pas de signal aujourd'hui, garder les positions actuelles
    if not _has_signal(past_prices):
        return state.get("weights", {})  # ← Ne rien faire
    
    # Sinon recalculer
    new_weights = _compute_weights(past_prices)
    state["weights"] = new_weights
    return new_weights
```

---

## 5. Stops par position

Le moteur a un stop global sur la NAV. Pour des **stops par ticker**, on les gère dans `on_bar`.

```python
def on_bar(self, dt, past_prices, params, state):
    weights = dict(state.get("weights", {}))
    entry_prices = state.setdefault("entry_prices", {})
    
    # ── Vérifier les stops sur les positions existantes ──────────────
    to_close = []
    for ticker, entry_price in entry_prices.items():
        if ticker not in past_prices.columns:
            continue
        
        current_price = float(past_prices[ticker].iloc[-1])
        pnl_pct = current_price / entry_price - 1
        
        STOP_LOSS = -0.08      # Stop à -8%
        PROFIT_TARGET = 0.20   # Objectif à +20%
        
        if pnl_pct <= STOP_LOSS or pnl_pct >= PROFIT_TARGET:
            to_close.append(ticker)
    
    # Fermer les positions qui ont touché le stop ou l'objectif
    for ticker in to_close:
        weights.pop(ticker, None)
        entry_prices.pop(ticker, None)
    
    # ── Calculer les nouvelles positions ─────────────────────────────
    new_entries = _select_candidates(past_prices)
    for ticker in new_entries:
        if ticker not in weights:
            weights[ticker] = 0.10  # 10% par nouvelle position
            entry_prices[ticker] = float(past_prices[ticker].iloc[-1])
    
    state["weights"] = weights
    return weights
```

---

## 6. Trailing stops

Un trailing stop monte avec le prix mais ne descend jamais.

```python
def on_bar(self, dt, past_prices, params, state):
    weights = dict(state.get("weights", {}))
    entry_prices = state.setdefault("entry_prices", {})
    high_prices = state.setdefault("high_prices", {})  # ← Prix max atteint
    
    TRAILING_PCT = 0.15  # Stop à 15% du plus haut
    
    to_close = []
    for ticker in list(weights.keys()):
        if ticker not in past_prices.columns:
            continue
        
        current = float(past_prices[ticker].iloc[-1])
        
        # Mettre à jour le plus haut depuis l'entrée
        high_prices[ticker] = max(high_prices.get(ticker, current), current)
        peak = high_prices[ticker]
        
        # Trailing stop : si le prix est redescendu de X% depuis le pic
        drawdown_from_peak = current / peak - 1
        if drawdown_from_peak <= -TRAILING_PCT:
            to_close.append(ticker)
    
    for ticker in to_close:
        weights.pop(ticker, None)
        entry_prices.pop(ticker, None)
        high_prices.pop(ticker, None)
    
    state["weights"] = weights
    return weights
```

---

## 7. Position sizing par ATR

L'ATR (Average True Range) mesure la volatilité récente d'un titre.
On l'utilise pour calibrer la taille de position : **moins volatile = plus grande position**.

```python
def _atr(prices: pd.Series, n: int = 14) -> float:
    """ATR-14 : volatilité absolue moyenne sur 14 jours."""
    if len(prices) < n + 1:
        return float(prices.iloc[-1]) * 0.02  # fallback 2%
    daily_ranges = prices.pct_change().abs().iloc[-n:]
    return float(prices.iloc[-1] * daily_ranges.mean())


def _size_by_atr(
    ticker: str,
    past_prices: pd.DataFrame,
    risk_per_trade: float = 0.01,  # Risquer 1% de la NAV par trade
    stop_atr_mult: float = 2.0,    # Stop à 2×ATR
) -> float:
    """Calcule le poids optimal selon le risque en ATR."""
    prices = past_prices[ticker].dropna()
    atr = _atr(prices)
    current = float(prices.iloc[-1])
    
    # Stop distance en % = 2 × ATR / prix actuel
    stop_pct = stop_atr_mult * atr / current
    
    # Poids = risque_par_trade / stop_pct
    # Ex : risque=1%, stop=4% → poids=25%
    weight = risk_per_trade / max(stop_pct, 0.001)
    return min(weight, 0.25)  # Cap à 25%


# Dans on_bar :
def on_bar(self, dt, past_prices, params, state):
    candidates = ["AAPL", "MSFT", "GOOGL"]
    weights = {}
    for ticker in candidates:
        if ticker in past_prices.columns:
            weights[ticker] = _size_by_atr(ticker, past_prices)
    return weights
```

---

## 8. Template complet commenté

```python
from __future__ import annotations
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.strategies.base import Strategy, StrategyParams
from backend.strategies.registry import strategy_registry


@strategy_registry.register
class MaStrategieStrategy(Strategy):
    """
    Description courte de la stratégie.
    
    Logique :
    ---------
    1. Condition d'entrée : ...
    2. Condition de sortie : stop à X%, objectif à Y%
    3. Sizing : Z% de la NAV par position
    
    Hypothèses :
    ------------
    - ...
    
    Limites :
    ---------
    - ...
    """

    # Nombre de barres à attendre avant le premier signal
    # (pour avoir assez d'historique pour les calculs)
    requires_warmup_days = 200

    # True si la stratégie entraîne un modèle ML
    is_walkforward_trained = False

    @property
    def name(self) -> str:
        return "ma_strategie"  # ← identifiant unique, snake_case

    @property
    def description(self) -> str:
        return "Description affichée dans l'interface."

    @property
    def benchmark(self) -> str:
        return "^GSPC"  # Benchmark pour le calcul alpha/beta

    @property
    def param_space(self) -> dict[str, Any]:
        """Plages pour l'optimisation des paramètres."""
        return {
            "ma_window": (100, 300),      # Fenêtre moyenne mobile
            "profit_target": (0.10, 0.30), # Objectif de gain
            "stop_loss": (0.05, 0.15),     # Stop loss
        }

    def on_bar(
        self,
        dt: date,
        past_prices: pd.DataFrame,
        params: StrategyParams,
        state: dict[str, Any],
    ) -> dict[str, float]:
        
        # ── 0. Lire les paramètres ────────────────────────────────────
        ma_window = int(params.custom.get("ma_window", 200))
        profit_target = float(params.custom.get("profit_target", 0.20))
        stop_loss = float(params.custom.get("stop_loss", 0.08))
        
        # ── 1. Vérifier qu'on a assez de données ─────────────────────
        if len(past_prices) < ma_window:
            return {}
        
        # ── 2. Récupérer l'état actuel ────────────────────────────────
        weights = dict(state.get("weights", {}))
        entry_prices = state.setdefault("entry_prices", {})
        
        # ── 3. Gérer les stops sur les positions existantes ───────────
        to_close = []
        for ticker, entry_price in list(entry_prices.items()):
            if ticker not in past_prices.columns:
                to_close.append(ticker)
                continue
            
            current = float(past_prices[ticker].iloc[-1])
            pnl = current / entry_price - 1
            
            if pnl <= -stop_loss or pnl >= profit_target:
                to_close.append(ticker)
        
        for ticker in to_close:
            weights.pop(ticker, None)
            entry_prices.pop(ticker, None)
        
        # ── 4. Sélectionner de nouveaux candidats ─────────────────────
        # (remplacer par votre logique)
        new_candidates = self._select_candidates(past_prices, ma_window)
        
        # ── 5. Ajouter les nouvelles positions ────────────────────────
        max_positions = 10
        for ticker in new_candidates:
            if len(weights) >= max_positions:
                break
            if ticker not in weights:
                weights[ticker] = 1.0 / max_positions
                entry_prices[ticker] = float(past_prices[ticker].iloc[-1])
        
        # ── 6. Sauvegarder et retourner ───────────────────────────────
        state["weights"] = weights
        return weights

    def _select_candidates(
        self,
        past_prices: pd.DataFrame,
        ma_window: int,
    ) -> list[str]:
        """Sélectionne les tickers candidats à l'achat."""
        candidates = []
        for ticker in past_prices.columns:
            if ticker.startswith("^"):  # Exclure les indices
                continue
            
            prices = past_prices[ticker].dropna()
            if len(prices) < ma_window:
                continue
            
            current = float(prices.iloc[-1])
            sma = float(prices.iloc[-ma_window:].mean())
            
            # Condition : prix au-dessus de la moyenne mobile
            if current > sma:
                candidates.append(ticker)
        
        return candidates
```

---

## 9. Exemples progressifs

### Niveau 1 — Buy & Hold simple

```python
def on_bar(self, dt, past_prices, params, state):
    if state.get("invested"):
        return state["weights"]  # Ne rien faire une fois investi
    
    tickers = [c for c in past_prices.columns if not c.startswith("^")]
    n = len(tickers)
    weights = {t: 1.0 / n for t in tickers}
    state["invested"] = True
    state["weights"] = weights
    return weights
```

### Niveau 2 — Momentum avec rééquilibrage mensuel

```python
def on_bar(self, dt, past_prices, params, state):
    # Rééquilibrer seulement le premier jour du mois
    bar_count = state.get("bar_count", 0) + 1
    state["bar_count"] = bar_count
    if bar_count % 21 != 0:  # ~21 jours de bourse par mois
        return state.get("weights", {})
    
    if len(past_prices) < 252:
        return {}
    
    # Momentum 12-1 mois
    ret_12m = past_prices.iloc[-252].pct_change()  # Non, c'est faux
    # Correct :
    ret_12m = (past_prices.iloc[-21] / past_prices.iloc[-252] - 1).dropna()
    
    # Top 20% par momentum
    n_top = max(1, int(len(ret_12m) * 0.2))
    winners = ret_12m.nlargest(n_top).index.tolist()
    
    weights = {t: 1.0 / n_top for t in winners}
    state["weights"] = weights
    return weights
```

### Niveau 3 — Trend following avec stops ATR

```python
def on_bar(self, dt, past_prices, params, state):
    weights = dict(state.get("weights", {}))
    entry_prices = state.setdefault("entry_prices", {})
    
    # Stops ATR sur positions existantes
    for ticker in list(weights.keys()):
        if ticker not in past_prices.columns:
            continue
        prices = past_prices[ticker].dropna()
        current = float(prices.iloc[-1])
        entry = entry_prices.get(ticker, current)
        atr = float(prices.pct_change().abs().iloc[-14:].mean() * current)
        
        if current < entry - 2 * atr:  # Stop à 2×ATR sous l'entrée
            weights.pop(ticker)
            entry_prices.pop(ticker, None)
    
    # Nouveaux signaux : prix > MM200
    for ticker in past_prices.columns:
        if ticker.startswith("^") or ticker in weights:
            continue
        prices = past_prices[ticker].dropna()
        if len(prices) < 200:
            continue
        if float(prices.iloc[-1]) > float(prices.iloc[-200:].mean()):
            atr = float(prices.pct_change().abs().iloc[-14:].mean() * prices.iloc[-1])
            risk_pct = 0.01  # Risquer 1% de la NAV
            stop_pct = 2 * atr / float(prices.iloc[-1])
            weight = min(risk_pct / max(stop_pct, 0.001), 0.20)
            weights[ticker] = weight
            entry_prices[ticker] = float(prices.iloc[-1])
    
    state["weights"] = weights
    return weights
```

### Niveau 4 — ML + fondamentaux + stops (voir EPR5)

Voir `backend/strategies/builtin/epr5.py` pour l'implémentation complète.

---

## 10. Checklist avant de lancer un backtest

- [ ] `requires_warmup_days` est suffisant pour tous les calculs (ex: si tu utilises une MM200, mettre ≥ 200)
- [ ] `on_bar` retourne toujours un dict (jamais `None`)
- [ ] Pas d'accès à `past_prices.iloc[future_index]` — uniquement des indices négatifs ou depuis le début
- [ ] Le `state` est initialisé avec `state.get("key", default)` pour le premier appel
- [ ] Les stops sont gérés **avant** les nouvelles entrées
- [ ] Les tickers commençant par `^` (indices) sont exclus des positions
- [ ] Le poids max respecte `params.max_position_pct` (ou est cappé manuellement à 0.25)
- [ ] Le `name` de la stratégie est unique (snake_case)
- [ ] La stratégie est décorée avec `@strategy_registry.register`

---

## Indicateurs techniques utiles

```python
# Moyenne mobile simple
sma = float(prices.iloc[-n:].mean())

# Moyenne mobile exponentielle
ema = float(prices.ewm(span=n).mean().iloc[-1])

# RSI-14
delta = prices.pct_change()
gain = delta.clip(lower=0).rolling(14).mean().iloc[-1]
loss = (-delta.clip(upper=0)).rolling(14).mean().iloc[-1]
rsi = 100 - (100 / (1 + gain / (loss + 1e-9)))

# ATR-14
atr = float(prices.pct_change().abs().iloc[-14:].mean() * prices.iloc[-1])

# Bollinger Bands
sma20 = prices.rolling(20).mean().iloc[-1]
std20 = prices.rolling(20).std().iloc[-1]
upper = sma20 + 2 * std20
lower = sma20 - 2 * std20
bb_position = (prices.iloc[-1] - lower) / (upper - lower)  # [0, 1]

# MACD
ema12 = prices.ewm(span=12).mean()
ema26 = prices.ewm(span=26).mean()
macd = ema12 - ema26
signal = macd.ewm(span=9).mean()
macd_hist = float((macd - signal).iloc[-1])

# Volatilité annualisée
vol_annualisee = float(prices.pct_change().iloc[-20:].std() * (252 ** 0.5))

# Momentum
momentum_12m = float(prices.iloc[-1] / prices.iloc[-252] - 1)
momentum_6m = float(prices.iloc[-1] / prices.iloc[-126] - 1)
momentum_1m = float(prices.iloc[-1] / prices.iloc[-21] - 1)
```
