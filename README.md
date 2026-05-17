# ☪️ Halal ETF Analytics — Efficient Portfolio 2

A fullstack quantitative finance application for **Shariah-compliant ETF analysis**, built with a serverless FastAPI backend and a React + TypeScript frontend.

Analyse 20+ quant metrics, backtest Renaissance & Buffett strategies, optimize multi-ETF halal portfolios, run smart DCA simulations, and export full PDF reports — all with a dynamic ticker registry you can extend at runtime.

🔗 **Live**: [efficient-portfolio2.vercel.app](https://efficient-portfolio2.vercel.app)
📦 **Repo**: [github.com/AzipSauhabah/efficient-portfolio2](https://github.com/AzipSauhabah/efficient-portfolio2)

---

## ✨ Features

### ☪️ Halal-first
- 5 Shariah-certified ETFs pre-loaded (ISWD, IUSF, ISDE, AMAL, HIWS)
- Shariah board info, purification notes, PEA/PER/CTO eligibility
- Halal badge per ticker in all views

### 📊 20+ Quantitative Metrics
| Category | Metrics |
|---|---|
| Performance | CAGR, Total Return, Annualized Slope |
| Risk-adjusted | Sharpe, Sortino, Calmar, Omega, Martin |
| Drawdown | Max Drawdown, Ulcer Index, Pain Index |
| Tail Risk | VaR 95/99%, CVaR 95/99%, Tail Ratio |
| Distribution | Skewness, Excess Kurtosis, Jarque-Bera p-value |
| Structure | Autocorrelation lag-1, Log R² (Buffett linearity score) |
| Trade stats | Win Rate, Avg Win/Loss, Profit Factor |

### 🔬 Quant Strategies (Backtestable)
- **Buffett Quality** — Log R² linearity + low volatility + momentum
- **Renaissance Composite** — Multi-factor stat-arb signal (momentum + trend + vol-normalized)
- **Dual Momentum** (Antonacci) — Absolute + relative momentum with risk-off filter
- **Trend Following EMA 50/200** — With configurable stop-loss
- **Mean Reversion Z-Score** — Buy on -1.5σ, sell at mean
- **RSI Contrarian** — Oversold < 30 entry

### 📐 Portfolio Optimization
- Max Sharpe (Markowitz)
- Min Volatility
- Risk Parity
- Equal Weight
- Max Diversification
- Efficient frontier visualization
- Correlation matrix

### 💰 DCA Variants
- **Classic** — Fixed monthly investment
- **Momentum-Weighted** — Invest more on dips, less on runs
- **Smart DCA** — Boost multiplier triggered on drawdown from ATH
- **Value Averaging** — Target a growth curve, auto-adjust monthly amount

### 🎯 AI / Statistical Signals (per ticker)
- RSI 14, Z-Score, Bollinger Band percentile
- EMA crossover, MACD histogram, 12-1 momentum
- Trend R² (log-linear quality)
- **Renaissance Score** (0–100) — composite stat signal
- **Buffett Quality Score** (0–100) — linearity + low vol + momentum

### ⚙️ Dynamic Ticker Registry
- Add any Yahoo Finance ticker at runtime via UI or `POST /api/registry/add`
- Configure GBM fallback parameters (μ, σ) per ticker
- Remove tickers on the fly
- Works for ETFs, stocks, commodities (e.g. GLD)

### 📄 PDF Export
- Full multi-portfolio report with metrics, DCA results, allocation breakdown
- Browser print-based, no server dependency

---

## 🏗️ Architecture

```
efficient-portfolio2/
│
├── api/
│   └── index.py                  # FastAPI backend (serverless on Vercel)
│                                 # Dynamic registry, 20+ metrics, signals,
│                                 # backtester, optimizer, DCA engine
│
├── src/
│   ├── App.tsx                   # Main dashboard (10 tabs)
│   ├── main.tsx                  # React entry point
│   ├── components/
│   │   └── QuantPanels.tsx       # Signals, Strategy, Optimizer, TickerManager
│   ├── hooks/
│   │   └── useApi.ts             # All API calls (live prices, compare, DCA, portfolio)
│   ├── types/
│   │   └── index.ts              # TypeScript types
│   └── utils/
│       └── pdfExport.ts          # PDF export (browser print)
│
├── index.html
├── package.json
├── vite.config.ts                # Vite + React plugin + /api proxy
├── tsconfig.json
├── vercel.json                   # Python + static build config
├── requirements.txt
└── README.md
```

---

## 🛠️ Tech Stack

### Backend (Python)
| Library | Role |
|---|---|
| FastAPI | REST API framework |
| yfinance | Live market data (with GBM fallback) |
| NumPy / Pandas | Data manipulation |
| SciPy | Optimization (Markowitz, Risk Parity), stats |
| scikit-learn | HRP clustering (KMeans) |
| Pydantic v2 | Request/response validation |
| Mangum | ASGI → Vercel serverless adapter |

### Frontend (TypeScript)
| Library | Role |
|---|---|
| React 18 | UI framework |
| TypeScript | Type safety |
| Vite 6 | Build tool |
| Recharts | Charts (Line, Area, Bar, Radar) |
| Custom hooks | useApi, useLivePrices, useCompare, useDCA |

### Deployment
- **Vercel** — serverless Python functions (`@vercel/python`) + static Vite build
- **GitHub** — auto-deploy on push to `main`

---

## 📡 API Endpoints

### Registry
```
GET    /api/registry              → List all tickers
POST   /api/registry/add          → Add a custom ticker
DELETE /api/registry/{key}        → Remove a ticker
```

### Data & Metrics
```
GET    /api/live                  → Live prices for all tickers
GET    /api/metrics/{key}         → 20+ metrics + signals for one ticker
GET    /api/compare               → Compare multiple tickers (normalized)
GET    /api/signals/{key}         → AI/stat signals only
GET    /api/rolling/{key}         → Rolling CAGR distribution
```

### Strategies & Backtesting
```
GET    /api/strategies/presets    → Available strategy presets
POST   /api/backtest              → Run strategy backtest with equity curve
```

### Optimization
```
POST   /api/optimize              → Portfolio optimization (5 methods)
```

### DCA
```
POST   /api/dca                   → DCA backtest (4 variants)
POST   /api/dca/compare           → Compare all DCA variants
```

### Portfolio
```
POST   /api/portfolio             → Multi-ETF portfolio analysis
```

---

## 🚀 Local Development

### Clone
```bash
git clone https://github.com/AzipSauhabah/efficient-portfolio2.git
cd efficient-portfolio2
```

### Backend
```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
# or: venv\Scripts\activate     # Windows

pip install -r requirements.txt
uvicorn api.index:app --reload --port 8000
```

### Frontend
```bash
npm install
npm run dev
# Vite proxies /api → http://localhost:8000 automatically
```

Open [http://localhost:5173](http://localhost:5173)

---

## 🧪 Adding a Custom Ticker

Via the **⚙️ Tickers** tab in the UI, or directly via API:

```bash
curl -X POST https://efficient-portfolio2.vercel.app/api/registry/add \
  -H "Content-Type: application/json" \
  -d '{
    "key": "MSFT",
    "ticker": "MSFT",
    "name": "Microsoft Corporation",
    "ter": 0.0,
    "halal": false,
    "category": "stock",
    "region": "USA",
    "gbm_mu": 0.18,
    "gbm_sigma": 0.28
  }'
```

> **Note**: Registry is in-memory on Vercel (resets on cold start). For persistence, connect a database.

---

## 📊 Pre-loaded ETFs

| Key | Name | ISIN | TER | Halal |
|---|---|---|---|---|
| ISWD | iShares MSCI World Islamic | IE00B27YCN58 | 0.50% | ✅ MSCI Shariah |
| IUSF | iShares MSCI USA Islamic | IE00B296QM64 | 0.30% | ✅ MSCI Shariah |
| ISDE | iShares MSCI EM Islamic | IE00B27YCP72 | 0.85% | ✅ MSCI Shariah |
| AMAL | Saturna Al-Kawthar | IE00BMYMHS24 | 0.75% | ✅ Saturna Capital SB |
| HIWS | HSBC MSCI EM Islamic | IE0009BC6K22 | 0.60% | ✅ HSBC Shariah SB |
| IWDA | MSCI World (Benchmark) | IE00B4L5Y983 | 0.20% | ❌ |
| CSPX | S&P 500 (Benchmark) | IE00B5BMR087 | 0.07% | ❌ |
| GLD | SPDR Gold Shares | US78463V1070 | 0.40% | ✅ Or physique |

---

## ⚠️ Disclaimer

This application is for **educational and informational purposes only**. It does not constitute investment advice under AMF regulations. Past performance does not guarantee future results. Always consult a qualified financial advisor and a Shariah scholar before investing.

---

## 👤 Author

**Azip Sauhabah**
GitHub: [github.com/AzipSauhabah](https://github.com/AzipSauhabah)

---

## 📄 License

GNU General Public License v3.0
