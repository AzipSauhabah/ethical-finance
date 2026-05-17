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
            Backtestez 11 stratégies quantitatives sur 20 ans d'historique. Générez des rapports de niveau Goldman Sachs. Respectez vos principes d'investissement éthique et islamique. Infrastructure 100% auto-hébergée.
          </p>
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            {[
              { n: '20+', l: 'Années de données' },
              { n: '11', l: 'Stratégies quantitatives' },
              { n: '25+', l: 'Métriques de risque' },
              { n: '2.5M', l: 'Barres OHLCV' },
              { n: 'SEC', l: 'Fondamentaux officiels US GAAP' },
              { n: '8', l: 'Graphiques institutionnels PDF' },
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
            { icon: '◈', title: 'Rapport institutionnel PDF', desc: 'Format Goldman Sachs : 15 pages avec charts matplotlib. Stress tests historiques. VaR/CVaR par position. Tests de Jobson-Korkie.' },
            { icon: '◆', title: 'Machine Learning avancé', desc: 'TensorFlow LSTM + RandomForest scikit-learn. Score combiné 60% RF + 40% LSTM. Walk-forward strict. Features techniques (RSI, MACD, Bollinger, EMA ratio).' },
            { icon: '◎', title: 'Screening éthique & Sharia', desc: 'Exclusion armement, tabac, jeux, énergies fossiles. Filtre islamique AAOIFI sur ratio dette/capital et revenus d\'intérêts.' },
            { icon: '▣', title: 'Stratégies quantitatives', desc: 'Buy & Hold, SMA Crossover, RSI Mean Reversion, Momentum, Magic Formula (EPR5), Risk Parity, Min Variance, ML Ensemble…' },
            { icon: '▤', title: 'Infrastructure auto-hébergée', desc: 'NAS Synology DS925+. PostgreSQL local. 2.5M barres SP500 + CAC40 (2006–2026). Cloudflare Tunnel. Zéro dépendance cloud externe.' },
            { icon: '◇', title: 'Fondamentaux SEC EDGAR', desc: 'Données officielles US GAAP depuis SEC.gov. 30+ métriques : PE, EV/EBITDA, ROE, ROIC, FCF yield, dette nette. Mis à jour quotidiennement par le scheduler.' },
            { icon: '◈', title: 'Rapport PDF institutionnel', desc: '15+ pages style Goldman Sachs. 8 graphiques matplotlib HD : heatmap mensuelle, rolling Sharpe, underwater plot, distribution des rendements, win/loss.' },
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
          <div style={{ fontSize: '0.65rem', letterSpacing: '3px', color: GOLD, marginBottom: '1.5rem' }}>STACK TECHNIQUE</div>

          {/* Backend */}
          <div style={{ marginBottom: '1.5rem' }}>
            <div style={{ fontSize: '0.6rem', letterSpacing: '2px', color: '#444', marginBottom: '0.75rem' }}>BACKEND</div>
            <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
              {['Python 3.11', 'FastAPI', 'NumPy / Pandas', 'scikit-learn', 'TensorFlow', 'LightGBM', 'matplotlib', 'SQLAlchemy', 'APScheduler', 'ReportLab'].map(t => (
                <span key={t} style={{ padding: '0.3rem 0.8rem', background: 'rgba(184,150,47,0.08)', border: '1px solid rgba(184,150,47,0.2)', borderRadius: 3, fontSize: '0.72rem', color: '#b8962f', fontFamily: '"JetBrains Mono", monospace' }}>{t}</span>
              ))}
            </div>
          </div>

          {/* Frontend */}
          <div style={{ marginBottom: '1.5rem' }}>
            <div style={{ fontSize: '0.6rem', letterSpacing: '2px', color: '#444', marginBottom: '0.75rem' }}>FRONTEND</div>
            <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
              {['React 18', 'TypeScript', 'Vite', 'Recharts', 'SSE temps réel'].map(t => (
                <span key={t} style={{ padding: '0.3rem 0.8rem', background: 'rgba(30,100,200,0.08)', border: '1px solid rgba(30,100,200,0.2)', borderRadius: 3, fontSize: '0.72rem', color: '#5b8dee', fontFamily: '"JetBrains Mono", monospace' }}>{t}</span>
              ))}
            </div>
          </div>

          {/* Infrastructure */}
          <div>
            <div style={{ fontSize: '0.6rem', letterSpacing: '2px', color: '#444', marginBottom: '0.75rem' }}>INFRASTRUCTURE</div>
            <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
              {['NAS Synology DS925+', 'Docker', 'PostgreSQL 16', 'Cloudflare Tunnel', 'Nginx', 'Gitea', 'GitHub Actions', 'SonarCloud'].map(t => (
                <span key={t} style={{ padding: '0.3rem 0.8rem', background: 'rgba(29,158,117,0.08)', border: '1px solid rgba(29,158,117,0.2)', borderRadius: 3, fontSize: '0.72rem', color: '#1d9e75', fontFamily: '"JetBrains Mono", monospace' }}>{t}</span>
              ))}
            </div>
          </div>
        </div>

        {/* Méthodologie EPR5 + LSTM */}
        <div style={{ marginTop: '3rem' }}>
          <div style={{ fontSize: '0.65rem', letterSpacing: '3px', color: GOLD, marginBottom: '1.5rem' }}>MÉTHODOLOGIE — EPR5 + IA HYBRIDE</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
            {[
              {
                icon: '◆', title: 'Magic Formula (Greenblatt)',
                desc: "Sélection par Earning Yield (EBIT/EV) et ROIC. Top quintile de l'univers rankés. Filtre régime : SPX > MM200. Filtre VIX : VIX < MM10.",
                color: '#b8962f',
              },
              {
                icon: '◉', title: 'RandomForest scikit-learn',
                desc: '50 arbres, profondeur 4, walk-forward 60j. Features : rendements 1/5/20/60j, volatilité, RSI, MM20/50/200, momentum. Label : rendement à 20j > +5%.',
                color: '#5b8dee',
              },
              {
                icon: '▣', title: 'LSTM TensorFlow (nouveau)',
                desc: 'Réseau récurrent : Input(30j×11) → LSTM(64) → LSTM(32) → Dense(16) → sigmoid. Capte les dépendances temporelles ignorées par le RF. Horizon 5j, seuil +2%.',
                color: '#1d9e75',
              },
              {
                icon: '◎', title: 'Score combiné + Sizing MC',
                desc: 'Score final = 0.6×RF + 0.4×LSTM. Sizing dynamique : base 10% NAV × multiplicateur Monte Carlo (Sharpe glissant 60j, clip 0.5×–1.5×). Stop ATR + profit target.',
                color: '#8a6f9c',
              },
            ].map(f => (
              <div key={f.title} style={{ padding: '1.25rem', background: '#111827', border: `1px solid ${f.color}22`, borderRadius: 8, borderLeft: `3px solid ${f.color}` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                  <span style={{ color: f.color, fontSize: '1rem' }}>{f.icon}</span>
                  <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#e8e8e8' }}>{f.title}</span>
                </div>
                <div style={{ fontSize: '0.74rem', color: '#666', lineHeight: 1.6 }}>{f.desc}</div>
              </div>
            ))}
          </div>

          {/* Hypothèses clés */}
          <div style={{ padding: '1.25rem', background: 'rgba(184,150,47,0.03)', border: '1px solid rgba(184,150,47,0.15)', borderRadius: 8 }}>
            <div style={{ fontSize: '0.6rem', letterSpacing: '2px', color: GOLD, marginBottom: '0.75rem' }}>HYPOTHÈSES & LIMITES</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
              {[
                '⚠ Les patterns historiques peuvent ne pas se répéter (rupture de régime)',
                '⚠ LSTM : faible signal/bruit sur horizon court (5j) — précision hors-échantillon ~55-62%',
                '⚠ Backtest walk-forward strict : aucune donnée future ne fuite dans les décisions',
                '⚠ Performances passées ne préjugent pas des performances futures',
              ].map(h => (
                <div key={h} style={{ fontSize: '0.72rem', color: '#555', lineHeight: 1.5 }}>{h}</div>
              ))}
            </div>
          </div>
        </div>

        {/* Architecture diagram link */}
        <div style={{ marginTop: '1.5rem', padding: '1rem 2rem', background: 'rgba(184,150,47,0.03)', border: '1px solid rgba(184,150,47,0.1)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: '0.75rem', color: '#e8e8e8', marginBottom: '0.25rem' }}>Infrastructure auto-hébergée — aucun port ouvert, HTTPS via Cloudflare Tunnel</div>
            <div style={{ fontSize: '0.7rem', color: '#555' }}>NAS Synology DS925+ · 32 Go RAM · Docker · PostgreSQL · Cloudflare Zero Trust</div>
          </div>
          <div style={{ fontSize: '0.65rem', letterSpacing: '2px', color: GOLD, whiteSpace: 'nowrap', marginLeft: '2rem' }}>AUTO-HÉBERGÉ ✓</div>
        </div>
      </div>
    </div>
  );
}
