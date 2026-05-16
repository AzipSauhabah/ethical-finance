// AboutPanel — Goldman Sachs institutional homepage
// © 2024 Sauhabah

const GOLD = '#b8962f';

export default function AboutPanel() {
  return (
    <div style={{ background: '#0a0f1e', minHeight: 'calc(100vh - 56px)' }}>
      {/* Hero */}
      <div style={{
        padding: '5rem 3rem 4rem',
        background: 'linear-gradient(180deg, #0d1528 0%, #0a0f1e 100%)',
        borderBottom: '1px solid #1a2035',
        position: 'relative', overflow: 'hidden',
      }}>
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, opacity: 0.03, backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 40px, #b8962f 40px, #b8962f 41px), repeating-linear-gradient(90deg, transparent, transparent 40px, #b8962f 40px, #b8962f 41px)' }} />
        <div style={{ maxWidth: 900, margin: '0 auto', position: 'relative' }}>
          <div style={{ fontSize: '0.65rem', letterSpacing: '4px', color: GOLD, marginBottom: '1rem' }}>PLATEFORME D'ANALYSE QUANTITATIVE</div>
          <h1 style={{ margin: '0 0 1rem', fontSize: '3.5rem', fontFamily: '"Playfair Display", serif', color: '#e8e8e8', fontWeight: 400, lineHeight: 1.1 }}>
            Finance éthique.<br />
            <span style={{ color: GOLD }}>Précision institutionnelle.</span>
          </h1>
          <p style={{ margin: '0 0 2rem', fontSize: '1rem', color: '#888', maxWidth: 600, lineHeight: 1.7 }}>
            Backtestez 11 stratégies quantitatives sur 20 ans d'historique. Générez des rapports de niveau Goldman Sachs. Respectez vos principes d'investissement éthique et islamique.
          </p>
          <div style={{ display: 'flex', gap: '1rem' }}>
            {[
              { n: '20+', l: 'Années de données' },
              { n: '11', l: 'Stratégies quantitatives' },
              { n: '25+', l: 'Métriques de risque' },
              { n: '500+', l: 'Titres SP500 + CAC40' },
            ].map(s => (
              <div key={s.n} style={{ padding: '1rem 1.5rem', background: 'rgba(184,150,47,0.05)', border: '1px solid rgba(184,150,47,0.2)', borderRadius: 6 }}>
                <div style={{ fontSize: '1.8rem', fontWeight: 700, color: GOLD, fontFamily: '"JetBrains Mono", monospace' }}>{s.n}</div>
                <div style={{ fontSize: '0.7rem', color: '#666', letterSpacing: '1px', marginTop: 2 }}>{s.l}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Features grid */}
      <div style={{ padding: '3rem', maxWidth: 1400, margin: '0 auto' }}>
        <div style={{ fontSize: '0.65rem', letterSpacing: '3px', color: GOLD, marginBottom: '1.5rem' }}>FONCTIONNALITÉS</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
          {[
            { icon: '◉', title: 'Backtest événementiel', desc: 'Moteur event-driven date par date. FX EUR/USD historique. Frais réels par courtier. Taxes françaises (PFU, TTF, PEA).' },
            { icon: '◈', title: 'Rapport institutionnel PDF', desc: 'Format Goldman Sachs : 15 pages. Stress tests historiques. VaR/CVaR par position. Tests statistiques de Jobson-Korkie.' },
            { icon: '◆', title: 'Machine Learning', desc: 'LightGBM + Random Forest. Features techniques (RSI, MACD, Bollinger). Walk-forward strict sans look-ahead bias.' },
            { icon: '◎', title: 'Screening éthique', desc: 'Exclusion armement, tabac, jeux, énergies fossiles. Filtre islamique sur ratio dette/capital et revenus d\'intérêts.' },
            { icon: '▣', title: 'Stratégies quantitatives', desc: 'Buy & Hold, SMA Crossover, RSI Mean Reversion, Momentum, Magic Formula (EPR5), Multi-Factor, ML RF/GBM…' },
            { icon: '▤', title: 'Données en temps réel', desc: 'Supabase PostgreSQL. 2.5M barres SP500 + CAC40 (2006–2026). Taux FX historiques EUR/USD. Mis à jour quotidiennement.' },
          ].map(f => (
            <div key={f.title} style={{ padding: '1.5rem', background: '#111827', border: '1px solid #1e2d4a', borderRadius: 8, transition: 'border-color 0.2s' }}>
              <div style={{ fontSize: '1.5rem', color: GOLD, marginBottom: '0.75rem' }}>{f.icon}</div>
              <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#e8e8e8', marginBottom: '0.5rem' }}>{f.title}</div>
              <div style={{ fontSize: '0.78rem', color: '#666', lineHeight: 1.6 }}>{f.desc}</div>
            </div>
          ))}
        </div>

        {/* Stack technique */}
        <div style={{ marginTop: '3rem', padding: '2rem', background: '#111827', border: '1px solid #1e2d4a', borderRadius: 8 }}>
          <div style={{ fontSize: '0.65rem', letterSpacing: '3px', color: GOLD, marginBottom: '1rem' }}>STACK TECHNIQUE</div>
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            {['Python 3.12', 'FastAPI', 'NumPy / Pandas', 'LightGBM', 'ReportLab', 'Supabase PostgreSQL', 'React 18', 'Recharts', 'Vercel', 'GitHub Actions'].map(t => (
              <span key={t} style={{ padding: '0.3rem 0.8rem', background: 'rgba(184,150,47,0.08)', border: '1px solid rgba(184,150,47,0.2)', borderRadius: 3, fontSize: '0.72rem', color: '#b8962f', fontFamily: '"JetBrains Mono", monospace' }}>{t}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
