// ScreeningPanel — Stock screener avec ranking IA et non-IA
// © 2024 Sauhabah

import { useState } from "react";

const GOLD = "#b8962f";
const API = import.meta.env.VITE_API_URL ?? "";

interface ScreenerResult {
  rank: number;
  ticker: string;
  name: string;
  sector: string;
  market_cap: number;
  earning_yield: number;
  roic: number;
  ret_1m: number;
  ret_6m: number;
  ret_12m: number;
  vol_20: number;
  beta: number;
  dividend_yield: number;
  score: number;
  is_sharia?: boolean | null;
  haram_revenue_ratio?: number | null;
  sharia_debt_ratio?: number | null;
}


// ── Badge compact Finance Islamique ──────────────────────────────────────────
function IslamicBadge({ isSharia }: { isSharia?: boolean | null }) {
  const c = isSharia === true ? { bg:"#14532d", border:"#16a34a", color:"#4ade80", icon:"✓" }
          : isSharia === false ? { bg:"#450a0a", border:"#dc2626", color:"#f87171", icon:"✗" }
          : { bg:"#1a1a1a", border:"#333", color:"#555", icon:"?" };
  const tip = isSharia === true ? "Conforme Finance Islamique (AAOIFI) — cliquer pour détails"
            : isSharia === false ? "Non conforme Finance Islamique — cliquer pour détails"
            : "Données insuffisantes — cliquer pour détails";
  return (
    <span title={tip} style={{
      display:"inline-flex", alignItems:"center", justifyContent:"center",
      width:20, height:20, borderRadius:"50%",
      background:c.bg, color:c.color,
      border:"1.5px solid "+c.border,
      fontSize:11, fontWeight:700, cursor:"pointer",
      transition:"transform 0.1s", flexShrink:0,
    }}
    onMouseEnter={e=>{(e.currentTarget as HTMLElement).style.transform="scale(1.2)";}}
    onMouseLeave={e=>{(e.currentTarget as HTMLElement).style.transform="scale(1)";}}
    >{c.icon}</span>
  );
}

