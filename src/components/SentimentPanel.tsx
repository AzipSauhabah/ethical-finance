// SentimentPanel — Analyse de sentiment RSS Yahoo Finance + VADER
// © 2024 Sauhabah

import { useState, useEffect } from "react";

const GOLD = "#b8962f";
const API = import.meta.env.VITE_API_URL ?? "";

interface ArticleData {
  title: string;
  score: number;
}

interface TickerSentiment {
  ticker: string;
  score: number;
  signal: string;
  n_articles: number;
  bullish: ArticleData[];
  bearish: ArticleData[];
}

interface MarketSentiment {
  score: number;
  signal: string;
  signal_fr: string;
  n_articles: number;
  top_news: { title: string; score: number; date: string }[];
}

function ScoreBadge({ score, signal }: { score: number; signal: string }) {
  const color =
    signal === "bullish" || signal === "risk_on"
      ? "#4ade80"
      : signal === "bearish" || signal === "risk_off"
      ? "#f87171"
      : "#888";
  const bg =
    signal === "bullish" || signal === "risk_on"
      ? "rgba(74,222,128,0.1)"
      : signal === "bearish" || signal === "risk_off"
      ? "rgba(248,113,113,0.1)"
      : "rgba(136,136,136,0.1)";
  const label =
    signal === "bullish" ? "BULLISH" :
    signal === "bearish" ? "BEARISH" :
    signal === "risk_on" ? "RISK ON" :
    signal === "risk_off" ? "RISK OFF" : "NEUTRE";

  return (
    <div style={{
      display: "inline-flex", alignItems: "center", gap: "0.4rem",
      padding: "0.2rem 0.6rem",
      background: bg, border: `1px solid ${color}`,
      borderRadius: 4, fontSize: "0.7rem", fontWeight: 700,
      color, letterSpacing: "1px",
    }}>
      <span style={{ fontSize: "0.6rem" }}>●</span>
      {label} {score > 0 ? "+" : ""}{(score * 100).toFixed(0)}
    </div>
  );
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.abs(score) * 100;
  const color = score > 0.15 ? "#4ade80" : score < -0.15 ? "#f87171" : "#888";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
      <div style={{ width: 80, height: 6, background: "#1e2d4a", borderRadius: 3, overflow: "hidden" }}>
        <div style={{
          width: `${Math.min(pct, 100)}%`, height: "100%",
          background: color, borderRadius: 3,
          transition: "width 0.5s ease",
        }} />
      </div>
      <span style={{ fontSize: "0.7rem", color, fontFamily: '"JetBrains Mono", monospace' }}>
        {score >= 0 ? "+" : ""}{score.toFixed(3)}
      </span>
    </div>
  );
}

