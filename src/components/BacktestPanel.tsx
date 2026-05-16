// Backtest panel: pick strategy & params, fire backtest, render results.
// © 2024 Sauhabah

import { useEffect, useState } from 'react';
import {
  XAxis, YAxis, Tooltip, Legend,
  AreaChart, Area, CartesianGrid,
  BarChart, Bar, LineChart, Line,
  PieChart, Pie, Cell,
} from 'recharts';
import { api } from '../utils/api';
import type { BacktestParams, StrategyMeta, Tearsheet } from '../types';

interface Props {
  tickers: string[];
}

export default function BacktestPanel({ tickers }: Props) {
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [result, setResult] = useState<Tearsheet | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    benchmark: '^FCHI',
    require_ethical: false,
    require_sharia: false,
  });

  useEffect(() => {
    api.strategies()
      .then((r) => setStrategies(r.strategies))
      .catch(console.error);
  }, []);

  useEffect(() => {
    setParams((p) => ({ ...p, tickers }));
  }, [tickers]);

  const run = async () => {
    if (!tickers.length) {
      setError('Ajoutez au moins un ticker.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await api.backtest(params);
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erreur inconnue');
    } finally {
      setLoading(false);
    }
  };

  const downloadPdf = async () => {
    const blob = await api.backtestPdf(params);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `rapport_${params.strategy}_${new Date().toISOString().slice(0, 10)}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ padding: '1rem' }}>
      <h2 style={{ color: '#142340' }}>Backtest & Performance</h2>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: '0.75rem',
        margin: '1rem 0'
      }}>
        <Field label="Stratégie">
          <select value={params.strategy} onChange={(e) => setParams({ ...params, strategy: e.target.value })} style={input}>
            {strategies.map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
          </select>
        </Field>

        <Field label="Période">
          <select value={params.period} onChange={(e) => setParams({ ...params, period: e.target.value })} style={input}>
            <option value="1y">1 an</option>
            <option value="3y">3 ans</option>
            <option value="5y">5 ans</option>
            <option value="10y">10 ans</option>
            <option value="15y">15 ans</option>
            <option value="20y">20 ans</option>
          </select>
        </Field>

        <Field label="Capital initial (€)">
          <input type="number" value={params.initial_capital} onChange={(e) => setParams({ ...params, initial_capital: +e.target.value })} style={input} />
        </Field>

        <Field label="Versement mensuel (€)">
          <input type="number" value={params.monthly_contribution} onChange={(e) => setParams({ ...params, monthly_contribution: +e.target.value })} style={input} />
        </Field>

        <Field label="Courtier">
          <select value={params.broker} onChange={(e) => setParams({ ...params, broker: e.target.value })} style={input}>
            <option value="degiro">Degiro</option>
            <option value="fortuneo">Fortuneo</option>
            <option value="bourse_direct">Bourse Direct</option>
            <option value="interactive_brokers">Interactive Brokers</option>
            <option value="default">Autre / défaut</option>
          </select>
        </Field>

        <Field label="Compte">
          <select value={params.account_type} onChange={(e) => setParams({ ...params, account_type: e.target.value as 'CTO' | 'PEA' })} style={input}>
            <option value="CTO">CTO</option>
            <option value="PEA">PEA</option>
          </select>
        </Field>

        <Field label="Rebalance">
          <select value={params.rebalance_frequency} onChange={(e) => setParams({ ...params, rebalance_frequency: e.target.value as BacktestParams['rebalance_frequency'] })} style={input}>
            <option value="daily">Quotidien</option>
            <option value="weekly">Hebdomadaire</option>
            <option value="monthly">Mensuel</option>
            <option value="quarterly">Trimestriel</option>
          </select>
        </Field>

        <Field label="Stop-loss (%)">
          <input type="number" step="0.01" value={params.stop_loss_pct ?? ''} onChange={(e) => setParams({ ...params, stop_loss_pct: e.target.value === '' ? 0 : +e.target.value })} style={input} />
        </Field>

        <Field label="Benchmark">
          <select value={params.benchmark} onChange={(e) => setParams({ ...params, benchmark: e.target.value })} style={input}>
            <option value="^GSPC">S&P 500</option>
            <option value="^FCHI">CAC 40</option>
            <option value="^STOXX50E">EuroStoxx 50</option>
          </select>
        </Field>
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <button onClick={run} disabled={loading} style={btnPrimary}>
          {loading ? 'Calcul en cours…' : 'Lancer le backtest'}
        </button>
        {result && (
          <button onClick={downloadPdf} style={btnGold}>
            📄 Télécharger le rapport PDF
          </button>
        )}
      </div>

      {error && <div style={{ color: '#b82424', marginBottom: '1rem' }}>{error}</div>}
      {result && <BacktestResults result={result} />}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', fontSize: '0.75rem', color: '#444' }}>
      <span style={{ marginBottom: '0.25rem' }}>{label}</span>
      {children}
    </label>
  );
}

const input: React.CSSProperties = { padding: '0.4rem', border: '1px solid #ccc', borderRadius: 4, fontSize: '0.85rem' };
const btnPrimary: React.CSSProperties = { padding: '0.6rem 1.2rem', background: '#142340', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600 };
const btnGold: React.CSSProperties = { padding: '0.6rem 1.2rem', background: '#b8962f', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600 };

const COLORS = ['#142340', '#b8962f', '#2e7d32', '#c62828', '#1565c0', '#6a1b9a', '#00838f', '#ef6c00'];

function BacktestResults({ result }: { result: Tearsheet }) {
  const m = result.metrics;
  const pct = (v: number) => (v * 100).toFixed(2) + '%';

  // Combine nav + benchmark pour le graphique principal
  const navWithBench = result.nav_chart.map((p, i) => ({
    ...p,
    benchmark: result.benchmark_chart?.[i]?.nav ?? null,
  }));

  // Coûts cumulés
  const costData = result.cost_chart?.map(p => ({
    date: p.date,
    'Commissions': +(p.costs ?? 0).toFixed(2),
    'Taxes': +(p.taxes ?? 0).toFixed(2),
  })) ?? [];

  // Allocation cash vs investi
  const allocData = result.allocation_chart?.map(p => ({
    date: p.date,
    'Investi': +(p.invested ?? 0).toFixed(2),
    'Cash': +(p.cash ?? 0).toFixed(2),
  })) ?? [];

  // Répartition des coûts (pie)
  const cb = result.cost_breakdown;
  const pieData = [
    { name: 'Commissions', value: +cb.commission.toFixed(2) },
    { name: 'Slippage', value: +cb.slippage.toFixed(2) },
    { name: 'FX Spread', value: +cb.fx_spread.toFixed(2) },
    { name: 'TTF', value: +cb.ttf.toFixed(2) },
  ].filter(d => d.value > 0);

  // Stress tests
  const stressData = result.stress_tests
    .filter(s => s.total_return !== undefined)
    .map(s => ({
      name: s.label,
      'Stratégie': +((s.total_return ?? 0) * 100).toFixed(2),
      'Benchmark': +((s.benchmark?.total_return ?? 0) * 100).toFixed(2),
    }));

  return (
    <div>
      <h3 style={{ color: '#b8962f' }}>Résultats</h3>

      {/* Métriques clés */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.5rem', marginBottom: '1.5rem' }}>
        {[
          ['Return', pct(m.total_return)],
          ['CAGR', pct(m.cagr)],
          ['Sharpe', (m.sharpe_ratio ?? 0).toFixed(2)],
          ['Sortino', (m.sortino_ratio ?? 0).toFixed(2)],
          ['Calmar', (m.calmar_ratio ?? 0).toFixed(2)],
          ['Max DD', pct(m.max_drawdown)],
          ['Vol', pct((m.annualised_volatility ?? 0))],
          ['Beta', (m.beta ?? 0).toFixed(2) ?? 'N/A'],
          ['Alpha', m.alpha_jensen?.toFixed(4) ?? 'N/A'],
          ['VaR 95%', pct(m.var_95)],
          ['CVaR 95%', pct(m.cvar_95)],
          ['Hit Rate', pct(m.hit_rate)],
        ].map(([k, v]) => (
          <div key={k} style={{ background: '#f8f8f8', padding: '0.5rem', borderRadius: 4, border: '1px solid #eee' }}>
            <div style={{ fontSize: '0.7rem', color: '#888' }}>{k}</div>
            <div style={{ fontSize: '1rem', fontWeight: 600, color: '#142340' }}>{v}</div>
          </div>
        ))}
      </div>

      {/* NAV + Benchmark */}
      {navWithBench.length > 0 && (
        <>
          <h4 style={{ color: '#142340' }}>Évolution du portefeuille vs Benchmark</h4>
          <AreaChart width={700} height={280} data={navWithBench} margin={{ top: 5, right: 20, bottom: 5, left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 9 }} />
            <YAxis tick={{ fontSize: 9 }} />
            <Tooltip formatter={(v: number) => v.toFixed(2) + ' €'} />
            <Legend />
            <Area type="monotone" dataKey="nav" stroke="#142340" fill="#e8edf5" name="NAV (€)" />
            <Line type="monotone" dataKey="benchmark" stroke="#b8962f" dot={false} name="Benchmark (€)" />
          </AreaChart>
        </>
      )}

      {/* Drawdown */}
      {result.drawdown_chart?.length > 0 && (
        <>
          <h4 style={{ color: '#142340', marginTop: '1.5rem' }}>Drawdown</h4>
          <AreaChart width={700} height={180} data={result.drawdown_chart} margin={{ top: 5, right: 20, bottom: 5, left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 9 }} />
            <YAxis tickFormatter={(v) => (v * 100).toFixed(1) + '%'} tick={{ fontSize: 9 }} />
            <Tooltip formatter={(v: number) => (v * 100).toFixed(2) + '%'} />
            <Area type="monotone" dataKey="drawdown" stroke="#b82424" fill="#f5e8e8" name="Drawdown" />
          </AreaChart>
        </>
      )}

      {/* Allocation cash vs investi */}
      {allocData.length > 0 && (
        <>
          <h4 style={{ color: '#142340', marginTop: '1.5rem' }}>Allocation Cash vs Investi</h4>
          <AreaChart width={700} height={200} data={allocData} margin={{ top: 5, right: 20, bottom: 5, left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 9 }} />
            <YAxis tick={{ fontSize: 9 }} />
            <Tooltip formatter={(v: number) => v.toFixed(2) + ' €'} />
            <Legend />
            <Area type="monotone" dataKey="Investi" stackId="1" stroke="#142340" fill="#e8edf5" />
            <Area type="monotone" dataKey="Cash" stackId="1" stroke="#b8962f" fill="#fdf3d8" />
          </AreaChart>
        </>
      )}

      {/* Coûts cumulés */}
      {costData.length > 0 && (
        <>
          <h4 style={{ color: '#142340', marginTop: '1.5rem' }}>Coûts cumulés (€)</h4>
          <AreaChart width={700} height={180} data={costData} margin={{ top: 5, right: 20, bottom: 5, left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 9 }} />
            <YAxis tick={{ fontSize: 9 }} />
            <Tooltip formatter={(v: number) => v.toFixed(2) + ' €'} />
            <Legend />
            <Area type="monotone" dataKey="Commissions" stackId="1" stroke="#142340" fill="#e8edf5" />
            <Area type="monotone" dataKey="Taxes" stackId="1" stroke="#b82424" fill="#f5e8e8" />
          </AreaChart>
        </>
      )}

      {/* Répartition des coûts (Pie) */}
      {pieData.length > 0 && (
        <>
          <h4 style={{ color: '#142340', marginTop: '1.5rem' }}>Répartition des coûts</h4>
          <div style={{ display: 'flex', alignItems: 'center', gap: '2rem' }}>
            <PieChart width={220} height={220}>
              <Pie data={pieData} cx={100} cy={100} outerRadius={90} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false}>
                {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip formatter={(v: number) => v.toFixed(2) + ' €'} />
            </PieChart>
            <div>
              {pieData.map((d, i) => (
                <div key={d.name} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, fontSize: '0.85rem' }}>
                  <span style={{ width: 12, height: 12, borderRadius: 2, background: COLORS[i % COLORS.length], display: 'inline-block' }} />
                  {d.name}: {d.value.toFixed(2)} €
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Stress tests */}
      {stressData.length > 0 && (
        <>
          <h4 style={{ color: '#142340', marginTop: '1.5rem' }}>Stress Tests — Crises historiques (%)</h4>
          <BarChart width={700} height={220} data={stressData} margin={{ top: 5, right: 20, bottom: 40, left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fontSize: 9 }} angle={-20} textAnchor="end" />
            <YAxis tickFormatter={(v) => v + '%'} tick={{ fontSize: 9 }} />
            <Tooltip formatter={(v: number) => v.toFixed(2) + '%'} />
            <Legend />
            <Bar dataKey="Stratégie" fill="#142340" />
            <Bar dataKey="Benchmark" fill="#b8962f" />
          </BarChart>
        </>
      )}

      {/* Résumé positions */}
      <h4 style={{ color: '#142340', marginTop: '1.5rem' }}>Positions finales</h4>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.5rem', marginBottom: '1rem' }}>
        {[
          ['NAV', result.positions.nav_eur.toFixed(2) + ' €'],
          ['Cash', result.positions.cash_eur.toFixed(2) + ' €'],
          ['Investi', result.positions.invested_eur.toFixed(2) + ' €'],
          ['Trades', result.positions.n_trades.toString()],
          ['Coûts totaux', result.positions.total_costs_eur.toFixed(2) + ' €'],
          ['Taxes totales', result.positions.total_taxes_eur.toFixed(2) + ' €'],
        ].map(([k, v]) => (
          <div key={k} style={{ background: '#f8f8f8', padding: '0.5rem', borderRadius: 4, border: '1px solid #eee' }}>
            <div style={{ fontSize: '0.7rem', color: '#888' }}>{k}</div>
            <div style={{ fontSize: '0.95rem', fontWeight: 600, color: '#142340' }}>{v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
