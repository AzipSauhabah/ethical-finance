// Backtest panel: pick strategy & params, fire backtest, render results.
// © 2024 Sauhabah

import { useEffect, useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, CartesianGrid, Legend,
} from 'recharts';
import { api } from '../utils/api';
import type { BacktestParams, StrategyMeta, Tearsheet } from '../types';

interface Props {
  tickers: string[];
}

export default function BacktestPanel({ tickers }: Props) {
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
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
  });
  const [result, setResult] = useState<Tearsheet | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    api.strategies().then((r) => setStrategies(r.strategies)).catch(console.error);
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
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url;
    a.download = `rapport_${params.strategy}_${new Date().toISOString().slice(0, 10)}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ padding: '1rem' }}>
      <h2 style={{ color: '#142340' }}>Backtest & Performance</h2>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem', margin: '1rem 0' }}>
        <Field label="Stratégie">
          <select
            value={params.strategy}
            onChange={(e) => setParams({ ...params, strategy: e.target.value })}
            style={input}
          >
            {strategies.map((s) => (
              <option key={s.name} value={s.name}>{s.name}</option>
            ))}
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
          <input type="number" value={params.initial_capital}
            onChange={(e) => setParams({ ...params, initial_capital: +e.target.value })}
            style={input} />
        </Field>

        <Field label="Versement mensuel (€)">
          <input type="number" value={params.monthly_contribution}
            onChange={(e) => setParams({ ...params, monthly_contribution: +e.target.value })}
            style={input} />
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
          <select value={params.account_type}
            onChange={(e) => setParams({ ...params, account_type: e.target.value as 'CTO' | 'PEA' })}
            style={input}>
            <option value="CTO">CTO</option>
            <option value="PEA">PEA</option>
          </select>
        </Field>

        <Field label="Rebalance">
          <select value={params.rebalance_frequency}
            onChange={(e) => setParams({ ...params, rebalance_frequency: e.target.value as BacktestParams['rebalance_frequency'] })}
            style={input}>
            <option value="daily">Quotidien</option>
            <option value="weekly">Hebdomadaire</option>
            <option value="monthly">Mensuel</option>
            <option value="quarterly">Trimestriel</option>
          </select>
        </Field>

        <Field label="Stop-loss (%)">
          <input type="number" step="0.01"
            value={params.stop_loss_pct ?? ''}
            onChange={(e) => setParams({ ...params, stop_loss_pct: e.target.value ? +e.target.value : null })}
            style={input} />
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
            📄 Télécharger le rapport PDF (Goldman Sachs style)
          </button>
        )}
      </div>

      {error && <div style={{ color: '#b82424', marginBottom: '1rem' }}>{error}</div>}

      {result && <BacktestResults result={result} />}
    </div>
  );
}

function BacktestResults({ result }: { result: Tearsheet }) {
  const m = result.metrics;
  const pct = (v: number) => (v * 100).toFixed(2) + '%';

  return (
    <div>
      <h3 style={{ color: '#b8962f' }}>Métriques clés</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.5rem' }}>
        <MetricCard label="Rendement total"    value={pct(m.total_return)} positive={m.total_return >= 0} />
        <MetricCard label="CAGR"                value={pct(m.cagr)} positive={m.cagr >= 0} />
        <MetricCard label="Sharpe"              value={m.sharpe_ratio.toFixed(2)} />
        <MetricCard label="Sortino"             value={m.sortino_ratio.toFixed(2)} />
        <MetricCard label="Calmar"              value={m.calmar_ratio.toFixed(2)} />
        <MetricCard label="Volatilité ann."     value={pct(m.annualised_volatility)} />
        <MetricCard label="Max Drawdown"        value={pct(m.max_drawdown)} positive={false} />
        <MetricCard label="VaR 95% (1j)"        value={pct(m.var_95)} positive={false} />
        <MetricCard label="CVaR 95%"            value={pct(m.cvar_95)} positive={false} />
        <MetricCard label="Hit Rate"            value={pct(m.hit_rate)} />
        <MetricCard label="Profit Factor"       value={m.profit_factor.toFixed(2)} />
        {m.beta !== undefined &&
          <MetricCard label="Bêta" value={m.beta.toFixed(2)} />}
        {m.alpha_jensen !== undefined &&
          <MetricCard label="Alpha (annuel)" value={pct(m.alpha_jensen)} positive={m.alpha_jensen >= 0} />}
        {m.information_ratio !== undefined &&
          <MetricCard label="Information Ratio" value={m.information_ratio.toFixed(2)} />}
      </div>

      <h3 style={{ color: '#b8962f', marginTop: '1.5rem' }}>NAV portefeuille</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={result.nav_chart}>
          <CartesianGrid stroke="#eee" />
          <XAxis dataKey="date" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} domain={['dataMin', 'dataMax']} />
          <Tooltip />
          <Line type="monotone" dataKey="nav" stroke="#142340" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>

      <h3 style={{ color: '#b8962f', marginTop: '1.5rem' }}>Drawdown</h3>
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={result.drawdown_chart}>
          <CartesianGrid stroke="#eee" />
          <XAxis dataKey="date" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => (v * 100).toFixed(0) + '%'} />
          <Tooltip formatter={(v: number) => (v * 100).toFixed(2) + '%'} />
          <Area type="monotone" dataKey="drawdown" stroke="#b82424" fill="#b82424" fillOpacity={0.2} />
        </AreaChart>
      </ResponsiveContainer>

      <h3 style={{ color: '#b8962f', marginTop: '1.5rem' }}>Tests de résistance</h3>
      <table style={{ width: '100%', fontSize: '0.85rem', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ background: '#142340', color: '#fff' }}>
            <th style={cell}>Scénario</th><th style={cell}>Rendement</th>
            <th style={cell}>Max DD</th><th style={cell}>Volatilité</th>
            <th style={cell}>VaR 95%</th><th style={cell}>Sharpe</th>
          </tr>
        </thead>
        <tbody>
          {result.stress_tests.map((s) => (
            <tr key={s.scenario} style={{ borderBottom: '1px solid #eee' }}>
              <td style={cell}>{s.label}</td>
              <td style={cell}>{s.total_return !== undefined ? pct(s.total_return) : '—'}</td>
              <td style={cell}>{s.max_drawdown !== undefined ? pct(s.max_drawdown) : '—'}</td>
              <td style={cell}>{s.volatility !== undefined ? pct(s.volatility) : '—'}</td>
              <td style={cell}>{s.var_95 !== undefined ? pct(s.var_95) : '—'}</td>
              <td style={cell}>{s.sharpe !== undefined ? s.sharpe.toFixed(2) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 style={{ color: '#b8962f', marginTop: '1.5rem' }}>Détail des coûts</h3>
      <p style={{ fontSize: '0.9rem' }}>
        Commissions de courtage : <strong>{result.cost_summary.total_costs_eur.toFixed(2)} €</strong> ·
        Taxes (PFU + TTF) : <strong>{result.cost_summary.total_taxes_eur.toFixed(2)} €</strong> ·
        Coût total / NAV : <strong>{pct(result.cost_summary.cost_pct_nav)}</strong>
      </p>

      <p style={{ fontSize: '0.75rem', color: '#666', marginTop: '2rem' }}>
        {result.meta.disclaimer}
      </p>
    </div>
  );
}

function MetricCard({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  return (
    <div style={{
      padding: '0.75rem', background: '#f8f8fb',
      border: '1px solid #e1e1ea', borderRadius: 4,
    }}>
      <div style={{ fontSize: '0.7rem', color: '#666', textTransform: 'uppercase' }}>{label}</div>
      <div style={{
        fontSize: '1.1rem', fontWeight: 700, marginTop: '0.25rem',
        color: positive === true ? '#1d8c41' : positive === false ? '#b82424' : '#142340',
      }}>{value}</div>
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

const input: React.CSSProperties = {
  padding: '0.4rem', border: '1px solid #ccc', borderRadius: 4, fontSize: '0.85rem',
};
const btnPrimary: React.CSSProperties = {
  padding: '0.6rem 1.2rem', background: '#142340', color: '#fff',
  border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600,
};
const btnGold: React.CSSProperties = {
  padding: '0.6rem 1.2rem', background: '#b8962f', color: '#fff',
  border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600,
};
const cell: React.CSSProperties = { padding: '0.4rem', textAlign: 'left' };
