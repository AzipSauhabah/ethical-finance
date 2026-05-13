// Ticker manager: add tickers, runs ethical screening, shows live quotes.
// © 2024 Sauhabah

import { useState } from 'react';
import { api } from '../utils/api';
import { useLiveQuotes } from '../hooks/useLiveQuotes';
import type { TickerScreenResult } from '../types';

interface Props {
  tickers: string[];
  setTickers: (t: string[]) => void;
}

export default function TickerManager({ tickers, setTickers }: Props) {
  const [input, setInput]   = useState('');
  const [loading, setLoad]  = useState(false);
  const [screened, setScrn] = useState<TickerScreenResult[]>([]);
  const quotes = useLiveQuotes(tickers);

  const addTickers = async () => {
    const newOnes = input
      .split(/[\s,]+/)
      .map((t) => t.trim().toUpperCase())
      .filter((t) => t && !tickers.includes(t));
    if (!newOnes.length) return;

    setLoad(true);
    try {
      const all = [...tickers, ...newOnes];
      setTickers(all);
      const result = await api.screenTickers(all);
      setScrn(result.tickers);
    } catch (e) {
      console.error(e);
    } finally {
      setLoad(false);
      setInput('');
    }
  };

  const removeTicker = (t: string) => {
    setTickers(tickers.filter((x) => x !== t));
    setScrn(screened.filter((x) => x.ticker !== t));
  };

  return (
    <div style={{ padding: '1rem' }}>
      <h2 style={{ color: '#142340', marginBottom: '0.5rem' }}>Portefeuille — Tickers</h2>
      <p style={{ fontSize: '0.85rem', color: '#666', marginBottom: '1rem' }}>
        Ajoutez des tickers (ex : AAPL, MSFT, MC.PA, OR.PA). Un screening éthique est exécuté
        automatiquement. Les prix bid/ask/last sont rafraîchis en temps réel toutes les 60 secondes.
      </p>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && addTickers()}
          placeholder="AAPL, MSFT, MC.PA …"
          style={{ flex: 1, padding: '0.5rem', border: '1px solid #ccc', borderRadius: 4 }}
        />
        <button
          onClick={addTickers}
          disabled={loading}
          style={{
            padding: '0.5rem 1rem',
            background: '#142340', color: '#fff',
            border: 'none', borderRadius: 4, cursor: 'pointer',
          }}
        >
          {loading ? '…' : 'Ajouter'}
        </button>
      </div>

      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
        <thead>
          <tr style={{ background: '#142340', color: '#fff' }}>
            <th style={th}>Ticker</th>
            <th style={th}>Nom</th>
            <th style={th}>Last</th>
            <th style={th}>Bid</th>
            <th style={th}>Ask</th>
            <th style={th}>Volume</th>
            <th style={th}>Δ%</th>
            <th style={th}>Ethical</th>
            <th style={th}>Score</th>
            <th style={th}></th>
          </tr>
        </thead>
        <tbody>
          {tickers.map((t) => {
            const q = quotes[t];
            const s = screened.find((x) => x.ticker === t);
            return (
              <tr key={t} style={{ borderBottom: '1px solid #eee' }}>
                <td style={td}><strong>{t}</strong></td>
                <td style={td}>{s?.name ?? '—'}</td>
                <td style={td}>{q ? q.last.toFixed(2) : '—'}</td>
                <td style={td}>{q ? q.bid.toFixed(2) : '—'}</td>
                <td style={td}>{q ? q.ask.toFixed(2) : '—'}</td>
                <td style={td}>{q ? q.volume.toLocaleString() : '—'}</td>
                <td style={{
                  ...td,
                  color: q && q.change_pct >= 0 ? '#1d8c41' : '#b82424',
                  fontWeight: 600,
                }}>
                  {q ? `${q.change_pct.toFixed(2)}%` : '—'}
                </td>
                <td style={td}>{s ? (s.is_ethical ? '✓' : '✗') : '…'}</td>
                <td style={td}>{s ? s.ethical_score.toFixed(2) : '—'}</td>
                <td style={td}>
                  <button
                    onClick={() => removeTicker(t)}
                    style={{ background: 'none', border: 'none', color: '#b82424', cursor: 'pointer' }}
                  >
                    ✕
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {screened.some((s) => !s.is_ethical) && (
        <div style={{
          marginTop: '1rem', padding: '0.75rem',
          background: '#fdf2e7', border: '1px solid #d97842', borderRadius: 4,
        }}>
          ⚠️ Certains tickers ne passent pas le filtre éthique. Vérifiez les raisons :
          {screened.filter((s) => !s.is_ethical).map((s) => (
            <div key={s.ticker} style={{ fontSize: '0.8rem', marginTop: '0.25rem' }}>
              <strong>{s.ticker}</strong> — {s.ethical_flags.join(', ')}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const th: React.CSSProperties = { padding: '0.5rem', textAlign: 'left' };
const td: React.CSSProperties = { padding: '0.5rem' };
