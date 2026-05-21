"""
:file: backend/quant/sentiment.py
:brief: Analyse de sentiment financier via RSS Yahoo Finance + VADER.

Sources :
  - Yahoo Finance RSS feeds (gratuit, pas de clé API)
  - VADER Sentiment (lexique financier inclus)

Sorties :
  - Score sentiment par ticker [-1, +1]
  - Score sentiment marché global
  - Corrélation sentiment vs rendement récent
  - Classement des news les plus bullish/bearish

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from functools import lru_cache

log = logging.getLogger(__name__)

# Mots financiers bullish/bearish pour booster VADER
FINANCIAL_LEXICON = {
    # Bullish
    "beat": 2.0,
    "beats": 2.0,
    "outperform": 2.5,
    "upgrade": 2.0,
    "buyback": 1.5,
    "dividend": 1.0,
    "growth": 1.5,
    "surge": 2.5,
    "rally": 2.0,
    "breakout": 2.0,
    "record": 1.5,
    "profit": 1.5,
    "revenue": 0.5,
    "expand": 1.5,
    "acquisition": 1.0,
    "partnership": 1.0,
    "innovation": 1.5,
    "margin": 1.0,
    "guidance": 0.5,
    "raised": 1.5,
    # Bearish
    "miss": -2.0,
    "misses": -2.0,
    "downgrade": -2.5,
    "loss": -2.0,
    "layoffs": -2.5,
    "recall": -2.0,
    "lawsuit": -2.0,
    "bankruptcy": -3.0,
    "fraud": -3.0,
    "decline": -1.5,
    "drop": -1.5,
    "fell": -1.5,
    "plunge": -2.5,
    "crash": -3.0,
    "warning": -2.0,
    "cut": -1.5,
    "reduces": -1.5,
    "below": -1.0,
    "weak": -1.5,
    "disappointing": -2.0,
    "shortfall": -2.0,
    "debt": -1.0,
    "deficit": -1.5,
    "investigation": -2.0,
}

# RSS feeds Yahoo Finance par ticker
YAHOO_RSS_TEMPLATE = (
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
)
YAHOO_MARKET_RSS = (
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC,%5EIXIC&region=US&lang=en-US"
)

# Google News RSS — gratuit, sans limite, 80 000+ sources
GOOGLE_NEWS_TEMPLATE = (
    "https://news.google.com/rss/search?q={query}+stock&hl=en-US&gl=US&ceid=US:en"
)
GOOGLE_NEWS_MARKET = (
    "https://news.google.com/rss/search?q=stock+market+investing&hl=en-US&gl=US&ceid=US:en"
)


# ─── VADER avec lexique financier ────────────────────────────────────────────


@lru_cache(maxsize=1)
def _get_analyzer():
    """Charge VADER avec le lexique financier personnalisé."""
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        analyzer = SentimentIntensityAnalyzer()
        # Ajouter le lexique financier
        analyzer.lexicon.update(FINANCIAL_LEXICON)
        return analyzer
    except ImportError:
        log.warning("vaderSentiment non disponible")
        return None


def _score_text(text: str) -> float:
    """Score de sentiment [-1, +1] pour un texte."""
    analyzer = _get_analyzer()
    if not analyzer:
        return 0.0
    scores = analyzer.polarity_scores(text)
    return float(scores["compound"])


# ─── Fetcher Google News RSS ─────────────────────────────────────────────────────
def _fetch_google_news(ticker: str, max_items: int = 10) -> list[dict]:
    """Fetch Google News RSS pour un ticker — gratuit, sans API key."""
    # Normalise le ticker pour la recherche (enlève .PA, .L, etc.)
    query = ticker.split(".")[0] if "." in ticker else ticker
    url = GOOGLE_NEWS_TEMPLATE.format(query=query)
    try:
        articles = _fetch_rss(url, max_items=max_items)
        # Google News encode le titre dans description — on extrait le texte brut
        import re

        for a in articles:
            if a.get("description"):
                # Enlève les balises HTML
                a["title"] = re.sub(
                    r"<[^>]+>", " ", a.get("description", a.get("title", ""))
                ).strip()
        return articles
    except Exception as e:
        log.debug("Google News fetch error for %s: %s", ticker, e)
        return []


# ─── Fetcher RSS ──────────────────────────────────────────────────────────────


def _fetch_rss(url: str, max_items: int = 10) -> list[dict]:
    """Fetch un flux RSS et retourne les items récents."""
    try:
        import feedparser

        feed = feedparser.parse(url)
        items = []
        cutoff = datetime.now() - timedelta(days=7)  # 7 derniers jours

        for entry in feed.entries[:max_items]:
            # Parser la date
            pub_date = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                pub_date = datetime(*entry.published_parsed[:6])

            if pub_date and pub_date < cutoff:
                continue

            title = getattr(entry, "title", "")
            summary = getattr(entry, "summary", "")
            text = f"{title}. {summary}"

            items.append(
                {
                    "title": title,
                    "text": text,
                    "date": pub_date.isoformat() if pub_date else None,
                    "url": getattr(entry, "link", ""),
                }
            )

        return items
    except Exception as e:
        log.debug("RSS fetch error for %s: %s", url, e)
        return []


# ─── Analyse par ticker ───────────────────────────────────────────────────────


def analyze_ticker_sentiment(ticker: str, max_articles: int = 10) -> dict:
    """
    Analyse le sentiment des news pour un ticker donné.

    Args:
        ticker: symbole boursier (ex: AAPL)
        max_articles: nombre max d'articles à analyser

    Returns:
        dict avec score, articles, tendance
    """
    # Source 1 : Yahoo Finance RSS
    url = YAHOO_RSS_TEMPLATE.format(ticker=ticker)
    yahoo_articles = _fetch_rss(url, max_items=max_articles)

    # Source 2 : Google News RSS (gratuit, sans API key)
    google_articles = _fetch_google_news(ticker, max_items=max_articles)

    # Fusion et déduplication par titre
    seen_titles = set()
    articles = []
    for a in yahoo_articles + google_articles:
        title_key = a.get("title", "")[:50].lower()
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            articles.append(a)

    articles = articles[: max_articles * 2]  # max 20 articles au total

    if not articles:
        return {
            "ticker": ticker,
            "score": 0.0,
            "signal": "neutral",
            "n_articles": 0,
            "articles": [],
            "bullish": [],
            "bearish": [],
            "sources": [],
        }

    # Scorer chaque article
    scored = []
    for a in articles:
        score = _score_text(a["text"])
        scored.append({**a, "score": round(score, 3)})

    # Score moyen pondéré (articles récents = poids plus fort)
    scores = [a["score"] for a in scored]
    weights = [1.0 / (i + 1) for i in range(len(scores))]  # décroissant
    total_weight = sum(weights)
    weighted_score = sum(s * w for s, w in zip(scores, weights)) / max(total_weight, 1)

    # Signal
    if weighted_score >= 0.15:
        signal = "bullish"
    elif weighted_score <= -0.15:
        signal = "bearish"
    else:
        signal = "neutral"

    # Top articles bullish/bearish
    sorted_articles = sorted(scored, key=lambda x: x["score"], reverse=True)
    bullish_articles = [a for a in sorted_articles if a["score"] > 0.1][:3]
    bearish_articles = [a for a in sorted_articles if a["score"] < -0.1][-3:]

    return {
        "ticker": ticker,
        "score": round(weighted_score, 3),
        "signal": signal,
        "n_articles": len(articles),
        "articles": scored,
        "bullish": [{"title": a["title"], "score": a["score"]} for a in bullish_articles],
        "bearish": [{"title": a["title"], "score": a["score"]} for a in bearish_articles],
    }


# ─── Analyse marché global ────────────────────────────────────────────────────


def analyze_market_sentiment() -> dict:
    """
    Analyse le sentiment global du marché (SP500 + Nasdaq news).

    Returns:
        dict avec score marché, top news, signal global
    """
    articles = _fetch_rss(YAHOO_MARKET_RSS, max_items=20)

    if not articles:
        return {"score": 0.0, "signal": "neutral", "n_articles": 0, "top_news": []}

    scored = []
    for a in articles:
        score = _score_text(a["text"])
        scored.append({**a, "score": round(score, 3)})

    avg_score = sum(a["score"] for a in scored) / max(len(scored), 1)

    if avg_score >= 0.10:
        signal = "risk_on"
        signal_fr = "Appétit au risque — marché haussier"
    elif avg_score <= -0.10:
        signal = "risk_off"
        signal_fr = "Aversion au risque — prudence conseillée"
    else:
        signal = "neutral"
        signal_fr = "Sentiment neutre — attentisme"

    top_news = sorted(scored, key=lambda x: abs(x["score"]), reverse=True)[:5]

    return {
        "score": round(avg_score, 3),
        "signal": signal,
        "signal_fr": signal_fr,
        "n_articles": len(articles),
        "top_news": [
            {"title": a["title"], "score": a["score"], "date": a["date"]} for a in top_news
        ],
    }


# ─── Analyse bulk ─────────────────────────────────────────────────────────────


def analyze_portfolio_sentiment(
    tickers: list[str],
    delay: float = 0.3,
) -> dict[str, dict]:
    """
    Analyse le sentiment pour une liste de tickers.
    Rate-limité pour ne pas surcharger Yahoo RSS.

    Args:
        tickers: liste de tickers
        delay: délai entre chaque requête (secondes)

    Returns:
        dict ticker → sentiment_data
    """
    results = {}
    for ticker in tickers:
        if ticker.startswith("^"):
            continue
        try:
            results[ticker] = analyze_ticker_sentiment(ticker)
            time.sleep(delay)
        except Exception as e:
            log.warning("Sentiment error for %s: %s", ticker, e)
            results[ticker] = {"ticker": ticker, "score": 0.0, "signal": "neutral"}

    return results


# ─── Corrélation sentiment vs rendement ──────────────────────────────────────


def sentiment_return_correlation(
    sentiment_scores: dict[str, float],
    returns_5d: dict[str, float],
) -> dict:
    """
    Calcule la corrélation entre les scores de sentiment et les rendements à 5j.

    Args:
        sentiment_scores: {ticker: score [-1,+1]}
        returns_5d: {ticker: rendement_5j [-1,+1]}

    Returns:
        dict avec corrélation, p-value et classification
    """
    try:
        import numpy as np

        common = [t for t in sentiment_scores if t in returns_5d]
        if len(common) < 5:
            return {"correlation": 0.0, "p_value": 1.0, "significant": False}

        s = np.array([sentiment_scores[t] for t in common])
        r = np.array([returns_5d[t] for t in common])

        # Corrélation de Pearson
        corr = float(np.corrcoef(s, r)[0, 1])

        # p-value approximée (t-test)
        n = len(common)
        t_stat = corr * np.sqrt(n - 2) / np.sqrt(max(1 - corr**2, 1e-9))
        from scipy import stats

        p_value = float(2 * stats.t.sf(abs(t_stat), df=n - 2))

        return {
            "correlation": round(corr, 3),
            "p_value": round(p_value, 4),
            "significant": p_value < 0.05,
            "n_tickers": n,
            "interpretation": (
                "Corrélation positive significative : le sentiment prédit les rendements."
                if corr > 0.3 and p_value < 0.05
                else "Corrélation négative : sentiment contrarian." if corr < -0.3 and p_value < 0.05
                else "Pas de corrélation significative sur la période."
            ),
        }
    except Exception as e:
        log.warning("Correlation error: %s", e)
        return {"correlation": 0.0, "p_value": 1.0, "significant": False}
