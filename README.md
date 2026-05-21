![Tests](https://github.com/AzipSauhabah/ethical-finance/actions/workflows/tests.yml/badge.svg)

![Tests](https://github.com/AzipSauhabah/ethical-finance/actions/workflows/tests.yml/badge.svg)

![Tests](https://github.com/AzipSauhabah/ethical-finance/actions/workflows/tests.yml/badge.svg)

# ☪️ Sauhabah Ethical Finance — Plateforme d'analyse quantitative

> Plateforme d'investissement éthique auto-hébergée, combinant backtesting event-driven, signaux ML/sentiment/fondamentaux, suivi de portefeuille en temps réel et analyse technique avancée. Gratuite, compréhensible, auto-critique.

[![Tests](https://git.sauhabah-advisory.eu/asauhabah/ethical-finance/actions/workflows/tests.yml/badge.svg)](https://git.sauhabah-advisory.eu/asauhabah/ethical-finance/actions)
[![SonarQube](https://git.sauhabah-advisory.eu/asauhabah/ethical-finance/actions/workflows/sonarqube.yml/badge.svg)](https://git.sauhabah-advisory.eu/asauhabah/ethical-finance/actions)
[![Auto-Fix](https://git.sauhabah-advisory.eu/asauhabah/ethical-finance/actions/workflows/auto-fix.yml/badge.svg)](https://git.sauhabah-advisory.eu/asauhabah/ethical-finance/actions)
[![NAS](https://img.shields.io/badge/Hébergement-Synology%20DS925%2B-blue)](https://www.synology.com)
[![Docker](https://img.shields.io/badge/Runtime-Docker%20Compose-2496ED)](https://docker.com)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%2FVite%2FTS-61DAFB)](https://vitejs.dev)
[![PostgreSQL](https://img.shields.io/badge/DB-PostgreSQL%2016-336791)](https://postgresql.org)
[![Cloudflare](https://img.shields.io/badge/Tunnel-Cloudflare-F38020)](https://cloudflare.com)
[![SonarQube](https://img.shields.io/badge/Code%20Quality-SonarQube%209.9-4E9BCD)](http://192.168.1.47:9000/dashboard?id=ethical-finance)

🔗 **Live** : [app.sauhabah-advisory.eu](https://app.sauhabah-advisory.eu)
🔗 **API** : [api.sauhabah-advisory.eu/docs](https://api.sauhabah-advisory.eu/docs)
🔗 **Gitea** : [git.sauhabah-advisory.eu](https://git.sauhabah-advisory.eu/asauhabah/ethical-finance)
📦 **Mirror GitHub** : [github.com/AzipSauhabah/ethical-finance](https://github.com/AzipSauhabah/ethical-finance)

---

## 🗺️ Roadmap

### Livré (v2 — 20/05/2026)
- [x] Auth JWT + persistance portfolio PostgreSQL
- [x] Page Signaux strategy-aware + historique jour/jour
- [x] Scheduler signaux 20h30 UTC (573 tickers × 6 stratégies)
- [x] Sentiment multi-sources : Yahoo Finance RSS + Google News RSS
- [x] Indicateurs configurables : RSI, Bollinger, MACD, Fibonacci
- [x] Elliott Wave — ZigZag + vagues 1-5 + validation + mode intraday 1h
- [x] ohlcv_intraday — table 1h + scheduler toutes les heures + endpoint API
- [x] Live intraday WebSocket + sparklines + P&L temps réel
- [x] Positions réelles (Qté/PRU) + P&L global dans Portfolio
- [x] Backtest : fractions par broker + dividendes réinvestis toggle
- [x] Cache mémoire local — zéro dépendance cloud externe
- [x] PostgreSQL source principale partout
- [x] Workers=1 Uvicorn
- [x] SonarQube 9.9 auto-hébergé + intégration Gitea Actions
- [x] Gitea Actions : tests + auto-fix ruff/black + SonarQube
- [x] Badges statut CI/CD dans README

### À venir
- [ ] NAV changements de composition d'indice (SP500/CAC40 annuels)
- [ ] Notifications Gitea (email sur échec de job)
- [ ] Ollama LLM local (après installation RAM 16 Go)
- [ ] TensorFlow EPR5 avancé (LSTM bidirectionnel, attention)
- [ ] Backtesting intraday (données Twelve Data historiques)

---

## ⚠️ Avertissement

Cette application est un outil d'analyse personnel à but éducatif. Elle ne constitue pas un conseil en investissement au sens de la réglementation AMF. Les performances passées ne présagent pas des performances futures.

---

## 👤 Auteur

**Azip Sauhabah** · GitHub : [github.com/AzipSauhabah](https://github.com/AzipSauhabah)

## 📄 Licence

GNU General Public License v3.0
