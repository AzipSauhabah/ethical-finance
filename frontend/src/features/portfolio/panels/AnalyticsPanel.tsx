import { useState, useEffect } from "react";

const GOLD = "#b8962f";
const NAVY2 = "#111e35";
const BORDER = "#1e2d4a";
const API = import.meta.env.VITE_API_URL ?? "";

interface AnalyticsData {
  metrics: { sharpe: number; sortino: number; ann_return: number; ann_volatility: number; max_drawdown: number; n_days: number };
  weights: Record<string, number>;
  risk_contribution: Record<string, number>;
  correlations: Record<string, Record<string, number>>;
  nav_history: { date: string; nav: number }[];
  tickers: string[];
}

function MetricCard({ label, value, unit = "", color }: { label: string; value: number; unit?: string; color: string }) {
  return (
    <div style={{ background: NAVY2, border: `1px solid ${BORDER}`, borderRadius: 6, padding: "0.75rem 1rem" }}>
      <div style={{ fontSize: "0.58rem", letterSpacing: "2px", color: "#475569", fontWeight: 700, marginBottom: "0.3rem" }}>{label}</div>
      <div style={{ fontSize: "1.2rem", fontWeight: 800, color, fontFamily: '"JetBrains Mono", monospace' }}>
        {value > 0 && unit === "%" ? "+" : ""}{value.toFixed(2)}{unit}
      </div>
    </div>
  );
}

