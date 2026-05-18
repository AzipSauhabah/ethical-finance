# ☪️ Sauhabah Ethical Finance — Plateforme d'analyse quantitative

> Plateforme d'investissement éthique auto-hébergée, combinant backtesting event-driven, signaux ML/sentiment/fondamentaux, suivi de portefeuille en temps réel et analyse technique avancée. Gratuite, compréhensible, auto-critique.

Analyse 20+ métriques quant, backtest des stratégies Renaissance & Buffett, optimise des portefeuilles ETF halal multi-actifs, simule du DCA intelligent, génère des rapports PDF institutionnels — le tout sur un NAS auto-hébergé avec pipeline de données automatisé.

🔗 **Live** : [app.sauhabah-advisory.eu](https://app.sauhabah-advisory.eu)
🔗 **API** : [api.sauhabah-advisory.eu](https://api.sauhabah-advisory.eu/docs)
📦 **Repo** : [github.com/AzipSauhabah/ethical-finance](https://github.com/AzipSauhabah/ethical-finance)

[![NAS](https://img.shields.io/badge/Hébergement-Synology%20DS925%2B-blue)](https://www.synology.com)
[![Docker](https://img.shields.io/badge/Runtime-Docker%20Compose-2496ED)](https://docker.com)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%2FVite%2FTS-61DAFB)](https://vitejs.dev)
[![PostgreSQL](https://img.shields.io/badge/DB-PostgreSQL%2016-336791)](https://postgresql.org)
[![Cloudflare](https://img.shields.io/badge/Tunnel-Cloudflare-F38020)](https://cloudflare.com)

---

## Architecture de la plateforme (v2)

```
┌─────────────────────────────────────────────────────────────────────┐
│  COUCHE DONNÉES  (PostgreSQL — source principale, zéro yfinance RT) │
│  OHLCV+splits │ Fundamentals SEC │ NAV div.réinvestis │ Intraday WS │
│  Sentiment VADER │ Cache mémoire local (TTL)                         │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────┐
│  MOTEUR DE SIGNAUX  (strategy-aware — 5 votes combinés)              │
│  EPR5 RF+LSTM │ Sentiment VADER │ Fondamental SEC │ RSI/Fibo/Elliott │
│  Persistance automatique dans signals_history à 20h30 UTC            │
└────────────────────┬────────────────────────────────────────────────┘
                     │
         ┌───────────▼───────────┐
         │   Filtre stratégie    │
         │  Poids adaptés selon  │
         │  EPR5/Momentum/etc.   │
         └───┬───────────────┬───┘
             │               │
    ┌────────▼──────┐ ┌──────▼────────────┐
    │ Signaux J+J   │ │ Live intraday      │
    │ préd. J+1..5  │ │ WebSocket 15min    │
    └────────┬──────┘ └──────┬────────────┘
             └───────┬───────┘
┌────────────────────▼────────────────────────────────────────────────┐
│  PERSISTANCE PORTFOLIO  (auth JWT requise)                           │
│  users │ user_portfolios │ signals_history │ nav_history             │
└──────────────────────────────┬──────────────────────────────────────┘
                                │  JWT FastAPI — pages publiques sans login
┌──────────────────────────────▼──────────────────────────────────────┐
│  FRONTEND  React / Vite / TypeScript — dark theme institutionnel     │
│  Accueil │ Portfolio │ Screener │ Backtest │ Signaux │ Sentiment     │
│  Technical │ Indicateurs │ Live                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## ✨ Fonctionnalités

### ☪️ Halal-first
- 5 ETF Shariah-certifiés pré-chargés (ISWD, IUSF, ISDE, AMAL, HIWS)
- Informations Shariah board, notes de purification, éligibilité PEA/PER/CTO
- Badge halal par ticker dans toutes les vues

### 🌍 Screener multi-univers
- 5 univers séparés : SP500, CAC40, ETF broad, ETF Precious Metals, MSCI World
- 573 tickers, 2.75M lignes OHLCV, 615 fiches fondamentales SEC EDGAR
- Filtres Magic Formula, Piotroski, PE/PB/rendement

### 📊 20+ Métriques quantitatives
| Catégorie | Métriques |
|---|---|
| Performance | CAGR, Total Return, Annualized Slope |
| Risk-adjusted | Sharpe, Sortino, Calmar, Omega, Martin |
| Drawdown | Max Drawdown, Ulcer Index, Pain Index |
| Tail Risk | VaR 95/99%, CVaR 95/99%, Tail Ratio |
| Distribution | Skewness, Excess Kurtosis, Jarque-Bera p-value |
| Structure | Autocorrelation lag-1, Log R² (Buffett linearity score) |
| Trade stats | Win Rate, Avg Win/Loss, Profit Factor |

### 🔬 Stratégies backtestables
- **EPR5** — RF + LSTM TensorFlow (40%/60%), 5 votes combinés
- **Buffett Quality** — Log R² linearity + low volatility + momentum
- **Renaissance Composite** — Multi-factor stat-arb signal
- **Dual Momentum** (Antonacci) — Absolute + relative momentum
- **Trend Following EMA 50/200**, **Mean Reversion Z-Score**, **RSI Contrarian**
- **SMA Crossover, Adaptive Trend, Buy & Hold, Equal Weight, Min Variance, Risk Parity**

Toutes les stratégies intègrent un `PositionManager` (ATR sizing, stop-loss, trailing stop).

**Réalisme broker :**
- Fortuneo / Boursorama / Degiro → actions entières uniquement (`floor`)
- Revolut → fractions d'actions permises (toggle)
- Toggle dividendes réinvestis (`adj_close`) ou perçus en cash (`close`)

### 🎯 Moteur de signaux strategy-aware (v2)
- **5 votes combinés** : SMA crossover, MACD, Sentiment VADER, RSI, Momentum
- **Poids adaptés selon la stratégie choisie** (EPR5 / Momentum / Mean Reversion / etc.)
- **Persistance automatique** dans `signals_history` à 20h30 UTC via APScheduler
- 573 tickers × 6 stratégies archivés chaque jour
- Prédictions J+1 à J+5 affichées dans le Dashboard Signaux
- Dans quelques années : vérification a posteriori de la qualité des prédictions

### 📈 Indicateurs techniques configurables (v2)
- **RSI** — période variable (5-30), seuils oversold/overbought ajustables, jauge animée
- **Bollinger Bands** — période et écart-type configurables, position actuelle dans les bandes
- **MACD** — EMA rapide/lente/signal ajustables, histogramme
- **Fibonacci** — retracements automatiques sur le range de la période, niveaux "PROCHE" alertés
- Calculs côté client sur données PostgreSQL (rapide, pas de yfinance RT)

### 📡 Live intraday WebSocket (v2)
- WebSocket `/ws/intraday/{ticker}` — prix toutes les 60s
- Source : Twelve Data (délai 15min, plan gratuit) → fallback PostgreSQL
- Badge honnête "15min" (pas de faux "LIVE")
- Sparkline des 30 derniers ticks par ticker
- Saisie positions réelles (Qté, PRU) → P&L calculé en temps réel

### 👤 Portfolio avec positions réelles (v2)
- Saisie Qté + PRU par ticker
- Valeur totale, P&L€, P&L% calculés sur le dernier cours
- Stats globales : VALEUR portefeuille, P&L total
- Sauvegarde automatique en PostgreSQL si connecté (JWT)
- Modal auth intégrée (login / inscription)

### 📐 Optimisation de portefeuille
- Max Sharpe (Markowitz), Min Volatility, Risk Parity, Equal Weight, Max Diversification
- Frontière efficiente, matrice de corrélations

### 💰 Variantes DCA
- Classic, Momentum-Weighted, Smart DCA (ATH trigger), Value Averaging

### 📄 Rapport PDF institutionnel
- 15 pages, style Goldman Sachs
- 8 graphiques matplotlib HD : rolling Sharpe, volatility, heatmap, distribution, underwater, beta, win/loss
- Narratif auto-généré par métrique

### 📈 Analyse fondamentale (SEC EDGAR)
- 30+ métriques GAAP (PE, PB, ROE, ROA, FCF, Debt/Equity…)
- Lookup CIK automatique depuis `www.sec.gov/files/company_tickers.json`
- Intégré comme vote dans le score composite des signaux

### ⚙️ Registre de tickers dynamique
- Ajouter n'importe quel ticker via UI ou `POST /api/registry/add`
- Configurer les paramètres GBM fallback (μ, σ) par ticker

---

## 🏗️ Architecture des fichiers

```
ethical-finance/
│
├── backend/
│   ├── app.py                      # FastAPI app + APScheduler (1 worker)
│   ├── index.py                    # Routes FastAPI
│   ├── config.py
│   ├── auth/
│   │   ├── jwt.py                  # JWT register/login/me
│   │   └── portfolio_routes.py     # Routes protégées portfolio + signals_history
│   ├── core/
│   │   ├── data.py                 # get_prices → PostgreSQL en priorité
│   │   ├── cache.py                # Cache mémoire local (remplace Vercel KV)
│   │   ├── registry.py             # Registre tickers + screening éthique
│   │   ├── sec_edgar.py            # SEC EDGAR — 30+ métriques GAAP
│   │   ├── fmp.py                  # FMP fundamentals non-US
│   │   ├── twelve_data.py          # Twelve Data — OHLCV pipeline
│   │   └── loader.py               # Chargement initial univers complet
│   ├── quant/
│   │   ├── metrics.py              # 25+ métriques
│   │   ├── signals.py              # Indicateurs techniques + ML
│   │   ├── sentiment.py            # VADER + lexique financier custom
│   │   └── montecarlo.py
│   ├── strategies/
│   │   ├── base.py                 # PositionManager + StrategyParams
│   │   └── builtin/                # EPR5, Momentum, MeanRev, SMA…
│   ├── backtest/
│   │   ├── engine.py               # Event-driven, anti look-ahead
│   │   ├── portfolio.py            # NAV, cash, positions
│   │   └── costs.py                # Frais broker + slippage + PFU 30%
│   ├── signals/
│   │   └── daily.py                # Signaux journaliers strategy-aware
│   ├── ws/
│   │   └── intraday.py             # WebSocket live intraday
│   └── report/
│       ├── pdf.py                  # PDF 15p matplotlib HD
│       └── tearsheet.py
│
├── src/                            # Frontend React / Vite / TypeScript
│   ├── App.tsx                     # 9 onglets
│   ├── components/
│   │   ├── TickerManager.tsx       # Portfolio + positions réelles + auth modal
│   │   ├── SignalsPanel.tsx        # Signaux strategy-aware + sparklines
│   │   ├── IndicatorsPanel.tsx     # RSI/Bollinger/MACD/Fibonacci
│   │   ├── LivePanel.tsx           # WebSocket intraday
│   │   ├── BacktestPanel.tsx       # Backtest + broker settings
│   │   ├── ScreeningPanel.tsx
│   │   ├── SentimentPanel.tsx
│   │   └── TechnicalPanel.tsx
│   └── hooks/
│       └── useLiveQuotes.ts
│
├── migrations/
│   └── v2_portfolio_auth.sql       # Tables users, portfolios, signals_history, nav_history
├── Dockerfile                      # workers=1 (évite double scheduler)
├── docker-compose.yml
├── .github/workflows/
│   ├── daily-ohlcv.yml             # 20h UTC — OHLCV + signaux
│   └── weekly-fundamentals.yml    # Dimanche 8h UTC
└── docs/
    └── STRATEGY_GUIDE.md
```

---

## 🛠️ Stack technique

### Backend (Python)
| Bibliothèque | Rôle |
|---|---|
| FastAPI + Uvicorn (workers=1) | Framework REST API + WebSocket |
| PostgreSQL 16 + asyncpg | Base de données principale |
| APScheduler 3.x | Pipeline automatique (5 jobs) |
| scikit-learn | Random Forest, clustering HRP |
| TensorFlow 2.17 | LSTM (EPR5 — 40% du score) |
| VADER + lexique custom | Sentiment financier |
| Twelve Data / FMP | Données OHLCV pipeline |
| python-jose + bcrypt | Auth JWT |
| httpx | Requêtes async |
| ReportLab + Matplotlib | PDF institutionnel 15 pages |
| Pydantic v2 | Validation |

### Frontend (TypeScript)
| Bibliothèque | Rôle |
|---|---|
| React 18 + Vite 6 | Framework + build |
| TypeScript | Typage |
| Recharts | Graphiques |
| Tailwind CSS | Styles |
| WebSocket natif | Live intraday |

### Infrastructure
| Composant | Détail |
|---|---|
| NAS | Synology DS925+ |
| Docker Compose | 3 services : api, db, pgadmin |
| Nginx | Sert le frontend (dist/) |
| Cloudflare Tunnel | HTTPS automatique, zéro port exposé |
| GitHub Actions | CI/CD + pipeline données |
| pgAdmin 4 | `192.168.1.139:5050` |

---

## 📡 API Endpoints principaux

### Public
```
GET    /api/prices/db             → Prix OHLCV depuis PostgreSQL (rapide)
POST   /api/signals/daily         → Signaux strategy-aware
POST   /api/screener              → Screener multi-univers
POST   /api/backtest              → Backtest event-driven
GET    /api/metrics/{ticker}      → 20+ métriques
POST   /api/optimize              → Optimisation portefeuille
POST   /api/dca                   → Backtest DCA
WS     /ws/intraday/{ticker}      → WebSocket live
```

### Auth
```
POST   /auth/register             → Créer un compte
POST   /auth/login                → Connexion → JWT
GET    /auth/me                   → Profil utilisateur
```

### Protégées (JWT)
```
GET    /api/portfolio/positions   → Positions réelles
POST   /api/portfolio/positions   → Ajouter une position
DELETE /api/portfolio/positions/{id} → Supprimer
GET    /api/portfolio/signals/history → Historique signaux archivés
```

---

## 🗄️ Schéma de base de données

```sql
-- Existant
ticker_fundamentals (ticker PK, universe, name, sector, pe, pb, roe, ...)
ohlcv (ticker, date, open, high, low, close, adj_close, volume, split_factor)
strategies (id, name, params_json)

-- v2
users (id UUID PK, email UNIQUE, password_hash, created_at)

user_portfolios (
  id UUID PK, user_id UUID FK,
  ticker, qty, avg_price, currency, opened_at, notes
)

signals_history (
  id UUID PK, ticker, date, strategy_id,
  signal_buy, signal_sell,
  rf_score, lstm_score, sentiment_score, fundamental_score, technical_score,
  composite_score, created_at,
  UNIQUE (ticker, date, strategy_id)
)

nav_history (
  ticker, date PRIMARY KEY,
  nav, nav_div_reinvested, split_factor
)
```

---

## ⏰ Pipeline automatique

| Heure UTC | Action |
|---|---|
| 20h00 | GitHub Actions → yfinance → OHLCV 7 derniers jours → Google Drive |
| 20h30 | NAS APScheduler → calcul signaux 573 tickers × 6 stratégies → `signals_history` |
| 22h00 | NAS APScheduler → SEC EDGAR fundamentals SP500 (100 tickers) |
| 22h30 | NAS APScheduler → FMP fundamentals CAC40 + MSCI |
| 23h00 | NAS APScheduler → backup PostgreSQL (7 jours de rétention) |
| 23h30 | NAS APScheduler → Drive sync → import OHLCV dans PostgreSQL |
| Dim 8h | GitHub Actions → mise à jour fundamentals yfinance (tous tickers) |

---

## 📊 ETF pré-chargés

| Clé | Nom | ISIN | TER | Halal |
|---|---|---|---|---|
| ISWD | iShares MSCI World Islamic | IE00B27YCN58 | 0.50% | ✅ MSCI Shariah |
| IUSF | iShares MSCI USA Islamic | IE00B296QM64 | 0.30% | ✅ MSCI Shariah |
| ISDE | iShares MSCI EM Islamic | IE00B27YCP72 | 0.85% | ✅ MSCI Shariah |
| AMAL | Saturna Al-Kawthar | IE00BMYMHS24 | 0.75% | ✅ Saturna Capital SB |
| HIWS | HSBC MSCI EM Islamic | IE0009BC6K22 | 0.60% | ✅ HSBC Shariah SB |
| IWDA | MSCI World (Benchmark) | IE00B4L5Y983 | 0.20% | ❌ |
| CSPX | S&P 500 (Benchmark) | IE00B5BMR087 | 0.07% | ❌ |
| GLD | SPDR Gold Shares | US78463V1070 | 0.40% | ✅ Or physique |
| SLV | iShares Silver Trust | US46428Q1094 | 0.50% | ✅ Argent physique |
| IAU | iShares Gold Trust | US4642851036 | 0.25% | ✅ Or physique |

---

## 🚀 Déploiement NAS

### Prérequis
- Synology DS925+ avec Docker
- Git wrapper : `/volume1/docker/bin/git` (alpine/git)
- `.env` : `TWELVE_DATA_API_KEY`, `FMP_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `DB_PASSWORD`, `JWT_SECRET`
- Google Service Account : `ethical-finance-nas-*.json`
- PostgreSQL port **5433** (5432 réservé NAS natif)

### Backend
```bash
export PATH="/volume1/docker/bin:$PATH"
cd /volume1/docker/ethical-finance
git pull
sudo docker-compose up -d --build api
```

> ⚠️ **JAMAIS** `git clean -fd` — détruit `postgres/` et `data-nas/` (bind mounts PostgreSQL)

### Frontend
```bash
sudo docker run --rm \
  -v /volume1/docker/ethical-finance:/app \
  -w /app \
  -e VITE_API_URL=https://api.sauhabah-advisory.eu \
  node:20-alpine \
  sh -c "npm install && npm run build"
sudo docker restart ethical-finance-frontend
```

> `VITE_API_URL` doit être injecté **au build**, pas au runtime.

### Migration DB v2
```bash
sudo docker exec -i ethical-finance-db \
  psql -U sauhabah -d ethical_finance \
  < migrations/v2_portfolio_auth.sql
```

### Développement local
```bash
# Backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn backend.index:app --reload --port 8000

# Frontend
npm install && npm run dev
```

---

## 📝 Notes techniques importantes

| Sujet | Note |
|---|---|
| Port PostgreSQL | **5433** externe ; 5432 dans Docker |
| Uvicorn workers | **1 seul worker** (évite double démarrage APScheduler) |
| Cache | Mémoire locale TTL — plus de Vercel KV / Supabase |
| `get_prices` | Lit PostgreSQL en priorité — yfinance seulement en fallback |
| `_fetch_fundamentals_db` | Lit PostgreSQL — plus de Supabase REST |
| git wrapper NAS | `export PATH="/volume1/docker/bin:$PATH"` avant tout git |
| sed macOS | `-i ''` (string vide après -i) |
| JSX apostrophes | Utiliser `"` pour les strings contenant `'` |
| `\copy` psql | Ne fonctionne pas dans `-c` multi-ligne |
| Yahoo Finance | Rate-limitée depuis NAS — préférer Twelve Data / FMP |
| VITE_API_URL | Injecté au **build**, pas au runtime |
| pgAdmin | `192.168.1.139:5050` — host: `ethical-finance-db`, port: `5432` |
| JWT_SECRET | Changer en production (`JWT_SECRET=...` dans `.env`) |

---

## 🗺️ Roadmap

### Livré (v2 — 18/05/2026)
- [x] Auth JWT + persistance portfolio utilisateurs
- [x] Page Signaux strategy-aware + historique jour/jour
- [x] Scheduler signaux 20h30 UTC (573 tickers × 6 stratégies)
- [x] Live intraday WebSocket + sparklines + P&L temps réel
- [x] RSI configurable + Bollinger + MACD + Fibonacci dans le frontend
- [x] Positions réelles (Qté/PRU) + P&L global dans Portfolio
- [x] Backtest : fractions par broker + dividendes réinvestis toggle
- [x] Cache mémoire local — suppression Supabase/Vercel KV
- [x] PostgreSQL source principale — yfinance relégué en fallback
- [x] Suppression double démarrage APScheduler (workers=1)

### À venir
- [ ] NAV changements de composition d'indice (SP500/CAC40 annuels)
- [ ] Ollama LLM local (après installation RAM 16 Go)
- [ ] TensorFlow modèles avancés EPR5 (LSTM bidirectionnel, attention)
- [ ] Backtesting intraday (données Twelve Data historiques)
- [ ] Elliott Wave automatique (détection pivots daily)

---

## ⚠️ Avertissement

Cette application est un outil d'analyse personnel à but éducatif. Elle ne constitue pas un conseil en investissement au sens de la réglementation AMF. Les performances passées ne présagent pas des performances futures. Consultez toujours un conseiller financier qualifié et un érudit en droit islamique avant d'investir.

---

## 👤 Auteur

**Azip Sauhabah**
GitHub : [github.com/AzipSauhabah](https://github.com/AzipSauhabah)

---

## 📄 Licence

GNU General Public License v3.0
