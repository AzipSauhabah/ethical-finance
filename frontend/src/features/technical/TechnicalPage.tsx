// TechnicalPanel — Architecture, Stratégies & Maths
// Style : Institutional dark — Goldman Sachs meets CERN documentation
// © 2024 Sauhabah

import { useState, useEffect, useRef } from "react";

const GOLD = "#b8962f";
const NAVY = "#0d1528";
const BLUE = "#1e3a5f";

// ── Animated Counter ──────────────────────────────────────────────────────────
function AnimatedNumber({ value, suffix = "", decimals = 0 }: { value: number; suffix?: string; decimals?: number }) {
  const [display, setDisplay] = useState(0);
  const ref = useRef<number>(0);
  useEffect(() => {
    const start = ref.current;
    const duration = 1200;
    const startTime = performance.now();
    const tick = (now: number) => {
      const progress = Math.min((now - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = start + (value - start) * eased;
      setDisplay(current);
      if (progress < 1) requestAnimationFrame(tick);
      else ref.current = value;
    };
    requestAnimationFrame(tick);
  }, [value]);
  return <>{display.toFixed(decimals)}{suffix}</>;
}

// ── Pipeline Node ─────────────────────────────────────────────────────────────
function PipelineNode({ label, time, color, icon, active, onClick }: any) {
  return (
    <div onClick={onClick} style={{
      display: "flex", flexDirection: "column", alignItems: "center", gap: "0.5rem",
      cursor: "pointer",
    }}>
      <div style={{
        width: 64, height: 64, borderRadius: "50%",
        background: active ? `radial-gradient(circle at 30% 30%, ${color}44, ${color}11)` : "#111827",
        border: `2px solid ${active ? color : "#1e2d4a"}`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: "1.5rem",
        boxShadow: active ? `0 0 20px ${color}44` : "none",
        transition: "all 0.3s ease",
      }}>{icon}</div>
      <div style={{ fontSize: "0.68rem", color: active ? color : "#555", textAlign: "center", maxWidth: 80, letterSpacing: "0.5px" }}>{label}</div>
      <div style={{ fontSize: "0.6rem", color: "#333", fontFamily: '"JetBrains Mono", monospace' }}>{time}</div>
    </div>
  );
}

// ── Math Formula ──────────────────────────────────────────────────────────────
function Formula({ title, formula, explanation, color = GOLD }: any) {
  return (
    <div style={{
      padding: "1.25rem", background: "#0a0f1e",
      border: `1px solid ${color}33`, borderLeft: `3px solid ${color}`,
      borderRadius: 6, marginBottom: "0.75rem",
    }}>
      <div style={{ fontSize: "0.65rem", letterSpacing: "2px", color, marginBottom: "0.5rem" }}>{title}</div>
      <div style={{
        fontFamily: '"JetBrains Mono", monospace', fontSize: "0.9rem",
        color: "#e8e8e8", marginBottom: "0.5rem", padding: "0.5rem",
        background: "#111827", borderRadius: 4,
      }}>{formula}</div>
      <div style={{ fontSize: "0.75rem", color: "#666", lineHeight: 1.6 }}>{explanation}</div>
    </div>
  );
}

// ── Strategy Card ─────────────────────────────────────────────────────────────
function StrategyCard({ name, type, description, conditions, signals, color }: any) {
  const [open, setOpen] = useState(false);
  return (
    <div onClick={() => setOpen(!open)} style={{
      padding: "1rem 1.25rem", background: "#111827",
      border: `1px solid ${open ? color : "#1e2d4a"}`,
      borderRadius: 8, cursor: "pointer", transition: "all 0.2s",
      marginBottom: "0.5rem",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
          <div style={{
            padding: "0.2rem 0.5rem", background: `${color}22`,
            border: `1px solid ${color}44`, borderRadius: 3,
            fontSize: "0.6rem", color, letterSpacing: "1px", fontWeight: 700,
          }}>{type}</div>
          <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "#e8e8e8" }}>{name}</span>
        </div>
        <span style={{ color: "#555", fontSize: "0.8rem" }}>{open ? "▲" : "▼"}</span>
      </div>
      {open && (
        <div style={{ marginTop: "1rem", paddingTop: "1rem", borderTop: "1px solid #1e2d4a" }}>
          <p style={{ fontSize: "0.78rem", color: "#888", lineHeight: 1.7, marginBottom: "0.75rem" }}>{description}</p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
            <div>
              <div style={{ fontSize: "0.6rem", letterSpacing: "2px", color: "#555", marginBottom: "0.4rem" }}>CONDITIONS D'ENTRÉE</div>
              {conditions.map((c: string, i: number) => (
                <div key={i} style={{ fontSize: "0.72rem", color: "#666", marginBottom: "0.25rem", display: "flex", gap: "0.4rem" }}>
                  <span style={{ color: "#4ade80" }}>✓</span>{c}
                </div>
              ))}
            </div>
            <div>
              <div style={{ fontSize: "0.6rem", letterSpacing: "2px", color: "#555", marginBottom: "0.4rem" }}>SIGNAUX</div>
              {signals.map((s: string, i: number) => (
                <div key={i} style={{ fontSize: "0.72rem", color: "#666", marginBottom: "0.25rem", display: "flex", gap: "0.4rem" }}>
                  <span style={{ color }}>◆</span>{s}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── LSTM Diagram ──────────────────────────────────────────────────────────────
function LSTMDiagram() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const interval = setInterval(() => setStep(s => (s + 1) % 5), 1500);
    return () => clearInterval(interval);
  }, []);

  const layers = [
    { label: "Input\n30j × 11", color: "#5b8dee", w: 60 },
    { label: "LSTM\n64 units", color: "#8a6f9c", w: 80 },
    { label: "LSTM\n32 units", color: "#b8962f", w: 70 },
    { label: "Dense\n16 ReLU", color: "#1d9e75", w: 60 },
    { label: "Output\nσ [0,1]", color: "#f87171", w: 50 },
  ];

  return (
    <div style={{ padding: "1.5rem", background: "#0a0f1e", borderRadius: 8, border: "1px solid #1e2d4a" }}>
      <div style={{ fontSize: "0.65rem", letterSpacing: "3px", color: GOLD, marginBottom: "1rem" }}>ARCHITECTURE LSTM TENSORFLOW</div>
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", justifyContent: "center", flexWrap: "wrap" }}>
        {layers.map((layer, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <div style={{
              padding: "0.75rem 1rem", background: i === step ? `${layer.color}22` : "#111827",
              border: `2px solid ${i === step ? layer.color : "#1e2d4a"}`,
              borderRadius: 6, textAlign: "center", minWidth: layer.w,
              boxShadow: i === step ? `0 0 15px ${layer.color}33` : "none",
              transition: "all 0.4s ease",
            }}>
              <div style={{ fontSize: "0.7rem", color: i === step ? layer.color : "#666", whiteSpace: "pre-line", lineHeight: 1.4 }}>
                {layer.label}
              </div>
            </div>
            {i < layers.length - 1 && (
              <div style={{ color: i < step ? GOLD : "#333", fontSize: "1rem", transition: "color 0.4s" }}>→</div>
            )}
          </div>
        ))}
      </div>
      <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem", justifyContent: "center" }}>
        {["Séquence temporelle", "Dépendances longues", "Compression", "Non-linéarité", "Probabilité"].map((label, i) => (
          <div key={i} style={{
            padding: "0.2rem 0.6rem", borderRadius: 3,
            background: i === step ? `${layers[i].color}22` : "transparent",
            border: `1px solid ${i === step ? layers[i].color : "#1e2d4a"}`,
            fontSize: "0.6rem", color: i === step ? layers[i].color : "#333",
            transition: "all 0.4s",
          }}>{label}</div>
        ))}
      </div>
    </div>
  );
}

// ── Data Pipeline Diagram ─────────────────────────────────────────────────────
function DataPipeline() {
  const [active, setActive] = useState(0);
  const nodes = [
    { label: "Yahoo Finance", time: "20h UTC", color: "#5b8dee", icon: "📊", detail: "GitHub Actions télécharge 200+ tickers via yfinance. IPs Microsoft non bloquées par Yahoo." },
    { label: "Google Drive", time: "20h10", color: "#1d9e75", icon: "☁️", detail: "CSV compressé (.csv.gz) stocké dans ethical-finance-data/ohlcv_latest.csv.gz. Service Account authentifié." },
    { label: "SEC EDGAR", time: "22h UTC", color: "#b8962f", icon: "🏛️", detail: "Fondamentaux US GAAP officiels : revenue, EBIT, dette, FCF, ratios pour 483 titres SP500." },
    { label: "FMP API", time: "22h30", color: "#8a6f9c", icon: "🌍", detail: "Financial Modeling Prep : profils et market caps pour CAC40, UK, JP, AU, CH, SE, NO, DK, ZA." },
    { label: "PostgreSQL", time: "23h30", color: "#f87171", icon: "🗄️", detail: "Drive sync → upsert en DB. 2.75M barres OHLCV, 573 tickers. ON CONFLICT DO NOTHING." },
    { label: "Backup", time: "23h UTC", color: "#fb923c", icon: "💾", detail: "pg_dump compressé (.sql.gz). 7 jours de rétention dans /backups/. 51Mo par backup." },
  ];

  return (
    <div style={{ padding: "1.5rem", background: "#0a0f1e", borderRadius: 8, border: "1px solid #1e2d4a" }}>
      <div style={{ fontSize: "0.65rem", letterSpacing: "3px", color: GOLD, marginBottom: "1.5rem" }}>PIPELINE DE DONNÉES — 100% AUTOMATIQUE</div>
      <div style={{ display: "flex", gap: "1rem", justifyContent: "center", flexWrap: "wrap", marginBottom: "1.5rem" }}>
        {nodes.map((node, i) => (
          <PipelineNode key={i} {...node} active={active === i} onClick={() => setActive(i)} />
        ))}
      </div>
      <div style={{
        padding: "1rem", background: "#111827", borderRadius: 6,
        border: `1px solid ${nodes[active].color}44`,
        borderLeft: `3px solid ${nodes[active].color}`,
        fontSize: "0.78rem", color: "#888", lineHeight: 1.6,
        transition: "all 0.3s",
      }}>
        <span style={{ color: nodes[active].color, fontWeight: 600 }}>{nodes[active].label} · </span>
        {nodes[active].detail}
      </div>
    </div>
  );
}

// ── Risk Metrics Viz ──────────────────────────────────────────────────────────
function RiskViz() {
  const metrics = [
    { name: "Sharpe", formula: "(R_p - R_f) / σ_p × √252", good: "> 1.5", bad: "< 0.5", color: "#5b8dee" },
    { name: "Sortino", formula: "(R_p - R_f) / σ_down × √252", good: "> 2.0", bad: "< 1.0", color: "#1d9e75" },
    { name: "Calmar", formula: "CAGR / |Max Drawdown|", good: "> 1.0", bad: "< 0.3", color: "#b8962f" },
    { name: "VaR 95%", formula: "P(L > VaR) = 5%", good: "< 1.5%/j", bad: "> 3%/j", color: "#f87171" },
    { name: "CVaR 95%", formula: "E[L | L > VaR]", good: "< 2%/j", bad: "> 5%/j", color: "#fb923c" },
    { name: "Omega", formula: "∫gains dP / ∫pertes dP", good: "> 1.5", bad: "< 1.0", color: "#8a6f9c" },
  ];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem" }}>
      {metrics.map((m, i) => (
        <div key={i} style={{
          padding: "1rem", background: "#111827",
          border: `1px solid ${m.color}33`, borderTop: `2px solid ${m.color}`,
          borderRadius: 6,
        }}>
          <div style={{ fontSize: "0.75rem", fontWeight: 700, color: m.color, marginBottom: "0.4rem" }}>{m.name}</div>
          <div style={{
            fontFamily: '"JetBrains Mono", monospace', fontSize: "0.65rem",
            color: "#888", marginBottom: "0.5rem", padding: "0.3rem",
            background: "#0d1528", borderRadius: 3,
          }}>{m.formula}</div>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <div style={{ fontSize: "0.62rem", color: "#4ade80" }}>✓ {m.good}</div>
            <div style={{ fontSize: "0.62rem", color: "#f87171" }}>✗ {m.bad}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function TechnicalPanel() {
  const [section, setSection] = useState("pipeline");
  const [mounted, setMounted] = useState(false);
  const [stats, setStats] = useState<{ohlcv_rows: number; tickers: number; fundamentals: number}>({ ohlcv_rows: 2753640, tickers: 573, fundamentals: 615 });
  const API = import.meta.env.VITE_API_URL ?? "";

  useEffect(() => {
    setMounted(true);
    fetch(`${API}/api/stats`)
      .then(r => r.json())
      .then(d => setStats({
        ohlcv_rows: parseInt(d.ohlcv?.value?.replace(/[^0-9]/g,'') || '0') || 3570000,
        tickers: parseInt(d.tickers?.value || '0') || 626,
        fundamentals: parseInt(d.fundamentals?.value || '0') || 626,
      }))
      .catch(() => {});
  }, []);

  const sections = [
    { id: "pipeline", label: "Pipeline données", icon: "◉" },
    { id: "strategies", label: "Stratégies", icon: "◆" },
    { id: "ml", label: "IA / ML", icon: "◈" },
    { id: "risk", label: "Métriques risque", icon: "◎" },
    { id: "costs", label: "Modèle de coûts", icon: "▣" },
    { id: "infra", label: "Infrastructure", icon: "◇" },
  ];

  const strategies = [
    {
      name: "EPR5 — Magic Formula + IA Hybride",
      type: "VALUE + ML",
      color: GOLD,
      description: "Stratégie phare combinant la Magic Formula de Greenblatt (Earning Yield + ROIC) avec un filtre de régime SPX/VIX et deux modèles ML en walk-forward strict : RandomForest (60%) + LSTM TensorFlow (40%). Sizing dynamique par Monte Carlo.",
      conditions: [
        "SPX > MM200 (régime haussier)",
        "VIX < MM10 (volatilité maîtrisée)",
        "Prix > MM200 (tendance titre)",
        "ML score combiné > 0.50",
        "EY > 0 et ROIC > 0",
      ],
      signals: [
        "Rank(EY) + Rank(ROIC) → top quintile",
        "RF score : rendement 20j > +5%",
        "LSTM score : rendement 5j > +2%",
        "Stop ATR-14 × 2.0",
        "Profit target +20%",
      ],
    },
    {
      name: "Momentum 12-1 mois",
      type: "MOMENTUM",
      color: "#5b8dee",
      description: "Sélectionne le top 30% de l'univers par rendement 12-1 mois (skip du dernier mois pour éviter le mean-reversion court terme). Stops ATR + trailing stop 12% depuis le pic.",
      conditions: [
        "Historique ≥ 252 jours",
        "Skip dernier mois (mean-reversion)",
        "Trailing stop 12% depuis le pic",
      ],
      signals: [
        "Rendement t-252 à t-21",
        "Top 30% par momentum",
        "Sizing ATR : risk 1% / (2×ATR/prix)",
        "Profit target +25%",
      ],
    },
    {
      name: "Mean Reversion Z-score",
      type: "MEAN REV",
      color: "#1d9e75",
      description: "Achète les actifs statistiquement sous-évalués (Z-score < -1.5σ sur 20 jours). Sort rapidement sur objectif +15% ou stop -8%.",
      conditions: [
        "Z-score < -1.5σ (sur-vendu)",
        "Fenêtre mobile 20 jours",
        "Stop fixe -8%",
      ],
      signals: [
        "Z = (prix - MM20) / σ20",
        "Entrée si Z < -threshold",
        "Sizing ATR inversé (vol élevée → petite position)",
        "Profit target +15%",
      ],
    },
    {
      name: "SMA Crossover (Golden Cross)",
      type: "TREND",
      color: "#8a6f9c",
      description: "Long quand la MM rapide (50j) croise au-dessus de la MM lente (200j). Trailing stop 10% + stop ATR 2.5× pour gérer les faux signaux.",
      conditions: [
        "MM50 > MM200 (Golden Cross)",
        "Trailing stop 10% depuis le pic",
        "Stop ATR-14 × 2.5",
      ],
      signals: [
        "Croisement MM50/MM200",
        "Fermeture si MM50 < MM200",
        "Sizing ATR : risk 1% NAV",
      ],
    },
    {
      name: "Dual Momentum (Antonacci)",
      type: "DUAL MOM",
      color: "#fb923c",
      description: "Momentum absolu + relatif. Investit dans le meilleur actif uniquement si son momentum absolu est positif, sinon reste en cash. Concentration maximale sur le meilleur titre.",
      conditions: [
        "Momentum absolu > 0 (vs cash)",
        "Meilleur momentum relatif",
        "Trailing stop 12%",
      ],
      signals: [
        "Rendement t-252 à t-0",
        "Si max(mom) > 0 : long best",
        "Si max(mom) ≤ 0 : cash",
        "Sizing ATR concentré (50%+ NAV possible)",
      ],
    },
    {
      name: "Risk Parity (Inverse Vol)",
      type: "RISK",
      color: "#f87171",
      description: "Pondération inversement proportionnelle à la volatilité réalisée 20j. Chaque actif contribue autant au risque du portefeuille. Rééquilibrage mensuel.",
      conditions: [
        "Historique ≥ 22 jours",
        "Volatilité > 0",
        "Rééquilibrage mensuel",
      ],
      signals: [
        "w_i = (1/σ_i) / Σ(1/σ_j)",
        "Cap à max_position_pct",
        "Normalisation Σw = 1",
      ],
    },
  ];

  return (
    <div style={{
      background: "#0a0f1e", minHeight: "calc(100vh - 56px)",
      fontFamily: '"Inter", system-ui, sans-serif',
    }}>
      {/* Hero */}
      <div style={{
        padding: "4rem 3rem 3rem",
        background: "linear-gradient(180deg, #0d1528 0%, #0a0f1e 100%)",
        borderBottom: "1px solid #1a2035",
        position: "relative", overflow: "hidden",
      }}>
        <div style={{
          position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
          opacity: 0.04,
          backgroundImage: "radial-gradient(circle at 20% 50%, #b8962f 0%, transparent 50%), radial-gradient(circle at 80% 20%, #1e3a5f 0%, transparent 50%)",
        }} />
        <div style={{ maxWidth: 1200, margin: "0 auto", position: "relative" }}>
          <div style={{ fontSize: "0.6rem", letterSpacing: "5px", color: GOLD, marginBottom: "1rem" }}>
            DOCUMENTATION TECHNIQUE
          </div>
          <h1 style={{
            margin: "0 0 1rem", fontSize: "2.8rem",
            fontFamily: '"Playfair Display", serif',
            color: "#e8e8e8", fontWeight: 400, lineHeight: 1.1,
          }}>
            Architecture &<br />
            <span style={{ color: GOLD }}>Méthodologie quantitative</span>
          </h1>
          <p style={{ color: "#666", fontSize: "0.9rem", maxWidth: 600, lineHeight: 1.7, margin: 0 }}>
            Pipeline de données 100% automatique · 11 stratégies event-driven · 
            ML hybride RF+LSTM · Modèle de coûts réaliste · Infrastructure NAS auto-hébergée
          </p>

          {/* Stats animées */}
          <div style={{ display: "flex", gap: "1.5rem", marginTop: "2rem", flexWrap: "wrap" }}>
            {[
              { value: stats.ohlcv_rows || 2753640, suffix: "", label: "Barres OHLCV", decimals: 0 },
              { value: stats.tickers || 573, suffix: "", label: "Tickers", decimals: 0 },
              { value: 20, suffix: " ans", label: "Historique", decimals: 0 },
              { value: 25, suffix: "+", label: "Métriques risque", decimals: 0 },
              { value: 100, suffix: "%", label: "Automatisé", decimals: 0 },
            ].map((s, i) => (
              <div key={i} style={{
                padding: "0.75rem 1.25rem",
                background: "rgba(184,150,47,0.05)",
                border: "1px solid rgba(184,150,47,0.15)",
                borderRadius: 6,
              }}>
                <div style={{
                  fontSize: "1.6rem", fontWeight: 700, color: GOLD,
                  fontFamily: '"JetBrains Mono", monospace',
                }}>
                  {mounted ? <AnimatedNumber value={s.value} suffix={s.suffix} decimals={s.decimals} /> : `${s.value}${s.suffix}`}
                </div>
                <div style={{ fontSize: "0.65rem", color: "#555", letterSpacing: "1px", marginTop: 2 }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Navigation sections */}
      <div style={{ padding: "0 3rem", maxWidth: 1200, margin: "0 auto" }}>
        <div style={{ display: "flex", gap: 0, borderBottom: "1px solid #1a2035", marginBottom: "2rem" }}>
          {sections.map(s => (
            <button key={s.id} onClick={() => setSection(s.id)} style={{
              padding: "1rem 1.25rem", background: "none",
              color: section === s.id ? GOLD : "#555",
              border: "none",
              borderBottom: `2px solid ${section === s.id ? GOLD : "transparent"}`,
              cursor: "pointer", fontSize: "0.78rem", fontWeight: section === s.id ? 600 : 400,
              display: "flex", alignItems: "center", gap: "0.4rem",
              transition: "all 0.2s",
            }}>
              <span style={{ fontSize: "0.65rem" }}>{s.icon}</span>
              {s.label}
            </button>
          ))}
        </div>

        {/* Section : Pipeline */}
        {section === "pipeline" && (
          <div>
            <DataPipeline />
            <div style={{ marginTop: "2rem", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              {[
                { time: "20h00 UTC", label: "GitHub Actions", desc: "Télécharge OHLCV 200+ tickers via yfinance (IPs Microsoft). Upload CSV.gz dans Google Drive.", color: "#5b8dee" },
                { time: "21h00 UTC", label: "Scheduler NAS", desc: "Fallback yfinance direct si GitHub Actions échoue. Met à jour les données récentes.", color: "#1d9e75" },
                { time: "22h00 UTC", label: "SEC EDGAR", desc: "Fondamentaux officiels US GAAP pour 483 titres SP500. Revenue, EBIT, dette, FCF, ratios.", color: GOLD },
                { time: "22h30 UTC", label: "FMP API", desc: "Financial Modeling Prep : profils non-US. CAC40, UK, AU, JP, CH, SE, NO, DK, ZA.", color: "#8a6f9c" },
                { time: "23h00 UTC", label: "Backup PostgreSQL", desc: "pg_dump compressé. 7 jours de rétention. Restauration en < 2 minutes.", color: "#fb923c" },
                { time: "23h30 UTC", label: "Drive Sync", desc: "NAS télécharge ohlcv_latest.csv.gz depuis Drive. Upsert en DB avec ON CONFLICT DO NOTHING.", color: "#f87171" },
              ].map((item, i) => (
                <div key={i} style={{
                  padding: "1rem", background: "#111827",
                  border: `1px solid ${item.color}33`, borderLeft: `3px solid ${item.color}`,
                  borderRadius: 6, display: "flex", gap: "1rem", alignItems: "flex-start",
                }}>
                  <div style={{
                    fontFamily: '"JetBrains Mono", monospace', fontSize: "0.7rem",
                    color: item.color, whiteSpace: "nowrap", paddingTop: 2,
                  }}>{item.time}</div>
                  <div>
                    <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "#e8e8e8", marginBottom: "0.25rem" }}>{item.label}</div>
                    <div style={{ fontSize: "0.72rem", color: "#666", lineHeight: 1.5 }}>{item.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Section : Stratégies */}
        {section === "strategies" && (
          <div>
            <div style={{ fontSize: "0.65rem", letterSpacing: "3px", color: GOLD, marginBottom: "1.5rem" }}>
              11 STRATÉGIES EVENT-DRIVEN — BACKTEST STRICT SANS LOOK-AHEAD
            </div>
            <div style={{
              padding: "1rem", background: "rgba(184,150,47,0.05)",
              border: "1px solid rgba(184,150,47,0.15)", borderRadius: 6,
              marginBottom: "1.5rem", fontSize: "0.78rem", color: "#888", lineHeight: 1.6,
            }}>
              <strong style={{ color: GOLD }}>Principe event-driven strict :</strong> le moteur appelle{" "}
              <code style={{ background: "#0d1528", padding: "0 0.3rem", borderRadius: 3, color: "#5b8dee" }}>on_bar(dt, past_prices[:dt], params, state)</code>{" "}
              une fois par jour de rebalancement. La stratégie ne voit que les données passées jusqu'à{" "}
              <code style={{ background: "#0d1528", padding: "0 0.3rem", borderRadius: 3, color: "#5b8dee" }}>dt</code> inclus.
              Aucune fuite du futur n'est possible par construction.
            </div>
            {strategies.map((s, i) => <StrategyCard key={i} {...s} />)}
          </div>
        )}

        {/* Section : ML */}
        {section === "ml" && (
          <div>
            <LSTMDiagram />
            <div style={{ marginTop: "2rem" }}>
              <Formula
                title="RANDOMFOREST — SCORING FONDAMENTAL/TECHNIQUE"
                formula="score_RF = P(rendement_20j > +5% | features_11)"
                explanation="11 features statiques : ret_1/5/20/60j, vol_20/60j, RSI-14, MM20/50/200 (0/1), momentum 12m. 50 arbres, profondeur 4, class_weight=balanced. Walk-forward : réentraîné tous les 60 jours sur données passées uniquement."
                color="#5b8dee"
              />
              <Formula
                title="LSTM — SCORING TEMPOREL"
                formula="score_LSTM = σ(LSTM(séquence_30j × 11_features))"
                explanation="Séquence temporelle de 30 jours × 11 features normalisées. Capte les dépendances temporelles ignorées par le RF : momentum, régimes de volatilité, retournements. Horizon de prédiction : 5 jours. Seuil positif : rendement > +2%."
                color="#8a6f9c"
              />
              <Formula
                title="SCORE COMBINÉ EPR5"
                formula="score_final = 0.6 × RF_score + 0.4 × LSTM_score"
                explanation="Pondération empirique favorisant le RF (plus stable hors-échantillon) avec une contribution LSTM pour le timing. Le seuil d'entrée ml_min_score (défaut 0.50) est optimisable entre 0.45 et 0.70."
                color={GOLD}
              />
              <Formula
                title="SIZING MONTE CARLO"
                formula="mult = clip(1.0 + Sharpe_proxy × 5, 0.5, 1.5)"
                explanation="Le multiplicateur est calculé sur le Sharpe proxy glissant des 60 derniers rendements. Une stratégie récemment performante augmente légèrement ses positions (max 1.5×), une stratégie en difficulté les réduit (min 0.5×). Poids de base : 10% NAV par titre."
                color="#1d9e75"
              />
            </div>
          </div>
        )}

        {/* Section : Métriques risque */}
        {section === "risk" && (
          <div>
            <div style={{ fontSize: "0.65rem", letterSpacing: "3px", color: GOLD, marginBottom: "1.5rem" }}>
              25+ MÉTRIQUES — CALCUL SANS HYPOTHÈSE GAUSSIENNE
            </div>
            <RiskViz />
            <div style={{ marginTop: "1.5rem" }}>
              <Formula
                title="VAR HISTORIQUE 95%"
                formula="VaR_95 = -Percentile(rendements, 5%)"
                explanation="Simulation historique pure : utilise les rendements réels observés sans hypothèse de distribution. Plus robuste que la VaR paramétrique gaussienne en présence de queues épaisses (kurtosis > 3). Calcul quotidien sur l'historique complet disponible."
                color="#f87171"
              />
              <Formula
                title="CVAR (EXPECTED SHORTFALL)"
                formula="CVaR_95 = E[perte | perte > VaR_95]"
                explanation="Mesure la perte moyenne dans les 5% de scénarios les plus défavorables. Plus conservative que la VaR et recommandée par les accords de Bâle III. Capte le risque de queue que la VaR ignore."
                color="#fb923c"
              />
              <Formula
                title="JOBSON-KORKIE TEST"
                formula="z = (SR_p - SR_b) / σ(SR_p - SR_b)"
                explanation="Test de significativité de la différence de Sharpe entre la stratégie et le benchmark. H0 : SR_p = SR_b. Rejeté à 5% si |z| > 1.96. Corrige le biais introduit par la corrélation entre les deux séries de rendements."
                color="#5b8dee"
              />
            </div>
          </div>
        )}

        {/* Section : Modèle de coûts */}
        {section === "costs" && (
          <div>
            <div style={{ fontSize: "0.65rem", letterSpacing: "3px", color: GOLD, marginBottom: "1.5rem" }}>
              MODÈLE DE COÛTS RÉALISTE — 6 COMPOSANTES
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem", marginBottom: "1.5rem" }}>
              {[
                { name: "Commission broker", formula: "fixe + notional × taux", note: "Grille réelle : Fortuneo 6.95€, Degiro 0.50€, IBKR 0.05%", color: GOLD },
                { name: "Slippage bid-ask", formula: "notional × BPS / 10 000", note: "Large cap 2 bps · Mid cap 8 bps · Small cap 20 bps · ETF 1 bp", color: "#5b8dee" },
                { name: "Impact marché", formula: "notional × bps × √(notional/ADV)", note: "Modèle racine carrée. Plus l'ordre est grand vs volume journalier, plus l'impact est élevé.", color: "#8a6f9c" },
                { name: "Spread FX", formula: "notional × 3 bps (si non-EUR)", note: "Spread retail EUR/USD ~3 bps. Nul pour les actifs en EUR.", color: "#1d9e75" },
                { name: "TTF (Tobin Tax)", formula: "notional × 0.30% (si FR, cap > 1Md€)", note: "Taxe sur les Transactions Financières française. Uniquement à l'achat.", color: "#f87171" },
                { name: "Stamp Duty", formula: "notional × taux selon pays", note: "UK 0.50% · Belgique 0.35% · Italie 0.20% (si cap > 500M€)", color: "#fb923c" },
              ].map((item, i) => (
                <div key={i} style={{
                  padding: "1rem", background: "#111827",
                  border: `1px solid ${item.color}33`, borderTop: `2px solid ${item.color}`,
                  borderRadius: 6,
                }}>
                  <div style={{ fontSize: "0.75rem", fontWeight: 600, color: item.color, marginBottom: "0.4rem" }}>{item.name}</div>
                  <div style={{
                    fontFamily: '"JetBrains Mono", monospace', fontSize: "0.65rem",
                    color: "#888", marginBottom: "0.5rem", padding: "0.3rem",
                    background: "#0d1528", borderRadius: 3,
                  }}>{item.formula}</div>
                  <div style={{ fontSize: "0.68rem", color: "#555", lineHeight: 1.5 }}>{item.note}</div>
                </div>
              ))}
            </div>
            <Formula
              title="WITHHOLDING TAX SUR DIVIDENDES"
              formula="retenue_nette = dividende × taux_pays × 0.5"
              explanation="Retenue à la source selon la convention fiscale FR avec le pays d'origine. US→FR 15%, DE→FR 26.5%, CH→FR 35%, UK→FR 0%. Le facteur 0.5 approxime le crédit d'impôt partiellement récupérable sur la déclaration fiscale. Nul sur PEA."
              color="#8a6f9c"
            />
          </div>
        )}

        {/* Section : Infrastructure */}
        {section === "infra" && (
          <div>
            <div style={{ fontSize: "0.65rem", letterSpacing: "3px", color: GOLD, marginBottom: "1.5rem" }}>
              INFRASTRUCTURE AUTO-HÉBERGÉE — ZÉRO PORT OUVERT
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1.5rem" }}>
              {[
                { layer: "Frontend", tech: "React 18 + TypeScript + Vite", host: "Build sur NAS, servi par Nginx", color: "#5b8dee" },
                { layer: "Backend API", tech: "FastAPI + Python 3.11 + Uvicorn", host: "Docker sur NAS Synology DS925+", color: "#1d9e75" },
                { layer: "Base de données", tech: "PostgreSQL 16 + SQLAlchemy", host: "Docker volume persistant NAS", color: GOLD },
                { layer: "Reverse proxy", tech: "Cloudflare Tunnel + Nginx", host: "HTTPS automatique, zéro port ouvert", color: "#8a6f9c" },
                { layer: "CI/CD", tech: "GitHub Actions (ubuntu-latest)", host: "Push → auto-build. Pas de Vercel.", color: "#f87171" },
                { layer: "Monitoring", tech: "pgAdmin 4 + Docker logs", host: "Port 5050 local uniquement", color: "#fb923c" },
              ].map((item, i) => (
                <div key={i} style={{
                  padding: "1rem", background: "#111827",
                  border: `1px solid ${item.color}33`, borderLeft: `3px solid ${item.color}`,
                  borderRadius: 6,
                }}>
                  <div style={{ fontSize: "0.6rem", letterSpacing: "2px", color: item.color, marginBottom: "0.4rem" }}>{item.layer}</div>
                  <div style={{ fontSize: "0.82rem", fontWeight: 600, color: "#e8e8e8", marginBottom: "0.3rem" }}>{item.tech}</div>
                  <div style={{ fontSize: "0.72rem", color: "#555" }}>{item.host}</div>
                </div>
              ))}
            </div>
            <div style={{ padding: "1.25rem", background: "#111827", border: "1px solid #1e2d4a", borderRadius: 8 }}>
              <div style={{ fontSize: "0.65rem", letterSpacing: "2px", color: GOLD, marginBottom: "1rem" }}>STACK COMPLET</div>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                {["Python 3.11", "FastAPI", "PostgreSQL 16", "React 18", "TypeScript", "Vite",
                  "Docker", "Nginx", "Cloudflare Tunnel", "GitHub Actions", "TensorFlow CPU",
                  "scikit-learn", "LightGBM", "matplotlib", "ReportLab", "vaderSentiment",
                  "yfinance", "SEC EDGAR API", "FMP API", "Google Drive API", "APScheduler",
                  "SQLAlchemy", "Pandas", "NumPy", "pgAdmin 4"].map(t => (
                  <span key={t} style={{
                    padding: "0.2rem 0.6rem", background: "rgba(184,150,47,0.06)",
                    border: "1px solid rgba(184,150,47,0.2)", borderRadius: 3,
                    fontSize: "0.68rem", color: "#b8962f",
                    fontFamily: '"JetBrains Mono", monospace',
                  }}>{t}</span>
                ))}
              </div>
            </div>
          </div>
        )}

        <div style={{ height: "3rem" }} />
      </div>
    </div>
  );
}