export default function AnalyticsPanel({ positions, tickers: tickerList }: { positions: Map<string, { qty: number; avg_price: number }>; tickers?: string[] }) {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if ((tickerList?.length ?? positions.size) === 0) return;
    setLoading(true);
    const payload: Record<string, Record<string, number>> = {};
    const allTickers = tickerList ?? [...positions.keys()];
    allTickers.forEach(ticker => {
      const pos = positions.get(ticker);
      payload[ticker] = { qty: pos?.qty || 1, avg_price: pos?.avg_price || 100, last_price: pos?.avg_price || 100 };
    });
    fetch(`${API}/api/portfolio/analytics`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ positions: payload, days: 365 }),
    })
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => { setError("Erreur chargement analytics"); setLoading(false); });
  }, [tickerList?.join(',') ?? positions.size]);

  const tickerCount = tickerList?.length ?? positions.size;
  if (tickerCount === 0) return (
    <div style={{ padding: "2rem", color: "#475569", textAlign: "center", fontSize: "0.8rem" }}>
      Ajoutez des positions pour voir les analytics
    </div>
  );

  if (loading) return <div style={{ padding: "1rem", color: "#475569", fontSize: "0.8rem" }}>Calcul en cours...</div>;
  if (error || !data) return <div style={{ padding: "1rem", color: "#f87171", fontSize: "0.8rem" }}>{error || "Aucune donnée"}</div>;
  if ("error" in (data as any)) return <div style={{ padding: "1rem", color: "#f87171", fontSize: "0.8rem" }}>{(data as any).error}</div>;

  const { metrics, weights, risk_contribution, correlations, nav_history, tickers } = data;

  return (
    <div style={{ padding: "1rem", display: "flex", flexDirection: "column", gap: "1.2rem" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
        <span style={{ fontSize: "0.6rem", letterSpacing: "3px", color: GOLD, fontWeight: 700 }}>PORTFOLIO ANALYTICS</span>
        <span style={{ fontSize: "0.65rem", color: "#475569", fontFamily: '"JetBrains Mono", monospace' }}>{metrics.n_days}j de données</span>
      </div>

      {/* Métriques clés */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.5rem" }}>
        <MetricCard label="SHARPE" value={metrics.sharpe} color={metrics.sharpe >= 1 ? "#4ade80" : metrics.sharpe >= 0.5 ? GOLD : "#f87171"} />
        <MetricCard label="SORTINO" value={metrics.sortino} color={metrics.sortino >= 1.5 ? "#4ade80" : metrics.sortino >= 0.8 ? GOLD : "#f87171"} />
        <MetricCard label="RENDEMENT AN." value={metrics.ann_return} unit="%" color={metrics.ann_return >= 0 ? "#4ade80" : "#f87171"} />
        <MetricCard label="VOLATILITÉ AN." value={metrics.ann_volatility} unit="%" color={metrics.ann_volatility <= 15 ? "#4ade80" : metrics.ann_volatility <= 25 ? GOLD : "#f87171"} />
        <MetricCard label="MAX DRAWDOWN" value={metrics.max_drawdown} unit="%" color={metrics.max_drawdown >= -10 ? "#4ade80" : metrics.max_drawdown >= -20 ? GOLD : "#f87171"} />
        <MetricCard label="TICKERS" value={tickers.length} color="#94a3b8" />
      </div>

      {/* NAV Chart simplifié */}
      {nav_history.length > 0 && (
        <div style={{ background: NAVY2, border: `1px solid ${BORDER}`, borderRadius: 6, padding: "0.75rem 1rem" }}>
          <div style={{ fontSize: "0.58rem", letterSpacing: "2px", color: "#475569", fontWeight: 700, marginBottom: "0.5rem" }}>NAV NORMALISÉE (base 1.0)</div>
          <svg viewBox={`0 0 400 80`} width="100%" style={{ display: "block" }}>
            {(() => {
              const vals = nav_history.map(d => d.nav);
              const min = Math.min(...vals);
              const max = Math.max(...vals);
              const range = max - min || 1;
              const pts = vals.map((v, i) => {
                const x = (i / (vals.length - 1)) * 400;
                const y = 80 - ((v - min) / range) * 70 - 5;
                return `${x},${y}`;
              }).join(" ");
              const lastVal = vals[vals.length - 1];
              const color = lastVal >= 1 ? "#4ade80" : "#f87171";
              return (
                <>
                  <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" />
                  <line x1="0" y1={80 - ((1 - min) / range) * 70 - 5} x2="400" y2={80 - ((1 - min) / range) * 70 - 5}
                    stroke="#1e2d4a" strokeWidth="0.5" strokeDasharray="4,4" />
                </>
              );
            })()}
          </svg>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.6rem", color: "#475569", fontFamily: '"JetBrains Mono", monospace', marginTop: "0.2rem" }}>
            <span>{nav_history[0]?.date}</span>
            <span style={{ color: nav_history[nav_history.length-1]?.nav >= 1 ? "#4ade80" : "#f87171", fontWeight: 700 }}>
              {nav_history[nav_history.length-1]?.nav.toFixed(3)}
            </span>
            <span>{nav_history[nav_history.length-1]?.date}</span>
          </div>
        </div>
      )}

      {/* Risk contribution */}
      <div style={{ background: NAVY2, border: `1px solid ${BORDER}`, borderRadius: 6, padding: "0.75rem 1rem" }}>
        <div style={{ fontSize: "0.58rem", letterSpacing: "2px", color: "#475569", fontWeight: 700, marginBottom: "0.5rem" }}>CONTRIBUTION AU RISQUE</div>
        {tickers.map(t => {
          const rc = risk_contribution[t] || 0;
          const w = weights[t] || 0;
          return (
            <div key={t} style={{ marginBottom: "0.4rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.7rem", marginBottom: "0.15rem" }}>
                <span style={{ fontFamily: '"JetBrains Mono", monospace', color: GOLD, fontWeight: 600 }}>{t}</span>
                <span style={{ color: "#94a3b8" }}>{w.toFixed(1)}% poids · {rc.toFixed(1)}% risque</span>
              </div>
              <div style={{ height: 4, background: "#0d1628", borderRadius: 2 }}>
                <div style={{ height: "100%", width: `${Math.min(rc * 2, 100)}%`, background: rc > w ? "#f87171" : "#4ade80", borderRadius: 2 }} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Matrice corrélations */}
      {tickers.length > 1 && (
        <div style={{ background: NAVY2, border: `1px solid ${BORDER}`, borderRadius: 6, padding: "0.75rem 1rem" }}>
          <div style={{ fontSize: "0.58rem", letterSpacing: "2px", color: "#475569", fontWeight: 700, marginBottom: "0.5rem" }}>CORRÉLATIONS</div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ borderCollapse: "collapse", fontSize: "0.65rem", fontFamily: '"JetBrains Mono", monospace' }}>
              <thead>
                <tr>
                  <th style={{ padding: "0.2rem 0.4rem", color: "#475569" }}></th>
                  {tickers.map(t => <th key={t} style={{ padding: "0.2rem 0.4rem", color: GOLD }}>{t}</th>)}
                </tr>
              </thead>
              <tbody>
                {tickers.map(t1 => (
                  <tr key={t1}>
                    <td style={{ padding: "0.2rem 0.4rem", color: GOLD, fontWeight: 700 }}>{t1}</td>
                    {tickers.map(t2 => {
                      const v = correlations[t1]?.[t2] ?? 0;
                      const abs = Math.abs(v);
                      const bg = t1 === t2 ? "rgba(184,150,47,0.15)" :
                        abs > 0.7 ? "rgba(248,113,113,0.2)" :
                        abs > 0.4 ? "rgba(251,191,36,0.1)" : "transparent";
                      return (
                        <td key={t2} style={{ padding: "0.2rem 0.5rem", textAlign: "center", background: bg,
                          color: t1 === t2 ? GOLD : abs > 0.7 ? "#f87171" : "#94a3b8" }}>
                          {v.toFixed(2)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
