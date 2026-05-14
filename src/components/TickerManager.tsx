// Ticker manager with dual ethical + sharia badges.
// © 2024 Sauhabah

import { useState } from 'react';
import { api } from '../utils/api';
import { useLiveQuotes } from '../hooks/useLiveQuotes';
import type { TickerScreenResult } from '../types';

interface Props {
  tickers: string[];
  setTickers: (t: string[]) => void;
}

const NAVY = '#142340';
const GREEN = '#1d8c41';
const RED = '#b82424';

export default function TickerManager({ tickers, setTickers }: Props) {
  const [input, setInput]   = useState('');
  const [loading, setLoad]  = useState(false);
  const [screened, setScrn] = useState<TickerScreenResult[]>([]);
  const quotes = useLiveQuotes(tickers);

  const add = async () => {
    const newOnes = input.split(/[\s,]+/).map((t) => t.trim().toUpperCase())
      .filter((t) => t && !tickers.includes(t));
    if (!newOnes.length) return;
    setLoad(true);
    try {
      const all = [...tickers, ...newOnes];
      setTickers(all);
      const r = await api.screenTickers(all);
      setScrn(r.tickers);
    } catch (e) { console.error(e); }
    finally { setLoad(false); setInput(''); }
  };

  const remove = (t: string) => {
    setTickers(tickers.filter((x) => x !== t));
    setScrn(screened.filter((x) => x.ticker !== t));
  };

  return (
    <div style={{ padding: '1rem' }}>
      <h2 style={{ color: NAVY }}>Portefeuille — Tickers</h2>
      <p style={{ fontSize: '0.85rem', color: '#666', maxWidth: 800 }}>
        Ajoutez des tickers (ex : AAPL, MC.PA, NESN.SW). Chaque ticker est évalué
        sur deux critères indépendants : <strong>Ethical (E)</strong> et <strong>Sharia (S)</strong>.
        Voir l'onglet <em>Screening</em> pour le détail.
      </p>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <input value={input} onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && add()}
          placeholder="AAPL, MSFT, MC.PA…"
          style={{ flex: 1, padding: '0.5rem', border: '1px solid #ccc', borderRadius: 4 }} />
        <button onClick={add} disabled={loading} style={{
          padding: '0.5rem 1rem', background: NAVY, color: '#fff',
          border: 'none', borderRadius: 4, cursor: 'pointer',
        }}>
          {loading ? '…' : 'Ajouter'}
        </button>
      </div>

      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
        <thead>
          <tr style={{ background: NAVY, color: '#fff' }}>
            <th style={th}>Ticker</th><th style={th}>Nom</th>
            <th style={th}>Last</th><th style={th}>Bid</th><th style={th}>Ask</th>
            <th style={th}>Volume</th><th style={th}>Δ%</th>
            <th style={th} title="Ethical">E</th>
            <th style={th} title="Sharia">S</th>
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
                <td style={{ ...td, color: q && q.change_pct >= 0 ? GREEN : RED, fontWeight: 600 }}>
                  {q ? `${q.change_pct.toFixed(2)}%` : '—'}
                </td>
                <td style={td}><Badge passed={s?.is_ethical} /></td>
                <td style={td}><Badge passed={s?.is_sharia} /></td>
                <td style={td}>
                  <button onClick={() => remove(t)}
                    style={{ background: 'none', border: 'none', color: RED, cursor: 'pointer' }}>✕</button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {!tickers.length && (
        <p style={{ color: '#888', fontStyle: 'italic', marginTop: '2rem', textAlign: 'center' }}>
          Aucun ticker. Tapez par exemple <code>AAPL, MSFT, MC.PA</code> et appuyez sur Entrée.
        </p>
      )}
    </div>
  );
}

function Badge({ passed }: { passed: boolean | undefined }) {
  if (passed === undefined) return <span style={{ color: '#888' }}>…</span>;
  return (
    <span style={{
      display: 'inline-block', width: 18, height: 18, borderRadius: 9,
      background: passed ? GREEN : RED, color: '#fff',
      fontSize: '0.7rem', textAlign: 'center', lineHeight: '18px', fontWeight: 700,
    }}>{passed ? '✓' : '✗'}</span>
  );
}

const th: React.CSSProperties = { padding: '0.5rem', textAlign: 'left' };
const td: React.CSSProperties = { padding: '0.5rem' };
