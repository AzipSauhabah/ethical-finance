import { useState } from 'react';
import { api } from '../utils/api';
import type { DailySignal } from '../types';

const GOLD = '#b8962f', GREEN = '#1d8c41', RED = '#b82424';

interface Props { tickers: string[]; strategy?: string; }

const STRATEGY_INDICATORS: Record<string, string[]> = {
  buy_hold:       ['Tendance long terme', 'Signal de maintien'],
  sma_crossover:  ['SMA 50/200', 'Golden/Death Cross', 'Tendance'],
  rsi_mean_rev:   ['RSI 14', 'Survente/Surachat', 'Mean Reversion'],
  momentum:       ['Momentum 3M', 'Momentum 6M', 'Force relative'],
  ml_rf:          ['ML Random Forest', 'Features: RSI, MACD, Bollinger', 'Probabilité directionnelle'],
  ml_gbm:         ['ML LightGBM', 'Features: Momentum, EMA, Vol', 'Probabilité directionnelle'],
  epr5:           ['Magic Formula', 'Earning Yield', 'ROIC'],
  multi_factor:   ['Value', 'Momentum', 'Quality', 'Low Vol'],
};

export default function SignalsPanel({ tickers, strategy = 'buy_hold' }: Props) {
  const [signals, setSignals] = useState<DailySignal[]>([]);
  const [loading, setLoad]    = useState(false);
  const [lastRun, setLast]    = useState('');

  const refresh = async () => {
    if (!tickers.length) return;
    setLoad(true);
    try {
      const r = await api.dailySignals(tickers);
      setSignals(r.signals);
      setLast(new Date().toLocaleString('fr-FR'));
    } catch(e) { console.error(e); }
    finally { setLoad(false); }
  };

  const indicators = STRATEGY_INDICATORS[strategy] || STRATEGY_INDICATORS['buy_hold'];
  const colorFor = (s: number) => s > 0 ? GREEN : s < 0 ? RED : '#555';

  const signalBadge = (label: string, signal: number) => (
    <span style={{
      display: 'inline-block', padding: '0.25rem 0.75rem', borderRadius: 3,
      background: signal > 0 ? 'rgba(29,140,65,0.15)' : signal < 0 ? 'rgba(184,36,36,0.15)' : 'rgba(255,255,255,0.05)',
      border: `1px solid ${colorFor(signal)}`,
      color: colorFor(signal), fontWeight: 700, fontSize: '0.75rem', letterSpacing: '1px',
    }}>{label}</span>
  );

  return (
    <div style={{ padding: '2rem', maxWidth: 1400, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '2rem', borderBottom: '1px solid #1a2035', paddingBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <div style={{ fontSize: '0.65rem', letterSpacing: '3px', color: GOLD, marginBottom: 4 }}>SIGNAUX QUOTIDIENS</div>
          <h2 style={{ margin: 0, fontSize: '1.8rem', fontFamily: '"Playfair Display", serif', color: '#e8e8e8', fontWeight: 400 }}>
            Prochains mouvements
          </h2>
          <p style={{ margin: '0.5rem 0 0', fontSize: '0.8rem', color: '#666' }}>
            Signaux générés par la stratégie <strong style={{ color: GOLD }}>{strategy.toUpperCase()}</strong> · Indicateurs : {indicators.join(' · ')}
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {lastRun && <span style={{ fontSize: '0.7rem', color: '#555', fontFamily: '"JetBrains Mono", monospace' }}>{lastRun}</span>}
          <button onClick={refresh} disabled={loading || !tickers.length} style={{
            padding: '0.6rem 1.5rem', background: loading ? '#1a2035' : GOLD,
            color: loading ? '#666' : '#0a0f1e', border: 'none', borderRadius: 4,
            cursor: tickers.length ? 'pointer' : 'not-allowed',
            fontWeight: 700, fontSize: '0.75rem', letterSpacing: '1.5px',
          }}>{loading ? 'CALCUL…' : 'ACTUALISER'}</button>
        </div>
      </div>

      {/* Strategy info card */}
      <div style={{ background: '#111827', border: '1px solid #1e2d4a', borderRadius: 8, padding: '1rem 1.5rem', marginBottom: '1.5rem', display: 'flex', gap: '2rem', alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: '0.6rem', letterSpacing: '2px', color: '#555', marginBottom: 4 }}>STRATÉGIE ACTIVE</div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: GOLD, fontFamily: '"JetBrains Mono", monospace' }}>{strategy.toUpperCase()}</div>
        </div>
        <div style={{ flex: 1, display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          {indicators.map(ind => (
            <span key={ind} style={{ padding: '0.25rem 0.75rem', background: 'rgba(184,150,47,0.1)', border: '1px solid rgba(184,150,47,0.2)', borderRadius: 3, fontSize: '0.7rem', color: '#b8962f', letterSpacing: '0.5px' }}>{ind}</span>
          ))}
        </div>
      </div>

      {/* Signals table */}
      <div style={{ background: '#111827', borderRadius: 8, overflow: 'hidden', border: '1px solid #1e2d4a' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
          <thead>
            <tr style={{ background: '#0d1528' }}>
              {['TICKER', 'SIGNAL', 'FORCE', 'SMA', 'RSI', 'MACD', 'MOMENTUM', 'RECOMMANDATION'].map(h => (
                <th key={h} style={{ padding: '0.75rem 1rem', textAlign: 'left', fontSize: '0.6rem', letterSpacing: '2px', color: '#555', fontWeight: 600, borderBottom: '1px solid #1e2d4a' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {signals.map((s, i) => {
              const rec = s.signal > 0 ? 'ACHETER' : s.signal < 0 ? 'VENDRE' : 'CONSERVER';
              return (
                <tr key={s.ticker} style={{ borderBottom: '1px solid #1a2035', background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)' }}>
                  <td style={{ padding: '0.85rem 1rem' }}>
                    <span style={{ fontFamily: '"JetBrains Mono", monospace', fontWeight: 600, color: '#e8e8e8' }}>{s.ticker}</span>
                  </td>
                  <td style={{ padding: '0.85rem 1rem' }}>{signalBadge(s.label, s.signal)}</td>
                  <td style={{ padding: '0.85rem 1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <div style={{ flex: 1, height: 4, background: '#1a2035', borderRadius: 2, overflow: 'hidden', maxWidth: 80 }}>
                        <div style={{ height: '100%', width: `${s.strength * 100}%`, background: colorFor(s.signal), borderRadius: 2 }} />
                      </div>
                      <span style={{ fontSize: '0.7rem', color: '#888', fontFamily: '"JetBrains Mono", monospace' }}>{(s.strength * 100).toFixed(0)}%</span>
                    </div>
                  </td>
                  {(['sma_crossover', 'rsi', 'macd', 'momentum'] as const).map(ind => (
                    <td key={ind} style={{ padding: '0.85rem 1rem' }}>
                      <span style={{ color: colorFor(s.indicators[ind] || 0), fontSize: '1rem', fontWeight: 700 }}>
                        {(s.indicators[ind] || 0) > 0 ? '▲' : (s.indicators[ind] || 0) < 0 ? '▼' : '●'}
                      </span>
                    </td>
                  ))}
                  <td style={{ padding: '0.85rem 1rem' }}>
                    <span style={{
                      padding: '0.3rem 0.8rem', borderRadius: 3, fontWeight: 700,
                      fontSize: '0.7rem', letterSpacing: '1.5px',
                      background: s.signal > 0 ? GREEN : s.signal < 0 ? RED : '#1a2035',
                      color: s.signal !== 0 ? '#fff' : '#666',
                    }}>{rec}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!signals.length && (
          <div style={{ padding: '4rem', textAlign: 'center', color: '#444' }}>
            <div style={{ fontSize: '2rem', marginBottom: '1rem', opacity: 0.3 }}>◆</div>
            <div style={{ fontSize: '0.85rem', letterSpacing: '1px' }}>
              {!tickers.length ? 'Ajoutez des tickers dans l\'onglet Portefeuille.' : 'Cliquez sur ACTUALISER pour générer les signaux.'}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
