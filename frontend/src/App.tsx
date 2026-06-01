// App.tsx — Goldman Sachs institutional redesign
// © 2024 Sauhabah

import { useState } from 'react';
import AboutPanel    from './features/about/AboutPage';
import TickerManager from './features/portfolio/PortfolioPage';
import BacktestPanel from './features/backtest/BacktestPage';
import SignalsPanel  from './features/signals/SignalsPanel';
import ScreeningPanel from './features/screener/ScreenerPage';
import SentimentPanel from './features/sentiment/SentimentPage';
import TechnicalPanel from './features/technical/TechnicalPage';
import IndicatorsPanel from './features/indicators/IndicatorsPage';
import LivePanel from './features/live/LivePage';
import StrategyBuilderPanel from './features/strategy-builder/StrategyBuilderPage';

type Tab = 'about' | 'tickers' | 'screener' | 'backtest' | 'signals' | 'sentiment' | 'technical' | 'indicators' | 'live' | 'builder';

const METHOD_LABELS: Record<string, { label: string; strategy: string }> = {
  magic_formula: { label: 'Magic Formula (Greenblatt)', strategy: 'epr5' },
  momentum:      { label: 'Momentum 12-6-1',            strategy: 'momentum' },
  low_vol:       { label: 'Low Volatility',              strategy: 'risk_parity' },
  ml:            { label: 'AI / ML Score',               strategy: 'ml_ensemble' },
  combined:      { label: 'Combined Value+Momentum+ML',  strategy: 'epr5' },
};

const TABS: { key: Tab; label: string; icon: string; group: string; tooltip: string }[] = [
  // Dashboard
  { key: 'about',      label: 'Home',       icon: '◈', group: 'dashboard', tooltip: 'Overview — signals, pipeline status, market summary' },
  { key: 'tickers',    label: 'Portfolio',  icon: '◎', group: 'dashboard', tooltip: 'Track positions, P&L, Sharpe, correlations, risk contribution' },
  { key: 'live',       label: 'Live',       icon: '⬤', group: 'dashboard', tooltip: 'Real-time quotes and intraday price streams' },
  // Research
  { key: 'screener',   label: 'Screener',   icon: '▣', group: 'research',  tooltip: 'Filter SP500/CAC40 by ESG, Sharia, Buffett Score, fundamentals' },
  { key: 'sentiment',  label: 'Sentiment',  icon: '◉', group: 'research',  tooltip: 'VADER sentiment analysis from news & social media' },
  { key: 'technical',  label: 'Technical',  icon: '◇', group: 'research',  tooltip: 'RSI, MACD, Bollinger, Fibonacci, Elliott Wave' },
  { key: 'indicators', label: 'Indicators', icon: '◈', group: 'research',  tooltip: 'Configurable technical indicators dashboard' },
  // Strategy
  { key: 'backtest',   label: 'Backtest',   icon: '◉', group: 'strategy',  tooltip: 'Event-driven backtester — strict no-lookahead, real costs' },
  { key: 'signals',    label: 'Signals',    icon: '◆', group: 'strategy',  tooltip: 'Daily buy/sell signals — 560 tickers × 6 strategies' },
  { key: 'builder',    label: 'Strategies', icon: '⚙', group: 'strategy',  tooltip: 'Build and deploy custom strategies — plug-and-play' },
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
          {/* Navbar avec groupes */}
          {['dashboard','research','strategy'].map(group => (
            <div key={group} style={{ display: 'flex', alignItems: 'center', gap: 0 }}>
              {group !== 'dashboard' && (
                <div style={{ display: 'flex', alignItems: 'center', padding: '0 6px' }}>
                  <span style={{ width: 1, height: 28, background: '#2a3a5a' }} />
                  <span style={{ fontSize: '0.45rem', letterSpacing: '2px', color: '#2a3a5a', writingMode: 'vertical-rl', marginLeft: 4, textTransform: 'uppercase', fontWeight: 700 }}>
                    {group === 'research' ? 'RESEARCH' : 'STRATEGY'}
                  </span>
                </div>
              )}
              {TABS.filter(t => t.group === group).map(t => (
            <button key={t.key} onClick={() => setTab(t.key)} title={t.tooltip} style={{
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
            </div>
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
        {tab === 'sentiment' && <SentimentPanel tickers={tickers} />}
        {tab === 'technical' && <TechnicalPanel />}
        {tab === 'indicators' && <IndicatorsPanel tickers={tickers} />}
        {tab === 'live'       && <LivePanel tickers={tickers} />}
        {tab === 'builder'    && <StrategyBuilderPanel />}
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
