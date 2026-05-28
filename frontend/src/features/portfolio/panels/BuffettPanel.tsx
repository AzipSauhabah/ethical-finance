import { useState } from 'react';

const GOLD = "#b8962f";

export default function BuffettPanel({ data, colSpan }: { data: any; colSpan: number }) {
  if (!data) return (
    <tr><td colSpan={colSpan} style={{ padding: "0.5rem 1rem", background: "#060b14" }}>
      <div style={{ fontSize: "0.7rem", color: "#555", padding: "0.5rem 1rem" }}>Chargement Buffett Score...</div>
    </td></tr>
  );
  const GOLD = "#b8962f";
  return (
    <tr>
      <td colSpan={colSpan} style={{ padding: 0, background: "#060b14" }}>
        <div style={{ margin: "0 1rem 0.75rem", border: "1px solid #2a1f0a", borderRadius: 8, overflow: "hidden" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0.6rem 1rem", background: "rgba(184,150,47,0.08)", borderBottom: "1px solid #2a1f0a" }}>
            <span style={{ fontSize: "0.63rem", letterSpacing: "2px", color: "#555", fontWeight: 700 }}>BUFFETT SCORE — QUALITE FONDAMENTALE</span>
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
              <span style={{ fontSize: "0.7rem", color: "#666" }}>{data.verdict}</span>
              <span style={{ fontSize: "1rem", fontWeight: 800, color: data.color, fontFamily: '"JetBrains Mono", monospace' }}>{data.score}<span style={{ fontSize: "0.6rem", color: "#555" }}>/100</span></span>
            </div>
          </div>
          <div style={{ height: 4, background: "#111" }}>
            <div style={{ height: "100%", width: data.score + "%", background: data.color, transition: "width 0.5s" }} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)" }}>
            {(data.checks || []).map((chk: any, i: number) => {
              const pct = chk.pts / chk.max;
              return (
                <div key={chk.id} style={{ padding: "0.75rem 1rem", borderRight: i < 3 ? "1px solid #1e1a0a" : "none" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.4rem" }}>
                    <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 16, height: 16, borderRadius: "50%", background: "rgba(184,150,47,0.15)", color: GOLD, fontSize: 9, fontWeight: 800, border: "1px solid #2a1f0a", flexShrink: 0 }}>{chk.icon}</span>
                    <span style={{ fontSize: "0.6rem", fontWeight: 700, color: "#999" }}>{chk.label}</span>
                  </div>
                  <div style={{ fontSize: "0.65rem", color: "#666", marginBottom: "0.4rem" }}>{chk.detail}</div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.2rem" }}>
                    <span style={{ fontSize: "0.8rem", fontWeight: 800, color: GOLD, fontFamily: '"JetBrains Mono", monospace' }}>{chk.pts}</span>
                    <span style={{ fontSize: "0.58rem", color: "#333" }}>/ {chk.max}</span>
                  </div>
                  <div style={{ height: 4, background: "#111", borderRadius: 2, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: (pct * 100) + "%", background: pct > 0.7 ? "#16a34a" : pct > 0.4 ? "#ca8a04" : "#dc2626", borderRadius: 2, transition: "width 0.4s" }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </td>
    </tr>
  );
}
