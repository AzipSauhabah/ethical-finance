// BacktestPanel.tsx — Goldman Sachs dark theme
// © 2024 Sauhabah

import { useEffect, useState } from 'react';
import {
  XAxis, YAxis, Tooltip, Legend, ResponsiveContainer,
  AreaChart, Area, CartesianGrid,
  BarChart, Bar, ComposedChart, Line,
  PieChart, Pie, Cell,
} from 'recharts';
import { api } from '../utils/api';
import type { BacktestParams, StrategyMeta, Tearsheet } from '../types';

const NAVY = '#0d1528';
const GOLD = '#b8962f';
const GREEN = '#1d8c41';
const RED = '#b82424';
const CARD_BG = '#111827';
const BORDER = '#1e2d4a';

interface Props {
  tickers: string[];
  onStrategyChange?: (s: string) => void;
  defaultStrategy?: string;
}

const select: React.CSSProperties = {
  padding: '0.5rem 0.75rem',
  background: '#1a2035',
  border: '1px solid #2a3555',
  borderRadius: 4,
  color: '#e8e8e8',
  fontSize: '0.82rem',
  width: '100%',
  outline: 'none',
  cursor: 'pointer',
};

const inputStyle: React.CSSProperties = {
  ...select,
  fontFamily: '"JetBrains Mono", monospace',
};

function Label({ children }: { children: React.ReactNode }) {
  return <div style={{ fontSize: '0.6rem', letterSpacing: '2px', color: '#555', marginBottom: 4, textTransform: 'uppercase' as const }}>{children}</div>;
}

function KpiCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  const isNeg = value.startsWith('-');
  const isPos = value.startsWith('+') || (!isNeg && parseFloat(value) > 0 && value.includes('%'));
  return (
    <div style={{ background: CARD_BG, border: `1px solid ${BORDER}`, borderRadius: 6, padding: '0.875rem 1rem' }}>
      <div style={{ fontSize: '0.6rem', letterSpacing: '2px', color: '#555', marginBottom: 6 }}>{label}</div>
      <div style={{
        fontSize: '1.2rem', fontWeight: 700,
        fontFamily: '"JetBrains Mono", monospace',
        color: isNeg ? RED : isPos ? GREEN : '#e8e8e8',
      }}>{value}</div>
      {sub && <div style={{ fontSize: '0.65rem', color: '#444', marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

const CustomTooltip = ({ active, payload, label, fmt }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: '#0d1528', border: '1px solid #2a3555', borderRadius: 4, padding: '0.5rem 0.75rem', fontSize: '0.75rem' }}>
      <div style={{ color: '#666', marginBottom: 4, fontFamily: '"JetBrains Mono", monospace' }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.name} style={{ color: p.color, fontFamily: '"JetBrains Mono", monospace' }}>
          {p.name}: {fmt ? fmt(p.value) : p.value}
        </div>
      ))}
    </div>
  );
};

