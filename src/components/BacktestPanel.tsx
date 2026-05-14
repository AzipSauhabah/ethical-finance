// Backtest panel: pick strategy & params, fire backtest, render results.
// © 2024 Sauhabah

import { useEffect, useState } from 'react';
import {
  XAxis, YAxis, Tooltip,
  AreaChart, Area, CartesianGrid,
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
          <select
            value={params.period}
            onChange={(e) => setParams({ ...params, period: e.target.value })}
            style={input}
          >
            <option value="1y">1 an</option>
            <option value="3y">3 ans</option>
            <option value="5y">5 ans</option>
            <option value="10y">10 ans</option>
            <option value="15y">15 ans</option>
            <option value="20y">20 ans</option>
          </select>
        </Field>

        <Field label="Capital initial (€)">
          <input
            type="number"
            value={params.initial_capital}
            onChange={(e) => setParams({ ...params, initial_capital: +e.target.value })}
            style={input}
          />
        </Field>

        <Field label="Versement mensuel (€)">
          <input
            type="number"
            value={params.monthly_contribution}
            onChange={(e) => setParams({ ...params, monthly_contribution: +e.target.value })}
            style={input}
          />
        </Field>

        <Field label="Courtier">
          <select
            value={params.broker}
            onChange={(e) => setParams({ ...params, broker: e.target.value })}
            style={input}
          >
            <option value="degiro">Degiro</option>
            <option value="fortuneo">Fortuneo</option>
            <option value="bourse_direct">Bourse Direct</option>
            <option value="interactive_brokers">Interactive Brokers</option>
            <option value="default">Autre / défaut</option>
          </select>
        </Field>

        <Field label="Compte">
          <select
            value={params.account_type}
            onChange={(e) => setParams({ ...params, account_type: e.target.value as 'CTO' | 'PEA' })}
            style={input}
          >
            <option value="CTO">CTO</option>
            <option value="PEA">PEA</option>
          </select>
        </Field>

        <Field label="Rebalance">
          <select
            value={params.rebalance_frequency}
            onChange={(e) => setParams({ ...params, rebalance_frequency: e.target.value as BacktestParams['rebalance_frequency'] })}
            style={input}
          >
            <option value="daily">Quotidien</option>
            <option value="weekly">Hebdomadaire</option>
            <option value="monthly">Mensuel</option>
            <option value="quarterly">Trimestriel</option>
          </select>
        </Field>

        <Field label="Stop-loss (%)">
          <input
            type="number"
            step="0.01"
            value={params.stop_loss_pct ?? ''}
            onChange={(e) => setParams({ ...params, stop_loss_pct: e.target.value === '' ? 0 : +e.target.value })}
            style={input}
          />
        </Field>

        <Field label="Benchmark">
          <select
            value={params.benchmark}
            onChange={(e) => setParams({ ...params, benchmark: e.target.value })}
            style={input}
          >
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

      {error && (
        <div style={{ color: '#b82424', marginBottom: '1rem' }}>{error}</div>
      )}

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

const input: React.CSSProperties = {
  padding: '0.4rem',
  border: '1px solid #ccc',
  borderRadius: 4,
  fontSize: '0.85rem',
};

const btnPrimary: React.CSSProperties = {
  padding: '0.6rem 1.2rem',
  background: '#142340',
  color: '#fff',
  border: 'none',
  borderRadius: 4,
  cursor: 'pointer',
  fontWeight: 600,
};

const btnGold: React.CSSProperties = {
  padding: '0.6rem 1.2rem',
  background: '#b8962f',
  color: '#fff',
  border: 'none',
  borderRadius: 4,
  cursor: 'pointer',
  fontWeight: 600,
};

function BacktestResults({ result }: { result: Tearsheet }) {
  const m = result.metrics;
  const pct = (v: number) => (v * 100).toFixed(2) + '%';

  return (
    <div>
      <h3 style={{ color: '#b8962f' }}>Résultats</h3>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.5rem', marginBottom: '1.5rem' }}>
        <div>Return: {pct(m.total_return)}</div>
        <div>CAGR: {pct(m.cagr)}</div>
        <div>Sharpe: {m.sharpe_ratio.toFixed(2)}</div>
        <div>Max DD: {pct(m.max_drawdown)}</div>
        <div>Sortino: {m.sortino_ratio.toFixed(2)}</div>
        <div>Calmar: {m.calmar_ratio.toFixed(2)}</div>
        <div>Vol: {pct(m.annualised_volatility)}</div>
        <div>Beta: {m.beta?.toFixed(2) ?? 'N/A'}</div>
      </div>

      {result.nav_chart && result.nav_chart.length > 0 && (
        <>
          <h4 style={{ color: '#142340' }}>Évolution du portefeuille</h4>
          <AreaChart width={700} height={250} data={result.nav_chart}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip />
            <Area type="monotone" dataKey="nav" stroke="#142340" fill="#e8edf5" name="NAV (€)" />
          </AreaChart>
        </>
      )}

      {result.drawdown_chart && result.drawdown_chart.length > 0 && (
        <>
          <h4 style={{ color: '#142340', marginTop: '1.5rem' }}>Drawdown</h4>
          <AreaChart width={700} height={180} data={result.drawdown_chart}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 10 }} />
            <YAxis tickFormatter={(v) => (v * 100).toFixed(1) + '%'} tick={{ fontSize: 10 }} />
            <Tooltip formatter={(v: number) => (v * 100).toFixed(2) + '%'} />
            <Area type="monotone" dataKey="drawdown" stroke="#b82424" fill="#f5e8e8" name="Drawdown" />
          </AreaChart>
        </>
      )}
    </div>
  );
}
