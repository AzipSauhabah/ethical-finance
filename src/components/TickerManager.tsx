import { useState, useEffect } from 'react';
import { api } from '../utils/api';
import { useLiveQuotes } from '../hooks/useLiveQuotes';
import type { TickerScreenResult } from '../types';

interface Props { tickers: string[]; setTickers: (t: string[]) => void; }

const N = '#0a0f1e', NAVY = '#142340', GOLD = '#b8962f', GREEN = '#1d8c41', RED = '#b82424', LIGHT = '#1a2035';

export default function TickerManager({ tickers, setTickers }: Props) {
  const [input, setInput]   = useState('');
  const [loading, setLoad]  = useState(false);
  const [screened, setScrn] = useState<TickerScreenResult[]>([]);
  const quotes = useLiveQuotes(tickers);

  const add = async () => {
    const newOnes = input.split(/[\s,]+/).map(t => t.trim().toUpperCase()).filter(t => t && !tickers.includes(t));
    if (!newOnes.length) return;
    setLoad(true);
    try {
      const all = [...tickers, ...newOnes];
      setTickers(all);
      const r = await api.screenTickers(all);
      setScrn(r.tickers);
    } catch(e) { console.error(e); }
    finally { setLoad(false); setInput(''); }
  };

  const remove = (t: string) => { setTickers(tickers.filter(x => x !== t)); setScrn(screened.filter(x => x.ticker !== t)); };
  const fmt = (v?: number) => v && v > 0 ? v.toFixed(2) : '—';

  return (
    <div style={{ padding: '2rem', maxWidth: 1400, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '2rem', borderBottom: '1px solid #1a2035', paddingBottom: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <div>
            <div style={{ fontSize: '0.65rem', letterSpacing: '3px', color: GOLD, marginBottom: 4 }}>SURVEILLANCE</div>
            <h2 style={{ margin: 0, fontSize: '1.8rem', fontFamily: '"Playfair Display", serif', color: '#e8e8e8', fontWeight: 400 }}>
              Univers d'investissement
            </h2>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <input value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && add()}
              placeholder="AAPL, MC.PA, MSFT…"
              style={{
                width: 280, padding: '0.6rem 1rem',
                background: '#1a2035', border: '1px solid #2a3555',
                borderRadius: 4, color: '#e8e8e8', fontSize: '0.85rem',
                fontFamily: '"JetBrains Mono", monospace',
                outline: 'none',
              }} />
            <button onClick={add} disabled={loading} style={{
              padding: '0.6rem 1.5rem', background: GOLD, color: '#0a0f1e',
              border: 'none', borderRadius: 4, cursor: 'pointer',
              fontWeight: 700, fontSize: '0.8rem', letterSpacing: '1px',
            }}>{loading ? '…' : 'AJOUTER'}</button>
          </div>
        </div>
      </div>

      {/* Stats bar */}
      {tickers.length > 0 && (
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
          {[
            { label: 'TITRES', value: tickers.length },
            { label: 'ÉTHIQUES', value: screened.filter(s => s.is_ethical).length },
            { label: 'CHARIA', value: screened.filter(s => s.is_sharia).length },
            { label: 'EXCLUS', value: screened.filter(s => !s.is_ethical).length },
          ].map(stat => (
            <div key={stat.label} style={{
              flex: 1, padding: '1rem 1.5rem',
              background: '#1a2035', borderRadius: 6,
              border: '1px solid #2a3555',
            }}>
              <div style={{ fontSize: '0.6rem', letterSpacing: '2px', color: '#666', marginBottom: 4 }}>{stat.label}</div>
              <div style={{ fontSize: '1.8rem', fontWeight: 700, color: GOLD, fontFamily: '"JetBrains Mono", monospace' }}>{stat.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Table */}
      <div style={{ background: '#111827', borderRadius: 8, overflow: 'hidden', border: '1px solid #1e2d4a' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
          <thead>
            <tr style={{ background: '#0d1528' }}>
              {['TICKER', 'NOM', 'DERNIER', 'BID', 'ASK', 'VOLUME', 'VAR. %', 'ÉTHIQUE', 'CHARIA', ''].map(h => (
                <th key={h} style={{ padding: '0.75rem 1rem', textAlign: 'left', fontSize: '0.65rem', letterSpacing: '2px', color: '#666', fontWeight: 600, borderBottom: '1px solid #1e2d4a' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tickers.map((t, i) => {
              const q = quotes[t];
              const s = screened.find(x => x.ticker === t);
              const last = q?.last && q.last > 0 ? q.last : undefined;
              const chg = q?.change_pct && q.last > 0 ? q.change_pct : undefined;
              return (
                <tr key={t} style={{ borderBottom: '1px solid #1a2035', background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)' }}>
                  <td style={{ padding: '0.85rem 1rem' }}>
                    <span style={{ fontFamily: '"JetBrains Mono", monospace', fontWeight: 600, color: '#e8e8e8', fontSize: '0.85rem' }}>{t}</span>
                  </td>
                  <td style={{ padding: '0.85rem 1rem', color: '#aaa', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {s?.name && s.name !== t ? s.name : <span style={{ color: '#444' }}>—</span>}
                  </td>
                  <td style={{ padding: '0.85rem 1rem', fontFamily: '"JetBrains Mono", monospace', fontWeight: 600, color: last ? '#e8e8e8' : '#444' }}>
                    {fmt(last)}
                  </td>
                  <td style={{ padding: '0.85rem 1rem', fontFamily: '"JetBrains Mono", monospace', color: '#888' }}>{fmt(q?.bid)}</td>
                  <td style={{ padding: '0.85rem 1rem', fontFamily: '"JetBrains Mono", monospace', color: '#888' }}>{fmt(q?.ask)}</td>
                  <td style={{ padding: '0.85rem 1rem', color: '#888' }}>{q?.volume && q.volume > 0 ? q.volume.toLocaleString('fr-FR') : '—'}</td>
                  <td style={{ padding: '0.85rem 1rem' }}>
                    {chg !== undefined ? (
                      <span style={{
                        color: chg >= 0 ? GREEN : RED, fontWeight: 700,
                        fontFamily: '"JetBrains Mono", monospace',
                        padding: '0.2rem 0.5rem',
                        background: chg >= 0 ? 'rgba(29,140,65,0.1)' : 'rgba(184,36,36,0.1)',
                        borderRadius: 3,
                      }}>{chg >= 0 ? '+' : ''}{chg.toFixed(2)}%</span>
                    ) : <span style={{ color: '#444' }}>—</span>}
                  </td>
                  <td style={{ padding: '0.85rem 1rem' }}><Badge passed={s?.is_ethical} /></td>
                  <td style={{ padding: '0.85rem 1rem' }}><Badge passed={s?.is_sharia} /></td>
                  <td style={{ padding: '0.85rem 1rem' }}>
                    <button onClick={() => remove(t)} style={{ background: 'none', border: '1px solid #2a3555', color: '#666', cursor: 'pointer', borderRadius: 3, padding: '0.2rem 0.5rem', fontSize: '0.7rem' }}>✕</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!tickers.length && (
          <div style={{ padding: '4rem', textAlign: 'center', color: '#444' }}>
            <div style={{ fontSize: '2rem', marginBottom: '1rem', opacity: 0.3 }}>◎</div>
            <div style={{ fontSize: '0.85rem', letterSpacing: '1px' }}>Aucun titre. Saisissez des tickers ci-dessus.</div>
          </div>
        )}
      </div>
    </div>
  );
}

function Badge({ passed }: { passed?: boolean }) {
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
