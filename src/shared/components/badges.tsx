/**
 * shared/components/badges.tsx
 * Badges réutilisables — ESG, Finance Islamique
 * Utilisés dans Portfolio (TickerManager) et Screener (ScreeningPanel)
 */

export function Badge({ passed }: { passed?: boolean }) {
  if (passed === undefined) return <span style={{ color: '#444', fontSize: '0.7rem' }}>…</span>;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      width: 22, height: 22, borderRadius: 4,
      background: passed ? 'rgba(29,140,65,0.15)' : 'rgba(184,36,36,0.15)',
      border: `1px solid ${passed ? '#1d8c41' : '#b82424'}`,
      color: passed ? '#1d8c41' : '#b82424',
      fontSize: '0.75rem', fontWeight: 700,
    }}>{passed ? '✓' : '✗'}</span>
  );
}

export function IslamicBadgeMini({ passed }: { passed?: boolean | null }) {
  const c = passed === true  ? { bg:"#14532d", border:"#16a34a", color:"#4ade80", icon:"✓" }
          : passed === false ? { bg:"#450a0a", border:"#dc2626", color:"#f87171", icon:"x" }
          : { bg:"#1a1a1a", border:"#333", color:"#555", icon:"?" };
  return (
    <span title={passed === true ? "Conforme Finance Islamique" : passed === false ? "Non conforme" : "Donnees insuffisantes"}
      style={{ display:"inline-flex", alignItems:"center", justifyContent:"center",
        width:22, height:22, borderRadius:4,
        background:c.bg, color:c.color, border:"1px solid "+c.border,
        fontSize:12, fontWeight:700, cursor:"pointer" }}>
      {c.icon}
    </span>
  );
}

export function IslamicBadge({ isSharia }: { isSharia?: boolean | null }) {
  const c = isSharia === true  ? { bg:"#14532d", border:"#16a34a", color:"#4ade80", icon:"✓" }
          : isSharia === false ? { bg:"#450a0a", border:"#dc2626", color:"#f87171", icon:"✗" }
          : { bg:"#1a1a1a", border:"#333", color:"#555", icon:"?" };
  const tip = isSharia === true  ? "Conforme Finance Islamique (AAOIFI) — cliquer pour détails"
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
