import { useState, useEffect } from "react";
const API = import.meta.env.VITE_API_URL ?? "";

// ─── Types ────────────────────────────────────────────────────────────────────
interface StatCard {
  label: string;
  value: string;
  sub?: string;
}

interface SignalRow {
  ticker: string;
  universe: string;
  composite: number;
  sentiment: number;
  fundamental: number;
  epr5: number;
  signal: "BUY" | "SELL" | "HOLD";
  date: string;
}

// ─── Stats dynamiques depuis /api/stats ─────────────────────────────────────
const STATS_DEFAULT: StatCard[] = [
  { label: "Tickers tracked",  value: "...", sub: "loading" },
  { label: "OHLCV in DB",      value: "...", sub: "loading" },
  { label: "Fundamentals",     value: "...", sub: "loading" },
  { label: "Signals archived", value: "...", sub: "loading" },
  { label: "Tests",            value: "195", sub: "195/195 passing" },
  { label: "Code Quality",     value: "A",   sub: "0 bugs · 0 vulns" },
];

const SIGNALS_STATIC: SignalRow[] = [];

// ─── Architecture SVG ─────────────────────────────────────────────────────────
function ArchitectureSVG() {
  return (
    <svg viewBox="0 0 680 500" width="100%" style={{ display: "block" }} aria-label="Architecture ethical-finance v2">
      <defs>
        <marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M2 1L8 5L2 9" fill="none" stroke="#6b7280" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </marker>
        <marker id="arr-purple" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M2 1L8 5L2 9" fill="none" stroke="#7F77DD" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </marker>
        <marker id="arr-teal" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M2 1L8 5L2 9" fill="none" stroke="#1D9E75" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </marker>
        <marker id="arr-amber" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M2 1L8 5L2 9" fill="none" stroke="#BA7517" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </marker>
      </defs>

      {/* Layer 1: Data */}
      <rect x="20" y="10" width="640" height="60" rx="8" fill="none" stroke="#9ca3af" strokeWidth="0.5" strokeDasharray="5 3"/>
      <text x="34" y="26" fontSize="9" fill="#9ca3af" fontFamily="monospace">COUCHE DONNÉES — PostgreSQL source principale, zéro yfinance temps réel</text>
      {[["OHLCV+splits",44],["Fundamentals SEC",168],["NAV div.réinv.",300],["Intraday WS",414],["Sentiment VADER",520]].map(([l,x])=>(
        <g key={l as string}>
          <rect x={x as number} y="30" width={(l as string).length*7+14} height="30" rx="5" fill="#1a1f2e" stroke="#374151" strokeWidth="0.5"/>
          <text x={(x as number)+((l as string).length*7+14)/2} y="50" fontSize="9" textAnchor="middle" fill="#9ca3af" fontFamily="monospace">{l as string}</text>
        </g>
      ))}

      <line x1="340" y1="70" x2="340" y2="95" stroke="#6b7280" strokeWidth="0.8" markerEnd="url(#arr)"/>

      {/* Layer 2: Signal engine */}
      <rect x="20" y="97" width="640" height="68" rx="8" fill="none" stroke="#7F77DD" strokeWidth="0.5" strokeDasharray="5 3"/>
      <text x="34" y="113" fontSize="9" fill="#7F77DD" fontFamily="monospace">MOTEUR DE SIGNAUX — persistance auto 20h30 UTC dans signals_history</text>
      {[["EPR5 RF+LSTM",30,"vote technique"],["Sentiment VADER",178,"lexique custom"],["Fondamental SEC",326,"30+ GAAP"],["RSI/Fibo/Elliott",474,"indicateurs v2"]].map(([l,x,s])=>(
        <g key={l as string}>
          <rect x={x as number} y="117" width="136" height="40" rx="5" fill="#1e1a3e" stroke="#534AB7" strokeWidth="0.5"/>
          <text x={(x as number)+68} y="132" fontSize="9" fontWeight="500" textAnchor="middle" fill="#AFA9EC" fontFamily="monospace">{l as string}</text>
          <text x={(x as number)+68} y="147" fontSize="8" textAnchor="middle" fill="#7F77DD" fontFamily="monospace">{s as string}</text>
        </g>
      ))}

      <line x1="340" y1="165" x2="340" y2="192" stroke="#7F77DD" strokeWidth="0.8" markerEnd="url(#arr-purple)"/>

      {/* Layer 3: Strategy filter */}
      <rect x="160" y="194" width="360" height="46" rx="8" fill="#0f2a1e" stroke="#1D9E75" strokeWidth="0.5"/>
      <text x="340" y="213" fontSize="10" fontWeight="500" textAnchor="middle" fill="#9FE1CB" fontFamily="monospace">filtre stratégie</text>
      <text x="340" y="230" fontSize="8" textAnchor="middle" fill="#1D9E75" fontFamily="monospace">poids adaptés — EPR5 / Momentum / Mean Reversion / SMA / Dual / Buy&Hold</text>

      <line x1="230" y1="240" x2="160" y2="272" stroke="#1D9E75" strokeWidth="0.8" markerEnd="url(#arr-teal)"/>
      <line x1="340" y1="240" x2="340" y2="272" stroke="#1D9E75" strokeWidth="0.8" markerEnd="url(#arr-teal)"/>
      <line x1="450" y1="240" x2="520" y2="272" stroke="#1D9E75" strokeWidth="0.8" markerEnd="url(#arr-teal)"/>

      {/* Layer 4: Outputs */}
      <rect x="20" y="274" width="240" height="46" rx="8" fill="#0a1929" stroke="#185FA5" strokeWidth="0.5"/>
      <text x="140" y="293" fontSize="10" fontWeight="500" textAnchor="middle" fill="#93C5FD" fontFamily="monospace">signaux J+J</text>
      <text x="140" y="309" fontSize="8" textAnchor="middle" fill="#378ADD" fontFamily="monospace">flux jour/jour + préd. J+1..J+5</text>

      <rect x="280" y="274" width="120" height="46" rx="8" fill="#0f2a1e" stroke="#1D9E75" strokeWidth="0.5"/>
      <text x="340" y="293" fontSize="10" fontWeight="500" textAnchor="middle" fill="#9FE1CB" fontFamily="monospace">backtest</text>
      <text x="340" y="309" fontSize="8" textAnchor="middle" fill="#1D9E75" fontFamily="monospace">event-driven</text>

      <rect x="420" y="274" width="240" height="46" rx="8" fill="#0a1929" stroke="#185FA5" strokeWidth="0.5"/>
      <text x="540" y="293" fontSize="10" fontWeight="500" textAnchor="middle" fill="#93C5FD" fontFamily="monospace">live intraday WS</text>
      <text x="540" y="309" fontSize="8" textAnchor="middle" fill="#378ADD" fontFamily="monospace">15min Twelve Data + P&L réel</text>

      <line x1="140" y1="320" x2="140" y2="352" stroke="#378ADD" strokeWidth="0.8" markerEnd="url(#arr)"/>
      <line x1="340" y1="320" x2="340" y2="352" stroke="#1D9E75" strokeWidth="0.8" markerEnd="url(#arr)"/>
      <line x1="540" y1="320" x2="540" y2="352" stroke="#378ADD" strokeWidth="0.8" markerEnd="url(#arr)"/>

      {/* Layer 5: Persistence */}
      <rect x="20" y="354" width="640" height="58" rx="8" fill="none" stroke="#BA7517" strokeWidth="0.5" strokeDasharray="5 3"/>
      <text x="34" y="370" fontSize="9" fill="#BA7517" fontFamily="monospace">PERSISTANCE — auth JWT requise pour portfolio et historique signaux</text>
      {[["users",30],["user_portfolios",130],["signals_history",290],["nav_history",460],["Cache mémoire",576]].map(([l,x])=>(
        <g key={l as string}>
          <rect x={x as number} y="374" width={(l as string).length*7+12} height="30" rx="5" fill="#1c1207" stroke="#854F0B" strokeWidth="0.5"/>
          <text x={(x as number)+((l as string).length*7+12)/2} y="393" fontSize="9" textAnchor="middle" fill="#D4881A" fontFamily="monospace">{l as string}</text>
        </g>
      ))}

      <line x1="340" y1="412" x2="340" y2="438" stroke="#BA7517" strokeWidth="0.8" markerEnd="url(#arr-amber)"/>

      {/* Layer 6: Frontend */}
      <rect x="20" y="440" width="640" height="34" rx="8" fill="none" stroke="#1D9E75" strokeWidth="0.5" strokeDasharray="5 3"/>
      {[["Accueil",30],["Portfolio",100],["Screener",190],["Backtest",280],["Signaux",368],["Sentiment",452],["Indicateurs",543]].map(([l,x])=>(
        <text key={l as string} x={x as number} y="462" fontSize="9" fill="#1D9E75" fontFamily="monospace" fontWeight="500">{l as string}</text>
      ))}
      <text x="656" y="462" fontSize="8" textAnchor="end" fill="#9FE1CB" fontFamily="monospace">Live</text>
      <text x="656" y="471" fontSize="7" textAnchor="end" fill="#4B8B6A" fontFamily="monospace">React/Vite/TS</text>
    </svg>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function SignalBadge({ signal }: { signal: "BUY" | "SELL" | "HOLD" }) {
  const cfg = { BUY: { bg: "#eaf3de", color: "#27500A", border: "#97C459" }, SELL: { bg: "#fcebeb", color: "#791F1F", border: "#F09595" }, HOLD: { bg: "#faeeda", color: "#633806", border: "#EF9F27" } }[signal];
  return <span style={{ background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}`, padding: "2px 10px", borderRadius: 12, fontSize: 11, fontFamily: "monospace", fontWeight: 600 }}>{signal}</span>;
}

function ScoreBar({ value, color }: { value: number; color: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{ flex: 1, height: 4, borderRadius: 2, background: "rgba(255,255,255,0.08)", overflow: "hidden" }}>
        <div style={{ width: `${value * 100}%`, height: "100%", background: color, borderRadius: 2 }}/>
      </div>
      <span style={{ fontSize: 11, color: "#9ca3af", fontFamily: "monospace", minWidth: 32, textAlign: "right" }}>{(value * 100).toFixed(0)}%</span>
    </div>
  );
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────
export default function DashboardPage() {
  const [showArch, setShowArch] = useState(false);
  const [activeUniverse, setActiveUniverse] = useState("All");
  const [stats, setStats] = useState<StatCard[]>(STATS_DEFAULT);

  useEffect(() => {
    fetch(`${API}/api/stats`)
      .then(r => r.json())
      .then(d => setStats([
        { label: "Tickers tracked",  value: d.tickers?.value  || "?", sub: d.tickers?.sub  || "" },
        { label: "OHLCV in DB",      value: d.ohlcv?.value    || "?", sub: d.ohlcv?.sub    || "" },
        { label: "Fundamentals",     value: d.fundamentals?.value || "?", sub: d.fundamentals?.sub || "" },
        { label: "Signals archived", value: d.signals?.value  || "?", sub: d.signals?.sub  || "" },
        { label: "Tests",            value: "195", sub: "195/195 passing" },
        { label: "Code Quality",     value: "A",   sub: "0 bugs · 0 vulns" },
      ]))
      .catch(() => {});
  }, []);
  const [signals, setSignals] = useState<SignalRow[]>([]);
  const [signalsLoading, setSignalsLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/signals/latest?limit=20&strategy=epr5`)
      .then(r => r.json())
      .then(d => {
        if (d.signals?.length > 0) {
          setSignals(d.signals.map((s: any) => ({
            ticker: s.ticker,
            universe: s.universe?.toUpperCase() || "SP500",
            composite: s.composite,
            sentiment: s.sentiment,
            fundamental: s.fundamental,
            epr5: s.epr5,
            signal: s.signal,
            date: s.date,
          })));
        }
        setSignalsLoading(false);
      })
      .catch(() => setSignalsLoading(false));
  }, []);

  const universes = ["All", "SP500", "CAC40", "ETF Precious", "ETF Broad", "MSCI World"];
  const allSignals = signals.length > 0 ? signals : SIGNALS_STATIC;
  const filtered = activeUniverse === "All" ? allSignals : allSignals.filter(s => s.universe === activeUniverse);

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", padding: "24px 32px", maxWidth: 1100, margin: "0 auto", color: "#e8e8e8" }}>

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 600, margin: 0, letterSpacing: "-0.02em" }}>Sauhabah Ethical Finance</h1>
          <p style={{ fontSize: 13, color: "#6b7280", margin: "4px 0 0", fontFamily: "monospace" }}>
            Dashboard — {new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
          </p>
        </div>
        <button onClick={() => setShowArch(v => !v)} style={{
          background: showArch ? "#eeedfe" : "transparent",
          border: "1px solid #AFA9EC", color: showArch ? "#3C3489" : "#534AB7",
          borderRadius: 8, padding: "8px 16px", fontSize: 12, fontFamily: "monospace", cursor: "pointer",
        }}>
          {showArch ? "Masquer" : "Voir"} l'architecture v2
        </button>
      </div>

      {/* Architecture panel */}
      {showArch && (
        <div style={{ border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, padding: "20px 24px", marginBottom: 28, background: "rgba(255,255,255,0.02)" }}>
          <p style={{ fontSize: 11, color: "#6b7280", fontFamily: "monospace", marginBottom: 16 }}>Architecture plateforme v2 — PostgreSQL source principale, zéro dépendance cloud externe</p>
          <ArchitectureSVG />
        </div>
      )}

      {/* KPI cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 28 }}>
        {stats.map(stat => (
          <div key={stat.label} style={{ border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, padding: "16px 20px", background: "rgba(255,255,255,0.03)" }}>
            <p style={{ fontSize: 11, color: "#9ca3af", margin: "0 0 6px", fontFamily: "monospace", textTransform: "uppercase", letterSpacing: "0.08em" }}>{stat.label}</p>
            <p style={{ fontSize: 22, fontWeight: 600, margin: "0 0 2px", letterSpacing: "-0.02em" }}>{stat.value}</p>
            {stat.sub && <p style={{ fontSize: 11, color: "#6b7280", margin: 0, fontFamily: "monospace" }}>{stat.sub}</p>}
          </div>
        ))}
      </div>

      {/* Pipeline status */}
      <div style={{ border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, padding: "12px 20px", marginBottom: 28, background: "rgba(0,255,100,0.03)", display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, fontFamily: "monospace", color: "#9FE1CB", fontWeight: 600 }}>Auto Pipeline</span>
        {[
          { label: "OHLCV 20h",    ok: true },
          { label: "Signals 20h30",ok: true },
          { label: "SEC 22h",      ok: true },
          { label: "FMP 22h30",    ok: true },
          { label: "Backup 23h",   ok: true },
          { label: "Drive 23h30",  ok: true },
        ].map(step => (
          <span key={step.label} style={{ fontSize: 11, fontFamily: "monospace", display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{ color: step.ok ? "#22c55e" : "#ef4444" }}>{step.ok ? "✓" : "✗"}</span>
            <span style={{ color: step.ok ? "#9FE1CB" : "#FCA5A5" }}>{step.label}</span>
          </span>
        ))}
        <span style={{ marginLeft: "auto", fontSize: 10, color: "#4b5563", fontFamily: "monospace" }}>
          pgAdmin: 192.168.1.139:5050 · PG port: 5433 · workers: 1
        </span>
      </div>

      {/* Signals table */}
      <div style={{ border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, overflow: "hidden" }}>
        <div style={{ padding: "14px 20px", borderBottom: "1px solid rgba(255,255,255,0.08)", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
          <span style={{ fontSize: 14, fontWeight: 600 }}>Today's Signals</span>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {universes.map(u => (
              <button key={u} onClick={() => setActiveUniverse(u)} style={{
                background: activeUniverse === u ? "#534AB7" : "transparent",
                color: activeUniverse === u ? "#fff" : "#6b7280",
                border: `1px solid ${activeUniverse === u ? "#534AB7" : "rgba(255,255,255,0.1)"}`,
                borderRadius: 20, padding: "3px 12px", fontSize: 11, fontFamily: "monospace", cursor: "pointer",
              }}>{u}</button>
            ))}
          </div>
        </div>

        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, background: "transparent" }}>
          <thead>
            <tr style={{ background: "rgba(255,255,255,0.04)" }}>
              {["Ticker", "Univers", "Signal", "Score composite", "Sentiment", "Fondamental", "EPR5"].map(h => (
                <th key={h} style={{ padding: "10px 16px", textAlign: "left", fontSize: 11, color: "#6b7280", fontFamily: "monospace", fontWeight: 500, borderBottom: "1px solid rgba(255,255,255,0.08)" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody style={{ background: "transparent" }}>
            {filtered.map((row, i) => (
              <tr key={row.ticker} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", background: "transparent" }}>
                <td style={{ padding: "12px 16px", fontFamily: "monospace", fontWeight: 600, color: "#fff" }}>{row.ticker}</td>
                <td style={{ padding: "12px 16px" }}>
                  <span style={{ fontSize: 11, fontFamily: "monospace", color: "#9ca3af", background: "rgba(255,255,255,0.08)", padding: "2px 8px", borderRadius: 4 }}>{row.universe}</span>
                </td>
                <td style={{ padding: "12px 16px" }}><SignalBadge signal={row.signal}/></td>
                <td style={{ padding: "12px 16px", width: 140 }}><ScoreBar value={row.composite} color="#534AB7"/></td>
                <td style={{ padding: "12px 16px", width: 120 }}><ScoreBar value={row.sentiment} color="#1D9E75"/></td>
                <td style={{ padding: "12px 16px", width: 120 }}><ScoreBar value={row.fundamental} color="#378ADD"/></td>
                <td style={{ padding: "12px 16px", width: 120 }}><ScoreBar value={row.epr5} color="#EF9F27"/></td>
              </tr>
            ))}
          </tbody>
        </table>

        <div style={{ padding: "10px 20px", borderTop: "1px solid rgba(255,255,255,0.06)", background: "rgba(255,255,255,0.02)", display: "flex", justifyContent: "space-between" }}>
          <span style={{ fontSize: 11, color: "#4b5563", fontFamily: "monospace" }}>
            Scores : EPR5 RF+LSTM · Sentiment VADER · Fondamental SEC EDGAR · Composite pondéré selon stratégie
          </span>
          <span style={{ fontSize: 11, color: "#4b5563", fontFamily: "monospace" }}>{filtered.length} signal{filtered.length !== 1 ? "s" : ""}</span>
        </div>
      </div>

      {/* Auth callout */}
      <div style={{ marginTop: 20, border: "1px dashed rgba(239,159,39,0.4)", borderRadius: 10, padding: "14px 20px", background: "rgba(239,159,39,0.05)", display: "flex", alignItems: "center", gap: 16 }}>
        <span style={{ fontSize: 20 }}>🔒</span>
        <div>
          <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: "#EF9F27" }}>Persistance portfolio — connexion dans l'onglet Portfolio</p>
          <p style={{ margin: "2px 0 0", fontSize: 12, color: "#BA7517", fontFamily: "monospace" }}>
            Sauvegardez vos positions, suivez votre P&L en temps réel, accédez à l'historique de vos signaux jour après jour.
          </p>
        </div>
        <span style={{ marginLeft: "auto", fontSize: 11, color: "#BA7517", fontFamily: "monospace", whiteSpace: "nowrap" }}>
          → onglet Portfolio
        </span>
      </div>
      <div style={{ marginTop: "1.5rem", padding: "0.75rem 1rem", background: "rgba(184,150,47,0.06)", border: "1px solid rgba(184,150,47,0.2)", borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>Documentation technique complète — architecture, API, modules, schéma DB</span>
        <a href="/docs/index.html" target="_blank" rel="noopener" style={{ fontSize: "0.72rem", color: "#b8962f", fontFamily: "monospace", fontWeight: 700, textDecoration: "none", border: "1px solid rgba(184,150,47,0.3)", padding: "0.25rem 0.75rem", borderRadius: 4 }}>DOCS →</a>
      </div>
    </div>
  );
}
