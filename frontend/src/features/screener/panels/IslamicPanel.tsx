
export default function IslamicFinancePanel({ r }: { r: any }) {
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
