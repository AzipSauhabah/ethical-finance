// App.tsx — Goldman Sachs institutional redesign
// © 2024 Sauhabah

import { useState } from 'react';
import AboutPanel    from './components/AboutPanel';
import TickerManager from './components/TickerManager';
import BacktestPanel from './components/BacktestPanel';
import SignalsPanel  from './components/SignalsPanel';
import ScreeningPanel from './components/ScreeningPanel';

type Tab = 'about' | 'tickers' | 'screener' | 'backtest' | 'signals';

const METHOD_LABELS: Record<string, { label: string; strategy: string }> = {
  magic_formula: { label: 'Magic Formula (Greenblatt)', strategy: 'epr5' },
  momentum:      { label: 'Momentum 12-6-1 mois',       strategy: 'momentum' },
  low_vol:       { label: 'Low Volatility',              strategy: 'risk_parity' },
  ml:            { label: 'IA / ML Score',               strategy: 'ml_ensemble' },
  combined:      { label: 'Combiné Value+Momentum+ML',   strategy: 'epr5' },
};

const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: 'about',    label: 'Vue d\'ensemble', icon: '◈' },
  { key: 'tickers',  label: 'Portefeuille',    icon: '◎' },
  { key: 'screener', label: 'Screener',         icon: '▣' },
  { key: 'backtest', label: 'Analyse',          icon: '◉' },
  { key: 'signals',  label: 'Signaux',          icon: '◆' },
];

export default function App() {
  const [tab, setTab]           = useState<Tab>('about');
  const [tickers, setTickers]   = useState<string[]>([]);
  const [strategy, setStrategy] = useState<string>("buy_hold");
  const [screenerSource, setScreenerSource] = useState<{ method: string; count: number } | null>(null);

  function handleScreenerSelection(selected: string[], method: string) {
    setTickers(Array.from(new Set(selected)));
    const mapped = METHOD_LABELS[method];
    if (mapped) setStrategy(mapped.strategy);
    setScreenerSource({ method, count: selected.length });
    setTab('backtest');
  }

  return (
    <div style={{ fontFamily: '"Inter", system-ui, sans-serif', color: '#e8e8e8', minHeight: '100vh', background: '#0a0f1e' }}>
      <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />

      <header style={{
        background: 'linear-gradient(135deg, #0d1528 0%, #142340 100%)',
        borderBottom: '1px solid rgba(184,150,47,0.3)',
        padding: '0 2rem',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        height: 56,
        position: 'sticky', top: 0, zIndex: 100,
        backdropFilter: 'blur(10px)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{
            width: 32, height: 32, borderRadius: 6,
            background: 'linear-gradient(135deg, #b8962f, #e8c547)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '1rem', fontWeight: 700, color: '#000',
          }}>S</div>
          <div>
            <div style={{ fontSize: '0.75rem', letterSpacing: '3px', color: '#b8962f', fontWeight: 600, textTransform: 'uppercase' }}>Sauhabah</div>
            <div style={{ fontSize: '0.65rem', color: '#666', letterSpacing: '1px' }}>Ethical Finance Platform</div>
          </div>
        </div>

        <nav style={{ display: 'flex', gap: 0 }}>
          {TABS.map((t) => (
            <button key={t.key} onClick={() => setTab(t.key)} style={{
              padding: '0 1.25rem',
              height: 56,
              background: 'none',
              color: tab === t.key ? '#b8962f' : '#888',
              border: 'none',
              borderBottom: tab === t.key ? '2px solid #b8962f' : '2px solid transparent',
              fontWeight: tab === t.key ? 600 : 400,
              cursor: 'pointer',
              fontSize: '0.8rem',
              letterSpacing: '0.5px',
              display: 'flex', alignItems: 'center', gap: '0.4rem',
              transition: 'all 0.2s',
            }}>
              <span style={{ fontSize: '0.7rem' }}>{t.icon}</span>
              {t.label}
            </button>
          ))}
        </nav>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {tickers.length > 0 && (
            <div style={{
              padding: '0.2rem 0.6rem',
              background: 'rgba(184,150,47,0.1)',
              border: '1px solid rgba(184,150,47,0.3)',
              borderRadius: 4,
              fontSize: '0.65rem',
              color: '#b8962f',
              fontFamily: '"JetBrains Mono", monospace',
            }}>
              {tickers.length} ticker{tickers.length > 1 ? 's' : ''}
            </div>
          )}
          <div style={{ width: 8, height: 8, borderRadius: 4, background: '#1d8c41', boxShadow: '0 0 6px #1d8c41' }} />
          <span style={{ fontSize: '0.7rem', color: '#666' }}>LIVE</span>
          <span style={{ fontSize: '0.65rem', color: '#444', fontFamily: '"JetBrains Mono", monospace' }}>v2.1</span>
        </div>
      </header>

      <main>
        {tab === 'about'    && <AboutPanel />}
        {tab === 'tickers'  && <TickerManager tickers={tickers} setTickers={setTickers} />}
        {tab === 'screener' && <ScreeningPanel onSelectTickers={handleScreenerSelection} />}
        {tab === 'backtest' && <BacktestPanel tickers={tickers} onStrategyChange={setStrategy} defaultStrategy={strategy} />}
        {tab === 'signals'  && <SignalsPanel tickers={tickers} strategy={strategy} />}
      </main>

      <footer style={{
        textAlign: 'center', padding: '1.5rem',
        fontSize: '0.65rem', color: '#333',
        borderTop: '1px solid #1a2035',
        letterSpacing: '1px',
        fontFamily: '"JetBrains Mono", monospace',
      }}>
        © 2024 SAUHABAH — ETHICAL FINANCE PLATFORM · PAS UN CONSEIL EN INVESTISSEMENT · PERFORMANCES PASSÉES ≠ FUTURES
      </footer>
    </div>
  );
}
