# 🚀 Ethical Finance Platform — A Sauhabah

> Backtest event-driven, screening **Ethical + Sharia**, reporting institutionnel.
> Stack full-Python / React — backend auto-hébergé sur NAS Synology, frontend sur Vercel.

[![License: GPL v3](https://img.shields.io/badge/License-GPL_v3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
![Python](https://img.shields.io/badge/python-3.11-blue)
![React](https://img.shields.io/badge/react-18.3-61dafb)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688)
![Docker](https://img.shields.io/badge/Docker-Synology-2496ED)
![Cloudflare](https://img.shields.io/badge/Cloudflare-Tunnel-F38020)
![Version](https://img.shields.io/badge/version-2.1-b8962f)

**Live demo** : <https://efficient-portfolio2.vercel.app>
**API** : <https://api.sauhabah-advisory.eu>

---

## 📋 Sommaire

- [Fonctionnalités](#-fonctionnalités)
- [Architecture](#-architecture)
- [Infrastructure NAS](#-infrastructure-nas-synology)
- [Démarrage rapide](#-démarrage-rapide)
- [Déploiement NAS](#-déploiement-nas-synology--docker)
- [Ajouter une nouvelle stratégie](#-ajouter-une-nouvelle-stratégie-en-3-minutes)
- [Stratégies disponibles](#-stratégies-disponibles)
- [Filtres Ethical & Sharia](#-filtres-ethical--sharia)
- [Méthodologie quantitative](#-méthodologie-quantitative)
- [Cache & performance](#-cache--performance)
- [FAQ](#-faq)

---

## ✨ Fonctionnalités

- **Screening dual** — Ethical (ESG sectoriel) ET Sharia (AAOIFI), chaque filtre activable indépendamment.
- **11 stratégies built-in** — Buy & Hold, Equal-Weight, Momentum, Mean Reversion, SMA Crossover, Risk Parity, Min Variance, Dual Momentum, Adaptive Trend, ML Ensemble (RF+GBM walk-forward), **EPR5** (Magic Formula + filtres SPX/VIX style Lean).
- **Builder de stratégies custom** — JSON → règles compilées dynamiquement.
- **Backtest STRICT event-driven** — la stratégie ne voit que les prix passés à chaque date, aucune fuite du futur n'est possible par construction.
- **Frais broker RÉELS** — Fortuneo (50 USD flat sous 7 500 USD), Degiro, Bourse Direct, Interactive Brokers, chacun avec sa vraie grille tarifaire.
- **Taxes françaises** — PFU 30 %, TTF 0.1 %, PEA exonération après 5 ans.
- **25+ métriques** — Sharpe, Sortino, Calmar, Omega, Treynor, VaR/CVaR, skewness, kurtosis, tail ratio, hit rate, profit factor, beta, alpha de Jensen, information ratio.
- **Tests statistiques** — Jobson-Korkie, bootstrap CI, t-test sur alpha de Jensen, White's Reality Check.
- **Stress tests** — 5 crises historiques (GFC 2008, COVID 2020, Bear 2022, Dot-com, EU 2011).
- **Monte Carlo** vectorisé (10 000 chemins GBM + bootstrap par blocs) avec calibration bayésienne.
- **Signaux quotidiens** — vote multi-indicateurs (SMA, RSI, MACD, momentum).
- **Recommandations de rééquilibrage** intégrant les coûts réels.
- **Quotes temps réel** via Server-Sent Events (thread background, refresh 60 s).
- **Rapport PDF 15+ pages style Goldman Sachs** — 8 graphiques matplotlib HD : heatmap mensuelle, rolling Sharpe/Vol/Beta, underwater plot, distribution des rendements, win/loss distribution.
- **Fondamentaux SEC EDGAR officiels** — 30+ métriques US GAAP (PE, EV/EBITDA, ROE, ROIC, FCF yield, dette nette) pour tout le SP500. Mis à jour quotidiennement à 22h UTC.
- **Backend auto-hébergé** sur NAS Synology DS925+ via Cloudflare Tunnel — aucun port ouvert, HTTPS automatique.

---

## 🏗️ Architecture

```
ethical-finance/
├── backend/                        # Backend Python (FastAPI sur NAS Synology)
│   ├── config.py                   # TOUTES les constantes (broker fees, taxes…)
│   ├── app.py                      # App FastAPI + scheduler APScheduler
│   ├── core/
│   │   ├── db.py                   # PostgreSQL via SQLAlchemy (ORM + upsert)
│   │   ├── cache.py                # L1 LRU + L2 Redis
│   │   ├── loader.py               # Chargement / mise à jour OHLCV daily
│   │   └── queue.py                # Thread background quotes live + SSE
│   ├── quant/
│   │   ├── metrics.py              # 25+ métriques pures
│   │   ├── signals.py              # Indicateurs techniques + ML
│   │   ├── significance.py         # Tests stats (Jobson-Korkie, bootstrap)
│   │   └── montecarlo.py           # MC + calibration bayésienne
│   ├── strategies/
│   │   ├── base.py                 # Classe abstraite Strategy.on_bar
│   │   ├── registry.py             # Auto-discovery @register
│   │   └── builtin/                # ← AJOUTEZ VOS STRATÉGIES ICI
│   │       ├── all_strategies.py
│   │       └── epr5.py
│   ├── backtest/
│   │   ├── engine.py               # STRICT event-driven date-par-date
│   │   ├── portfolio.py            # NAV, cash, positions, corrélations
│   │   ├── costs.py                # Frais broker RÉELS + taxes FR
│   │   └── stress.py               # 5 crises historiques
│   └── report/
│       ├── pdf.py                  # PDF 12 pages style GS (matplotlib)
│       └── tearsheet.py            # Dict structuré JSON-serialisable
│
├── src/                            # Frontend React + Vite + TypeScript (Vercel)
│   ├── App.tsx
│   ├── components/
│   │   ├── BacktestPanel.tsx
│   │   ├── SignalsPanel.tsx
│   │   ├── ScreeningPanel.tsx
│   │   └── TickerManager.tsx
│   └── utils/api.ts                # Client API → https://api.sauhabah-advisory.eu
│
├── Dockerfile                      # Image backend FastAPI
├── docker-compose.yml              # FastAPI + PostgreSQL sur NAS
├── docs/
│   └── synology_cloudflare_docker_architecture.svg
├── vercel.json                     # Frontend React uniquement
├── requirements.txt
└── package.json
```

---

## 🌐 Infrastructure NAS Synology

L'intégralité du backend tourne en auto-hébergement sur un **NAS Synology DS925+**, exposé publiquement via un **Cloudflare Tunnel** — sans aucun port ouvert sur la box.

![Architecture Synology — Cloudflare Tunnel + backends Docker](docs/synology_cloudflare_docker_architecture.svg)

### Stack infrastructure

| Couche | Technologie | URL publique |
|--------|-------------|--------------|
| DNS + Proxy + TLS | Cloudflare (Free) | `*.sauhabah-advisory.eu` |
| Tunnel sécurisé | `cloudflared` Docker | — |
| Backend API | FastAPI + Uvicorn | `https://api.sauhabah-advisory.eu` |
| Base de données | PostgreSQL 16 (Docker) | interne |
| Gestionnaire de mots de passe | Vaultwarden | `https://vault.sauhabah-advisory.eu` |
| Hébergement Git | Gitea | `https://git.sauhabah-advisory.eu` |
| Domaine | OVH Registrar | `sauhabah-advisory.eu` |
| Frontend | Vercel (CDN) | `https://efficient-portfolio2.vercel.app` |

### Pourquoi ce choix d'architecture ?

- **Pas de port forwarding** — le tunnel Cloudflare est purement sortant (outbound), la box n'expose rien.
- **HTTPS automatique** — Cloudflare termine le TLS, le trafic interne reste en HTTP simple.
- **Performances** — le NAS DS925+ avec 32 Go RAM peut faire tourner TensorFlow, LightGBM, matplotlib sans les restrictions CPU/RAM de Vercel serverless.
- **Coût** — zéro € d'hébergement backend (NAS déjà possédé), domaine ~5€/an OVH.
- **Confidentialité** — données financières stockées localement, pas dans le cloud.

---

## 🚀 Démarrage rapide

### Prérequis
- Python 3.11+
- Node.js 18+
- Docker (pour le NAS) ou PostgreSQL local

### Développement local

```bash
git clone https://github.com/AzipSauhabah/ethical-finance.git
cd ethical-finance

python3.11 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

# Variables d'environnement
cp .env.example .env
# éditer .env : DATABASE_URL=postgresql://...

uvicorn backend.app:app --reload --port 8000
```

### Frontend (dans un autre terminal)

```bash
npm install
npm run dev
```

→ Ouvrir <http://localhost:5173>

---

## 🐳 Déploiement NAS Synology + Docker

### 1. Préparer les dossiers sur le NAS

```bash
mkdir -p /volume1/docker/ethical-finance/postgres
mkdir -p /volume1/docker/ethical-finance/data
```

### 2. Copier les fichiers sur le NAS

```bash
scp Dockerfile docker-compose.yml .env user@192.168.1.47:/volume1/docker/ethical-finance/
scp -r backend/ user@192.168.1.47:/volume1/docker/ethical-finance/
```

### 3. Créer le fichier .env

```bash
cp .env.example .env
# Éditer .env :
# DB_PASSWORD=MotDePasseForte123!
```

### 4. Build et lancement

```bash
ssh user@192.168.1.47
cd /volume1/docker/ethical-finance
docker-compose up -d --build
```

### 5. Vérifier

```bash
curl http://192.168.1.47:8000/docs
```

### 6. Route Cloudflare

Dans Cloudflare Zero Trust → Networks → Connectors → sauhabah-nas → Published application routes :

| Subdomain | Domain | Service |
|-----------|--------|---------|
| `api` | `sauhabah-advisory.eu` | `http://192.168.1.47:8000` |
| `vault` | `sauhabah-advisory.eu` | `http://192.168.1.47:8222` |
| `git` | `sauhabah-advisory.eu` | `http://192.168.1.47:3000` |

### Variables d'environnement

| Variable | Description | Obligatoire |
|----------|-------------|-------------|
| `DATABASE_URL` | URL PostgreSQL | Oui |
| `APP_ENV` | `production` ou `development` | Non |
| `KV_REST_API_URL` | Vercel KV (cache L2) | Non |
| `KV_REST_API_TOKEN` | Token Vercel KV | Non |
| `DB_PASSWORD` | Mot de passe PostgreSQL | Oui |

---

## 🆕 Ajouter une nouvelle stratégie en 3 minutes

**Pas besoin de toucher la GUI.** Le frontend lit dynamiquement la liste des stratégies via `/api/strategies`.

### Étape 1 — Créer le fichier

Dans `backend/strategies/builtin/`, créez `ma_strategie.py` :

```python
from __future__ import annotations
from datetime import date
from typing import Any
import pandas as pd
from backend.strategies.base import Strategy, StrategyParams
from backend.strategies.registry import strategy_registry

@strategy_registry.register
class MaStrategie(Strategy):
    """Long les actifs au-dessus de leur SMA 100."""

    requires_warmup_days = 100

    @property
    def name(self) -> str:
        return "ma_strategie"

    @property
    def description(self) -> str:
        return "Long les actifs au-dessus de leur SMA 100"

    @property
    def benchmark(self) -> str:
        return "^GSPC"

    def on_bar(self, dt: date, past_prices: pd.DataFrame,
               params: StrategyParams, state: dict[str, Any]) -> dict[str, float]:
        sma_window = int(params.custom.get("sma_window", 100))
        if len(past_prices) < sma_window:
            return {}
        sma = past_prices.iloc[-sma_window:].mean()
        current = past_prices.iloc[-1]
        winners = current[current > sma].index
        if not len(winners):
            return {}
        weight = 1.0 / len(winners)
        return {ticker: weight for ticker in winners}
```

### Étape 2 — Redémarrer

```bash
docker-compose restart api
```

### Conventions importantes

| Aspect | Règle |
|--------|-------|
| **Pas de look-ahead** | `past_prices` ne contient jamais de futur |
| **Retourner des poids** | Somme ≤ 1, le reste est du cash |
| **State persistant** | `state["ma_clé"] = ...` persiste entre les barres |
| **ML walk-forward** | Ajouter `is_walkforward_trained = True` et `walkforward_refit_days = 60` |

---


## 🧠 Stratégies disponibles

| Stratégie | Description | Benchmark |
|-----------|-------------|-----------|
| Buy & Hold | Allocation statique équipondérée | ^GSPC |
| Equal-Weight | Rééquilibrage mensuel équipondéré | ^GSPC |
| Momentum | Rendement 12-1 mois, top quintile | ^GSPC |
| Mean Reversion | Z-score 20j, contre-tendance | ^GSPC |
| SMA Crossover | Croisement 50/200 jours | ^GSPC |
| Risk Parity | Pondération inverse de la volatilité | ^GSPC |
| Min Variance | Optimisation Markowitz variance minimale | ^GSPC |
| Dual Momentum | Momentum absolu + relatif (Antonacci) | ^GSPC |
| Adaptive Trend | Filtre de tendance adaptatif multi-timeframe | ^GSPC |
| ML Ensemble | RandomForest + GBM walk-forward | ^GSPC |
| **EPR5** | Magic Formula + SPX/VIX + RF + **LSTM TensorFlow** | ^GSPC |

---

## 🔬 Méthodologie quantitative

### Backtest event-driven strict

Le moteur de backtest simule le passage du temps jour par jour. À chaque date `t`, la stratégie ne voit que les données disponibles jusqu'à `t-1`. Aucune donnée future ne peut fuiter dans les décisions de trading — c'est la garantie fondamentale de validité des résultats.

**Frais réels intégrés :**
- Commissions broker : grille tarifaire réelle (Fortuneo, Degiro, Bourse Direct, IBKR)
- Slippage : modèle linéaire calibré sur la liquidité du titre
- Spread FX EUR/USD : taux réel de la date d'exécution
- TTF (Taxe sur les Transactions Financières) : 0.1% sur actions françaises
- PFU 30% (Flat Tax) ou exonération PEA après 5 ans

### Métriques de risque

- **Sharpe** : `(CAGR - Rf) / Vol_annualisée` avec Rf = 0%
- **Sortino** : pénalise uniquement la volatilité négative (downside deviation)
- **Calmar** : `CAGR / |Max Drawdown|` — horizon long terme
- **VaR/CVaR historique** à 95% et 99% — simulation historique pure, sans hypothèse gaussienne
- **Omega** : ratio probabilité de gain / probabilité de perte au-delà d'un seuil
- **Tail Ratio** : `CVaR_gain / CVaR_perte` — asymétrie des queues de distribution

### Tests statistiques

- **Jobson-Korkie** : test de significativité de la différence de Sharpe entre stratégie et benchmark
- **Bootstrap IC 95%** sur le Sharpe : 10 000 rééchantillonnages par blocs (Stationary Bootstrap)
- **t-test Jensen alpha** : H0 = alpha = 0, p-value bilatérale

---

## 🤖 EPR5 — Magic Formula + IA Hybride

EPR5 est la stratégie phare de la plateforme. Elle combine :

### 1. Sélection fondamentale — Magic Formula (Greenblatt)

**Earning Yield** = `EBIT / Enterprise Value`
**ROIC** = `EBIT / Net Assets`

Les titres sont rankés par la somme des rangs (EY + ROIC). Le top quintile (paramètre `top_quintile_pct`, défaut 20%) est sélectionné.

> **Hypothèse** : les titres sous-évalués avec un fort retour sur capital tendent à surperformer à moyen terme (12-18 mois). Cette hypothèse est validée empiriquement sur le marché US sur la période 1988-2004 (Greenblatt, 2005).

### 2. Filtre de régime de marché

**Condition** : S&P 500 > sa moyenne mobile à `ma_window` jours (défaut : 200j)

> **Hypothèse** : un marché en tendance haussière (SPX au-dessus de sa MM200) favorise les stratégies long-only. En bear market, la stratégie est mise en veille pour protéger le capital.

### 3. Timing VIX

**Condition** : VIX < sa moyenne mobile à `vix_ma_window` jours (défaut : 10j)

> **Hypothèse** : la volatilité implicite (VIX) est un proxy de la peur des marchés. Entrer en position quand le VIX repasse sous sa moyenne mobile indique une détente des conditions de marché — contexte favorable aux positions acheteuses.

### 4. ML Score — RandomForest (scikit-learn)

**Features** (11 indicateurs techniques) :
- Rendements : 1j, 5j, 20j, 60j
- Volatilité réalisée : 20j, 60j
- Position relative aux MM20, MM50, MM200 (0/1)
- RSI-14 normalisé [0,1]
- Momentum 12 mois

**Architecture** :
- RandomForestClassifier : 50 arbres, profondeur max 4, class_weight="balanced"
- Labels : 1 si rendement à 20j > +5%, 0 sinon
- Walk-forward : réentraîné tous les `walkforward_refit_days` jours (défaut 60j) sur les données passées uniquement

> **Hypothèse** : les patterns techniques historiques contiennent de l'information prédictive sur le rendement à court terme. Le RF capture les interactions non-linéaires entre indicateurs que les modèles linéaires manquent.

### 5. ML Score — LSTM TensorFlow *(nouveau)*

**Architecture du réseau** :
```
Input (30j × 11 features)
    → LSTM(64 units, return_sequences=True)
    → Dropout(0.2)
    → LSTM(32 units)
    → Dropout(0.2)
    → Dense(16, ReLU)
    → Dropout(0.3)
    → Dense(1, sigmoid)
```

**Features temporelles** (séquence de 30 jours) :
- Rendements : 1j, 5j, 20j
- Volatilité réalisée : 10j, 20j
- RSI-14 normalisé
- EMA20/EMA50 ratio (tendance)
- MACD histogram normalisé
- Position dans les bandes de Bollinger [0,1]
- Momentum : 20j, 60j

**Entraînement** :
- Horizon de prédiction : 5 jours
- Seuil positif : rendement > +2%
- Walk-forward : réentraîné en même temps que le RF (tous les 60j)
- Epochs : 10, batch_size : 32, validation_split : 15%
- Optimiseur : Adam (lr=1e-3), loss : binary_crossentropy

**Score final combiné** :
```
score_final = 0.6 × RF_score + 0.4 × LSTM_score
```

> **Hypothèse LSTM** : les dépendances temporelles dans les séries de prix (momentum, mean-reversion, régimes de volatilité) contiennent de l'information que le RF ne capte pas car il ignore l'ordre des observations. Le LSTM, par sa mémoire à long terme sélective (portes input/forget/output), est architecturalement adapté à la prédiction de séries financières non-stationnaires.

> **Limites** : le LSTM suppose que les patterns temporels passés se répètent. Cette hypothèse est fragile en période de rupture de régime. Le modèle ne tient pas compte des données fondamentales ou macroéconomiques. Sur des horizons très courts (1-5j), le rapport signal/bruit est faible et la précision hors-échantillon est modeste (55-62% en conditions normales).

### 6. Sizing dynamique — Monte Carlo

**Taille de base** : 10% de la NAV par titre

**Multiplicateur MC** : calculé sur le Sharpe glissant des 60 derniers trades
```
mult = clip(1.0 + Sharpe_proxy × 5, 0.5, 1.5)
```
- Stratégie récemment performante → augmente légèrement les positions (max 1.5×)
- Stratégie en difficulté → réduit les positions (min 0.5×)

### 7. Sorties de position

- **Profit target** : `+profit_target`% (défaut 20%, paramétrable 10-25%)
- **Stop ATR** : `max(-1 000€ absolu, -atr_stop_mult × ATR14)` (défaut mult=2.0)

> Le stop combiné (dollar absolu + ATR) protège contre les gaps violents tout en laissant respirer les positions en conditions normales de volatilité.

### Paramètres configurables EPR5

| Paramètre | Défaut | Plage | Description |
|-----------|--------|-------|-------------|
| `profit_target` | 0.20 | 0.10–0.25 | Objectif de gain par position |
| `atr_stop_mult` | 2.0 | 1.5–3.0 | Multiplicateur ATR pour le stop |
| `top_quintile_pct` | 0.20 | 0.10–0.30 | % de l'univers sélectionné |
| `ma_window` | 200 | 150–250 | Fenêtre MM filtre de tendance |
| `vix_ma_window` | 10 | 5–15 | Fenêtre MM du VIX |
| `ml_min_score` | 0.50 | 0.45–0.70 | Score ML minimum pour entrer |

---

## 📄 Rapport PDF institutionnel

Le rapport généré comprend 15 pages :

1. **Cover** — identité de la stratégie et date
2. **Résumé exécutif** — narrative contextuelle (générée automatiquement selon les métriques)
3. **Performance NAV vs Benchmark** — graphique évolution + commentaire analytique
4. **Analyse du drawdown** — graphique + récupération
5. **Métriques de risque** — VaR/CVaR quotidien et annualisé
6. **Stress tests** — 5 crises historiques avec graphique
7. **Évolution des coûts** — commissions cumulées
8. **Décomposition des coûts** — pie chart + tableau
9. **Allocation Cash vs Investi** — évolution temporelle
10. **Significativité statistique** — Jobson-Korkie, bootstrap, t-test alpha
11. **Positions finales** — tableau détaillé
12. **Journal des trades** — jusqu'à 300 trades
13. **Risque par position** — VaR individuelle + contribution au risque
14. **Intelligence artificielle** — description des modèles ML/LSTM utilisés
15. **Méthodologie, limites, glossaire** — hypothèses et avertissements réglementaires

> Les narratives analytiques de chaque section sont générées dynamiquement selon les valeurs réelles des métriques (Sharpe, drawdown, alpha, stress tests). Le ton et le contenu s'adaptent automatiquement : une stratégie avec Sharpe > 2 reçoit un commentaire différent d'une stratégie avec Sharpe < 0.5.

---

## 🌍 Univers d'investissement

| Univers | Tickers | Description |
|---------|---------|-------------|
| `sp500` | 483 | Actions S&P 500 — grandes capitalisations US |
| `cac40` | 34 | Actions CAC 40 — grandes capitalisations françaises |
| `etf_broad` | 6 | ETF indiciels mondiaux (MSCI World, S&P 500 UCITS) |
| `etf_precious_metals` | 6 | ETF métaux précieux (GLD, IAU, SLV, SGOL, PPLT, PALL) |

Les données OHLCV couvrent la période 2006–2026 (20 ans) et sont mises à jour quotidiennement via un scheduler APScheduler à 21h.


## 🛡️ Filtres Ethical & Sharia

**Deux jeux de critères INDÉPENDANTS** activables par checkbox dans le Backtest.

### Ethical Screen (ESG occidental)
- Exclusion sectorielle : armement, tabac, jeux d'argent, énergies fossiles, pornographie
- Ratio dette / capitalisation ≤ 33 %
- Revenus d'intérêts / CA ≤ 5 %

### Sharia Screen (AAOIFI / Dow Jones Islamic Market)
1. **Activité halal** — pas de banque, assurance, alcool, porc, tabac, jeu, armes
2. **Dette portant intérêts / capitalisation ≤ 33 %**
3. **Liquidités productives / capitalisation ≤ 33 %**
4. **Revenus non-permis / CA ≤ 5 %**

---

## 🧪 Méthodologie quantitative

### Strict event-driven (anti look-ahead)
À chaque jour de trading, le moteur appelle `strategy.on_bar(dt, past_prices[:dt], params, state)`. Le DataFrame `past_prices` est mécaniquement tronqué à `dt` inclus.

### Coûts réels intégrés
- **Degiro** : 0.50 € + 0.04 %
- **Fortuneo** : 50 USD fixe sous 7 500 USD, puis 0.20 % + 9 USD
- **Bourse Direct** : 0.99 € fixe
- **Interactive Brokers** : 0.05 % cap 1 USD
- **Slippage** par capitalisation (2/5/15 bps)

### Taxes françaises
- **PFU** 30 % (12.8 % IR + 17.2 % PS)
- **TTF** 0.1 % à l'achat pour entreprises FR > 1 Md€
- **PEA** exonéré IR après 5 ans

### Significativité
- **Jobson-Korkie** — test de différence de Sharpe vs benchmark
- **Bootstrap CI** — intervalle de confiance Sharpe non-paramétrique
- **t-test Jensen alpha**
- **White's Reality Check** — correction multi-tests

---

## ⚡ Cache & performance

| Niveau | Type | Persistance | TTL |
|--------|------|-------------|-----|
| **L1** | LRU in-memory | Vidé au redémarrage | 1 h |
| **L2** | Redis / Vercel KV | Persiste entre sessions | 1 h prix / 24 h fondamentaux |

---

## ❓ FAQ

**Pourquoi NAS plutôt que Vercel pour le backend ?**
Vercel serverless est limité à 250 Mo RAM et 10 s de timeout — incompatible avec TensorFlow, LightGBM, matplotlib, et les backtests longs. Le NAS DS925+ avec 32 Go RAM n'a aucune de ces contraintes, pour un coût marginal nul (NAS déjà possédé).

**Pourquoi Cloudflare Tunnel plutôt que port forwarding ?**
Aucun port ouvert sur la box = surface d'attaque nulle. Cloudflare filtre les attaques DDoS et gère le TLS en amont.

**Pourquoi pas Zipline ?**
Zipline est en fin de maintenance et requiert SQLite local + bundles → incompatible avec l'architecture cloud/NAS. Le moteur custom adopte les conventions Lean (event-driven, `on_bar`, past_prices, state) sans le coût d'infrastructure.

**Comment ajouter un broker ?**
Éditez `backend/config.py` → `BROKER_FEES` → ajoutez une entrée avec la grille tarifaire.

---

## 📜 Disclaimer

> Ce projet est fourni à titre informatif et pédagogique. **Il ne constitue pas un conseil
> en investissement.** Les performances passées ne préjugent pas des performances futures.
> Tout investissement comporte un risque de perte en capital. Sauhabah Ethical Finance
> Platform n'est pas agréée par l'AMF.

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
**API** : <https://api.sauhabah-advisory.eu>
**Git** : <https://git.sauhabah-advisory.eu>
