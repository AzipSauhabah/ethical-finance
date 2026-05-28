export default function BuffettPanelScreener({ data }: { data: any }) {
  if (!data) return (
    <tr><td colSpan={17} style={{ padding: "0.5rem 1rem", background: "#060b14" }}>
      <div style={{ fontSize: "0.7rem", color: "#555", padding: "0.5rem 1rem" }}>Chargement...</div>
    </td></tr>
  );
  return (
    <tr>
      <td colSpan={17} style={{ padding: 0, background: "#060b14" }}>
        <div style={{ margin: "0 0.5rem 0.5rem", border: "1px solid #2a1f0a", borderRadius: 6, overflow: "hidden" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0.5rem 1rem", background: "rgba(184,150,47,0.08)", borderBottom: "1px solid #2a1f0a" }}>
            <span style={{ fontSize: "0.6rem", letterSpacing: "2px", color: "#555", fontWeight: 700 }}>BUFFETT SCORE</span>
            <span style={{ fontSize: "0.9rem", fontWeight: 800, color: data.color, fontFamily: '"JetBrains Mono", monospace' }}>{data.score}<span style={{ fontSize: "0.55rem", color: "#555" }}>/100</span> — {data.verdict}</span>
          </div>
          <div style={{ height: 3, background: "#111" }}>
            <div style={{ height: "100%", width: data.score + "%", background: data.color, transition: "width 0.5s" }} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)" }}>
            {(data.checks || []).map((chk: any, i: number) => (
              <div key={chk.id} style={{ padding: "0.6rem 1rem", borderRight: i < 3 ? "1px solid #1e1a0a" : "none" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.3rem", marginBottom: "0.3rem" }}>
                  <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 14, height: 14, borderRadius: "50%", background: "rgba(184,150,47,0.15)", color: "#b8962f", fontSize: 8, fontWeight: 800, border: "1px solid #2a1f0a" }}>{chk.icon}</span>
                  <span style={{ fontSize: "0.58rem", fontWeight: 700, color: "#999" }}>{chk.label}</span>
                  <span style={{ fontSize: "0.75rem", fontWeight: 800, color: "#b8962f", fontFamily: '"JetBrains Mono", monospace', marginLeft: "auto" }}>{chk.pts}<span style={{ fontSize: "0.5rem", color: "#444" }}>/{chk.max}</span></span>
                </div>
                <div style={{ fontSize: "0.6rem", color: "#555" }}>{chk.detail}</div>
                <div style={{ height: 3, background: "#111", borderRadius: 2, marginTop: "0.3rem" }}>
                  <div style={{ height: "100%", width: (chk.pts/chk.max*100) + "%", background: chk.pts/chk.max > 0.7 ? "#16a34a" : chk.pts/chk.max > 0.4 ? "#ca8a04" : "#dc2626", borderRadius: 2 }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </td>
    </tr>
  );
}
