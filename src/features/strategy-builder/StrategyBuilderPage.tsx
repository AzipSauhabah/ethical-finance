import { useState, useRef, useEffect } from "react";

const GOLD = "#b8962f";
const NAVY = "#0d1628";
const NAVY2 = "#111e35";
const BORDER = "#1e2d4a";

const TEMPLATE_CODE = `from __future__ import annotations
import numpy as np
import pandas as pd
from backend.strategies.base import Strategy
from backend.strategies.registry import strategy_registry


@strategy_registry.register
class MaStrategieCustom(Strategy):
    name        = "ma_strategie"        # ID unique dans la GUI
    description = "Ma première stratégie personnalisée"
    benchmark   = "SPY"

    param_space = {
        "lookback": [20, 60, 120],      # testé en backtest
        "top_n":    [5, 10, 20],
    }

    def on_bar(self, dt, past_prices, params, state):
        """
        Appelée une fois par jour de rebalancement.
        Retourne {ticker: poids} — somme = 1.0
        """
        lookback = params.get("lookback", 60)
        top_n    = params.get("top_n", 10)

        if len(past_prices) < lookback:
            return {}  # pas assez d'historique

        # Calcul momentum sur lookback jours
        rets = past_prices.iloc[-lookback:].pct_change().dropna()
        total_ret = (1 + rets).prod() - 1

        # Top N tickers par rendement
        top = total_ret.nlargest(top_n).index.tolist()
        w = 1.0 / len(top)
        return {t: w for t in top}
`;

const STEPS = [
  {
    id: 1,
    icon: "①",
    title: "Décore ta classe",
    desc: "@strategy_registry.register — une seule ligne suffit pour que la stratégie apparaisse dans toute l'interface.",
    line: 7,
    highlight: "@strategy_registry.register",
  },
  {
    id: 2,
    icon: "②",
    title: "Définis les métadonnées",
    desc: "name, description, benchmark — ces champs alimentent automatiquement le dropdown Backtest et la page Signaux.",
    line: 9,
    highlight: "name        =",
  },
  {
    id: 3,
    icon: "③",
    title: "Déclare l'espace de paramètres",
    desc: "param_space définit les valeurs testées en walk-forward. Le moteur optimise automatiquement.",
    line: 13,
    highlight: "param_space",
  },
  {
    id: 4,
    icon: "④",
    title: "Implémente on_bar()",
    desc: "Seule méthode obligatoire. Reçoit les prix passés — aucune fuite du futur possible par construction.",
    line: 18,
    highlight: "def on_bar",
  },
  {
    id: 5,
    icon: "⑤",
    title: "Retourne les poids",
    desc: "Dict {ticker: poids_cible} — somme = 1.0. Le moteur gère les transactions, coûts et stops automatiquement.",
    line: 32,
    highlight: "return {t: w",
  },
];

const EXAMPLES = [
  {
    id: "momentum",
    label: "Momentum",
    color: "#16a34a",
    desc: "Achète les N meilleurs rendements passés",
    code: `    # Momentum pur — top N sur lookback jours
    lookback = params.get("lookback", 60)
    top_n = params.get("top_n", 10)
    if len(past_prices) < lookback:
        return {}
    rets = past_prices.iloc[-lookback:].pct_change().dropna()
    total = (1 + rets).prod() - 1
    top = total.nlargest(top_n).index.tolist()
    return {t: 1/len(top) for t in top}`,
  },
  {
    id: "mean_rev",
    label: "Mean Reversion",
    color: "#3b82f6",
    desc: "Achète les plus sur-vendus (RSI bas)",
    code: `    # Mean Reversion — achète les oversold
    lookback = params.get("lookback", 14)
    top_n = params.get("top_n", 10)
    if len(past_prices) < lookback + 1:
        return {}
    delta = past_prices.diff()
    gain = delta.clip(lower=0).rolling(lookback).mean()
    loss = (-delta.clip(upper=0)).rolling(lookback).mean()
    rs = gain / loss.replace(0, 1e-9)
    rsi = 100 - (100 / (1 + rs))
    oversold = rsi.iloc[-1].nsmallest(top_n).index.tolist()
    return {t: 1/len(oversold) for t in oversold}`,
  },
  {
    id: "equal",
    label: "Equal Weight",
    color: GOLD,
    desc: "Poids égaux — simple et robuste",
    code: `    # Equal weight — allocation uniforme
    tickers = past_prices.columns.tolist()
    if not tickers:
        return {}
    w = 1.0 / len(tickers)
    return {t: w for t in tickers}`,
  },
];

