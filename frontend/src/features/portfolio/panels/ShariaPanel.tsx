export function IslamicFinancePanelPortfolio({ s, colSpan }: { s: any; colSpan: number }) {
  const checks = s.sharia?.checks || [];
  const overall = s.is_sharia;
  const CRITERIA = [
    { id:1, icon:"H", label:"ACTIVITE", threshold: null },
    { id:2, icon:"D", label:"DETTE PORTANT INTERETS", threshold: 0.33 },
    { id:3, icon:"L", label:"LIQUIDITES PORTANT INTERETS", threshold: 0.33 },
    { id:4, icon:"R", label:"REVENUS NON-PERMISSIBLES", threshold: 0.05 },
  ];
  return (
    <tr>
      <td colSpan={colSpan} style={{ padding:0, background:"#060b14" }}>
        <div style={{
          margin:"0 1rem 0.75rem",
          border:"1px solid "+(overall===true?"#14532d":overall===false?"#450a0a":"#1e2d4a"),
          borderRadius:8, overflow:"hidden",
        }}>
          <div style={{
            display:"flex", alignItems:"center", justifyContent:"space-between",
            padding:"0.6rem 1rem",
            background:overall===true?"rgba(20,83,45,0.25)":overall===false?"rgba(69,10,10,0.25)":"rgba(30,45,74,0.2)",
            borderBottom:"1px solid #1e2d4a",
          }}>
            <span style={{ fontSize:"0.63rem", letterSpacing:"2px", color:"#555", fontWeight:700 }}>
              FINANCE ISLAMIQUE - CONFORMITE AAOIFI
            </span>
            <span style={{ fontSize:"0.7rem", fontWeight:800,
              color:overall===true?"#4ade80":overall===false?"#f87171":"#555" }}>
              {overall===true?"CONFORME":overall===false?"NON CONFORME":"INDETERMINE"}
            </span>
          </div>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)" }}>
            {CRITERIA.map((crit, i) => {
              const chk = checks.find((c: any) => c.name.startsWith(String(crit.id)+"."));
              const passed = chk?.passed;
              const val = chk?.value;
              const tc = passed===true?"#4ade80":passed===false?"#f87171":"#555";
              const bc = passed===true?"#16a34a":passed===false?"#dc2626":"#2a2a2a";
              const pct = val!=null && crit.threshold ? Math.min(val/crit.threshold,1.5) : null;
              return (
                <div key={crit.id} style={{ padding:"0.75rem 1rem", borderRight:i<3?"1px solid #1e2d4a":"none" }}>
                  <div style={{ display:"flex", alignItems:"center", gap:"0.4rem", marginBottom:"0.4rem" }}>
                    <span style={{
                      display:"inline-flex", alignItems:"center", justifyContent:"center",
                      width:16, height:16, borderRadius:"50%",
                      background:passed===true?"rgba(20,83,45,0.6)":passed===false?"rgba(69,10,10,0.6)":"#111",
                      color:tc, fontSize:9, fontWeight:800, border:"1px solid "+bc, flexShrink:0,
                    }}>{passed===true?"v":passed===false?"x":"?"}</span>
                    <span style={{ fontSize:"0.6rem", fontWeight:700, color:"#999" }}>{crit.label}</span>
                  </div>
                  {chk?.description && (
                    <div style={{ fontSize:"0.62rem", color:"#555", marginBottom:"0.4rem", lineHeight:1.4 }}>
                      {chk.description.length > 90 ? chk.description.slice(0,90)+"..." : chk.description}
                    </div>
                  )}
                  {val!=null && crit.threshold!=null && (
                    <>
                      <div style={{ display:"flex", justifyContent:"space-between", marginBottom:"0.2rem" }}>
                        <span style={{ fontSize:"0.8rem", fontWeight:800, color:tc, fontFamily:'"JetBrains Mono",monospace' }}>
                          {(val*100).toFixed(1)}%
                        </span>
                        <span style={{ fontSize:"0.58rem", color:"#333" }}>seuil {(crit.threshold*100).toFixed(0)}%</span>
                      </div>
                      <div style={{ height:4, background:"#111", borderRadius:2, overflow:"hidden" }}>
                        <div style={{ height:"100%", width:Math.min((pct||0)*100,100)+"%",
                          background:bc, borderRadius:2, transition:"width 0.4s" }}/>
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
          {s.revenue_segments && Object.keys(s.revenue_segments).length > 0 && (
            <div style={{ padding:"0.5rem 1rem", borderTop:"1px solid #1e2d4a" }}>
              <div style={{ fontSize:"0.6rem", color:"#444", marginBottom:"0.3rem", letterSpacing:"1px" }}>SEGMENTS DE REVENUS</div>
              <div style={{ display:"flex", flexWrap:"wrap", gap:"0.4rem" }}>
                {Object.entries(s.revenue_segments).sort(([,a],[,b]) => (b as number)-(a as number)).map(([name, ratio]) => (
                  <span key={name} style={{ fontSize:"0.62rem", padding:"0.15rem 0.5rem", borderRadius:3,
                    background:"rgba(20,83,45,0.3)", color:"#4ade80", border:"1px solid #16a34a" }}>
                    {name} ({((ratio as number)*100).toFixed(0)}%)
                  </span>
                ))}
              </div>
            </div>
          )}
          <div style={{ padding:"0.35rem 1rem", borderTop:"1px solid #1e2d4a", display:"flex", justifyContent:"space-between" }}>
            <span style={{ fontSize:"0.58rem", color:"#252525" }}>AAOIFI - 4 criteres cumulatifs</span>
            <span style={{ fontSize:"0.58rem", color:"#252525" }}>Sources : ESEF - SEC EDGAR - MAJ hebdomadaire</span>
          </div>
        </div>
      </td>
    </tr>
  );
}