export default function BacktestPanel({ tickers, onStrategyChange, defaultStrategy }: Props) {
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [result, setResult] = useState<Tearsheet | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);

  useEffect(() => {
    if (defaultStrategy) setParams(p => ({ ...p, strategy: defaultStrategy }));
  }, [defaultStrategy]);

  const [params, setParams] = useState<BacktestParams>({
    tickers,
    strategy: 'buy_hold',
    period: '5y',
    initial_capital: 30000,
    monthly_contribution: 0,
    broker: 'degiro',
    account_type: 'CTO',
    rebalance_frequency: 'monthly',
    max_position_pct: 0.25,
    stop_loss_pct: 0.10,
    use_var_constraint: false,
    benchmark: '^FCHI',
    require_ethical: false,
    require_sharia: false,
  });

  useEffect(() => { api.strategies().then(r => setStrategies(r.strategies)).catch(console.error); }, []);
  useEffect(() => { setParams(p => ({ ...p, tickers })); }, [tickers]);

  const run = async () => {
    if (!tickers.length) { setError('Ajoutez au moins un ticker.'); return; }
    setLoading(true); setError(null);
    try { setResult(await api.backtest(params)); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : 'Erreur'); }
    finally { setLoading(false); }
  };

  const downloadPdf = async () => {
    setPdfLoading(true);
    try {
      const blob = await api.backtestPdf(params);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `sauhabah_${params.strategy}_${new Date().toISOString().slice(0, 10)}.pdf`;
      a.click(); URL.revokeObjectURL(url);
    } finally { setPdfLoading(false); }
  };

  const m = result?.metrics;
  const pct = (v?: number | null) => v == null ? 'N/A' : (v >= 0 ? '+' : '') + (v * 100).toFixed(2) + '%';
  const eur = (v?: number | null) => v == null ? 'N/A' : v.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';

  const [navCcy, setNavCcy] = useState<string>('EUR');
  const CCY_LABELS: Record<string, string> = {
    EUR: 'EUR €', USD: 'USD $', GBP: 'GBP £', CHF: 'CHF', JPY: 'JPY ¥', XAU: 'Or (oz)',
  };

  const navMultiCcy = result?.nav_multiccy || {};
  const activeNavData = navMultiCcy[navCcy] || result?.nav_chart || [];

  const navWithBench = activeNavData.map((d: any, i: number) => ({
    date: d.date,
    NAV: d.nav,
    Benchmark: navCcy === 'EUR' ? result?.benchmark_chart?.[i]?.nav : undefined,
  }));

  const allocData = (result?.allocation_chart || []).map((d: any) => ({
    date: d.date, Investi: d.invested, Cash: d.cash,
  }));

  const costData = (result?.cost_chart || []).map((d: any) => ({
    date: d.date, Commissions: d.costs, Taxes: d.total - d.costs,
  }));

  const cb = (result?.cost_breakdown || {}) as any;
  const pieData = [
    { name: 'Commissions', value: +(cb.commission || 0).toFixed(2) },
    { name: 'Slippage', value: +(cb.slippage || 0).toFixed(2) },
    { name: 'Impact marché', value: +(cb.market_impact || 0).toFixed(2) },
    { name: 'FX Spread', value: +(cb.fx_spread || 0).toFixed(2) },
    { name: 'TTF', value: +(cb.ttf || 0).toFixed(2) },
    { name: 'Stamp Duty', value: +(cb.stamp_duty || 0).toFixed(2) },
  ].filter(d => d.value > 0);

  const stressData = (result?.stress_tests || [])
    .filter((s: any) => s.total_return !== undefined)
    .map((s: any) => ({
      name: s.label,
      Stratégie: +((s.total_return ?? 0) * 100).toFixed(2),
      Benchmark: +((s.benchmark?.total_return ?? 0) * 100).toFixed(2),
    }));

  const PIE_COLORS = [NAVY, GOLD, '#8a6f9c', '#3e8260'];

  return (
    <div style={{ padding: '2rem', maxWidth: 1400, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '2rem', borderBottom: '1px solid #1a2035', paddingBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <div style={{ fontSize: '0.65rem', letterSpacing: '3px', color: GOLD, marginBottom: 4 }}>ANALYSE QUANTITATIVE</div>
          <h2 style={{ margin: 0, fontSize: '1.8rem', fontFamily: '"Playfair Display", serif', color: '#e8e8e8', fontWeight: 400 }}>
            Backtest & Performance
          </h2>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button onClick={run} disabled={loading} style={{
            padding: '0.6rem 2rem', background: loading ? '#1a2035' : GOLD,
            color: loading ? '#666' : '#0a0f1e', border: 'none', borderRadius: 4,
            fontWeight: 700, fontSize: '0.8rem', letterSpacing: '1.5px', cursor: loading ? 'wait' : 'pointer',
          }}>{loading ? 'CALCUL…' : 'LANCER'}</button>
          {result && (
            <button onClick={downloadPdf} disabled={pdfLoading} style={{
              padding: '0.6rem 1.5rem', background: 'transparent',
              color: GOLD, border: `1px solid ${GOLD}`, borderRadius: 4,
              fontWeight: 600, fontSize: '0.78rem', letterSpacing: '1px', cursor: 'pointer',
            }}>{pdfLoading ? '…' : '↓ RAPPORT PDF'}</button>
          )}
        </div>
      </div>

      {/* Params grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.75rem', marginBottom: '1.5rem' }}>
        <div><Label>Stratégie</Label>
          <select value={params.strategy} onChange={e => { setParams({ ...params, strategy: e.target.value }); onStrategyChange?.(e.target.value); }} style={select}>
            {strategies.map(s => <option key={s.name} value={s.name}>{s.name}</option>)}
          </select>
        </div>
        <div><Label>Période</Label>
          <select value={params.period} onChange={e => setParams({ ...params, period: e.target.value })} style={select}>
            {[['1y','1 an'],['3y','3 ans'],['5y','5 ans'],['10y','10 ans'],['20y','20 ans']].map(([v,l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div><Label>Capital initial (€)</Label>
          <input type="number" value={params.initial_capital} onChange={e => setParams({ ...params, initial_capital: +e.target.value })} style={inputStyle} />
        </div>
        <div><Label>Versement mensuel (€)</Label>
          <input type="number" value={params.monthly_contribution} onChange={e => setParams({ ...params, monthly_contribution: +e.target.value })} style={inputStyle} />
        </div>
        <div><Label>Courtier</Label>
          <select value={params.broker} onChange={e => setParams({ ...params, broker: e.target.value })} style={select}>
            {['degiro','interactive_brokers','trade_republic','boursorama','default'].map(b => <option key={b} value={b}>{b}</option>)}
          </select>
        </div>
        <div><Label>Compte</Label>
          <select value={params.account_type} onChange={e => setParams({ ...params, account_type: e.target.value as 'CTO' | 'PEA' })} style={select}>
            <option value="CTO">CTO</option><option value="PEA">PEA</option>
          </select>
        </div>
        <div><Label>Rebalancement</Label>
          <select value={params.rebalance_frequency} onChange={e => setParams({ ...params, rebalance_frequency: e.target.value as BacktestParams['rebalance_frequency'] })} style={select}>
            {[['daily','Quotidien'],['weekly','Hebdo'],['monthly','Mensuel'],['quarterly','Trimestriel'],['annually','Annuel']].map(([v,l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div><Label>Benchmark</Label>
          <select value={params.benchmark} onChange={e => setParams({ ...params, benchmark: e.target.value })} style={select}>
            {[['^FCHI','CAC 40'],['^GSPC','S&P 500'],['^STOXX50E','EuroStoxx 50'],['^GDAXI','DAX']].map(([v,l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div><Label>Stop-loss (%)</Label>
          <input type="number" step="0.01" value={params.stop_loss_pct ?? ''} onChange={e => setParams({ ...params, stop_loss_pct: e.target.value === '' ? null : +e.target.value })} style={inputStyle} />
        </div>
        <div><Label>Position max (%)</Label>
          <input type="number" step="0.05" value={params.max_position_pct} onChange={e => setParams({ ...params, max_position_pct: +e.target.value })} style={inputStyle} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', paddingTop: '1.2rem' }}>
          <input type="checkbox" id="ethical" checked={params.require_ethical} onChange={e => setParams({ ...params, require_ethical: e.target.checked })} />
          <label htmlFor="ethical" style={{ fontSize: '0.75rem', color: '#888', cursor: 'pointer' }}>Éthique uniquement</label>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', paddingTop: '1.2rem' }}>
          <input type="checkbox" id="var" checked={params.use_var_constraint} onChange={e => setParams({ ...params, use_var_constraint: e.target.checked })} />
          <label htmlFor="var" style={{ fontSize: '0.75rem', color: '#888', cursor: 'pointer' }}>Contrainte VaR</label>
        </div>
      </div>

      {error && <div style={{ background: 'rgba(184,36,36,0.1)', border: '1px solid #b82424', borderRadius: 4, padding: '0.75rem 1rem', color: '#b82424', fontSize: '0.82rem', marginBottom: '1rem' }}>{error}</div>}

      {/* RESULTS */}
      {result && m && (
        <div>
          {/* KPIs */}
          <div style={{ fontSize: '0.65rem', letterSpacing: '3px', color: GOLD, marginBottom: '0.75rem', marginTop: '0.5rem' }}>MÉTRIQUES DE PERFORMANCE</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '0.5rem', marginBottom: '1.5rem' }}>
            <KpiCard label="RETURN TOTAL" value={pct(m.total_return)} />
            <KpiCard label="CAGR" value={pct(m.cagr)} />
            <KpiCard label="SHARPE" value={(m.sharpe_ratio ?? 0).toFixed(2)} sub="Taux sans risque 2%" />
            <KpiCard label="SORTINO" value={(m.sortino_ratio ?? 0).toFixed(2)} />
            <KpiCard label="CALMAR" value={(m.calmar_ratio ?? 0).toFixed(2)} />
            <KpiCard label="MAX DRAWDOWN" value={pct(m.max_drawdown)} />
            <KpiCard label="VOLATILITÉ" value={(( m.annualised_volatility ?? 0) * 100).toFixed(2) + "%"} sub="Annualisée" />
            <KpiCard label="BETA" value={(m.beta ?? 0).toFixed(3)} />
            <KpiCard label="ALPHA JENSEN" value={(m.alpha_jensen ?? 0).toFixed(4)} sub="Annualisé" />
            <KpiCard label="VAR 95%" value={((m.var_95 ?? 0) * 100).toFixed(2) + "%"} sub="Journalière" />
            <KpiCard label="CVAR 95%" value={((m.cvar_95 ?? 0) * 100).toFixed(2) + "%"} sub="Expected Shortfall" />
            <KpiCard label="HIT RATE" value={pct(m.hit_rate)} />
          </div>

          {/* Sélecteur devise NAV */}
          {Object.keys(navMultiCcy).length > 1 && (
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.7rem', color: '#555', alignSelf: 'center' }}>NAV en :</span>
              {Object.keys(CCY_LABELS).filter(c => navMultiCcy[c] || c === 'EUR').map(ccy => (
                <button key={ccy} onClick={() => setNavCcy(ccy)} style={{
                  padding: '0.2rem 0.6rem',
                  background: navCcy === ccy ? 'rgba(184,150,47,0.15)' : '#0d1528',
                  border: `1px solid ${navCcy === ccy ? '#b8962f' : '#1e2d4a'}`,
                  borderRadius: 4, color: navCcy === ccy ? '#b8962f' : '#555',
                  fontSize: '0.72rem', cursor: 'pointer',
                }}>
                  {CCY_LABELS[ccy]}
                </button>
              ))}
            </div>
          )}

          {/* NAV Chart */}
          {navWithBench.length > 0 && (
            <div style={{ background: CARD_BG, border: `1px solid ${BORDER}`, borderRadius: 8, padding: '1.5rem', marginBottom: '1rem' }}>
              <div style={{ fontSize: '0.65rem', letterSpacing: '2px', color: '#555', marginBottom: '1rem' }}>ÉVOLUTION DU PORTEFEUILLE VS BENCHMARK</div>
              <ResponsiveContainer width="100%" height={280}>
                <ComposedChart data={navWithBench}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1a2035" />
                  <XAxis dataKey="date" tick={{ fontSize: 9, fill: '#555' }} tickLine={false} />
                  <YAxis tick={{ fontSize: 9, fill: '#555' }} tickLine={false} axisLine={false} tickFormatter={v => v.toLocaleString('fr-FR')} />
                  <Tooltip content={<CustomTooltip fmt={(v: number) => eur(v)} />} />
                  <Legend wrapperStyle={{ fontSize: '0.75rem', color: '#888' }} />
                  <Area type="monotone" dataKey="NAV" stroke="#4a7fd4" fill="rgba(74,127,212,0.15)" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="Benchmark" stroke={GOLD} strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Drawdown + Allocation row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
            {result.drawdown_chart?.length > 0 && (
              <div style={{ background: CARD_BG, border: `1px solid ${BORDER}`, borderRadius: 8, padding: '1.5rem' }}>
                <div style={{ fontSize: '0.65rem', letterSpacing: '2px', color: '#555', marginBottom: '1rem' }}>DRAWDOWN</div>
                <ResponsiveContainer width="100%" height={180}>
                  <AreaChart data={result.drawdown_chart}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1a2035" />
                    <XAxis dataKey="date" tick={{ fontSize: 8, fill: '#555' }} tickLine={false} />
                    <YAxis tick={{ fontSize: 8, fill: '#555' }} tickLine={false} axisLine={false} tickFormatter={v => (v * 100).toFixed(0) + '%'} />
                    <Tooltip content={<CustomTooltip fmt={(v: number) => (v * 100).toFixed(2) + '%'} />} />
                    <Area type="monotone" dataKey="drawdown" stroke={RED} fill="rgba(184,36,36,0.2)" strokeWidth={1.5} dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
            {allocData.length > 0 && (
              <div style={{ background: CARD_BG, border: `1px solid ${BORDER}`, borderRadius: 8, padding: '1.5rem' }}>
                <div style={{ fontSize: '0.65rem', letterSpacing: '2px', color: '#555', marginBottom: '1rem' }}>ALLOCATION CASH VS INVESTI</div>
                <ResponsiveContainer width="100%" height={180}>
                  <AreaChart data={allocData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1a2035" />
                    <XAxis dataKey="date" tick={{ fontSize: 8, fill: '#555' }} tickLine={false} />
                    <YAxis tick={{ fontSize: 8, fill: '#555' }} tickLine={false} axisLine={false} />
                    <Tooltip content={<CustomTooltip fmt={(v: number) => eur(v)} />} />
                    <Legend wrapperStyle={{ fontSize: '0.72rem', color: '#888' }} />
                    <Area type="monotone" dataKey="Investi" stackId="1" stroke="#4a7fd4" fill="rgba(74,127,212,0.4)" strokeWidth={1} dot={false} />
                    <Area type="monotone" dataKey="Cash" stackId="1" stroke={GOLD} fill="rgba(184,150,47,0.3)" strokeWidth={1} dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Costs row */}
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
            {costData.length > 0 && (
              <div style={{ background: CARD_BG, border: `1px solid ${BORDER}`, borderRadius: 8, padding: '1.5rem' }}>
                <div style={{ fontSize: '0.65rem', letterSpacing: '2px', color: '#555', marginBottom: '1rem' }}>COÛTS CUMULÉS (€)</div>
                <ResponsiveContainer width="100%" height={160}>
                  <AreaChart data={costData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1a2035" />
                    <XAxis dataKey="date" tick={{ fontSize: 8, fill: '#555' }} tickLine={false} />
                    <YAxis tick={{ fontSize: 8, fill: '#555' }} tickLine={false} axisLine={false} />
                    <Tooltip content={<CustomTooltip fmt={(v: number) => eur(v)} />} />
                    <Legend wrapperStyle={{ fontSize: '0.72rem', color: '#888' }} />
                    <Area type="monotone" dataKey="Commissions" stackId="1" stroke="#4a7fd4" fill="rgba(74,127,212,0.4)" strokeWidth={1} dot={false} />
                    <Area type="monotone" dataKey="Taxes" stackId="1" stroke={RED} fill="rgba(184,36,36,0.3)" strokeWidth={1} dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
            {pieData.length > 0 && (
              <div style={{ background: CARD_BG, border: `1px solid ${BORDER}`, borderRadius: 8, padding: '1.5rem' }}>
                <div style={{ fontSize: '0.65rem', letterSpacing: '2px', color: '#555', marginBottom: '1rem' }}>RÉPARTITION COÛTS</div>
                <PieChart width={200} height={160}>
                  <Pie data={pieData} cx={100} cy={75} outerRadius={65} dataKey="value" labelLine={false}>
                    {pieData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(v: number) => [eur(v), '']} />
                </PieChart>
                <div style={{ marginTop: '0.5rem' }}>
                  {pieData.map((d, i) => (
                    <div key={d.name} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.7rem', color: '#888', marginBottom: 2 }}>
                      <span style={{ width: 8, height: 8, borderRadius: 2, background: PIE_COLORS[i % PIE_COLORS.length], display: 'inline-block', flexShrink: 0 }} />
                      {d.name}: {eur(d.value)}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Stress tests */}
          {stressData.length > 0 && (
            <div style={{ background: CARD_BG, border: `1px solid ${BORDER}`, borderRadius: 8, padding: '1.5rem', marginBottom: '1rem' }}>
              <div style={{ fontSize: '0.65rem', letterSpacing: '2px', color: '#555', marginBottom: '1rem' }}>STRESS TESTS — CRISES HISTORIQUES</div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={stressData} margin={{ bottom: 40 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1a2035" />
                  <XAxis dataKey="name" tick={{ fontSize: 8, fill: '#555' }} angle={-20} textAnchor="end" tickLine={false} />
                  <YAxis tick={{ fontSize: 8, fill: '#555' }} tickLine={false} axisLine={false} tickFormatter={v => v + '%'} />
                  <Tooltip content={<CustomTooltip fmt={(v: number) => v.toFixed(2) + '%'} />} />
                  <Legend wrapperStyle={{ fontSize: '0.72rem', color: '#888' }} />
                  <Bar dataKey="Stratégie" fill="#4a7fd4" radius={[2,2,0,0]} />
                  <Bar dataKey="Benchmark" fill={GOLD} radius={[2,2,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Positions summary */}
          {result.positions && (
            <div style={{ background: CARD_BG, border: `1px solid ${BORDER}`, borderRadius: 8, padding: '1.5rem' }}>
              <div style={{ fontSize: '0.65rem', letterSpacing: '2px', color: '#555', marginBottom: '1rem' }}>POSITIONS FINALES</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '0.5rem' }}>
                {[
                  ['NAV', eur(result.positions?.nav_eur)],
                  ['CASH', eur(result.positions?.cash_eur)],
                  ['INVESTI', eur(result.positions?.invested_eur)],
                  ['TRADES', result.positions.n_trades?.toString() || '0'],
                  ['COÛTS', eur(result.positions.total_costs_eur)],
                  ['TAXES', eur(result.positions.total_taxes_eur)],
                ].map(([k, v]) => (
                  <div key={k} style={{ padding: '0.75rem', background: '#0d1528', borderRadius: 4, border: '1px solid #1a2035' }}>
                    <div style={{ fontSize: '0.6rem', letterSpacing: '2px', color: '#444', marginBottom: 4 }}>{k}</div>
                    <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#e8e8e8', fontFamily: '"JetBrains Mono", monospace' }}>{v}</div>
                  </div>
                ))}
              </div>

              {/* Détail des coûts */}
              {cb && Object.keys(cb).length > 0 && (
                <div style={{ marginTop: '1rem', padding: '1rem', background: '#0d1528', borderRadius: 6, border: '1px solid #1a2035' }}>
                  <div style={{ fontSize: '0.6rem', letterSpacing: '2px', color: '#555', marginBottom: '0.75rem' }}>DÉCOMPOSITION DES COÛTS</div>
                  <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                    {[
                      { label: 'Commissions', key: 'commission', color: '#b8962f' },
                      { label: 'Slippage', key: 'slippage', color: '#5b8dee' },
                      { label: 'Impact marché', key: 'market_impact', color: '#8a6f9c' },
                      { label: 'Spread FX', key: 'fx_spread', color: '#1d9e75' },
                      { label: 'TTF', key: 'ttf', color: '#f87171' },
                      { label: 'Stamp Duty', key: 'stamp_duty', color: '#fb923c' },
                    ].filter(item => (cb[item.key] || 0) > 0).map(item => (
                      <div key={item.key} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <div style={{ width: 8, height: 8, borderRadius: 2, background: item.color }} />
                        <span style={{ fontSize: '0.72rem', color: '#666' }}>{item.label}</span>
                        <span style={{ fontSize: '0.72rem', color: '#e8e8e8', fontFamily: '"JetBrains Mono", monospace' }}>
                          {eur(cb[item.key])}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
