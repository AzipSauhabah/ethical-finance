// IndicatorsPanel.tsx — Analyse technique préconfigurée
// RSI, Fibonacci, Bollinger Bands, MACD sur données réelles
// © 2024 Sauhabah — Ethical Finance Platform

import { useState, useEffect, useCallback } from "react";

const API = (import.meta as any).env?.VITE_API_URL || "";

// ─── Types ────────────────────────────────────────────────────────────────────
interface OHLCV { date: string; close: number; }

interface IndicatorConfig {
  rsi:       { period: number; oversold: number; overbought: number };
  bollinger: { period: number; stdDev: number };
  macd:      { fast: number; slow: number; signal: number };
  fibo:      { enabled: boolean };
}

// ─── Calculs ──────────────────────────────────────────────────────────────────
function calcRSI(closes: number[], period: number): number[] {
  const rsi: number[] = Array(closes.length).fill(null);
  if (closes.length < period + 1) return rsi;
  let gains = 0, losses = 0;
  for (let i = 1; i <= period; i++) {
    const d = closes[i] - closes[i - 1];
    if (d > 0) gains += d; else losses -= d;
  }
  let avgGain = gains / period;
  let avgLoss = losses / period;
  rsi[period] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  for (let i = period + 1; i < closes.length; i++) {
    const d = closes[i] - closes[i - 1];
    avgGain = (avgGain * (period - 1) + Math.max(d, 0)) / period;
    avgLoss = (avgLoss * (period - 1) + Math.max(-d, 0)) / period;
    rsi[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  }
  return rsi;
}

function calcEMA(data: number[], period: number): number[] {
  const ema: number[] = Array(data.length).fill(null);
  const k = 2 / (period + 1);
  let first = data.slice(0, period).filter(v => v !== null).reduce((a, b) => a + b, 0) / period;
  ema[period - 1] = first;
  for (let i = period; i < data.length; i++) {
    ema[i] = data[i] * k + ema[i - 1] * (1 - k);
  }
  return ema;
}

function calcMACD(closes: number[], fast: number, slow: number, sig: number) {
  const emaFast = calcEMA(closes, fast);
  const emaSlow = calcEMA(closes, slow);
  const macdLine = closes.map((_, i) =>
    emaFast[i] !== null && emaSlow[i] !== null ? emaFast[i] - emaSlow[i] : null
  ) as number[];
  const signalLine = calcEMA(macdLine.map(v => v ?? 0), sig);
  const histogram = macdLine.map((v, i) =>
    v !== null && signalLine[i] !== null ? v - signalLine[i] : null
  ) as number[];
  return { macdLine, signalLine, histogram };
}

function calcBollinger(closes: number[], period: number, stdDev: number) {
  const mid: number[] = Array(closes.length).fill(null);
  const upper: number[] = Array(closes.length).fill(null);
  const lower: number[] = Array(closes.length).fill(null);
  for (let i = period - 1; i < closes.length; i++) {
    const slice = closes.slice(i - period + 1, i + 1);
    const mean = slice.reduce((a, b) => a + b) / period;
    const std = Math.sqrt(slice.reduce((a, b) => a + (b - mean) ** 2, 0) / period);
    mid[i] = mean;
    upper[i] = mean + stdDev * std;
    lower[i] = mean - stdDev * std;
  }
  return { mid, upper, lower };
}

function calcFibo(closes: number[]) {
  const high = Math.max(...closes);
  const low = Math.min(...closes);
  const diff = high - low;
  return {
    high, low,
    levels: [
      { label: "100%", value: high, color: "#ef4444" },
      { label: "78.6%", value: low + diff * 0.786, color: "#f97316" },
      { label: "61.8%", value: low + diff * 0.618, color: "#eab308" },
      { label: "50%",   value: low + diff * 0.500, color: "#b8962f" },
      { label: "38.2%", value: low + diff * 0.382, color: "#22c55e" },
      { label: "23.6%", value: low + diff * 0.236, color: "#06b6d4" },
      { label: "0%",    value: low,                color: "#6366f1" },
    ],
  };
}

// ─── Mini chart SVG ───────────────────────────────────────────────────────────
function LineChart({ data, color, height = 80, fiboLevels, yMin, yMax }: {
  data: (number | null)[]; color: string; height?: number;
  fiboLevels?: { value: number; color: string; label: string }[];
  yMin?: number; yMax?: number;
}) {
  const valid = data.filter(v => v !== null) as number[];
  if (valid.length < 2) return null;
  const min = yMin ?? Math.min(...valid);
  const max = yMax ?? Math.max(...valid);
  const range = max - min || 1;
  const W = 600, H = height;
  const step = W / (data.length - 1);

  const points = data.map((v, i) => {
    if (v === null) return null;
    return `${i * step},${H - ((v - min) / range) * H}`;
  }).filter(Boolean).join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block", overflow: "visible" }}>
      {fiboLevels?.map(fl => {
        const y = H - ((fl.value - min) / range) * H;
        if (y < 0 || y > H) return null;
        return (
          <g key={fl.label}>
            <line x1={0} y1={y} x2={W} y2={y} stroke={fl.color} strokeWidth="0.8" strokeDasharray="4 3" opacity="0.6"/>
            <text x={W - 2} y={y - 3} fontSize="9" fill={fl.color} textAnchor="end" opacity="0.8">{fl.label}</text>
          </g>
        );
      })}
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round"/>
    </svg>
  );
}

