# 🚀 Ethical Finance Platform — A Sauhabah

> Backtest event-driven, screening **Ethical + Sharia**, reporting institutionnel.
> Stack full-Python / React / Vercel, niveau quant institutionnel.

[![License: GPL v3](https://img.shields.io/badge/License-GPL_v3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
![Python](https://img.shields.io/badge/python-3.11-blue)
![React](https://img.shields.io/badge/react-18.3-61dafb)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![Version](https://img.shields.io/badge/version-2.1-b8962f)

**Live demo** : <https://efficient-portfolio2.vercel.app>

---

## 📋 Sommaire

- [Fonctionnalités](#-fonctionnalités)
- [Démarrage rapide](#-démarrage-rapide-5-minutes)
- [Ajouter une nouvelle stratégie](#-ajouter-une-nouvelle-stratégie-en-3-minutes)
- [Architecture](#-architecture)
- [Stratégies disponibles](#-stratégies-disponibles)
- [Filtres Ethical & Sharia](#-filtres-ethical--sharia)
- [Méthodologie quantitative](#-méthodologie-quantitative)
- [Cache & performance](#-cache--performance)
- [Déploiement Vercel](#-déploiement-vercel)
- [FAQ](#-faq)

---

## ✨ Fonctionnalités

- **Screening dual** — Ethical (ESG sectoriel) ET Sharia (AAOIFI), chaque filtre activable indépendamment.
- **11 stratégies built-in** — Buy & Hold, Equal-Weight, Momentum, Mean Reversion, SMA Crossover, Risk Parity, Min Variance, Dual Momentum, Adaptive Trend, ML Ensemble (RF+GBM walk-forward), **EPR5** (Magic Formula + filtres SPX/VIX style Lean).
- **Builder de stratégies custom** — JSON → règles compilées dynamiquement.
- **Backtest STRICT event-driven** — la stratégie ne voit que les prix passés à chaque date, aucune fuite du futur n'est possible par construction.
- **Frais broker RÉELS** — Fortuneo (50 USD flat sous 7 500 USD), Degiro, Bourse Direct, Interactive Brokers, chacun avec sa vraie grille tarifaire.
- **Taxes françaises** — PFU 30 %, TTF 0.1 %, PEA exonération après 5 ans.
- **25+ métriques** — Sharpe, Sortino, Calmar, Omega, Treynor, VaR/CVaR (historique + paramétrique), skewness, kurtosis, tail ratio, hit rate, profit factor, beta, alpha de Jensen, information ratio.
- **Tests statistiques** — Jobson-Korkie, bootstrap CI, t-test sur alpha de Jensen, White's Reality Check.
- **Stress tests** — 5 crises historiques (GFC 2008, COVID 2020, Bear 2022, Dot-com, EU 2011).
- **Monte Carlo** vectorisé (10 000 chemins GBM + bootstrap par blocs) avec calibration bayésienne.
- **Signaux quotidiens** — vote multi-indicateurs (SMA, RSI, MACD, momentum).
- **Recommandations de rééquilibrage** intégrant les coûts réels.
- **Quotes temps réel** via Server-Sent Events (thread background, refresh 60 s).
- **Rapport PDF 12 pages style Goldman Sachs** avec charts matplotlib intégrés.
- **Caching 2 niveaux** — LRU in-memory (L1) + Vercel KV / Redis (L2) pour persistance cross-invocation.
- **UX moderne** — empty states, portefeuille de démo, progress bar, persistance localStorage.

---

## 🚀 Démarrage rapide (5 minutes)

### Prérequis
- Python 3.11+
- Node.js 18+

### Backend Python

```bash
git clone https://github.com/AzipSauhabah/efficient-portfolio2.git
cd efficient-portfolio2

python3.11 -m venv .venv
source .venv/bin/activate     # macOS/Linux
# .venv\Scripts\activate      # Windows

pip install -r requirements.txt
uvicorn api.index:app --reload --port 8000
```

### Frontend React (dans un autre terminal)

```bash
npm install
npm run dev
```

→ Ouvrir <http://localhost:5173>. Le proxy Vite redirige `/api/*` vers <http://localhost:8000>.

**Test rapide** :
```bash
curl http://localhost:8000/api/health
# {"status":"ok","version":"2.1.0","strategies":11}
```

---

## 🆕 Ajouter une nouvelle stratégie en 3 minutes

**Pas besoin de toucher la GUI.** Le frontend lit dynamiquement la liste des stratégies via `/api/strategies` et l'affiche automatiquement dans le dropdown du Backtest.

### Étape 1 — Créer le fichier

Dans `api/strategies/builtin/`, créez `ma_strategie.py` :

```python
"""
:file: api/strategies/builtin/ma_strategie.py
:brief: Description de ma stratégie en une phrase.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from api.strategies.base import Strategy, StrategyParams
from api.strategies.registry import strategy_registry


@strategy_registry.register      # ← cette ligne suffit pour l'enregistrer
class MaStrategie(Strategy):
    """Une stratégie d'exemple : achète tout au-dessus de SMA 100."""

    # Combien de barres minimum avant de pouvoir générer un signal
    requires_warmup_days = 100

    @property
    def name(self) -> str:
        return "ma_strategie"            # ← clé technique (sans espaces)

    @property
    def description(self) -> str:
        return "Long les actifs au-dessus de leur SMA 100"

    @property
    def benchmark(self) -> str:
        return "^GSPC"                    # ← S&P 500 ou ^FCHI pour CAC 40

    @property
    def param_space(self) -> dict[str, Any]:
        # Optionnel : pour la calibration bayésienne automatique
        return {"sma_window": (50, 200)}

    def on_bar(
        self,
        dt: date,
        past_prices: pd.DataFrame,        # ← IMPORTANT : uniquement le passé
        params: StrategyParams,
        state: dict[str, Any],            # ← dict mutable, persiste entre bars
    ) -> dict[str, float]:
        """
        Le moteur appelle cette méthode à chaque jour du backtest.

        :param dt:          date courante
        :param past_prices: DataFrame[date, ticker] — UNIQUEMENT les prix
                            jusqu'à dt inclus (pas de look-ahead possible)
        :param params:      paramètres saisis par l'utilisateur
        :param state:       dict persistant pour cacher des modèles, des
                            indicateurs roulants, etc.
        :returns: dict {ticker: target_weight}.  Somme ≤ 1, cash = reste.
        """
        sma_window = int(params.custom.get("sma_window", 100))

        if len(past_prices) < sma_window:
            return {}                     # warmup pas terminé

        # Pour chaque ticker : long si prix > SMA
        sma     = past_prices.iloc[-sma_window:].mean()
        current = past_prices.iloc[-1]
        winners = current[current > sma].index

        if len(winners) == 0:
            return {}                     # 100 % cash

        weight = 1.0 / len(winners)
        return {ticker: weight for ticker in winners}
```

### Étape 2 — Redémarrer le backend

```bash
# Si uvicorn tourne avec --reload, il recharge automatiquement.
# Sinon :
uvicorn api.index:app --reload --port 8000
```

Vous devriez voir dans les logs :
```
INFO:api: API ready — 12 strategies registered.
```

### Étape 3 — Tester

Allez dans l'onglet **Backtest** du frontend. Le dropdown contient maintenant `ma_strategie`. **Pas une seule ligne de TypeScript à toucher.**

### Conventions importantes

| Aspect | Règle |
|---|---|
| **Pas de look-ahead** | `past_prices` ne contient JAMAIS de futur. Si vous écrivez `past_prices.iloc[i+1]`, ça lèvera une exception. |
| **Positions entières** | Le moteur gère ça — vous retournez juste des poids. |
| **Cash non-négatif** | Le moteur réduit automatiquement les ordres si insuffisant. |
| **State persistant** | Utilisez `state["ma_clé"] = ...` pour cacher des calculs entre bars. |
| **ML refit** | Si votre stratégie fit un modèle, ajoutez `is_walkforward_trained = True` et `walkforward_refit_days = 60` au début de la classe. |

### Exemples concrets fournis dans le repo

Lisez ces fichiers comme templates :
- `api/strategies/builtin/all_strategies.py` — 10 stratégies simples
- `api/strategies/builtin/epr5.py` — stratégie avancée avec fundamentals + state + Monte Carlo sizing

---

## 🏗️ Architecture

```
efficient-portfolio2/
├── api/                            # Backend Python (FastAPI sur Vercel)
│   ├── config.py                   # TOUTES les constantes (broker fees, taxes…)
│   ├── index.py                    # Routes FastAPI (thin layer)
│   ├── core/
│   │   ├── cache.py                # L1 LRU + L2 Vercel KV
│   │   ├── data.py                 # Multi-source (yfinance → Stooq → GBM)
│   │   ├── registry.py             # Registre tickers + screening dual
│   │   └── queue.py                # Thread background quotes live + SSE
│   ├── quant/
│   │   ├── metrics.py              # 25+ métriques pures
│   │   ├── signals.py              # Indicateurs techniques + ML
│   │   ├── significance.py         # Tests stats (Jobson-Korkie, bootstrap)
│   │   └── montecarlo.py           # MC + calibration bayésienne
│   ├── strategies/
│   │   ├── base.py                 # Classe abstraite Strategy.on_bar
│   │   ├── registry.py             # Auto-discovery @register
│   │   ├── builtin/                # ← AJOUTEZ VOS STRATÉGIES ICI
│   │   │   ├── all_strategies.py
│   │   │   └── epr5.py
│   │   └── custom.py               # Builder JSON → Strategy
│   ├── backtest/
│   │   ├── engine.py               # STRICT event-driven date-par-date
│   │   ├── portfolio.py            # NAV, cash, positions, corrélations
│   │   ├── costs.py                # Frais broker RÉELS + taxes FR
│   │   └── stress.py               # 5 crises historiques
│   ├── report/
│   │   ├── tearsheet.py            # Dict structuré JSON-serialisable
│   │   ├── pdf.py                  # PDF 12 pages style GS (matplotlib)
│   │   └── glossary.py             # Glossaire FR/EN
│   └── signals/
│       ├── daily.py                # Signaux quotidiens BUY/SELL/HOLD
│       └── rebalance.py            # Ordres de rééquilibrage
│
├── src/                            # Frontend React + Vite + TypeScript
│   ├── App.tsx                     # Shell 5 onglets
│   ├── main.tsx
│   ├── components/
│   │   ├── AboutPanel.tsx          # Pitch + stack
│   │   ├── TickerManager.tsx       # Ajout + badges E/S
│   │   ├── ScreeningPanel.tsx      # Détail par critère
│   │   ├── BacktestPanel.tsx       # Config + résultats + PDF
│   │   └── SignalsPanel.tsx        # Signaux quotidiens
│   ├── hooks/useLiveQuotes.ts      # SSE temps réel
│   ├── types/index.ts              # Types partagés
│   └── utils/api.ts                # Client API typé
│
├── vercel.json                     # Routing Vercel (Python + SPA)
├── requirements.txt
├── package.json
├── tsconfig.json
└── vite.config.ts                  # Proxy dev /api → :8000
```

---

## 📊 Stratégies disponibles

| Nom | Type | Description courte | Look-back |
|-----|------|--------------------|-----------|
| `buy_hold` | Passive | Achète et conserve à pondération égale | 1 j |
| `equal_weight` | Passive | Rééquilibrage périodique à pondération égale | 1 j |
| `momentum` | Trend | Momentum 12-1 mois, long top 30 % | 252 j |
| `mean_reversion` | Reversal | Z-score sur 20 j, long si Z < -1.5σ | 25 j |
| `sma_crossover` | Trend | Long si SMA 50 > SMA 200 | 200 j |
| `risk_parity` | Risk | Pondération inverse vol 20 j | 25 j |
| `min_variance` | Optim | Markowitz min variance, refit 60 j | 60 j |
| `dual_momentum` | Trend | Antonacci : meilleur actif si abs mom > 0 | 252 j |
| `adaptive_trend` | Trend | EMA 12 vs EMA 26 | 100 j |
| `ml_ensemble` | ML | RF + Gradient Boosting walk-forward | 252 j |
| **`epr5`** | **Value+Regime** | **Magic Formula + SPX/VIX + MC sizing** | **252 j** |

Détails complets de chaque stratégie dans `api/strategies/builtin/all_strategies.py` et `epr5.py`.

---

## 🛡️ Filtres Ethical & Sharia

**Deux jeux de critères INDÉPENDANTS** activables par checkbox dans le Backtest.

### Ethical Screen (ESG occidental)
- Exclusion sectorielle : armement, tabac, jeux d'argent, énergies fossiles, pornographie
- Ratio dette / capitalisation ≤ 33 % (informationnel)
- Revenus d'intérêts / CA ≤ 5 % (informationnel)

### Sharia Screen (AAOIFI / Dow Jones Islamic Market)
1. **Activité halal** — pas de banque, assurance, alcool, porc, tabac, jeu, armes, divertissement adulte
2. **Dette portant intérêts / capitalisation ≤ 33 %**
3. **Liquidités productives / capitalisation ≤ 33 %**
4. **Revenus non-permis / CA ≤ 5 %**

Un ticker passe le filtre Sharia uniquement si les 4 critères sont validés.

**Voir l'onglet "Screening" du frontend** pour le détail par critère, valeur observée vs seuil, et description en français.

---

## 🧪 Méthodologie quantitative

### Strict event-driven (anti look-ahead)
À chaque jour de trading, le moteur appelle `strategy.on_bar(dt, past_prices[:dt], params, state)`. Le DataFrame `past_prices` est **mécaniquement tronqué** à `dt` inclus — la stratégie ne peut pas voir le futur, même par erreur de code.

### Coûts réels intégrés
- **Degiro** : 0.50 € + 0.04 % (EU et US)
- **Fortuneo** : **50 USD fixe** sous 7 500 USD, puis 0.20 % + 9 USD
- **Bourse Direct** : 0.99 € fixe
- **Interactive Brokers** : 0.05 % avec cap 1 USD
- **Slippage** par capitalisation (2/5/15 bps)
- **Spread FX EUR/USD** : 3 bps retail

### Taxes françaises
- **PFU** 30 % (12.8 % IR + 17.2 % PS)
- **TTF** 0.1 % à l'achat pour entreprises FR > 1 Md€
- **PEA** exonéré IR après 5 ans (PS 17.2 % uniquement)

### Significativité
- **Jobson-Korkie** — test de différence de Sharpe vs benchmark
- **Bootstrap CI** — intervalle de confiance Sharpe non-paramétrique
- **t-test Jensen alpha** — alpha significativement non-nul ?
- **White's Reality Check** — correction multi-tests

---

## ⚡ Cache & performance

### Deux niveaux de cache **backend**

| Niveau | Type | Persistance | TTL | À quoi sert |
|--------|------|-------------|-----|-------------|
| **L1** | LRU in-memory (RAM serveur) | Vidé au redémarrage du serverless function | 1 h | Accélérer les requêtes répétées dans la même session |
| **L2** | Vercel KV (Redis REST) | **PERSISTE entre toutes les visites et utilisateurs** | 1 h pour prix, 24 h pour fondamentaux | Éviter de retaper yfinance |

**Important** : le L2 (Vercel KV) ne fonctionne que si les variables d'environnement `KV_REST_API_URL` et `KV_REST_API_TOKEN` sont configurées. Sinon, seul le L1 fonctionne et le cache est perdu à chaque cold start (~5 minutes d'inactivité sur Vercel Hobby).

### Cache **frontend** (navigateur)

| Donnée | Stockage | Persistance |
|--------|----------|-------------|
| Liste de tickers du portefeuille | `localStorage` | Permanente jusqu'à clic "Vider" |
| Résultats de backtest | RAM React | Perdu en quittant l'onglet (recalcul ~5 s avec cache backend) |
| Live quotes SSE | RAM React | Perdu en quittant l'onglet, reconnexion auto au retour |
| Screening tickers | RAM React | Idem |

→ **Si vous fermez l'onglet et revenez**, vos tickers sont là, mais vous devez relancer le backtest. Côté serveur, les prix sont en cache donc c'est rapide.

---

## 🚢 Déploiement Vercel

```bash
vercel deploy
```

`vercel.json` route automatiquement :
- `/api/*` → function Python serverless (`api/index.py`)
- `/*` → SPA statique build par Vite

### Variables d'environnement à configurer dans Vercel Dashboard → Settings → Environment Variables

| Variable | Description | Obligatoire ? |
|----------|-------------|---------------|
| `KV_REST_API_URL` | URL REST du store Vercel KV | Non, mais fortement recommandé |
| `KV_REST_API_TOKEN` | Token d'authentification | Idem |
| `APP_ENV` | `development` ou `production` | Optionnel |

Pour activer Vercel KV : Dashboard → Storage → Create Database → KV → Connect Project.

---

## 🐍 Style Python (niveau C1/C2)

- **Programmation fonctionnelle** : générateurs paresseux, lambdas, dataclasses
- **Async/await** partout pour l'I/O (yfinance, KV, FX)
- **Type hints stricts** (`from __future__ import annotations`)
- **Décorateurs** : `@cached`, `@strategy_registry.register`
- **Multiprocessing/threading** : thread background pour le price feed
- **Modules à responsabilité unique** (SRP)
- **Toutes constantes externalisées** dans `api/config.py`
- **Docstrings Doxygen-style** (`:param:`, `:returns:`, `:brief:`)

Génération de la doc :
```bash
pip install sphinx sphinx-autodoc-typehints
sphinx-apidoc -o docs/source api/
sphinx-build -b html docs/source docs/build
```

---

## ❓ FAQ

### Pourquoi pas Zipline ?
Zipline est en fin de maintenance (Quantopian a fermé en 2020) et requiert SQLite local + bundles de données → incompatible Vercel serverless. Le moteur custom est plus adapté au marché français (TTF, PFU, PEA, Fortuneo) que Zipline ne supporte pas nativement.

### Pourquoi pas Lean (QuantConnect) ?
Lean est en C# avec wrapper PythonNet, nécessite .NET runtime + 50 GB de bundles et un serveur dédié. Le moteur custom adopte les **conventions Lean** (event-driven, `on_bar`, slice de past_prices, state mutable) sans le coût d'infrastructure. Code portable vers Lean si besoin futur.

### Y a-t-il une LLM intégrée ?
Pas de LLM conversationnelle (volontairement — risque d'hallucinations sur des sujets financiers). En revanche : ML via scikit-learn (Random Forest + Gradient Boosting) pour les signaux, et optimisation bayésienne pour la calibration des hyperparamètres.

### Comment ajouter une stratégie ?
Voir la section [Ajouter une nouvelle stratégie en 3 minutes](#-ajouter-une-nouvelle-stratégie-en-3-minutes). Aucun fichier React à modifier.

### Comment ajouter un broker ?
Éditez `api/config.py` → `BROKER_FEES` → ajoutez une nouvelle entrée avec votre grille. Puis dans `BacktestPanel.tsx` → ajoutez une `<option>` dans le `<select>` du courtier.

### Les fundamentals viennent d'où ?
yfinance pour le démo. Pour usage pro : brancher Financial Modeling Prep (gratuit 250 req/jour) ou MSCI ESG.

### Le repo doit-il être privé ?
Non. Aucun secret commercial : pas de clés API en dur (uniquement env vars Vercel), pas de stratégie alpha-génératrice unique (toutes sont des classiques académiques). Le repo public est un **portfolio technique** démontrant : Python avancé, async, type hints, modular design, FastAPI, React/TS, Vercel deployment, tests statistiques.

---

## 📜 Disclaimer

> Ce projet est fourni à titre informatif et pédagogique. **Il ne constitue pas un conseil
> en investissement.** Les performances passées ne préjugent pas des performances futures.
> Tout investissement comporte un risque de perte en capital. Sauhabah Ethical Finance
> Platform n'est pas agréée par l'AMF. L'utilisateur reste seul responsable de ses
> décisions.

---

## 📜 Code Coverage

[![Quality Gate](https://sonarcloud.io/api/project_badges/measure?project=AzipSauhabah_ethical-finance&metric=alert_status)](https://sonarcloud.io/dashboard?id=AzipSauhabah_ethical-finance)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=AzipSauhabah_ethical-finance&metric=coverage)](https://sonarcloud.io/dashboard?id=AzipSauhabah_ethical-finance)
[![Maintainability](https://sonarcloud.io/api/project_badges/measure?project=AzipSauhabah_ethical-finance&metric=sqale_rating)](https://sonarcloud.io/dashboard?id=AzipSauhabah_ethical-finance)

---

## 📄 Licence

GPL-3.0 — © 2024 Sauhabah. Voir [LICENSE](LICENSE).

---

**Author** : [Azip Sauhabah](https://github.com/AzipSauhabah)
**Live demo** : <https://efficient-portfolio2.vercel.app>
