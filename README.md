# 🚀 Ethical Finance Platform — Sauhabah

> Backtest, optimisation et reporting institutionnel pour portefeuilles **éthiques**.
> Stack full-Python / React / Vercel, niveau quant institutionnel.

[![License: GPL v3](https://img.shields.io/badge/License-GPL_v3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
![Python](https://img.shields.io/badge/python-3.11-blue)
![React](https://img.shields.io/badge/react-18.3-61dafb)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)

---

## ✨ Fonctionnalités

- **Screening éthique automatique** — exclusion sectorielle (armement, tabac, fossiles, jeux) + ratios financiers (dette / revenus d'intérêts).
- **10 stratégies quantitatives built-in** : Buy & Hold, Equal-Weight, Momentum, Mean Reversion, SMA Crossover, Risk Parity, Min Variance (Markowitz), Dual Momentum (Antonacci), Adaptive Trend, ML Ensemble (RF + GBM).
- **Builder de stratégies custom** — JSON → règles compilées dynamiquement.
- **Backtest event-driven path-dependent** — simulation jour par jour, positions entières, FX EUR/USD, slippage par capitalisation, taxes françaises (PFU 30 %, TTF 0,1 %), schedules par courtier (Degiro, Fortuneo, Bourse Direct, IBKR).
- **25+ métriques** — Sharpe, Sortino, Calmar, Omega, Treynor, VaR/CVaR (historique + paramétrique), skewness, kurtosis, tail ratio, hit rate, profit factor, beta, alpha de Jensen, information ratio.
- **Tests statistiques** — Jobson-Korkie (différence de Sharpe), t-test sur l'alpha de Jensen, bootstrap CI, White's Reality Check.
- **Stress tests** sur 5 crises historiques (GFC 2008, COVID 2020, Bear 2022, Dot-com 2000, Crise EU 2011).
- **Monte Carlo** vectorisé (GBM + bootstrap par blocs) avec calibration bayésienne (scikit-optimize).
- **Signaux quotidiens** d'achat/vente (vote multi-indicateurs : SMA, RSI, MACD, momentum).
- **Recommandations de rééquilibrage** intégrant les coûts réels.
- **Quotes temps réel** via Server-Sent Events (thread background, refresh 60 s).
- **Rapport PDF style Goldman Sachs** — cover, executive summary, charts, stress tests, coûts, significativité, glossaire.
- **Caching deux niveaux** — LRU in-memory + Vercel KV (Redis REST).

---

## 🏗️ Architecture

```
efficient-portfolio2/
├── api/                       # Backend Python (FastAPI sur Vercel)
│   ├── config.py              # TOUTES les constantes (broker fees, taux, etc.)
│   ├── index.py               # Routes FastAPI (thin layer uniquement)
│   ├── core/
│   │   ├── cache.py           # Vercel KV + LRU in-memory
│   │   ├── data.py            # Multi-source (yfinance → Stooq → GBM)
│   │   ├── registry.py        # Registre tickers + screening éthique
│   │   └── queue.py           # asyncio Queue + thread background prix live
│   ├── quant/
│   │   ├── metrics.py         # 25+ métriques pures
│   │   ├── signals.py         # Signaux techniques + ML (RF, GBM)
│   │   ├── significance.py    # Tests stats (Jobson-Korkie, bootstrap, alpha)
│   │   └── montecarlo.py      # Monte Carlo + calibration bayésienne
│   ├── strategies/
│   │   ├── base.py            # Classe abstraite Strategy (template pattern)
│   │   ├── registry.py        # Registre dynamique (@decorator)
│   │   ├── builtin/
│   │   │   └── all_strategies.py  # 10 stratégies built-in
│   │   └── custom.py          # Builder interface (JSON → Strategy)
│   ├── backtest/
│   │   ├── engine.py          # Event-driven loop (date par date)
│   │   ├── portfolio.py       # NAV, cash, positions entières, corrélations
│   │   ├── costs.py           # Frais broker RÉELS + slippage + taxes FR
│   │   └── stress.py          # Stress tests historiques
│   ├── report/
│   │   ├── tearsheet.py       # Métriques complètes par stratégie
│   │   ├── pdf.py             # PDF Goldman Sachs style (ReportLab)
│   │   └── glossary.py        # Glossaire FR/EN
│   └── signals/
│       ├── daily.py           # Signaux achat/vente journaliers
│       └── rebalance.py       # Recommandations de rebalancement
│
├── src/                       # Frontend React + Vite + TypeScript
│   ├── App.tsx                # Shell avec onglets
│   ├── main.tsx               # Entry point
│   ├── components/
│   │   ├── AboutPanel.tsx     # Présentation + stack technique
│   │   ├── TickerManager.tsx  # Ajout tickers + screening + quotes live
│   │   ├── BacktestPanel.tsx  # Config backtest + résultats + PDF download
│   │   └── SignalsPanel.tsx   # Signaux quotidiens + rebalance
│   ├── hooks/
│   │   └── useLiveQuotes.ts   # Hook SSE pour prix temps réel
│   ├── types/
│   │   └── index.ts           # Types TypeScript partagés
│   └── utils/
│       └── api.ts             # Client API typé
│
├── vercel.json                # Routing Vercel (Python + SPA)
├── requirements.txt           # Dépendances Python
├── package.json               # Dépendances Node
├── tsconfig.json              # Config TypeScript
└── vite.config.ts             # Config Vite + proxy dev
```

---

## 🚀 Installation & démarrage

### Backend Python

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn api.index:app --reload --port 8000
```

### Frontend React

```bash
npm install
npm run dev
```

Le frontend est dispo sur <http://localhost:5173>, l'API sur <http://localhost:8000>.
Le proxy Vite redirige automatiquement `/api/*` vers le backend.

### Déploiement Vercel

```bash
vercel deploy
```

`vercel.json` route les requêtes `/api/*` vers la function Python serverless,
le reste vers le SPA statique.

---

## 🔧 Variables d'environnement

| Variable | Description |
|----------|-------------|
| `KV_REST_API_URL`   | URL REST du store Vercel KV |
| `KV_REST_API_TOKEN` | Token d'authentification |
| `APP_ENV`           | `development` ou `production` |

---

## 📊 Exemple d'usage API

### Screening de tickers

```bash
curl -X POST http://localhost:8000/api/tickers/screen \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["AAPL", "MSFT", "MC.PA", "TTE"]}'
```

### Backtest

```bash
curl -X POST http://localhost:8000/api/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "tickers": ["AAPL", "MSFT", "GOOGL"],
    "strategy": "risk_parity",
    "period": "10y",
    "initial_capital": 30000,
    "monthly_contribution": 500,
    "broker": "degiro",
    "account_type": "CTO",
    "rebalance_frequency": "monthly",
    "max_position_pct": 0.25,
    "stop_loss_pct": 0.10,
    "benchmark": "^GSPC"
  }'
```

### Export PDF

```bash
curl -X POST http://localhost:8000/api/backtest/pdf \
  -H "Content-Type: application/json" \
  -d '{ ... mêmes paramètres ... }' \
  --output rapport.pdf
```

---

## 🧪 Méthodologie quantitative

- **Path-dependent backtesting** : la NAV est recalculée jour après jour ; à chaque date,
  on applique stop-loss, signaux, rebalancement, frais et FX réels.
- **Frais broker réels** :
  - Degiro : 0.50 € + 0.04 % (EU)
  - Fortuneo : **50 USD fixe** sous 7 500 USD, puis 0.20 % + 9 USD
  - Bourse Direct : 0.99 € fixe
  - Interactive Brokers : 0.05 % avec cap 1 USD
- **Taxes françaises** : PFU 30 %, TTF 0.1 % > 1 Md€, PEA exonéré après 5 ans (PS 17.2 % seulement).
- **Slippage** par capitalisation (2/5/15 bps), spread FX 3 bps.
- **Significativité** : tout résultat est testé par Jobson-Korkie (vs benchmark) et bootstrap CI.

---

## 🐍 Style Python

Code Python avancé (C1/C2) :
- Programmation **fonctionnelle** (lambdas, générateurs paresseux, map/filter)
- **Modules** dédiés par responsabilité (SRP)
- **Async/await** partout pour l'I/O
- **Type hints** stricts (PEP 585, `from __future__ import annotations`)
- **Multiprocessing/threading** pour les jobs lourds (price feed background)
- **Decorateurs** (`@cached`, `@strategy_registry.register`)
- **Dataclasses** pour les modèles
- **Constantes externalisées** dans `api/config.py`
- **Docstrings Doxygen-style** (`:param:`, `:returns:`, `:brief:`) — peut être généré avec Sphinx :

```bash
pip install sphinx sphinx-autodoc-typehints
sphinx-apidoc -o docs/source api/
sphinx-build -b html docs/source docs/build
```

---

## 📜 Disclaimer

> Ce projet est fourni à titre informatif et pédagogique. **Il ne constitue pas un conseil
> en investissement.** Les performances passées ne préjugent pas des performances futures.
> Tout investissement comporte un risque de perte en capital. Sauhabah Ethical Finance
> Platform n'est pas agréée par l'AMF. L'utilisateur reste seul responsable de ses
> décisions.

---

## 📄 Licence

GPL-3.0 — © 2026 Sauhabah. Voir [LICENSE](LICENSE) pour les détails.

---

## ❓ FAQ

**Pourquoi mettre le repo en public ?**
Aucun secret commercial n'est exposé : pas de clés API en dur, pas de modèle propriétaire,
pas de stratégie alpha-générant elle-même. Le repo public sert de **portfolio
technique** démontrant des compétences en quant finance, Python avancé, FastAPI,
React/TS, et déploiement serverless.

**Y a-t-il une IA / LLM intégrée ?**
Pas de LLM conversationnelle (volontairement, pour éviter les hallucinations sur
des sujets financiers). En revanche : ML via scikit-learn (Random Forest +
Gradient Boosting) pour les signaux, et optimisation bayésienne (scikit-optimize)
pour la calibration des hyperparamètres de stratégie.

**Comment ajouter une nouvelle stratégie ?**
Deux options :
1. **Programmatique** : créer une classe dans `api/strategies/builtin/` héritant de
   `Strategy`, décorer avec `@strategy_registry.register`. C'est tout — la stratégie
   apparaît automatiquement dans le dropdown du frontend.
2. **Interface utilisateur** : POST `/api/strategies/custom` avec un JSON décrivant
   les règles (sma_crossover, rsi, momentum, mean_reversion) et leur combinaison
   (`all`, `any`, `majority`).

---

**Author** : [Azip Sauhabah](https://github.com/AzipSauhabah)
**Live demo** : <https://ethical-finance-ebon.vercel.app>
