// LivePanel.tsx — Suivi intraday en temps réel via WebSocket
// Style TradingView institutional dark
// © 2024 Sauhabah — Ethical Finance Platform

import { useState, useEffect, useRef, useCallback } from "react";

const WS_BASE = (import.meta as any).env?.VITE_API_URL?.replace("https://", "wss://").replace("http://", "ws://") || "ws://localhost:8000";

// ─── Types ────────────────────────────────────────────────────────────────────
interface Tick {
  ticker: string;
  price: number;
  change_pct: number;
  change_abs: number;
  volume: number;
  timestamp: string;
  source: "twelve_data" | "db";
  error?: string;
}

interface Position {
  ticker: string;
  qty: number;
  avg_price: number;
  currency: string;
}

interface LiveRow {
  ticker: string;
  price: number | null;
  prev_price: number | null;
  change_pct: number;
  change_abs: number;
  volume: number;
  source: string;
  last_update: string;
  ticks: number[];  // sparkline des 30 derniers ticks
  connected: boolean;
  position?: Position;
  pnl?: number;
  pnl_pct?: number;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function fmt(v: number, decimals = 2) {
  return v.toLocaleString("fr-FR", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function SignBadge({ value, suffix = "%" }: { value: number; suffix?: string }) {
  const color = value > 0 ? "#22c55e" : value < 0 ? "#ef4444" : "#9ca3af";
  const sign = value > 0 ? "+" : "";
  return (
    <span style={{ color, fontFamily: "monospace", fontSize: 13, fontWeight: 600 }}>
      {sign}{fmt(value, 2)}{suffix}
    </span>
  );
}

function MiniSparkline({ ticks, color }: { ticks: number[]; color: string }) {
  if (ticks.length < 2) return <span style={{ color: "#444", fontSize: 10, fontFamily: "monospace" }}>—</span>;
  const min = Math.min(...ticks), max = Math.max(...ticks);
  const range = max - min || 0.001;
  const W = 80, H = 28;
  const pts = ticks.map((v, i) => {
    const x = (i / (ticks.length - 1)) * W;
    const y = H - ((v - min) / range) * H;
    return `${x},${y}`;
  }).join(" ");
  return (
    <svg width={W} height={H} style={{ display: "block" }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round"/>
    </svg>
  );
}

function SourceBadge({ source }: { source: string }) {
  const live = source === "twelve_data";
  return (
    <span style={{
      fontSize: 9, fontFamily: "monospace", padding: "1px 6px", borderRadius: 3,
      background: live ? "rgba(34,197,94,0.15)" : "rgba(255,255,255,0.06)",
      color: live ? "#22c55e" : "#6b7280",
      border: `1px solid ${live ? "rgba(34,197,94,0.3)" : "rgba(255,255,255,0.08)"}`,
    }}>
      {live ? "LIVE" : "DB"}
    </span>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
interface Props { tickers: string[]; }

export default function LivePanel({ tickers }: Props) {
  const [rows, setRows] = useState<Map<string, LiveRow>>(new Map());
  const [positions, setPositions] = useState<Position[]>([]);
  const [newTicker, setNewTicker] = useState("");
  const [activeTickers, setActiveTickers] = useState<string[]>([]);
  const [interval, setInterval_] = useState(10);
  const wsRefs = useRef<Map<string, WebSocket>>(new Map());
  const tickCountRef = useRef(0);

  // Init tickers depuis props
  useEffect(() => {
    if (tickers.length > 0) setActiveTickers(tickers);
  }, [tickers]);

  // Connexion WebSocket par ticker
  const connectTicker = useCallback((ticker: string) => {
    if (wsRefs.current.has(ticker)) return;

    const url = `${WS_BASE}/ws/intraday/${ticker}?interval=${interval}`;
    const ws = new WebSocket(url);

    ws.onopen = () => {
      setRows(prev => {
        const next = new Map(prev);
        const existing = next.get(ticker);
        next.set(ticker, { ...(existing || { ticker, price: null, prev_price: null, change_pct: 0, change_abs: 0, volume: 0, source: "db", last_update: "", ticks: [], connected: false }), connected: true });
        return next;
      });
    };

    ws.onmessage = (e) => {
      const tick: Tick = JSON.parse(e.data);
      if (tick.error) return;

      tickCountRef.current++;
      setRows(prev => {
        const next = new Map(prev);
        const existing = next.get(ticker);
        const prevPrice = existing?.price ?? null;
        const ticks = [...(existing?.ticks || []), tick.price].slice(-30);

        // P&L si position
        const pos = positions.find(p => p.ticker === ticker);
        const pnl = pos ? (tick.price - pos.avg_price) * pos.qty : undefined;
        const pnl_pct = pos ? ((tick.price - pos.avg_price) / pos.avg_price * 100) : undefined;

        next.set(ticker, {
          ticker,
          price: tick.price,
          prev_price: prevPrice,
          change_pct: tick.change_pct,
          change_abs: tick.change_abs,
          volume: tick.volume,
          source: tick.source,
          last_update: new Date(tick.timestamp).toLocaleTimeString("fr-FR"),
          ticks,
          connected: true,
          position: pos,
          pnl,
          pnl_pct,
        });
        return next;
      });
    };

    ws.onclose = () => {
      wsRefs.current.delete(ticker);
      setRows(prev => {
        const next = new Map(prev);
        const existing = next.get(ticker);
        if (existing) next.set(ticker, { ...existing, connected: false });
        return next;
      });
    };

    ws.onerror = () => ws.close();
    wsRefs.current.set(ticker, ws);
  }, [interval, positions]);

  const disconnectTicker = useCallback((ticker: string) => {
    wsRefs.current.get(ticker)?.close();
    wsRefs.current.delete(ticker);
    setActiveTickers(prev => prev.filter(t => t !== ticker));
    setRows(prev => { const next = new Map(prev); next.delete(ticker); return next; });
  }, []);

  // Connecte/déconnecte selon activeTickers
  useEffect(() => {
    activeTickers.forEach(t => connectTicker(t));
    // Déconnecte les tickers retirés
    wsRefs.current.forEach((_, t) => {
      if (!activeTickers.includes(t)) {
        wsRefs.current.get(t)?.close();
        wsRefs.current.delete(t);
      }
    });
  }, [activeTickers, connectTicker]);

  // Cleanup
  useEffect(() => () => { wsRefs.current.forEach(ws => ws.close()); }, []);

  const addTicker = () => {
    const t = newTicker.trim().toUpperCase();
    if (t && !activeTickers.includes(t)) {
      setActiveTickers(prev => [...prev, t]);
      setNewTicker("");
    }
  };

  const rowsArray = Array.from(rows.values()).sort((a, b) => a.ticker.localeCompare(b.ticker));
  const connectedCount = rowsArray.filter(r => r.connected).length;

  return (
    <div style={{ fontFamily: '"JetBrains Mono", "Fira Code", monospace', padding: "24px 32px", maxWidth: 1200, margin: "0 auto", color: "#e8e8e8" }}>

      {/* ── Header ── */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 600, margin: 0, letterSpacing: "-0.02em", fontFamily: "system-ui" }}>
            Live Intraday
          </h1>
          <p style={{ fontSize: 12, color: "#6b7280", margin: "4px 0 0" }}>
            {connectedCount}/{activeTickers.length} connexions actives · {tickCountRef.current} ticks reçus
          </p>
        </div>

        {/* Intervalle */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 11, color: "#6b7280" }}>Intervalle :</span>
          {[5, 10, 30, 60].map(s => (
            <button key={s} onClick={() => setInterval_(s)} style={{
              background: interval === s ? "rgba(184,150,47,0.2)" : "transparent",
              color: interval === s ? "#b8962f" : "#6b7280",
              border: `1px solid ${interval === s ? "#b8962f" : "rgba(255,255,255,0.08)"}`,
              borderRadius: 6, padding: "3px 10px", fontSize: 11, cursor: "pointer",
            }}>{s}s</button>
          ))}
        </div>
      </div>

      {/* ── Ajouter ticker ── */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
        {activeTickers.map(t => (
          <span key={t} style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 6, padding: "4px 10px", fontSize: 12,
          }}>
            <span style={{ color: rows.get(t)?.connected ? "#22c55e" : "#ef4444", fontSize: 8 }}>●</span>
            {t}
            <span onClick={() => disconnectTicker(t)} style={{ cursor: "pointer", color: "#6b7280", fontSize: 14, lineHeight: 1 }}>×</span>
          </span>
        ))}
        <div style={{ display: "flex", gap: 6 }}>
          <input
            value={newTicker}
            onChange={e => setNewTicker(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === "Enter" && addTicker()}
            placeholder="AAPL, MC.PA..."
            style={{
              background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: 6, padding: "5px 12px", fontSize: 12, color: "#e8e8e8",
              outline: "none", width: 130,
            }}
          />
          <button onClick={addTicker} style={{
            background: "#b8962f", color: "#000", border: "none",
            borderRadius: 6, padding: "5px 14px", fontSize: 12, cursor: "pointer", fontWeight: 700,
          }}>+</button>
        </div>
      </div>

      {/* ── Table ── */}
      {rowsArray.length === 0 ? (
        <div style={{ textAlign: "center", padding: 60, color: "#444", fontSize: 12 }}>
          Ajoute des tickers depuis Portefeuille ou saisis un ticker ci-dessus.
        </div>
      ) : (
        <div style={{ border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "rgba(255,255,255,0.04)" }}>
                {["", "Ticker", "Prix", "Variation", "Variation abs.", "Volume", "Sparkline", "P&L", "P&L %", "Heure", "Source"].map(h => (
                  <th key={h} style={{ padding: "10px 12px", textAlign: "left", fontSize: 10, color: "#6b7280", fontWeight: 500, borderBottom: "1px solid rgba(255,255,255,0.08)", whiteSpace: "nowrap" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rowsArray.map((row, i) => {
                const flash = row.price !== null && row.prev_price !== null && row.price !== row.prev_price;
                const priceColor = row.change_pct > 0 ? "#22c55e" : row.change_pct < 0 ? "#ef4444" : "#e8e8e8";
                return (
                  <tr key={row.ticker} style={{
                    borderBottom: "1px solid rgba(255,255,255,0.05)",
                    background: flash ? "rgba(184,150,47,0.05)" : "transparent",
                    transition: "background 0.3s",
                  }}>
                    {/* Status */}
                    <td style={{ padding: "10px 8px 10px 12px" }}>
                      <span style={{ color: row.connected ? "#22c55e" : "#ef4444", fontSize: 8 }}>●</span>
                    </td>
                    {/* Ticker */}
                    <td style={{ padding: "10px 12px", fontWeight: 700, color: "#fff", fontSize: 13 }}>
                      {row.ticker}
                    </td>
                    {/* Prix */}
                    <td style={{ padding: "10px 12px", color: priceColor, fontWeight: 700, fontSize: 14 }}>
                      {row.price !== null ? fmt(row.price, 3) : <span style={{ color: "#444" }}>—</span>}
                    </td>
                    {/* Variation % */}
                    <td style={{ padding: "10px 12px" }}>
                      {row.price !== null ? <SignBadge value={row.change_pct} suffix="%" /> : "—"}
                    </td>
                    {/* Variation abs */}
                    <td style={{ padding: "10px 12px" }}>
                      {row.price !== null ? <SignBadge value={row.change_abs} suffix="" /> : "—"}
                    </td>
                    {/* Volume */}
                    <td style={{ padding: "10px 12px", color: "#9ca3af", fontSize: 11 }}>
                      {row.volume > 0 ? (row.volume / 1e6).toFixed(2) + "M" : "—"}
                    </td>
                    {/* Sparkline */}
                    <td style={{ padding: "6px 12px" }}>
                      <MiniSparkline ticks={row.ticks} color={priceColor} />
                    </td>
                    {/* P&L */}
                    <td style={{ padding: "10px 12px" }}>
                      {row.pnl !== undefined ? <SignBadge value={row.pnl} suffix="€" /> : <span style={{ color: "#444", fontSize: 11 }}>—</span>}
                    </td>
                    {/* P&L % */}
                    <td style={{ padding: "10px 12px" }}>
                      {row.pnl_pct !== undefined ? <SignBadge value={row.pnl_pct} suffix="%" /> : <span style={{ color: "#444", fontSize: 11 }}>—</span>}
                    </td>
                    {/* Heure */}
                    <td style={{ padding: "10px 12px", color: "#6b7280", fontSize: 11 }}>
                      {row.last_update || "—"}
                    </td>
                    {/* Source */}
                    <td style={{ padding: "10px 12px" }}>
                      <SourceBadge source={row.source} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {/* Footer */}
          <div style={{ padding: "8px 16px", borderTop: "1px solid rgba(255,255,255,0.06)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 10, color: "#444" }}>
              LIVE = Twelve Data temps réel · DB = dernier cours PostgreSQL
            </span>
            <span style={{ fontSize: 10, color: "#444" }}>
              Intervalle : {interval}s · {rowsArray.length} ticker{rowsArray.length !== 1 ? "s" : ""}
            </span>
          </div>
        </div>
      )}

      {/* ── Saisie positions réelles ── */}
      <div style={{ marginTop: 20, border: "1px dashed rgba(184,150,47,0.3)", borderRadius: 10, padding: "16px 20px", background: "rgba(184,150,47,0.04)" }}>
        <p style={{ fontSize: 12, fontWeight: 600, color: "#b8962f", margin: "0 0 12px", fontFamily: "system-ui" }}>
          Positions réelles — calcul P&L
        </p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {activeTickers.map(t => {
            const pos = positions.find(p => p.ticker === t);
            return (
              <div key={t} style={{
                background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)",
                borderRadius: 8, padding: "10px 14px", minWidth: 180,
              }}>
                <p style={{ fontSize: 11, fontWeight: 700, color: "#e8e8e8", margin: "0 0 6px" }}>{t}</p>
                <div style={{ display: "flex", gap: 6 }}>
                  <input
                    type="number"
                    placeholder="Qté"
                    value={pos?.qty ?? ""}
                    onChange={e => {
                      const qty = parseFloat(e.target.value) || 0;
                      setPositions(prev => {
                        const existing = prev.find(p => p.ticker === t);
                        if (existing) return prev.map(p => p.ticker === t ? { ...p, qty } : p);
                        return [...prev, { ticker: t, qty, avg_price: 0, currency: "EUR" }];
                      });
                    }}
                    style={{ width: 60, background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 4, padding: "3px 6px", fontSize: 11, color: "#e8e8e8", outline: "none" }}
                  />
                  <input
                    type="number"
                    placeholder="PRU"
                    value={pos?.avg_price ?? ""}
                    onChange={e => {
                      const avg_price = parseFloat(e.target.value) || 0;
                      setPositions(prev => {
                        const existing = prev.find(p => p.ticker === t);
                        if (existing) return prev.map(p => p.ticker === t ? { ...p, avg_price } : p);
                        return [...prev, { ticker: t, qty: 0, avg_price, currency: "EUR" }];
                      });
                    }}
                    style={{ width: 70, background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 4, padding: "3px 6px", fontSize: 11, color: "#e8e8e8", outline: "none" }}
                  />
                </div>
              </div>
            );
          })}
        </div>
        <p style={{ fontSize: 10, color: "#444", margin: "8px 0 0", fontFamily: "system-ui" }}>
          Connectez-vous pour sauvegarder vos positions en base.
        </p>
      </div>
    </div>
  );
}
