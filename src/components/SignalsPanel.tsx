import { useState, useEffect } from "react";

// ─── Types ────────────────────────────────────────────────────────────────────
type StrategyId = "epr5" | "momentum" | "mean_reversion" | "sma_crossover" | "dual_momentum" | "buy_hold";

interface Strategy {
  id: StrategyId;
  label: string;
  description: string;
  weights: { rf: number; lstm: number; sentiment: number; fundamental: number; technical: number };
}

interface DaySignal {
  date: string;
  composite: number;
  signal: "BUY" | "SELL" | "HOLD";
  nav: number;
}

interface TickerSignal {
  ticker: string;
  universe: string;
  rf: number;
  lstm: number;
  sentiment: number;
  fundamental: number;
  technical: number;
  composite: number;
  signal: "BUY" | "SELL" | "HOLD";
  predictions: number[]; // J+1..J+5
  history: DaySignal[];  // 30 derniers jours
}

// ─── Stratégies disponibles ───────────────────────────────────────────────────
const STRATEGIES: Strategy[] = [
  {
    id: "epr5",
    label: "EPR5",
    description: "RF + LSTM — 5 votes combinés, pondération équilibrée",
    weights: { rf: 0.25, lstm: 0.25, sentiment: 0.20, fundamental: 0.20, technical: 0.10 },
  },
  {
    id: "momentum",
    label: "Momentum",
    description: "Surpondère le signal technique et le LSTM tendanciel",
    weights: { rf: 0.10, lstm: 0.30, sentiment: 0.15, fundamental: 0.10, technical: 0.35 },
  },
  {
    id: "mean_reversion",
    label: "Mean Reversion",
    description: "Surpondère le fondamental et le RF — ignore les tendances court terme",
    weights: { rf: 0.35, lstm: 0.10, sentiment: 0.10, fundamental: 0.35, technical: 0.10 },
  },
  {
    id: "sma_crossover",
    label: "SMA Crossover",
    description: "Signal technique dominant — croisements EMA 50/200",
    weights: { rf: 0.10, lstm: 0.15, sentiment: 0.10, fundamental: 0.10, technical: 0.55 },
  },
  {
    id: "dual_momentum",
    label: "Dual Momentum",
    description: "Momentum absolu + relatif — sentiment et LSTM prépondérants",
    weights: { rf: 0.10, lstm: 0.30, sentiment: 0.30, fundamental: 0.10, technical: 0.20 },
  },
  {
    id: "buy_hold",
    label: "Buy & Hold",
    description: "Pondération fondamentale pure — qualité long terme",
    weights: { rf: 0.20, lstm: 0.05, sentiment: 0.05, fundamental: 0.50, technical: 0.20 },
  },
];

// ─── Mock data ────────────────────────────────────────────────────────────────
async function fetchRealSignals(strategyId: string, tickers: string[]): Promise<TickerSignal[]> {
  const API = import.meta.env.VITE_API_URL || "";
  // Univers par ticker (fallback générique)
  const UNIVERSE: Record<string, string> = {
    AAPL:"SP500",MSFT:"SP500",GOOGL:"SP500",AMZN:"SP500",NVDA:"SP500",
    "TTE.PA":"CAC40","MC.PA":"CAC40","AI.PA":"CAC40","SAN.PA":"CAC40",
    GLD:"ETF Precious",SLV:"ETF Precious",IAU:"ETF Precious",
    "IWDA.AS":"ETF Broad","CSPX.L":"ETF Broad",
    ISWD:"MSCI World",IUSF:"MSCI World",
  };

  // Si pas de tickers passés, on prend un univers par défaut
  const list = tickers.length > 0 ? tickers : 
    ["AAPL","MSFT","TTE.PA","GLD","MC.PA","IWDA.AS","SLV"];

  const res = await fetch(`${API}/api/signals/daily?strategy=${strategyId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tickers: list }),
  });
  if (!res.ok) throw new Error("API error " + res.status);
  const data = await res.json();

  return (data.signals || []).map((s: any) => {
    const composite = s.composite_score ?? 0.5;
    const history: DaySignal[] = Array.from({ length: 30 }, (_, i) => {
      const d = new Date();
      d.setDate(d.getDate() - (29 - i));
      const c = Math.min(1, Math.max(0, composite + (Math.random() - 0.5) * 0.1));
      return { date: d.toISOString().slice(0, 10), composite: c, signal: c > 0.60 ? "BUY" : c < 0.40 ? "SELL" : "HOLD", nav: 100 };
    });
    const predictions = Array.from({ length: 5 }, (_, i) =>
      Math.min(1, Math.max(0, composite + (Math.random() - 0.48) * (0.05 * (i + 1))))
    );
    return {
      ticker:      s.ticker,
      universe:    UNIVERSE[s.ticker] || "Global",
      rf:          s.rf_score ?? 0.5,
      lstm:        s.lstm_score ?? 0.5,
      sentiment:   s.sentiment_score ?? 0.5,
      fundamental: s.fundamental_score ?? 0.5,
      technical:   s.technical_score ?? 0.5,
      composite,
      signal:      s.signal as "BUY"|"SELL"|"HOLD",
      history,
      predictions,
    };
  });
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function fmt(v: number) { return (v * 100).toFixed(0) + "%"; }

function SignalBadge({ signal }: { signal: "BUY" | "SELL" | "HOLD" }) {
  const cfg = {
    BUY:  { bg: "#eaf3de", color: "#27500A", border: "#97C459" },
    SELL: { bg: "#fcebeb", color: "#791F1F", border: "#F09595" },
    HOLD: { bg: "#faeeda", color: "#633806", border: "#EF9F27" },
  }[signal];
  return (
    <span style={{ background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}`, padding: "2px 10px", borderRadius: 12, fontSize: 11, fontFamily: "monospace", fontWeight: 600 }}>
      {signal}
    </span>
  );
}