function BarChart({ data, height = 60 }: { data: (number | null)[]; height?: number }) {
  const valid = data.filter(v => v !== null) as number[];
  if (!valid.length) return null;
  const max = Math.max(...valid.map(Math.abs));
  const W = 600, H = height;
  const w = W / data.length;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block" }}>
      <line x1={0} y1={H / 2} x2={W} y2={H / 2} stroke="rgba(255,255,255,0.1)" strokeWidth="0.5"/>
      {data.map((v, i) => {
        if (v === null) return null;
        const barH = (Math.abs(v) / max) * (H / 2);
        const y = v >= 0 ? H / 2 - barH : H / 2;
        return <rect key={i} x={i * w + 1} y={y} width={w - 2} height={barH} fill={v >= 0 ? "#1d9e75" : "#e53e3e"} opacity="0.8"/>;
      })}
    </svg>
  );
}

// ─── RSI gauge ───────────────────────────────────────────────────────────────
function RSIGauge({ value, oversold, overbought }: { value: number; oversold: number; overbought: number }) {
  if (value === null || isNaN(value)) return <span style={{ color: "#666", fontFamily: "monospace", fontSize: 12 }}>—</span>;
  const color = value < oversold ? "#22c55e" : value > overbought ? "#ef4444" : "#b8962f";
  const label = value < oversold ? "SURVENTE" : value > overbought ? "SURACHAT" : "NEUTRE";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <div style={{ position: "relative", width: 80, height: 80 }}>
        <svg viewBox="0 0 80 80" width="80" height="80">
          <circle cx="40" cy="40" r="32" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="6"/>
          <circle cx="40" cy="40" r="32" fill="none" stroke={color} strokeWidth="6"
            strokeDasharray={`${(value / 100) * 201} 201`}
            strokeLinecap="round"
            transform="rotate(-90 40 40)"
            style={{ transition: "stroke-dasharray 0.6s ease" }}
          />
          <text x="40" y="44" textAnchor="middle" fontSize="14" fontWeight="700" fill={color} fontFamily="monospace">
            {value.toFixed(0)}
          </text>
        </svg>
      </div>
      <div>
        <div style={{ fontSize: 11, color, fontFamily: "monospace", fontWeight: 600, letterSpacing: "0.1em" }}>{label}</div>
        <div style={{ fontSize: 10, color: "#666", fontFamily: "monospace" }}>Seuils {oversold}/{overbought}</div>
      </div>
    </div>
  );
}

