# ☪️ Sauhabah Ethical Finance — Plateforme d'analyse quantitative

> Plateforme d'investissement éthique auto-hébergée, combinant backtesting event-driven, signaux ML/sentiment/fondamentaux, suivi de portefeuille en temps réel et analyse technique avancée. Gratuite, compréhensible, auto-critique.

Analyse 20+ métriques quant, backtest des stratégies Renaissance & Buffett, optimise des portefeuilles ETF halal multi-actifs, simule du DCA intelligent, génère des rapports PDF institutionnels — le tout sur un NAS auto-hébergé avec pipeline de données automatisé.

🔗 **Live** : [app.sauhabah-advisory.eu](https://app.sauhabah-advisory.eu)
🔗 **API** : [api.sauhabah-advisory.eu/docs](https://api.sauhabah-advisory.eu/docs)
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
│  ohlcv (daily) │ ohlcv_intraday (1h) │ ticker_fundamentals          │
│  nav_history │ signals_history │ user_portfolios │ users             │
│  Cache mémoire local TTL — zéro Supabase / Vercel KV                │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────┐
│  MOTEUR DE SIGNAUX  (strategy-aware — 5 votes combinés)              │
│  SMA crossover │ MACD │ Momentum │ RSI │ Sentiment                   │
│  Sources sentiment : Yahoo Finance RSS + Google News RSS (VADER)     │
│  Persistance auto dans signals_history à 20h30 UTC                   │
└────────────────────┬────────────────────────────────────────────────┘
                     │
         ┌───────────▼───────────┐
         │   Filtre stratégie    │
         │  EPR5 / Momentum /    │
         │  Mean Rev / SMA /     │
         │  Dual Mom / Buy&Hold  │
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
│  Technical │ Indicateurs (RSI/BB/MACD/Fibo/Elliott) │ Live           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## ✨ Fonctionnalités

### ☪️ Halal-first
- 5 ETF Shariah-certifiés pré-chargés (ISWD, IUSF, ISDE, AMAL, HIWS)
- Informations Shariah board, notes de purification, éligibilité PEA/PER/CTO
- Badge halal par ticker dans toutes les vues

### 🌍 Screener multi-univers
- 5 univers : SP500, CAC40, ETF broad, ETF Precious Metals, MSCI World
- 573 tickers, 2.75M lignes OHLCV daily, 615 fiches fondamentales
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
- **EPR5** — RF + LSTM TensorFlow, 5 votes combinés
- **Buffett Quality**, **Renaissance Composite**, **Dual Momentum** (Antonacci)
- **Trend Following EMA 50/200**, **Mean Reversion Z-Score**, **RSI Contrarian**
- **SMA Crossover, Adaptive Trend, Buy & Hold, Equal Weight, Min Variance, Risk Parity**

Toutes les stratégies intègrent un `PositionManager` (ATR sizing, stop-loss, trailing stop).

**Réalisme broker :**
- Fortuneo / Boursorama / Degiro → actions entières (`floor`)
- Revolut → fractions d'actions (toggle)
- Toggle dividendes réinvestis (`adj_close`) ou perçus en cash (`close`)

### 🎯 Moteur de signaux strategy-aware (v2)
- 5 votes pondérés selon la stratégie choisie
- Persistance automatique dans `signals_history` à 20h30 UTC
- 573 tickers × 6 stratégies archivés chaque jour
- Prédictions J+1 à J+5 dans le Dashboard Signaux

### 😐 Sentiment multi-sources (v2)
- **Yahoo Finance RSS** — flux financier par ticker
- **Google News RSS** — 80 000+ sources, gratuit, sans API key
- Fusion et déduplication automatique, jusqu'à 20 articles par ticker
- VADER avec lexique financier custom (beat, downgrade, bankruptcy…)
- Score composite [-1, +1] intégré comme vote dans les signaux

### 📈 Indicateurs techniques configurables (v2)
- **RSI** — période variable, seuils ajustables, jauge animée
- **Bollinger Bands** — période et écart-type configurables
- **MACD** — EMA rapide/lente/signal ajustables, histogramme
- **Fibonacci** — retracements auto sur le range, alertes "PROCHE"
- **Elliott Wave** — ZigZag + identification vagues 1-5 + validation règles strictes
  - Mode **daily** (6 mois de données) → vagues hebdomadaires/mensuelles
  - Mode **intraday 1h** (données Twelve Data, alimentées toutes les heures) → micro-vagues
  - Tableau de validation : Wave 2 < Wave 1, Wave 3 la plus longue, Wave 4 sans chevauchement
  - Confiance calculée sur 6 règles Elliott, affichée honnêtement

### 📡 Live intraday WebSocket (v2)
- WebSocket `/ws/intraday/{ticker}` — prix toutes les 60s
- Source : Twelve Data (délai 15min, plan gratuit) → fallback PostgreSQL
- Badge honnête "15min" (pas de faux "LIVE")
- Sparkline des 30 derniers ticks, P&L temps réel

### 👤 Portfolio avec positions réelles (v2)
- Saisie Qté + PRU par ticker, P&L€ et P&L% temps réel
- Valeur totale et P&L global du portefeuille
- Modal auth intégrée (login / inscription)
- Sauvegarde automatique en PostgreSQL si connecté

### 📐 Optimisation & DCA
- Max Sharpe, Min Volatility, Risk Parity, Equal Weight, Max Diversification
- DCA Classic, Momentum-Weighted, Smart DCA, Value Averaging

### 📄 Rapport PDF institutionnel
- 15 pages, style Goldman Sachs
- 8 graphiques matplotlib HD : rolling Sharpe, volatility, heatmap, distribution, underwater, beta, win/loss

---

## 🏗️ Architecture des fichiers

```
ethical-finance/
│
├── backend/
│   ├── app.py                      # FastAPI app + APScheduler (1 worker)
│   ├── index.py                    # Routes FastAPI
│   ├── auth/
│   │   ├── jwt.py                  # JWT register/login/me (bcrypt)
│   │   └── portfolio_routes.py     # Routes protégées portfolio
│   ├── core/
│   │   ├── data.py                 # get_prices → PostgreSQL priorité
│   │   ├── cache.py                # Cache mémoire local TTL
│   │   ├── registry.py             # Registre tickers + screening
│   │   ├── sec_edgar.py            # SEC EDGAR 30+ GAAP
│   │   ├── fmp.py                  # FMP fundamentals non-US
│   │   └── twelve_data.py          # Twelve Data OHLCV + intraday
│   ├── quant/
│   │   ├── metrics.py              # 25+ métriques
│   │   ├── signals.py              # Indicateurs techniques + ML
│   │   └── sentiment.py            # VADER + Yahoo RSS + Google News RSS
│   ├── strategies/builtin/         # EPR5, Momentum, MeanRev…
│   ├── backtest/engine.py          # Event-driven, anti look-ahead
│   ├── signals/daily.py            # Signaux journaliers strategy-aware
│   └── ws/intraday.py              # WebSocket live intraday
│
├── src/
│   ├── App.tsx                     # 9 onglets
│   └── components/
│       ├── TickerManager.tsx       # Portfolio + positions + auth modal
│       ├── SignalsPanel.tsx        # Signaux strategy-aware
│       ├── IndicatorsPanel.tsx     # RSI/BB/MACD/Fibo/Elliott Wave
│       ├── LivePanel.tsx           # WebSocket intraday
│       └── BacktestPanel.tsx       # Backtest + broker settings
│
├── migrations/
│   └── v2_portfolio_auth.sql       # users, portfolios, signals_history, nav_history, ohlcv_intraday
├── Dockerfile                      # workers=1
└── .github/workflows/
    ├── daily-ohlcv.yml             # 20h UTC
    └── weekly-fundamentals.yml    # Dimanche 8h UTC
```

---

## 🛠️ Stack technique

### Backend (Python)
| Bibliothèque | Rôle |
|---|---|
| FastAPI + Uvicorn (workers=1) | REST API + WebSocket |
| PostgreSQL 16 + asyncpg | Base de données principale |
| APScheduler 3.x | 6 jobs automatiques |
| scikit-learn | Random Forest, HRP |
| TensorFlow 2.17 | LSTM (EPR5) |
| VADER + lexique custom | Sentiment financier |
| python-jose + bcrypt | Auth JWT |
| httpx | Requêtes async |
| Matplotlib + ReportLab | PDF 15 pages |

### Frontend (TypeScript)
| Bibliothèque | Rôle |
|---|---|
| React 18 + Vite 6 | Framework + build |
| Recharts | Graphiques |
| WebSocket natif | Live intraday |

---

## 📡 API Endpoints

### Public
```
GET    /api/prices/db             → Prix daily depuis PostgreSQL
GET    /api/prices/intraday       → Prix 1h depuis ohlcv_intraday
POST   /api/signals/daily         → Signaux strategy-aware
POST   /api/screener              → Screener multi-univers
POST   /api/backtest              → Backtest event-driven
POST   /api/sentiment             → Sentiment Yahoo+Google News
WS     /ws/intraday/{ticker}      → WebSocket live
```

### Auth
```
POST   /auth/register
POST   /auth/login                → JWT
GET    /auth/me
```

### Protégées (JWT)
```
GET/POST/DELETE  /api/portfolio/positions
GET              /api/portfolio/signals/history
```

---

## 🗄️ Schéma de base de données

```sql
-- Daily OHLCV
ohlcv (ticker, date PK, open, high, low, close, adj_close, volume, split_factor)

-- Intraday 1h (Twelve Data — alimenté toutes les heures)
ohlcv_intraday (ticker, datetime, interval PK, open, high, low, close, volume)

-- Fundamentals
ticker_fundamentals (ticker PK, universe, name, sector, pe, pb, roe, ...)

-- Signaux archivés (1 entrée/ticker/stratégie/jour)
signals_history (ticker, date, strategy_id PK, signal_buy, signal_sell,
                 rf_score, lstm_score, sentiment_score, fundamental_score,
                 technical_score, composite_score)

-- Auth + Portfolio
users          (id UUID PK, email UNIQUE, password_hash, created_at)
user_portfolios(id UUID PK, user_id FK, ticker, qty, avg_price, currency, opened_at)
nav_history    (ticker, date PK, nav, nav_div_reinvested, split_factor)
```

---

## ⏰ Pipeline automatique

| Heure UTC | Service | Action |
|---|---|---|
| 20h00 | GitHub Actions | yfinance → OHLCV 7j → Google Drive |
| 20h30 | APScheduler NAS | Signaux 573 tickers × 6 stratégies → `signals_history` |
| **toutes les heures** | **APScheduler NAS** | **Twelve Data 1h → `ohlcv_intraday` (top 50 tickers)** |
| 22h00 | APScheduler NAS | SEC EDGAR fundamentals SP500 |
| 22h30 | APScheduler NAS | FMP fundamentals CAC40 + MSCI |
| 23h00 | APScheduler NAS | Backup PostgreSQL (7j rétention) |
| 23h30 | APScheduler NAS | Drive sync → import OHLCV daily |
| Dim 8h | GitHub Actions | Fundamentals yfinance tous tickers |

---

## 🚀 Déploiement NAS

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

### Migration DB v2
```bash
sudo docker exec -i ethical-finance-db \
  psql -U sauhabah -d ethical_finance \
  < migrations/v2_portfolio_auth.sql
```

### Peupler ohlcv_intraday manuellement (premier run)
```bash
sudo docker exec -it ethical-finance-api python3 -c "
import asyncio, os, sqlalchemy as sa, httpx
# ... voir script complet dans migrations/seed_intraday.py
"
```

---

## 📝 Notes techniques importantes

| Sujet | Note |
|---|---|
| Port PostgreSQL | **5433** externe ; 5432 dans Docker |
| Uvicorn workers | **1 seul** (évite double démarrage APScheduler) |
| Cache | Mémoire locale TTL — zéro Vercel KV / Supabase |
| `get_prices` | PostgreSQL priorité — yfinance seulement en fallback |
| `_fetch_fundamentals_db` | PostgreSQL — zéro Supabase REST |
| Sentiment | Yahoo Finance RSS + Google News RSS (gratuit, sans clé) |
| Elliott Wave daily | 6 mois données daily — vagues hebdo/mensuelles |
| Elliott Wave intraday | Twelve Data 1h — micro-vagues — plan gratuit OK |
| Twelve Data | 800 req/jour gratuit — intraday job : 1 req/2s |
| `.env` dédoublons | Vérifier unicité des clés (pas de doublon TWELVE_DATA_API_KEY) |
| JWT_SECRET | Changer en production dans `.env` |
| pgAdmin | `192.168.1.139:5050` — host: `ethical-finance-db`, port: `5432` |
| sed macOS | `-i ''` (string vide après -i) |
| VITE_API_URL | Injecté au **build**, pas au runtime |

---

## 🗺️ Roadmap

### Livré (v2 — 18/05/2026)
- [x] Auth JWT + persistance portfolio PostgreSQL
- [x] Page Signaux strategy-aware + historique jour/jour
- [x] Scheduler signaux 20h30 UTC (573 tickers × 6 stratégies)
- [x] Sentiment multi-sources : Yahoo Finance RSS + Google News RSS
- [x] Indicateurs configurables : RSI, Bollinger, MACD, Fibonacci
- [x] **Elliott Wave** — ZigZag + vagues 1-5 + validation + mode intraday 1h
- [x] **ohlcv_intraday** — table 1h + scheduler toutes les heures + endpoint API
- [x] Live intraday WebSocket + sparklines + P&L temps réel
- [x] Positions réelles (Qté/PRU) + P&L global dans Portfolio
- [x] Backtest : fractions par broker + dividendes réinvestis toggle
- [x] Cache mémoire local — zéro dépendance cloud externe
- [x] PostgreSQL source principale partout
- [x] Workers=1 Uvicorn

### À venir
- [ ] NAV changements de composition d'indice (SP500/CAC40 annuels)
- [ ] Elliott Wave ML supervisé (entraînement sur historique labeled)
- [ ] Ollama LLM local (après installation RAM 16 Go)
- [ ] TensorFlow EPR5 avancé (LSTM bidirectionnel, attention)
- [ ] Backtesting intraday (données Twelve Data historiques)

---

## 📊 ETF pré-chargés

| Clé | Nom | ISIN | TER | Halal |
|---|---|---|---|---|
| ISWD | iShares MSCI World Islamic | IE00B27YCN58 | 0.50% | ✅ |
| IUSF | iShares MSCI USA Islamic | IE00B296QM64 | 0.30% | ✅ |
| ISDE | iShares MSCI EM Islamic | IE00B27YCP72 | 0.85% | ✅ |
| AMAL | Saturna Al-Kawthar | IE00BMYMHS24 | 0.75% | ✅ |
| HIWS | HSBC MSCI EM Islamic | IE0009BC6K22 | 0.60% | ✅ |
| IWDA | MSCI World (Benchmark) | IE00B4L5Y983 | 0.20% | ❌ |
| CSPX | S&P 500 (Benchmark) | IE00B5BMR087 | 0.07% | ❌ |
| GLD | SPDR Gold Shares | US78463V1070 | 0.40% | ✅ |
| SLV | iShares Silver Trust | US46428Q1094 | 0.50% | ✅ |
| IAU | iShares Gold Trust | US4642851036 | 0.25% | ✅ |

---

## ⚠️ Avertissement

Cette application est un outil d'analyse personnel à but éducatif. Elle ne constitue pas un conseil en investissement au sens de la réglementation AMF. Les performances passées ne présagent pas des performances futures. Consultez toujours un conseiller financier qualifié et un érudit en droit islamique avant d'investir.

---

## 👤 Auteur

**Azip Sauhabah** · GitHub : [github.com/AzipSauhabah](https://github.com/AzipSauhabah)

## 📄 Licence

GNU General Public License v3.0
