// Daily signals + rebalancing recommendations panel.
// © 2024 Sauhabah

import { useState } from 'react';
import { api } from '../utils/api';
import type { DailySignal } from '../types';

export default function SignalsPanel({ tickers }: { tickers: string[] }) {
  const [signals, setSignals] = useState<DailySignal[]>([]);
  const [loading, setLoad]    = useState(false);
  const [lastRun, setLast]    = useState<string>('');

  const refresh = async () => {
    if (!tickers.length) return;
    setLoad(true);
    try {
      const r = await api.dailySignals(tickers);
      setSignals(r.signals);
      setLast(new Date().toLocaleString('fr-FR'));
    } catch (e) { console.error(e); }
    finally { setLoad(false); }
  };

  const colorFor = (s: number) => s > 0 ? '#1d8c41' : s < 0 ? '#b82424' : '#888';

  return (
    <div style={{ padding: '1rem' }}>
      <h2 style={{ color: '#142340' }}>Prochains mouvements — Signaux quotidiens</h2>
      <p style={{ fontSize: '0.85rem', color: '#666' }}>
        Signaux d'achat/vente calculés à partir d'un vote multi-indicateurs
        (SMA crossover, RSI, MACD, Momentum). Actualisés à la demande ou par un
        thread serveur quotidien.
      </p>

      <button onClick={refresh} disabled={loading} style={{
        padding: '0.5rem 1rem', background: '#142340', color: '#fff',
        border: 'none', borderRadius: 4, cursor: 'pointer', marginBottom: '1rem',
      }}>
        {loading ? '…' : 'Recalculer les signaux'}
      </button>

      {lastRun && <span style={{ marginLeft: '1rem', fontSize: '0.8rem', color: '#666' }}>
        Dernière mise à jour : {lastRun}
      </span>}

      <table style={{ width: '100%', fontSize: '0.85rem', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ background: '#142340', color: '#fff' }}>
            <th style={th}>Ticker</th><th style={th}>Signal</th><th style={th}>Force</th>
            <th style={th}>SMA</th><th style={th}>RSI</th><th style={th}>MACD</th><th style={th}>Mom.</th>
          </tr>
        </thead>
        <tbody>
          {signals.map((s) => (
            <tr key={s.ticker} style={{ borderBottom: '1px solid #eee' }}>
              <td style={td}><strong>{s.ticker}</strong></td>
              <td style={{ ...td, color: colorFor(s.signal), fontWeight: 700 }}>
                {s.label}
              </td>
              <td style={td}>{(s.strength * 100).toFixed(0)}%</td>
              <td style={{ ...td, color: colorFor(s.indicators.sma_crossover) }}>
                {s.indicators.sma_crossover > 0 ? '↑' : s.indicators.sma_crossover < 0 ? '↓' : '—'}
              </td>
              <td style={{ ...td, color: colorFor(s.indicators.rsi) }}>
                {s.indicators.rsi > 0 ? '↑' : s.indicators.rsi < 0 ? '↓' : '—'}
              </td>
              <td style={{ ...td, color: colorFor(s.indicators.macd) }}>
                {s.indicators.macd > 0 ? '↑' : s.indicators.macd < 0 ? '↓' : '—'}
              </td>
              <td style={{ ...td, color: colorFor(s.indicators.momentum) }}>
                {s.indicators.momentum > 0 ? '↑' : s.indicators.momentum < 0 ? '↓' : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {!signals.length && !loading && (
        <p style={{ color: '#888', fontStyle: 'italic' }}>
          Ajoutez des tickers et cliquez sur « Recalculer les signaux ».
        </p>
      )}
    </div>
  );
}

const th: React.CSSProperties = { padding: '0.5rem', textAlign: 'left' };
const td: React.CSSProperties = { padding: '0.5rem' };
