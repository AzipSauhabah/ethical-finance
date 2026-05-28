import { IslamicBadge } from '../../shared/components/badges';
import BuffettPanelScreener from './panels/BuffettPanelScreener';
import IslamicFinancePanel from './panels/IslamicPanel';
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

// ── Panel détaillé Finance Islamique ─────────────────────────────────────────
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
  const [expandedBuffett, setExpandedBuffett] = useState<string | null>(null);
  const [buffettCache, setBuffettCache] = useState<Record<string, any>>({});
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
                    {["", "#", "Ticker", "Nom", "Secteur", "Cap.", "EY", "ROIC", "1M", "6M", "12M", "Vol", "Beta", "Div", "Score", "Sharia", "Buffett"].map((h) => (
                      <th key={h} style={{ padding: "0.75rem 0.6rem", textAlign: "left", color: "#555", fontWeight: 500, fontSize: "0.68rem", letterSpacing: "1px", whiteSpace: "nowrap" }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {results.map((r) => (
                    <>
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
                      <td style={{ padding: "0.6rem 0.6rem", textAlign: "center" }}>
                        <button onClick={(e) => { e.stopPropagation(); const next = expandedBuffett === r.ticker ? null : r.ticker; setExpandedBuffett(next); if (next && !buffettCache[r.ticker]) { fetch(`${API}/api/tickers/${r.ticker}/buffett`).then(res => res.json()).then(d => setBuffettCache(prev => ({ ...prev, [r.ticker]: d }))); } }} title="Buffett Score" style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 24, height: 24, borderRadius: 4, background: expandedBuffett === r.ticker ? "#b8962f" : "rgba(184,150,47,0.12)", border: "1.5px solid " + (expandedBuffett === r.ticker ? "#b8962f" : "#4a3a10"), color: expandedBuffett === r.ticker ? "#000" : "#b8962f", cursor: "pointer", fontSize: "0.65rem", fontWeight: 800 }}>B</button>
                      </td>
                    </tr>
                    {expandedTicker === r.ticker && <IslamicFinancePanel r={r} />}
                    {expandedBuffett === r.ticker && <BuffettPanelScreener data={buffettCache[r.ticker]} />}
                  </>
                  ))}
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