// ── Panel détaillé Finance Islamique ─────────────────────────────────────────
function IslamicFinancePanel({ r }: { r: ScreenerResult }) {
  const criteria = [
    {
      id: 1, label: "Activité", icon: "🏭",
      desc: "Secteur exclu de la Finance Islamique (alcool, tabac, armement, jeux, intérêts)",
      value: null, threshold: null,
      passed: r.is_sharia != null ? (r.is_sharia || r.sharia_debt_ratio != null) : null,
      detail: r.sector || "N/A",
    },
    {
      id: 2, label: "Dette portant intérêts", icon: "📊",
      desc: "Dette ST + LT / capitalisation boursière ≤ 33%",
      value: r.sharia_debt_ratio, threshold: 0.33,
      passed: r.sharia_debt_ratio != null ? r.sharia_debt_ratio <= 0.33 : null,
      detail: r.sharia_debt_ratio != null ? (r.sharia_debt_ratio*100).toFixed(1)+"%" : "N/D",
    },
    {
      id: 3, label: "Liquidités portant intérêts", icon: "💰",
      desc: "Trésorerie + actifs financiers / capitalisation ≤ 33%",
      value: null, threshold: 0.33,
      passed: null, detail: "N/D",
    },
    {
      id: 4, label: "Revenus non-permissibles", icon: "📋",
      desc: "Revenus issus d'activités non-conformes / CA total ≤ 5%",
      value: r.haram_revenue_ratio, threshold: 0.05,
      passed: r.haram_revenue_ratio != null ? r.haram_revenue_ratio <= 0.05 : null,
      detail: r.haram_revenue_ratio != null ? (r.haram_revenue_ratio*100).toFixed(1)+"%" : "N/D",
    },
  ];

  const overall = r.is_sharia;
  const passCount = criteria.filter(c => c.passed === true).length;
  const failCount = criteria.filter(c => c.passed === false).length;

  return (
    <tr>
      <td colSpan={17} style={{ padding: 0, background: "#060b14" }}>
        <div style={{
          margin: "0 0.75rem 0.75rem",
          border: "1px solid " + (overall === true ? "#14532d" : overall === false ? "#450a0a" : "#1e2d4a"),
          borderRadius: 8, overflow: "hidden",
        }}>

          {/* Header */}
          <div style={{
            display:"flex", alignItems:"center", justifyContent:"space-between",
            padding:"0.65rem 1.1rem",
            background: overall === true ? "rgba(20,83,45,0.25)" : overall === false ? "rgba(69,10,10,0.25)" : "rgba(30,45,74,0.2)",
            borderBottom:"1px solid #1e2d4a",
          }}>
            <div style={{ display:"flex", alignItems:"center", gap:"0.75rem" }}>
              <span style={{ fontSize:"0.65rem", letterSpacing:"2px", color:"#444", fontWeight:700 }}>
                FINANCE ISLAMIQUE — CONFORMITÉ AAOIFI
              </span>
              <span style={{ fontSize:"0.62rem", color:"#333" }}>
                {passCount}/4 critères satisfaits
              </span>
            </div>
            <div style={{
              display:"flex", alignItems:"center", gap:"0.5rem",
              padding:"0.25rem 0.75rem", borderRadius:4,
              background: overall === true ? "rgba(74,222,128,0.08)" : overall === false ? "rgba(248,113,113,0.08)" : "rgba(80,80,80,0.08)",
              border:"1px solid " + (overall === true ? "#16a34a" : overall === false ? "#dc2626" : "#2a2a2a"),
            }}>
              <span style={{ fontSize:14, color: overall === true ? "#4ade80" : overall === false ? "#f87171" : "#555" }}>
                {overall === true ? "✓" : overall === false ? "✗" : "?"}
              </span>
              <span style={{ fontSize:"0.72rem", fontWeight:800, letterSpacing:"1px",
                color: overall === true ? "#4ade80" : overall === false ? "#f87171" : "#555" }}>
                {overall === true ? "CONFORME" : overall === false ? "NON CONFORME" : "INDÉTERMINÉ"}
              </span>
            </div>
          </div>

          {/* 4 critères en grille */}
          <div style={{ display:"grid", gridTemplateColumns:"repeat(4, 1fr)" }}>
            {criteria.map((c, i) => {
              const pct = c.value != null && c.threshold ? Math.min(c.value / c.threshold, 1.5) : null;
              const tc = c.passed === true ? "#4ade80" : c.passed === false ? "#f87171" : "#555";
              const bc = c.passed === true ? "#16a34a" : c.passed === false ? "#dc2626" : "#2a2a2a";

              return (
                <div key={c.id} style={{
                  padding:"0.9rem 1rem",
                  borderRight: i < 3 ? "1px solid #1e2d4a" : "none",
                  borderTop:"none",
                }}>
                  {/* Titre critère */}
                  <div style={{ display:"flex", alignItems:"center", gap:"0.4rem", marginBottom:"0.5rem" }}>
                    <span style={{
                      display:"inline-flex", alignItems:"center", justifyContent:"center",
                      width:18, height:18, borderRadius:"50%", flexShrink:0,
                      background: c.passed === true ? "rgba(20,83,45,0.6)" : c.passed === false ? "rgba(69,10,10,0.6)" : "#111",
                      color:tc, fontSize:10, fontWeight:800, border:"1px solid "+bc,
                    }}>{c.passed === true ? "✓" : c.passed === false ? "✗" : "?"}</span>
                    <span style={{ fontSize:"0.65rem", fontWeight:700, color:"#aaa", letterSpacing:"0.5px" }}>
                      {c.icon} Critère {c.id} — {c.label.toUpperCase()}
                    </span>
                  </div>

                  {/* Description */}
                  <div style={{ fontSize:"0.62rem", color:"#555", marginBottom:"0.6rem", lineHeight:1.5 }}>
                    {c.desc}
                  </div>

                  {/* Valeur dynamique + barre */}
                  {c.value != null && c.threshold != null ? (
                    <>
                      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"baseline", marginBottom:"0.3rem" }}>
                        <span style={{ fontSize:"0.85rem", fontWeight:800, color:tc, fontFamily:'"JetBrains Mono", monospace' }}>
                          {c.detail}
                        </span>
                        <span style={{ fontSize:"0.6rem", color:"#333" }}>
                          seuil {(c.threshold*100).toFixed(0)}%
                        </span>
                      </div>
                      {/* Barre de progression */}
                      <div style={{ height:5, background:"#111", borderRadius:3, overflow:"hidden", marginBottom:"0.25rem" }}>
                        <div style={{
                          height:"100%",
                          width: Math.min((pct||0)*100, 100)+"%",
                          background: bc,
                          borderRadius:3,
                          transition:"width 0.5s ease",
                        }}/>
                      </div>
                      {/* Indicateur seuil */}
                      <div style={{ position:"relative", height:8 }}>
                        <div style={{
                          position:"absolute",
                          left: Math.min((1/1.5)*100, 100)+"%",
                          top:0, width:1, height:8,
                          background:"#444",
                          transform:"translateX(-50%)",
                        }}/>
                      </div>
                    </>
                  ) : (
                    <div style={{ fontSize:"0.75rem", fontWeight:700, color:tc }}>
                      {c.detail}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Footer méthodologie */}
          <div style={{
            padding:"0.4rem 1.1rem",
            borderTop:"1px solid #1e2d4a",
            display:"flex", justifyContent:"space-between",
          }}>
            <span style={{ fontSize:"0.58rem", color:"#2a2a2a" }}>
              AAOIFI · Accounting and Auditing Organisation for Islamic Financial Institutions · 4 critères cumulatifs obligatoires
            </span>
            <span style={{ fontSize:"0.58rem", color:"#2a2a2a" }}>
              Sources : ESEF filings · SEC EDGAR · Rapports annuels · MAJ hebdomadaire
            </span>
          </div>
        </div>
      </td>
    </tr>
  );
}

const METHODS = [
  { id: "magic_formula", label: "Magic Formula", desc: "Greenblatt — EBIT/EV + ROIC", icon: "◆" },
  { id: "momentum", label: "Momentum", desc: "Rendement 12-6-1 mois pondéré", icon: "◉" },
  { id: "low_vol", label: "Low Volatility", desc: "Volatilité 20 jours minimale", icon: "◎" },
  { id: "ml", label: "IA / ML Score", desc: "scikit-learn — score multifacteur", icon: "◈" },
  { id: "combined", label: "Combiné", desc: "Value + Momentum + Low Vol + ML", icon: "▣" },
];

function fmt(n: number | undefined, suffix = "%", digits = 1) {
  if (n === undefined || n === null || isNaN(n)) return "—";
  return `${n >= 0 ? "+" : ""}${n.toFixed(digits)}${suffix}`;
}

function fmtCap(n: number) {
  if (n >= 1e12) return `${(n / 1e12).toFixed(1)} T$`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)} Md$`;
  return `${(n / 1e6).toFixed(0)} M$`;
}

export default function ScreeningPanel({
  onSelectTickers,
}: {
  onSelectTickers?: (tickers: string[], method: string) => void;
}) {
  const [method, setMethod] = useState("magic_formula");
  const [universe, setUniverse] = useState("sp500");
  const [topN, setTopN] = useState(20);
  const [requireEthical, setRequireEthical] = useState(false);
  const [requireSharia, setRequireSharia] = useState(false);
  const [minCap, setMinCap] = useState(1e9);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<ScreenerResult[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function runScreener() {
    setLoading(true);
    setError("");
    setResults([]);
    try {
      const res = await fetch(`${API}/api/screener`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          method,
          universe,
          top_n: topN,
          require_ethical: requireEthical,
          require_sharia: requireSharia,
          min_market_cap: minCap,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setResults(data.results || []);
      setSelected(new Set(data.results?.map((r: ScreenerResult) => r.ticker) || []));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  }

  function toggleTicker(ticker: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(ticker) ? next.delete(ticker) : next.add(ticker);
      return next;
    });
  }

  function sendToBacktest() {
    if (onSelectTickers) {
      onSelectTickers(Array.from(selected), method);
    }
  }

  const colStyle = (val: number): string => {
    if (val > 5) return "#4ade80";
    if (val < -5) return "#f87171";
    return "#888";
  };

  return (
    <div style={{ background: "#0a0f1e", minHeight: "calc(100vh - 56px)", padding: "2rem 3rem" }}>
      {/* Header */}
      <div style={{ maxWidth: 1400, margin: "0 auto" }}>
        <div style={{ fontSize: "0.65rem", letterSpacing: "4px", color: GOLD, marginBottom: "0.5rem" }}>
          STOCK SCREENER
        </div>
        <h1 style={{ margin: "0 0 0.5rem", fontSize: "2rem", fontFamily: '"Playfair Display", serif', color: "#e8e8e8", fontWeight: 400 }}>
          Sélection quantitative de titres
        </h1>
        <p style={{ color: "#666", fontSize: "0.85rem", margin: "0 0 2rem" }}>
          Rankez 500+ titres SP500 / CAC40 par méthode quantitative ou IA. Exportez la sélection vers le backtest.
        </p>

        {/* Universe selector */}
        <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem", flexWrap: "wrap" }}>
          {[
            { id: "sp500", label: "S&P 500", desc: "483 titres US" },
            { id: "cac40", label: "CAC 40", desc: "34 titres FR" },
            { id: "etf_broad", label: "ETF World", desc: "MSCI World · Vanguard · iShares" },
            { id: "etf_precious_metals", label: "ETF Métaux", desc: "Or · Argent · Platine" },
            { id: "msci_world", label: "MSCI World", desc: "UK · AU · JP · CH · SE · NO · DK · ZA" },
            { id: "all", label: "Tous", desc: "Univers complet" },
          ].map((u) => (
            <button
              key={u.id}
              onClick={() => setUniverse(u.id)}
              style={{
                padding: "0.5rem 1rem",
                background: universe === u.id ? "rgba(184,150,47,0.15)" : "#0d1528",
                border: `1px solid ${universe === u.id ? GOLD : "#1e2d4a"}`,
                borderRadius: 6,
                color: universe === u.id ? GOLD : "#555",
                cursor: "pointer",
                transition: "all 0.2s",
                textAlign: "left",
              }}
            >
              <div style={{ fontSize: "0.82rem", fontWeight: 600 }}>{u.label}</div>
              <div style={{ fontSize: "0.68rem", color: universe === u.id ? "#b8962f99" : "#333", marginTop: "0.15rem" }}>{u.desc}</div>
            </button>
          ))}
        </div>

        {/* Method selector */}
        <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1.5rem", flexWrap: "wrap" }}>
          {METHODS.map((m) => (
            <button
              key={m.id}
              onClick={() => setMethod(m.id)}
              style={{
                padding: "0.75rem 1.25rem",
                background: method === m.id ? "rgba(184,150,47,0.15)" : "#111827",
                border: `1px solid ${method === m.id ? GOLD : "#1e2d4a"}`,
                borderRadius: 8,
                color: method === m.id ? GOLD : "#888",
                cursor: "pointer",
                transition: "all 0.2s",
                textAlign: "left",
                minWidth: 160,
              }}
            >
              <div style={{ fontSize: "1.2rem", marginBottom: "0.25rem" }}>{m.icon}</div>
              <div style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.2rem" }}>{m.label}</div>
              <div style={{ fontSize: "0.7rem", color: "#555" }}>{m.desc}</div>
            </button>
          ))}
        </div>

        {/* Filters */}
        <div style={{ display: "flex", gap: "1.5rem", alignItems: "center", marginBottom: "1.5rem", flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span style={{ fontSize: "0.8rem", color: "#888" }}>Top</span>
            <select
              value={topN}
              onChange={(e) => setTopN(Number(e.target.value))}
              style={{ background: "#111827", border: "1px solid #1e2d4a", color: "#e8e8e8", padding: "0.4rem 0.75rem", borderRadius: 6, fontSize: "0.85rem" }}
            >
              {[10, 20, 30, 50].map((n) => <option key={n} value={n}>{n} titres</option>)}
            </select>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span style={{ fontSize: "0.8rem", color: "#888" }}>Cap. min</span>
            <select
              value={minCap}
              onChange={(e) => setMinCap(Number(e.target.value))}
              style={{ background: "#111827", border: "1px solid #1e2d4a", color: "#e8e8e8", padding: "0.4rem 0.75rem", borderRadius: 6, fontSize: "0.85rem" }}
            >
              <option value={1e8}>100 M$</option>
              <option value={1e9}>1 Md$</option>
              <option value={1e10}>10 Md$</option>
              <option value={1e11}>100 Md$</option>
            </select>
          </div>

          <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
            <input type="checkbox" checked={requireEthical} onChange={(e) => setRequireEthical(e.target.checked)} />
            <span style={{ fontSize: "0.8rem", color: requireEthical ? GOLD : "#888" }}>Filtre Ethical</span>
          </label>

          <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
            <input type="checkbox" checked={requireSharia} onChange={(e) => setRequireSharia(e.target.checked)} />
            <span style={{ fontSize: "0.8rem", color: requireSharia ? GOLD : "#888" }}>Filtre Sharia</span>
          </label>

          <button
            onClick={runScreener}
            disabled={loading}
            style={{
              padding: "0.6rem 1.5rem",
              background: loading ? "#1e2d4a" : GOLD,
              color: loading ? "#888" : "#000",
              border: "none",
              borderRadius: 6,
              fontWeight: 700,
              fontSize: "0.85rem",
              cursor: loading ? "not-allowed" : "pointer",
              letterSpacing: "1px",
            }}
          >
            {loading ? "Calcul en cours…" : "▶ LANCER LE SCREENER"}
          </button>
        </div>

        {error && (
          <div style={{ padding: "0.75rem 1rem", background: "rgba(248,113,113,0.1)", border: "1px solid #f87171", borderRadius: 6, color: "#f87171", marginBottom: "1rem", fontSize: "0.85rem" }}>
            {error}
          </div>
        )}

        {/* Results */}
        {results.length > 0 && (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
              <div style={{ fontSize: "0.65rem", letterSpacing: "3px", color: GOLD }}>
                RÉSULTATS — {results.length} TITRES
              </div>
              <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
                <span style={{ fontSize: "0.75rem", color: "#555" }}>
                  {selected.size} sélectionné{selected.size > 1 ? "s" : ""}
                </span>
                <button
                  onClick={() => setSelected(new Set(results.map((r) => r.ticker)))}
                  style={{ padding: "0.3rem 0.75rem", background: "transparent", border: "1px solid #1e2d4a", color: "#888", borderRadius: 4, fontSize: "0.72rem", cursor: "pointer" }}
                >
                  Tout sélectionner
                </button>
                <button
                  onClick={sendToBacktest}
                  disabled={selected.size === 0}
                  style={{
                    padding: "0.4rem 1rem",
                    background: selected.size > 0 ? "rgba(184,150,47,0.15)" : "#111",
                    border: `1px solid ${selected.size > 0 ? GOLD : "#1e2d4a"}`,
                    color: selected.size > 0 ? GOLD : "#444",
                    borderRadius: 6,
                    fontSize: "0.78rem",
                    fontWeight: 600,
                    cursor: selected.size > 0 ? "pointer" : "not-allowed",
                    letterSpacing: "0.5px",
                  }}
                >
                  → Envoyer au backtest
                </button>
              </div>
            </div>

            {/* Table */}
            <div style={{ overflowX: "auto", background: "#111827", border: "1px solid #1e2d4a", borderRadius: 8 }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.78rem" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #1e2d4a" }}>
                    {["", "#", "Ticker", "Nom", "Secteur", "Cap.", "EY", "ROIC", "1M", "6M", "12M", "Vol", "Beta", "Div", "Score", "Sharia"].map((h) => (
                      <th key={h} style={{ padding: "0.75rem 0.6rem", textAlign: "left", color: "#555", fontWeight: 500, fontSize: "0.68rem", letterSpacing: "1px", whiteSpace: "nowrap" }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {results.map((r) => (
                    <tr
                      key={r.ticker}
                      onClick={() => { toggleTicker(r.ticker); setExpandedTicker(expandedTicker === r.ticker ? null : r.ticker); }}
                      style={{
                        borderBottom: "1px solid #0d1528",
                        background: selected.has(r.ticker) ? "rgba(184,150,47,0.04)" : "transparent",
                        cursor: "pointer",
                        transition: "background 0.15s",
                      }}
                    >
                      <td style={{ padding: "0.6rem 0.6rem" }}>
                        <input type="checkbox" checked={selected.has(r.ticker)} onChange={() => toggleTicker(r.ticker)} onClick={(e) => e.stopPropagation()} />
                      </td>
                      <td style={{ padding: "0.6rem 0.6rem", color: GOLD, fontFamily: '"JetBrains Mono", monospace', fontWeight: 700 }}>
                        {r.rank}
                      </td>
                      <td style={{ padding: "0.6rem 0.6rem", color: "#e8e8e8", fontFamily: '"JetBrains Mono", monospace', fontWeight: 600 }}>
                        {r.ticker}
                      </td>
                      <td style={{ padding: "0.6rem 0.6rem", color: "#aaa", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {r.name}
                      </td>
                      <td style={{ padding: "0.6rem 0.6rem", color: "#666", maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {r.sector}
                      </td>
                      <td style={{ padding: "0.6rem 0.6rem", color: "#888", whiteSpace: "nowrap" }}>
                        {fmtCap(r.market_cap)}
                      </td>
                      <td style={{ padding: "0.6rem 0.6rem", color: "#e8e8e8" }}>
                        {(r.earning_yield * 100).toFixed(1)}%
                      </td>
                      <td style={{ padding: "0.6rem 0.6rem", color: "#e8e8e8" }}>
                        {(r.roic * 100).toFixed(1)}%
                      </td>
                      <td style={{ padding: "0.6rem 0.6rem", color: colStyle(r.ret_1m) }}>
                        {fmt(r.ret_1m)}
                      </td>
                      <td style={{ padding: "0.6rem 0.6rem", color: colStyle(r.ret_6m) }}>
                        {fmt(r.ret_6m)}
                      </td>
                      <td style={{ padding: "0.6rem 0.6rem", color: colStyle(r.ret_12m) }}>
                        {fmt(r.ret_12m)}
                      </td>
                      <td style={{ padding: "0.6rem 0.6rem", color: "#888" }}>
                        {r.vol_20?.toFixed(1)}%
                      </td>
                      <td style={{ padding: "0.6rem 0.6rem", color: "#888" }}>
                        {r.beta?.toFixed(2)}
                      </td>
                      <td style={{ padding: "0.6rem 0.6rem", color: "#888" }}>
                        {r.dividend_yield?.toFixed(1)}%
                      </td>
                      <td style={{ padding: "0.6rem 0.6rem", color: GOLD, fontFamily: '"JetBrains Mono", monospace' }}>
                        {r.score}
                      </td>
                      <td style={{ padding: "0.6rem 0.6rem", textAlign: "center" }}>
                        <IslamicBadge isSharia={r.is_sharia} />
                      </td>
                    </tr>
                    {expandedTicker === r.ticker && <IslamicFinancePanel r={r} />}
                  </>) }
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}

        {!loading && results.length === 0 && !error && (
          <div style={{ textAlign: "center", padding: "4rem", color: "#333" }}>
            <div style={{ fontSize: "2rem", marginBottom: "1rem" }}>◈</div>
            <div style={{ fontSize: "0.85rem" }}>Choisissez une méthode et lancez le screener</div>
          </div>
        )}
      </div>
    </div>
  );
}