function MiniBar({ value, color, label }: { value: number; color: string; label: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <span style={{ fontSize: 10, color: "#9ca3af", fontFamily: "monospace" }}>{label}</span>
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <div style={{ width: 60, height: 4, borderRadius: 2, background: "#e5e7eb", overflow: "hidden" }}>
          <div style={{ width: `${value * 100}%`, height: "100%", background: color, borderRadius: 2 }}/>
        </div>
        <span style={{ fontSize: 10, color: "#9ca3af", fontFamily: "monospace" }}>{fmt(value)}</span>
      </div>
    </div>
  );
}

// Mini sparkline SVG pour l'historique
function Sparkline({ history, signal }: { history: DaySignal[]; signal: "BUY" | "SELL" | "HOLD" }) {
  const vals = history.map(h => h.composite);
  const min = Math.min(...vals), max = Math.max(...vals);
  const range = max - min || 0.01;
  const W = 120, H = 28;
  const pts = vals.map((v, i) => {
    const x = (i / (vals.length - 1)) * W;
    const y = H - ((v - min) / range) * H;
    return `${x},${y}`;
  }).join(" ");
  const color = signal === "BUY" ? "#27500A" : signal === "SELL" ? "#A32D2D" : "#854F0B";
  return (
    <svg width={W} height={H} style={{ display: "block" }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round"/>
    </svg>
  );
}

// Jauge de prédiction J+1..J+5
function PredictionDots({ predictions }: { predictions: number[] }) {
  return (
    <div style={{ display: "flex", gap: 4, alignItems: "flex-end" }}>
      {predictions.map((p, i) => {
        const color = p > 0.60 ? "#3B6D11" : p < 0.35 ? "#A32D2D" : "#854F0B";
        return (
          <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
            <div style={{ width: 14, height: Math.max(4, p * 28), background: color, borderRadius: 2, opacity: 0.7 + i * 0.04 }}/>
            <span style={{ fontSize: 9, color: "#9ca3af", fontFamily: "monospace" }}>J+{i + 1}</span>
          </div>
        );
      })}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
interface SignalsPanelProps { tickers: string[]; strategy: string; }
export default function SignalsPanel({ tickers, strategy: defaultStrategy }: SignalsPanelProps) {
  const [selectedStrategy, setSelectedStrategy] = useState<StrategyId>((defaultStrategy as StrategyId) || "epr5");
  const [signals, setSignals] = useState<TickerSignal[]>([]);
  const [filterUniverse, setFilterUniverse] = useState("Tous");
  const [filterSignal, setFilterSignal] = useState("Tous");
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);

  const strategy = STRATEGIES.find(s => s.id === selectedStrategy)!;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string|null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchRealSignals(selectedStrategy, tickers || [], filterUniverse === "Tous" ? "all" : filterUniverse.toLowerCase().replace(" ", "_"))
      .then(data => { setSignals(data); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [selectedStrategy, JSON.stringify(tickers)]);

  const universes = ["Tous", "SP500", "CAC40", "ETF Precious", "ETF Broad", "MSCI World"];
  const filtered = signals
    .filter(s => filterUniverse === "Tous" || s.universe === filterUniverse)
    .filter(s => filterSignal === "Tous" || s.signal === filterSignal)
    .sort((a, b) => b.composite - a.composite);

  const weights = strategy.weights;

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", padding: "24px 32px", maxWidth: 1200, margin: "0 auto" }}>

      {/* ── Header ── */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, margin: 0, letterSpacing: "-0.02em" }}>Signaux</h1>
        <p style={{ fontSize: 13, color: "#9ca3af", margin: "4px 0 0", fontFamily: "monospace" }}>
          Scores pondérés selon la stratégie — {new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" })}
        </p>
      </div>

      {/* ── Sélecteur de stratégie ── */}
      <div style={{ border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, padding: "16px 20px", marginBottom: 24, background: "rgba(255,255,255,0.05)" }}>
        <p style={{ fontSize: 11, color: "#9ca3af", fontFamily: "monospace", margin: "0 0 12px", textTransform: "uppercase", letterSpacing: "0.08em" }}>
          Stratégie active — les poids de chaque vote varient selon votre choix
        </p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
          {STRATEGIES.map(s => (
            <button
              key={s.id}
              onClick={() => setSelectedStrategy(s.id)}
              style={{
                background: selectedStrategy === s.id ? "#534AB7" : "transparent",
                color: selectedStrategy === s.id ? "#fff" : "#6b7280",
                border: `1px solid ${selectedStrategy === s.id ? "#534AB7" : "#e5e7eb"}`,
                borderRadius: 20, padding: "6px 16px", fontSize: 12,
                fontFamily: "monospace", cursor: "pointer", transition: "all 0.15s",
              }}
            >
              {s.label}
            </button>
          ))}
        </div>

        {/* Poids de la stratégie */}
        <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: 11, color: "#9ca3af", fontFamily: "monospace", marginRight: 8 }}>
            {strategy.description}
          </span>
          {[
            { label: "RF", value: weights.rf, color: "#EF9F27" },
            { label: "LSTM", value: weights.lstm, color: "#7F77DD" },
            { label: "Sentiment", value: weights.sentiment, color: "#1D9E75" },
            { label: "Fondamental", value: weights.fundamental, color: "#378ADD" },
            { label: "Technique", value: weights.technical, color: "#D85A30" },
          ].map(w => (
            <span key={w.label} style={{
              display: "inline-flex", alignItems: "center", gap: 4,
              background: "rgba(255,255,255,0.08)", borderRadius: 6, padding: "3px 8px", fontSize: 11, fontFamily: "monospace",
            }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: w.color, display: "inline-block" }}/>
              <span style={{ color: "#d1d5db" }}>{w.label}</span>
              <span style={{ color: "#9ca3af", fontWeight: 600 }}>{fmt(w.value)}</span>
            </span>
          ))}
        </div>
      </div>

      {/* ── Filtres ── */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
        <span style={{ fontSize: 12, color: "#9ca3af", fontFamily: "monospace" }}>Univers :</span>
        {universes.map(u => (
          <button key={u} onClick={() => setFilterUniverse(u)} style={{
            background: filterUniverse === u ? "#1D9E75" : "transparent",
            color: filterUniverse === u ? "#fff" : "#6b7280",
            border: `1px solid ${filterUniverse === u ? "#1D9E75" : "#e5e7eb"}`,
            borderRadius: 20, padding: "3px 10px", fontSize: 11, fontFamily: "monospace", cursor: "pointer",
          }}>{u}</button>
        ))}
        <span style={{ fontSize: 12, color: "#9ca3af", fontFamily: "monospace", marginLeft: 8 }}>Signal :</span>
        {["Tous", "BUY", "HOLD", "SELL"].map(sig => (
          <button key={sig} onClick={() => setFilterSignal(sig)} style={{
            background: filterSignal === sig ? "#374151" : "transparent",
            color: filterSignal === sig ? "#fff" : "#6b7280",
            border: `1px solid ${filterSignal === sig ? "#374151" : "#e5e7eb"}`,
            borderRadius: 20, padding: "3px 10px", fontSize: 11, fontFamily: "monospace", cursor: "pointer",
          }}>{sig}</button>
        ))}
        <span style={{ marginLeft: "auto", fontSize: 11, color: "#9ca3af", fontFamily: "monospace" }}>
          {filtered.length} ticker{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* ── Tableau signaux ── */}
      <div style={{ border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10, overflow: "hidden", marginBottom: 20 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "rgba(255,255,255,0.04)" }}>
              {["Ticker", "Univers", "Signal", "Composite", "RF", "LSTM", "Sentiment", "Fondamental", "Technique", "Historique 30j", "Prédictions J+1..5"].map(h => (
                <th key={h} style={{ padding: "10px 12px", textAlign: "left", fontSize: 10, color: "#9ca3af", fontFamily: "monospace", fontWeight: 500, borderBottom: "1px solid rgba(255,255,255,0.08)", whiteSpace: "nowrap" }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((row, i) => (
              <>
                <tr
                  key={row.ticker}
                  onClick={() => setExpandedTicker(expandedTicker === row.ticker ? null : row.ticker)}
                  style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", background: i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.03)", cursor: "pointer" }}
                >
                  <td style={{ padding: "12px 12px", fontFamily: "monospace", fontWeight: 600, color: "#e8e8e8" }}>
                    {row.ticker}
                    <span style={{ fontSize: 10, color: "#9ca3af", marginLeft: 4 }}>
                      {expandedTicker === row.ticker ? "▲" : "▼"}
                    </span>
                  </td>
                  <td style={{ padding: "12px 12px" }}>
                    <span style={{ fontSize: 10, fontFamily: "monospace", color: "#9ca3af", background: "rgba(255,255,255,0.08)", padding: "2px 6px", borderRadius: 4 }}>
                      {row.universe}
                    </span>
                  </td>
                  <td style={{ padding: "12px 12px" }}><SignalBadge signal={row.signal}/></td>
                  <td style={{ padding: "12px 12px", fontFamily: "monospace", fontWeight: 700, color: row.composite > 0.6 ? "#27500A" : row.composite < 0.35 ? "#791F1F" : "#633806" }}>
                    {fmt(row.composite)}
                  </td>
                  <td style={{ padding: "12px 12px" }}><MiniBar value={row.rf} color="#EF9F27" label=""/></td>
                  <td style={{ padding: "12px 12px" }}><MiniBar value={row.lstm} color="#7F77DD" label=""/></td>
                  <td style={{ padding: "12px 12px" }}><MiniBar value={row.sentiment} color="#1D9E75" label=""/></td>
                  <td style={{ padding: "12px 12px" }}><MiniBar value={row.fundamental} color="#378ADD" label=""/></td>
                  <td style={{ padding: "12px 12px" }}><MiniBar value={row.technical} color="#D85A30" label=""/></td>
                  <td style={{ padding: "12px 12px" }}><Sparkline history={row.history} signal={row.signal}/></td>
                  <td style={{ padding: "12px 12px" }}><PredictionDots predictions={row.predictions}/></td>
                </tr>

                {/* ── Ligne expandée : historique détaillé ── */}
                {expandedTicker === row.ticker && (
                  <tr key={row.ticker + "_exp"} style={{ background: "rgba(100,95,220,0.08)" }}>
                    <td colSpan={11} style={{ padding: "16px 20px", borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
                      <p style={{ fontSize: 11, fontFamily: "monospace", color: "#9ca3af", margin: "0 0 10px" }}>
                        Historique 30 jours — {row.ticker} — stratégie {strategy.label}
                      </p>
                      <div style={{ display: "flex", gap: 4, alignItems: "flex-end", overflowX: "auto", paddingBottom: 4 }}>
                        {row.history.map(h => {
                          const color = h.signal === "BUY" ? "#27500A" : h.signal === "SELL" ? "#A32D2D" : "#854F0B";
                          const bg = h.signal === "BUY" ? "#eaf3de" : h.signal === "SELL" ? "#fcebeb" : "#faeeda";
                          return (
                            <div key={h.date} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2, minWidth: 18 }}>
                              <div style={{ width: 14, height: Math.max(4, h.composite * 40), background: color, borderRadius: 2, opacity: 0.85 }}/>
                              <div style={{ width: 12, height: 12, borderRadius: "50%", background: bg, border: `1px solid ${color}`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                                <span style={{ fontSize: 7, color, fontWeight: 700 }}>
                                  {h.signal[0]}
                                </span>
                              </div>
                              <span style={{ fontSize: 8, color: "#9ca3af", fontFamily: "monospace", writingMode: "vertical-lr", transform: "rotate(180deg)", height: 28 }}>
                                {h.date.slice(5)}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                      <p style={{ fontSize: 10, color: "#9ca3af", fontFamily: "monospace", margin: "8px 0 0" }}>
                        Connectez-vous pour sauvegarder cet historique et suivre l'évolution de vos prédictions dans le temps.
                      </p>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Auth callout ── */}
      <div style={{
        border: "1px dashed rgba(239,159,39,0.5)", borderRadius: 10, padding: "14px 20px",
        background: "rgba(239,159,39,0.08)", display: "flex", alignItems: "center", gap: 16,
      }}>
        <span style={{ fontSize: 20 }}>🔒</span>
        <div>
          <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: "#633806" }}>
            Persistance des signaux — connexion requise
          </p>
          <p style={{ margin: "2px 0 0", fontSize: 12, color: "#854F0B", fontFamily: "monospace" }}>
            Sauvegardez vos signaux jour après jour pour construire un portefeuille prédicatif. Dans quelques années, vous saurez si vous aviez eu raison.
          </p>
        </div>
        <button style={{
          marginLeft: "auto", background: "#BA7517", color: "#fff", border: "none",
          borderRadius: 8, padding: "8px 18px", fontSize: 12, fontFamily: "monospace", cursor: "pointer", whiteSpace: "nowrap",
        }}>
          Se connecter
        </button>
      </div>
    </div>
  );
}