function CodeLine({ line, index, highlighted }: { line: string; index: number; highlighted: boolean }) {
  return (
    <div style={{
      display: "flex",
      background: highlighted ? "rgba(184,150,47,0.1)" : "transparent",
      borderLeft: highlighted ? `2px solid ${GOLD}` : "2px solid transparent",
      transition: "all 0.3s",
    }}>
      <span style={{
        width: 36, textAlign: "right", paddingRight: 12, paddingLeft: 8,
        color: "#333", fontSize: 11, fontFamily: '"JetBrains Mono", monospace',
        userSelect: "none", flexShrink: 0,
      }}>{index + 1}</span>
      <pre style={{
        margin: 0, padding: "0 12px 0 0", fontSize: 12,
        fontFamily: '"JetBrains Mono", monospace',
        color: highlighted ? "#e8d5a3" : "#c9d1d9",
        whiteSpace: "pre", overflow: "hidden",
      }}>{line}</pre>
    </div>
  );
}

export default function StrategyBuilderPanel() {
  const [activeStep, setActiveStep] = useState<number | null>(null);
  const [activeExample, setActiveExample] = useState<string | null>(null);
  const [code, setCode] = useState(TEMPLATE_CODE);
  const [copied, setCopied] = useState(false);
  const [tab, setTab] = useState<"guide" | "deploy" | "rules">("guide");
  const codeRef = useRef<HTMLDivElement>(null);

  const lines = code.split("\n");
  const activeStepData = STEPS.find(s => s.id === activeStep);
  const highlightedLines = activeStepData
    ? lines.map((l, i) => l.includes(activeStepData.highlight) || i + 1 === activeStepData.line)
    : lines.map(() => false);

  function handleExample(ex: typeof EXAMPLES[0]) {
    setActiveExample(ex.id);
    const newCode = TEMPLATE_CODE.replace(
      /    # Calcul momentum[\s\S]*?return \{t: w for t in top\}/,
      ex.code
    );
    setCode(newCode);
  }

  function handleCopy() {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div style={{ fontFamily: '"Syne", sans-serif', padding: "2rem 2.5rem", maxWidth: 1200, margin: "0 auto", color: "#e2e8f0" }}>
      {/* Header */}
      <div style={{ marginBottom: "2rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "0.5rem" }}>
          <span style={{ fontSize: "0.6rem", letterSpacing: "4px", color: GOLD, fontWeight: 700 }}>STRATEGY BUILDER</span>
          <span style={{ height: 1, flex: 1, background: `linear-gradient(to right, ${GOLD}, transparent)` }} />
        </div>
        <h1 style={{ fontSize: "1.8rem", fontWeight: 800, margin: 0, color: "#fff" }}>
          Créer une stratégie
        </h1>
        <p style={{ color: "#64748b", fontSize: "0.85rem", marginTop: "0.4rem" }}>
          Plug-and-play — une classe Python + un décorateur = présent dans toute l'interface
        </p>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 0, borderBottom: `1px solid ${BORDER}`, marginBottom: "1.5rem" }}>
        {[
          { id: "guide", label: "① Guide interactif" },
          { id: "deploy", label: "② Déploiement" },
          { id: "rules", label: "③ Règles du moteur" },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id as typeof tab)} style={{
            padding: "0.6rem 1.2rem", fontSize: "0.75rem", fontWeight: 600,
            color: tab === t.id ? GOLD : "#475569",
            background: "none", border: "none", cursor: "pointer",
            borderBottom: tab === t.id ? `2px solid ${GOLD}` : "2px solid transparent",
            letterSpacing: "1px", transition: "all 0.15s",
          }}>{t.label}</button>
        ))}
      </div>

      {tab === "guide" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: "1.5rem" }}>
          {/* Code editor */}
          <div style={{ background: "#0d1117", border: `1px solid ${BORDER}`, borderRadius: 8, overflow: "hidden" }}>
            {/* Toolbar */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0.6rem 1rem", background: "#161b22", borderBottom: `1px solid ${BORDER}` }}>
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#ff5f57" }} />
                <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#ffbd2e" }} />
                <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#28c840" }} />
                <span style={{ marginLeft: "0.5rem", fontSize: "0.7rem", color: "#555", fontFamily: '"JetBrains Mono", monospace' }}>
                  backend/strategies/builtin/ma_strategie.py
                </span>
              </div>
              <button onClick={handleCopy} style={{
                background: copied ? "rgba(22,163,74,0.2)" : "rgba(184,150,47,0.1)",
                border: `1px solid ${copied ? "#16a34a" : GOLD}`,
                color: copied ? "#4ade80" : GOLD,
                borderRadius: 4, padding: "0.2rem 0.7rem", fontSize: "0.65rem",
                fontWeight: 700, cursor: "pointer", letterSpacing: "1px",
              }}>{copied ? "✓ COPIÉ" : "COPIER"}</button>
            </div>
            {/* Code */}
            <div ref={codeRef} style={{ overflowX: "auto", padding: "0.5rem 0" }}>
              {lines.map((line, i) => (
                <CodeLine key={i} line={line} index={i} highlighted={highlightedLines[i]} />
              ))}
            </div>
          </div>

          {/* Right panel */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {/* Steps */}
            <div style={{ background: NAVY2, border: `1px solid ${BORDER}`, borderRadius: 8, overflow: "hidden" }}>
              <div style={{ padding: "0.75rem 1rem", borderBottom: `1px solid ${BORDER}` }}>
                <span style={{ fontSize: "0.6rem", letterSpacing: "3px", color: "#475569", fontWeight: 700 }}>ANATOMIE</span>
              </div>
              {STEPS.map(step => (
                <div key={step.id}
                  onClick={() => setActiveStep(activeStep === step.id ? null : step.id)}
                  style={{
                    padding: "0.75rem 1rem", cursor: "pointer",
                    borderBottom: `1px solid ${BORDER}`,
                    background: activeStep === step.id ? "rgba(184,150,47,0.08)" : "transparent",
                    transition: "background 0.15s",
                  }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: activeStep === step.id ? "0.4rem" : 0 }}>
                    <span style={{ fontSize: "0.9rem", color: activeStep === step.id ? GOLD : "#475569" }}>{step.icon}</span>
                    <span style={{ fontSize: "0.75rem", fontWeight: 600, color: activeStep === step.id ? GOLD : "#94a3b8" }}>{step.title}</span>
                  </div>
                  {activeStep === step.id && (
                    <p style={{ margin: 0, fontSize: "0.72rem", color: "#64748b", lineHeight: 1.5 }}>{step.desc}</p>
                  )}
                </div>
              ))}
            </div>

            {/* Examples */}
            <div style={{ background: NAVY2, border: `1px solid ${BORDER}`, borderRadius: 8, overflow: "hidden" }}>
              <div style={{ padding: "0.75rem 1rem", borderBottom: `1px solid ${BORDER}` }}>
                <span style={{ fontSize: "0.6rem", letterSpacing: "3px", color: "#475569", fontWeight: 700 }}>EXEMPLES RAPIDES</span>
              </div>
              {EXAMPLES.map(ex => (
                <div key={ex.id}
                  onClick={() => handleExample(ex)}
                  style={{
                    padding: "0.6rem 1rem", cursor: "pointer",
                    borderBottom: `1px solid ${BORDER}`,
                    background: activeExample === ex.id ? `rgba(${ex.color === GOLD ? "184,150,47" : ex.color === "#16a34a" ? "22,163,74" : "59,130,246"},0.08)` : "transparent",
                    transition: "background 0.15s",
                    display: "flex", alignItems: "center", gap: "0.75rem",
                  }}>
                  <span style={{ width: 8, height: 8, borderRadius: "50%", background: ex.color, flexShrink: 0 }} />
                  <div>
                    <div style={{ fontSize: "0.75rem", fontWeight: 600, color: activeExample === ex.id ? ex.color : "#94a3b8" }}>{ex.label}</div>
                    <div style={{ fontSize: "0.65rem", color: "#475569" }}>{ex.desc}</div>
                  </div>
                </div>
              ))}
              <div onClick={() => { setCode(TEMPLATE_CODE); setActiveExample(null); }}
                style={{ padding: "0.5rem 1rem", cursor: "pointer", fontSize: "0.65rem", color: "#475569", textAlign: "center" }}>
                ↺ Réinitialiser le template
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === "deploy" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
          {[
            {
              step: "1", title: "Crée le fichier",
              cmd: "cp backend/strategies/builtin/_template.py\n   backend/strategies/builtin/ma_strategie.py",
              desc: "Copie le template et renomme la classe + le name.",
            },
            {
              step: "2", title: "Push vers git",
              cmd: "git add backend/strategies/builtin/ma_strategie.py\ngit commit -m 'feat: nouvelle stratégie'\ngit push",
              desc: "Le code est versionné — rollback possible à tout moment.",
            },
            {
              step: "3", title: "Déploie sur NAS",
              cmd: "git pull  # sur le NAS\ndocker cp backend/strategies/builtin/ma_strategie.py \\\n  ethical-finance-api:/app/backend/strategies/builtin/\ndocker restart ethical-finance-api",
              desc: "Pas de rebuild Docker nécessaire — juste un restart.",
            },
            {
              step: "4", title: "Vérifie dans la GUI",
              cmd: 'curl http://localhost:8000/api/strategies \\\n  | python3 -m json.tool \\\n  | grep -i "ma_strategie"',
              desc: "La stratégie apparaît automatiquement dans Backtest, Signaux et Screener.",
            },
          ].map(item => (
            <div key={item.step} style={{ background: NAVY2, border: `1px solid ${BORDER}`, borderRadius: 8, overflow: "hidden" }}>
              <div style={{ padding: "0.75rem 1rem", background: "#0d1528", borderBottom: `1px solid ${BORDER}`, display: "flex", alignItems: "center", gap: "0.75rem" }}>
                <span style={{ width: 24, height: 24, borderRadius: "50%", background: `rgba(184,150,47,0.15)`, border: `1px solid ${GOLD}`, display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: "0.7rem", fontWeight: 800, color: GOLD }}>{item.step}</span>
                <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "#e2e8f0" }}>{item.title}</span>
              </div>
              <div style={{ padding: "0.75rem 1rem" }}>
                <pre style={{ background: "#0d1117", border: `1px solid ${BORDER}`, borderRadius: 4, padding: "0.75rem", fontSize: 11, fontFamily: '"JetBrains Mono", monospace', color: "#7ee787", margin: "0 0 0.75rem", overflowX: "auto", whiteSpace: "pre" }}>{item.cmd}</pre>
                <p style={{ margin: 0, fontSize: "0.72rem", color: "#64748b", lineHeight: 1.5 }}>{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "rules" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem" }}>
          {[
            { icon: "⚡", title: "Causalité stricte", color: "#f59e0b", desc: "on_bar reçoit past_prices[:t] — les données du futur sont physiquement inaccessibles. Aucune fuite possible par construction." },
            { icon: "🔄", title: "Walk-forward", color: "#3b82f6", desc: "Les modèles ML sont ré-entraînés tous les walkforward_refit_days bars sur les données passées uniquement." },
            { icon: "💰", title: "Coûts réels", color: "#16a34a", desc: "TTF, Stamp Duty, slippage, impact marché, commissions broker — tout est déduit automatiquement selon le broker choisi." },
            { icon: "🛡️", title: "PositionManager", color: GOLD, desc: "Stops par position (ATR-based), trailing stops, sizing par volatilité — hérités de BaseStrategy. Activer avec use_position_manager=True." },
            { icon: "📊", title: "Poids normalisés", color: "#8b5cf6", desc: "La somme des poids retournés doit être ≤ 1.0. Le moteur normalise automatiquement si nécessaire. Retourner {} = tout en cash." },
            { icon: "⚙️", title: "param_space", color: "#ec4899", desc: "Chaque combinaison de param_space est testée en walk-forward. Évite les espaces > 100 combinaisons pour limiter le temps de calcul." },
          ].map(rule => (
            <div key={rule.icon} style={{ background: NAVY2, border: `1px solid ${BORDER}`, borderRadius: 8, padding: "1.2rem" }}>
              <div style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>{rule.icon}</div>
              <div style={{ fontSize: "0.78rem", fontWeight: 700, color: rule.color, marginBottom: "0.4rem" }}>{rule.title}</div>
              <p style={{ margin: 0, fontSize: "0.72rem", color: "#64748b", lineHeight: 1.6 }}>{rule.desc}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