export default function SentimentPanel({ tickers }: { tickers: string[] }) {
  const [market, setMarket] = useState<MarketSentiment | null>(null);
  const [tickerData, setTickerData] = useState<Record<string, TickerSentiment>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  async function fetchSentiment() {
    if (tickers.length === 0) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/api/sentiment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tickers: tickers.slice(0, 10) }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setMarket(data.market);
      setTickerData(data.tickers || {});
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  }

  async function fetchMarket() {
    try {
      const res = await fetch(`${API}/api/sentiment/market`);
      if (!res.ok) return;
      const data = await res.json();
      setMarket(data);
    } catch {}
  }

  useEffect(() => {
    fetchMarket();
  }, []);

  return (
    <div style={{ background: "#0a0f1e", minHeight: "calc(100vh - 56px)", padding: "2rem 3rem" }}>
      <div style={{ maxWidth: 1400, margin: "0 auto" }}>

        {/* Header */}
        <div style={{ marginBottom: "2rem" }}>
          <div style={{ fontSize: "0.65rem", letterSpacing: "4px", color: GOLD, marginBottom: "0.5rem" }}>
            ANALYSE DE SENTIMENT
          </div>
          <h1 style={{ margin: "0 0 0.5rem", fontSize: "2rem", fontFamily: '"Playfair Display", serif', color: "#e8e8e8", fontWeight: 400 }}>
            Sentiment des marchés
          </h1>
          <p style={{ color: "#666", fontSize: "0.85rem", margin: 0 }}>
            Score VADER sur news RSS Yahoo Finance — mis à jour à la demande. Influence le vote des signaux techniques.
          </p>
        </div>

        {/* Marché global */}
        {market && (
          <div style={{
            padding: "1.5rem", marginBottom: "1.5rem",
            background: "linear-gradient(135deg, #0d1528, #111827)",
            border: `1px solid ${market.signal === "risk_on" ? "rgba(74,222,128,0.3)" : market.signal === "risk_off" ? "rgba(248,113,113,0.3)" : "#1e2d4a"}`,
            borderRadius: 8,
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem" }}>
              <div>
                <div style={{ fontSize: "0.6rem", letterSpacing: "2px", color: "#555", marginBottom: "0.5rem" }}>SENTIMENT MARCHÉ GLOBAL</div>
                <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#e8e8e8", marginBottom: "0.5rem" }}>
                  {market.signal_fr}
                </div>
                <ScoreBadge score={market.score} signal={market.signal} />
                <span style={{ marginLeft: "0.75rem", fontSize: "0.72rem", color: "#555" }}>
                  basé sur {market.n_articles} articles
                </span>
              </div>
              <div style={{ fontSize: "0.72rem", color: "#555", maxWidth: 300 }}>
                <div style={{ marginBottom: "0.25rem", color: "#888" }}>Top news :</div>
                {market.top_news?.slice(0, 3).map((n, i) => (
                  <div key={i} style={{ marginBottom: "0.25rem", display: "flex", gap: "0.5rem", alignItems: "flex-start" }}>
                    <span style={{ color: n.score > 0 ? "#4ade80" : "#f87171", flexShrink: 0 }}>
                      {n.score >= 0 ? "▲" : "▼"}
                    </span>
                    <span style={{ color: "#666", lineHeight: 1.4 }}>{n.title.slice(0, 80)}...</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Analyse portefeuille */}
        <div style={{ display: "flex", gap: "1rem", alignItems: "center", marginBottom: "1.5rem" }}>
          <button
            onClick={fetchSentiment}
            disabled={loading || tickers.length === 0}
            style={{
              padding: "0.6rem 1.5rem",
              background: loading ? "#1e2d4a" : GOLD,
              color: loading ? "#888" : "#000",
              border: "none", borderRadius: 6,
              fontWeight: 700, fontSize: "0.85rem",
              cursor: loading || tickers.length === 0 ? "not-allowed" : "pointer",
              letterSpacing: "1px",
            }}
          >
            {loading ? "Analyse en cours…" : "▶ ANALYSER LE PORTEFEUILLE"}
          </button>
          {tickers.length === 0 && (
            <span style={{ fontSize: "0.78rem", color: "#555" }}>
              Ajoutez des tickers dans l'onglet Portefeuille
            </span>
          )}
          {tickers.length > 0 && (
            <span style={{ fontSize: "0.72rem", color: "#555" }}>
              {Math.min(tickers.length, 10)} ticker{tickers.length > 1 ? "s" : ""} analysés (max 10)
            </span>
          )}
        </div>

        {error && (
          <div style={{ padding: "0.75rem 1rem", background: "rgba(248,113,113,0.1)", border: "1px solid #f87171", borderRadius: 6, color: "#f87171", marginBottom: "1rem", fontSize: "0.85rem" }}>
            {error}
          </div>
        )}

        {/* Tableau tickers */}
        {Object.keys(tickerData).length > 0 && (
          <div style={{ background: "#111827", border: "1px solid #1e2d4a", borderRadius: 8, overflow: "hidden" }}>
            <div style={{ padding: "0.75rem 1rem", borderBottom: "1px solid #1e2d4a", display: "flex", gap: "2rem" }}>
              <span style={{ fontSize: "0.65rem", letterSpacing: "2px", color: GOLD }}>
                SENTIMENT PAR TICKER — {Object.keys(tickerData).length} TITRES
              </span>
              <span style={{ fontSize: "0.65rem", color: "#444" }}>
                Score [-1, +1] · Seuil signal : ±0.15
              </span>
            </div>

            {Object.entries(tickerData).map(([ticker, data]) => (
              <div key={ticker}>
                <div
                  onClick={() => setExpanded(expanded === ticker ? null : ticker)}
                  style={{
                    display: "flex", alignItems: "center", gap: "1.5rem",
                    padding: "0.75rem 1rem",
                    borderBottom: "1px solid #0d1528",
                    cursor: "pointer",
                    background: expanded === ticker ? "rgba(184,150,47,0.04)" : "transparent",
                    transition: "background 0.15s",
                  }}
                >
                  <div style={{ width: 80, fontFamily: '"JetBrains Mono", monospace', fontWeight: 700, color: "#e8e8e8", fontSize: "0.85rem" }}>
                    {ticker}
                  </div>
                  <ScoreBadge score={data.score} signal={data.signal} />
                  <ScoreBar score={data.score} />
                  <div style={{ fontSize: "0.7rem", color: "#555", marginLeft: "auto" }}>
                    {data.n_articles} articles · {expanded === ticker ? "▲" : "▼"}
                  </div>
                </div>

                {/* News détaillées */}
                {expanded === ticker && (
                  <div style={{ padding: "1rem 1.5rem", background: "#0d1528", borderBottom: "1px solid #1e2d4a" }}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                      <div>
                        <div style={{ fontSize: "0.65rem", letterSpacing: "2px", color: "#4ade80", marginBottom: "0.5rem" }}>
                          ▲ BULLISH ({data.bullish?.length || 0})
                        </div>
                        {data.bullish?.length ? data.bullish.map((a, i) => (
                          <div key={i} style={{ marginBottom: "0.4rem", fontSize: "0.75rem", color: "#888", lineHeight: 1.4, display: "flex", gap: "0.5rem" }}>
                            <span style={{ color: "#4ade80", flexShrink: 0 }}>+{(a.score * 100).toFixed(0)}</span>
                            {a.title.slice(0, 100)}
                          </div>
                        )) : <div style={{ fontSize: "0.72rem", color: "#444" }}>Aucune news bullish</div>}
                      </div>
                      <div>
                        <div style={{ fontSize: "0.65rem", letterSpacing: "2px", color: "#f87171", marginBottom: "0.5rem" }}>
                          ▼ BEARISH ({data.bearish?.length || 0})
                        </div>
                        {data.bearish?.length ? data.bearish.map((a, i) => (
                          <div key={i} style={{ marginBottom: "0.4rem", fontSize: "0.75rem", color: "#888", lineHeight: 1.4, display: "flex", gap: "0.5rem" }}>
                            <span style={{ color: "#f87171", flexShrink: 0 }}>{(a.score * 100).toFixed(0)}</span>
                            {a.title.slice(0, 100)}
                          </div>
                        )) : <div style={{ fontSize: "0.72rem", color: "#444" }}>Aucune news bearish</div>}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {!loading && Object.keys(tickerData).length === 0 && tickers.length > 0 && (
          <div style={{ textAlign: "center", padding: "4rem", color: "#333" }}>
            <div style={{ fontSize: "2rem", marginBottom: "1rem" }}>◉</div>
            <div style={{ fontSize: "0.85rem" }}>Cliquez sur "Analyser le portefeuille" pour charger les sentiments</div>
          </div>
        )}

        {/* Méthodologie */}
        <div style={{ marginTop: "2rem", padding: "1rem 1.5rem", background: "rgba(184,150,47,0.03)", border: "1px solid rgba(184,150,47,0.1)", borderRadius: 8 }}>
          <div style={{ fontSize: "0.6rem", letterSpacing: "2px", color: GOLD, marginBottom: "0.5rem" }}>MÉTHODOLOGIE</div>
          <div style={{ fontSize: "0.72rem", color: "#555", lineHeight: 1.6 }}>
            Score VADER (Valence Aware Dictionary and sEntiment Reasoner) enrichi d'un lexique financier (beat/miss/upgrade/downgrade...).
            Sources : RSS Yahoo Finance. Score [-1, +1] : &gt;0.15 = bullish (+1 dans le vote), &lt;-0.15 = bearish (-1).
            Le sentiment constitue le 5ème signal dans le vote des signaux techniques (SMA + RSI + MACD + Momentum + Sentiment).
            Limite : le sentiment des news est un signal retardé et bruité — à utiliser en confirmation, pas en déclencheur principal.
          </div>
        </div>
      </div>
    </div>
  );
}