// ─── Slider ───────────────────────────────────────────────────────────────────
function Slider({ label, value, min, max, step = 1, onChange }: any) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <span style={{ fontSize: 11, color: "#9ca3af", fontFamily: "monospace", minWidth: 80 }}>{label}</span>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(Number(e.target.value))}
        style={{ flex: 1, accentColor: "#b8962f", cursor: "pointer" }}
      />
      <span style={{ fontSize: 11, color: "#b8962f", fontFamily: "monospace", minWidth: 28, textAlign: "right" }}>{value}</span>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
interface Props { tickers: string[]; }

export default function IndicatorsPanel({ tickers }: Props) {
  const [ticker, setTicker] = useState<string>("");
  const [period, setPeriod] = useState("6mo");
  const [data, setData] = useState<OHLCV[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"rsi" | "bollinger" | "macd" | "fibo">("rsi");
  const [config, setConfig] = useState<IndicatorConfig>({
    rsi:       { period: 14, oversold: 30, overbought: 70 },
    bollinger: { period: 20, stdDev: 2 },
    macd:      { fast: 12, slow: 26, signal: 9 },
    fibo:      { enabled: true },
  });

  // Ticker par défaut = premier du portefeuille
  useEffect(() => {
    if (tickers.length > 0 && !ticker) setTicker(tickers[0]);
  }, [tickers]);

  const fetchData = useCallback(async () => {
    if (!ticker) return;
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/prices/db?tickers=${ticker}&period=${period}`);
      const json = await res.json();
      const rows: OHLCV[] = (json.data || []).map((d: any) => ({
        date: d.date,
        close: d[ticker] ?? null,
      })).filter((d: OHLCV) => d.close !== null);
      setData(rows);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  }, [ticker, period]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const closes = data.map(d => d.close);
  const dates = data.map(d => d.date);
  const lastClose = closes[closes.length - 1] ?? 0;

  // Calculs
  const rsiValues = calcRSI(closes, config.rsi.period);
  const lastRSI = rsiValues.filter(v => v !== null).slice(-1)[0] ?? NaN;
  const boll = calcBollinger(closes, config.bollinger.period, config.bollinger.stdDev);
  const macdData = calcMACD(closes, config.macd.fast, config.macd.slow, config.macd.signal);
  const fibo = closes.length > 0 ? calcFibo(closes) : null;

  const TABS = [
    { key: "rsi",       label: "RSI",          color: "#b8962f" },
    { key: "bollinger", label: "Bollinger",     color: "#6366f1" },
    { key: "macd",      label: "MACD",          color: "#1d9e75" },
    { key: "fibo",      label: "Fibonacci",     color: "#f97316" },
  ] as const;

  const PERIODS = ["1mo", "3mo", "6mo", "1y", "2y"];

  return (
    <div style={{ fontFamily: '"Inter", system-ui, sans-serif', padding: "24px 32px", maxWidth: 1100, margin: "0 auto", color: "#e8e8e8" }}>

      {/* ── Header ── */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, margin: 0, letterSpacing: "-0.02em" }}>Indicateurs techniques</h1>
        <p style={{ fontSize: 13, color: "#6b7280", margin: "4px 0 0", fontFamily: "monospace" }}>
          RSI · Bollinger Bands · MACD · Fibonacci — paramètres configurables
        </p>
      </div>

      {/* ── Sélection ticker + période ── */}
      <div style={{ display: "flex", gap: 12, marginBottom: 24, flexWrap: "wrap", alignItems: "center" }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {(tickers.length > 0 ? tickers : ["AAPL", "MSFT", "GLD"]).map(t => (
            <button key={t} onClick={() => setTicker(t)} style={{
              background: ticker === t ? "#b8962f" : "transparent",
              color: ticker === t ? "#000" : "#9ca3af",
              border: `1px solid ${ticker === t ? "#b8962f" : "rgba(255,255,255,0.1)"}`,
              borderRadius: 6, padding: "6px 14px", fontSize: 12,
              fontFamily: "monospace", cursor: "pointer", fontWeight: ticker === t ? 700 : 400,
            }}>{t}</button>
          ))}
          {/* Input ticker manuel */}
          <input
            placeholder="Autre ticker..."
            onKeyDown={e => { if (e.key === "Enter") setTicker((e.target as HTMLInputElement).value.toUpperCase()); }}
            style={{
              background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: 6, padding: "6px 12px", fontSize: 12, color: "#e8e8e8",
              fontFamily: "monospace", outline: "none", width: 130,
            }}
          />
        </div>
        <div style={{ display: "flex", gap: 6, marginLeft: "auto" }}>
          {PERIODS.map(p => (
            <button key={p} onClick={() => setPeriod(p)} style={{
              background: period === p ? "rgba(184,150,47,0.2)" : "transparent",
              color: period === p ? "#b8962f" : "#6b7280",
              border: `1px solid ${period === p ? "#b8962f" : "rgba(255,255,255,0.08)"}`,
              borderRadius: 6, padding: "4px 10px", fontSize: 11,
              fontFamily: "monospace", cursor: "pointer",
            }}>{p}</button>
          ))}
        </div>
      </div>

      {loading && (
        <div style={{ textAlign: "center", padding: 40, color: "#666", fontFamily: "monospace", fontSize: 12 }}>
          Chargement {ticker}...
        </div>
      )}

      {!loading && data.length > 0 && (
        <>
          {/* ── Prix + last close ── */}
          <div style={{ display: "flex", gap: 16, marginBottom: 20, flexWrap: "wrap" }}>
            {[
              { label: ticker, value: lastClose.toFixed(2), sub: "dernier cours" },
              { label: "RSI " + config.rsi.period, value: isNaN(lastRSI) ? "—" : lastRSI.toFixed(1), sub: lastRSI < config.rsi.oversold ? "survente" : lastRSI > config.rsi.overbought ? "surachat" : "neutre" },
              { label: "BB Upper", value: boll.upper.filter(v=>v!==null).slice(-1)[0]?.toFixed(2) ?? "—", sub: "bande supérieure" },
              { label: "BB Lower", value: boll.lower.filter(v=>v!==null).slice(-1)[0]?.toFixed(2) ?? "—", sub: "bande inférieure" },
              { label: "MACD", value: macdData.macdLine.filter(v=>v!==null).slice(-1)[0]?.toFixed(3) ?? "—", sub: "ligne MACD" },
            ].map(card => (
              <div key={card.label} style={{
                border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8,
                padding: "12px 16px", background: "rgba(255,255,255,0.03)", flex: "1 1 140px",
              }}>
                <p style={{ fontSize: 10, color: "#6b7280", margin: "0 0 4px", fontFamily: "monospace", textTransform: "uppercase", letterSpacing: "0.1em" }}>{card.label}</p>
                <p style={{ fontSize: 20, fontWeight: 600, margin: "0 0 2px", fontFamily: "monospace", color: "#e8e8e8" }}>{card.value}</p>
                <p style={{ fontSize: 10, color: "#4b5563", margin: 0, fontFamily: "monospace" }}>{card.sub}</p>
              </div>
            ))}
          </div>

          {/* ── Tabs indicateurs ── */}
          <div style={{ display: "flex", gap: 6, marginBottom: 16 }}>
            {TABS.map(t => (
              <button key={t.key} onClick={() => setActiveTab(t.key)} style={{
                background: activeTab === t.key ? `${t.color}22` : "transparent",
                color: activeTab === t.key ? t.color : "#6b7280",
                border: `1px solid ${activeTab === t.key ? t.color : "rgba(255,255,255,0.08)"}`,
                borderRadius: 8, padding: "8px 20px", fontSize: 12,
                fontFamily: "monospace", cursor: "pointer", fontWeight: activeTab === t.key ? 600 : 400,
              }}>{t.label}</button>
            ))}
          </div>

          {/* ── Contenu par tab ── */}
          <div style={{ border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, padding: "20px 24px", background: "rgba(255,255,255,0.02)" }}>

            {/* RSI */}
            {activeTab === "rsi" && (
              <div>
                <div style={{ display: "flex", gap: 40, marginBottom: 20, flexWrap: "wrap" }}>
                  <RSIGauge value={lastRSI} oversold={config.rsi.oversold} overbought={config.rsi.overbought} />
                  <div style={{ flex: 1, minWidth: 200 }}>
                    <Slider label="Période" value={config.rsi.period} min={5} max={30}
                      onChange={(v: number) => setConfig(c => ({ ...c, rsi: { ...c.rsi, period: v } }))} />
                    <div style={{ marginTop: 8 }}>
                      <Slider label="Survente" value={config.rsi.oversold} min={10} max={40}
                        onChange={(v: number) => setConfig(c => ({ ...c, rsi: { ...c.rsi, oversold: v } }))} />
                    </div>
                    <div style={{ marginTop: 8 }}>
                      <Slider label="Surachat" value={config.rsi.overbought} min={60} max={90}
                        onChange={(v: number) => setConfig(c => ({ ...c, rsi: { ...c.rsi, overbought: v } }))} />
                    </div>
                  </div>
                </div>
                <LineChart data={rsiValues} color="#b8962f" height={100}
                  fiboLevels={[
                    { value: config.rsi.overbought, color: "#ef4444", label: `Surachat ${config.rsi.overbought}` },
                    { value: 50, color: "rgba(255,255,255,0.2)", label: "50" },
                    { value: config.rsi.oversold, color: "#22c55e", label: `Survente ${config.rsi.oversold}` },
                  ]}
                  yMin={0} yMax={100}
                />
              </div>
            )}

            {/* Bollinger */}
            {activeTab === "bollinger" && (
              <div>
                <div style={{ display: "flex", gap: 20, marginBottom: 16, flexWrap: "wrap" }}>
                  <div style={{ flex: 1, minWidth: 200 }}>
                    <Slider label="Période" value={config.bollinger.period} min={5} max={50}
                      onChange={(v: number) => setConfig(c => ({ ...c, bollinger: { ...c.bollinger, period: v } }))} />
                    <div style={{ marginTop: 8 }}>
                      <Slider label="Écart-type" value={config.bollinger.stdDev} min={1} max={4} step={0.5}
                        onChange={(v: number) => setConfig(c => ({ ...c, bollinger: { ...c.bollinger, stdDev: v } }))} />
                    </div>
                  </div>
                  <div style={{ fontSize: 11, color: "#6b7280", fontFamily: "monospace" }}>
                    <p style={{ margin: "0 0 4px" }}>Position actuelle :</p>
                    {(() => {
                      const lastUpper = boll.upper.filter(v=>v!==null).slice(-1)[0];
                      const lastLower = boll.lower.filter(v=>v!==null).slice(-1)[0];
                      const lastMid = boll.mid.filter(v=>v!==null).slice(-1)[0];
                      if (!lastUpper || !lastLower) return null;
                      const pct = ((lastClose - lastLower) / (lastUpper - lastLower) * 100).toFixed(1);
                      const pos = lastClose > lastUpper ? "Au-dessus" : lastClose < lastLower ? "En-dessous" : "Dans les bandes";
                      return <>
                        <p style={{ margin: "0 0 2px", color: "#b8962f" }}>{pos} ({pct}%)</p>
                        <p style={{ margin: 0 }}>Mid: {lastMid?.toFixed(2)}</p>
                      </>;
                    })()}
                  </div>
                </div>
                <LineChart
                  data={boll.upper} color="#6366f1" height={120}
                  fiboLevels={[
                    { value: boll.upper.filter(v=>v!==null).slice(-1)[0] ?? 0, color: "#6366f1", label: "Upper" },
                    { value: boll.mid.filter(v=>v!==null).slice(-1)[0] ?? 0, color: "rgba(255,255,255,0.4)", label: "Mid" },
                    { value: boll.lower.filter(v=>v!==null).slice(-1)[0] ?? 0, color: "#6366f1", label: "Lower" },
                  ]}
                  yMin={Math.min(...closes) * 0.98}
                  yMax={Math.max(...closes) * 1.02}
                />
                <div style={{ marginTop: 4 }}>
                  <LineChart data={closes} color="#b8962f" height={120}
                    yMin={Math.min(...closes) * 0.98}
                    yMax={Math.max(...closes) * 1.02}
                  />
                </div>
              </div>
            )}

            {/* MACD */}
            {activeTab === "macd" && (
              <div>
                <div style={{ marginBottom: 16 }}>
                  <Slider label="EMA rapide" value={config.macd.fast} min={5} max={20}
                    onChange={(v: number) => setConfig(c => ({ ...c, macd: { ...c.macd, fast: v } }))} />
                  <div style={{ marginTop: 8 }}>
                    <Slider label="EMA lente" value={config.macd.slow} min={15} max={50}
                      onChange={(v: number) => setConfig(c => ({ ...c, macd: { ...c.macd, slow: v } }))} />
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <Slider label="Signal" value={config.macd.signal} min={3} max={15}
                      onChange={(v: number) => setConfig(c => ({ ...c, macd: { ...c.macd, signal: v } }))} />
                  </div>
                </div>
                <p style={{ fontSize: 10, color: "#6b7280", fontFamily: "monospace", margin: "0 0 8px" }}>Ligne MACD</p>
                <LineChart data={macdData.macdLine} color="#1d9e75" height={80}/>
                <p style={{ fontSize: 10, color: "#6b7280", fontFamily: "monospace", margin: "8px 0" }}>Histogramme</p>
                <BarChart data={macdData.histogram} height={60}/>
              </div>
            )}

            {/* Fibonacci */}
            {activeTab === "fibo" && fibo && (
              <div>
                <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
                  <div style={{ flex: 1, minWidth: 220 }}>
                    <p style={{ fontSize: 11, color: "#6b7280", fontFamily: "monospace", margin: "0 0 12px" }}>
                      Niveaux de retracement — range {period}
                    </p>
                    {fibo.levels.map(fl => {
                      const dist = ((lastClose - fl.value) / fl.value * 100);
                      return (
                        <div key={fl.label} style={{
                          display: "flex", alignItems: "center", gap: 10,
                          padding: "6px 0", borderBottom: "1px solid rgba(255,255,255,0.04)",
                        }}>
                          <span style={{ width: 8, height: 8, borderRadius: "50%", background: fl.color, display: "inline-block", flexShrink: 0 }}/>
                          <span style={{ fontSize: 11, fontFamily: "monospace", color: "#9ca3af", width: 42 }}>{fl.label}</span>
                          <span style={{ fontSize: 12, fontFamily: "monospace", color: "#e8e8e8", fontWeight: 600, width: 70 }}>
                            {fl.value.toFixed(2)}
                          </span>
                          <span style={{ fontSize: 10, fontFamily: "monospace", color: Math.abs(dist) < 2 ? "#b8962f" : "#4b5563" }}>
                            {dist > 0 ? "+" : ""}{dist.toFixed(1)}% vs cours
                          </span>
                          {Math.abs(dist) < 2 && (
                            <span style={{ fontSize: 9, color: "#b8962f", fontFamily: "monospace", background: "rgba(184,150,47,0.1)", padding: "1px 6px", borderRadius: 4 }}>
                              PROCHE
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  <div style={{ flex: 2, minWidth: 300 }}>
                    <LineChart
                      data={closes} color="#b8962f" height={200}
                      fiboLevels={fibo.levels}
                      yMin={fibo.low * 0.99}
                      yMax={fibo.high * 1.01}
                    />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Footer note */}
          <p style={{ fontSize: 10, color: "#374151", fontFamily: "monospace", margin: "12px 0 0", textAlign: "right" }}>
            Calculs côté client sur {closes.length} séances · {dates[0]} → {dates[dates.length - 1]}
          </p>
        </>
      )}

      {!loading && data.length === 0 && ticker && (
        <div style={{ textAlign: "center", padding: 60, color: "#444", fontFamily: "monospace", fontSize: 12 }}>
          Aucune donnée pour {ticker} — vérifie que ce ticker est dans la base.
        </div>
      )}

      {!ticker && (
        <div style={{ textAlign: "center", padding: 60, color: "#444", fontFamily: "monospace", fontSize: 12 }}>
          Ajoute des tickers dans Portefeuille ou saisit un ticker ci-dessus.
        </div>
      )}
    </div>
  );
}
