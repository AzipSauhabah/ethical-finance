// Main shell: tabbed layout for the Ethical Finance Platform.
// © 2024 Sauhabah

import { useState } from 'react';
import AboutPanel    from './components/AboutPanel';
import TickerManager from './components/TickerManager';
import BacktestPanel from './components/BacktestPanel';
import SignalsPanel  from './components/SignalsPanel';

type Tab = 'about' | 'tickers' | 'backtest' | 'signals';

const TABS: { key: Tab; label: string }[] = [
  { key: 'about',    label: 'Accueil' },
  { key: 'tickers',  label: 'Portefeuille' },
  { key: 'backtest', label: 'Backtest & Rapport' },
  { key: 'signals',  label: 'Prochains mouvements' },
];

export default function App() {
  const [tab, setTab]         = useState<Tab>('about');
  const [tickers, setTickers] = useState<string[]>([]);

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', color: '#222', minHeight: '100vh', background: '#fff' }}>
      <header style={{
        background: '#142340', color: '#fff', padding: '0.75rem 1.5rem',
        borderBottom: '3px solid #b8962f',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <h1 style={{ margin: 0, fontSize: '1.1rem', letterSpacing: '0.5px' }}>
          ETHICAL FINANCE PLATFORM <span style={{ color: '#b8962f' }}>—</span> SAUHABAH
        </h1>
        <span style={{ fontSize: '0.75rem', color: '#b8962f' }}>v2.0</span>
      </header>

      <nav style={{ borderBottom: '1px solid #ddd', background: '#f4f4f8' }}>
        <div style={{ display: 'flex', maxWidth: 1200, margin: '0 auto' }}>
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              style={{
                padding: '0.75rem 1.25rem',
                background: tab === t.key ? '#fff' : 'transparent',
                color: tab === t.key ? '#142340' : '#666',
                border: 'none',
                borderBottom: tab === t.key ? '3px solid #b8962f' : '3px solid transparent',
                fontWeight: tab === t.key ? 700 : 500,
                cursor: 'pointer',
                fontSize: '0.9rem',
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
      </nav>

      <main style={{ maxWidth: 1200, margin: '0 auto', padding: '1rem' }}>
        {tab === 'about'    && <AboutPanel />}
        {tab === 'tickers'  && <TickerManager tickers={tickers} setTickers={setTickers} />}
        {tab === 'backtest' && <BacktestPanel tickers={tickers} />}
        {tab === 'signals'  && <SignalsPanel tickers={tickers} />}
      </main>

      <footer style={{
        textAlign: 'center', padding: '1rem',
        fontSize: '0.7rem', color: '#888', borderTop: '1px solid #eee',
      }}>
        © 2024 Sauhabah — Ethical Finance Platform · Pas un conseil en investissement · Performances passées ≠ futures
      </footer>
    </div>
  );
}
