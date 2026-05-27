// Thin wrapper around fetch() for the Ethical Finance Platform API.
// © 2024 Sauhabah

import type {
  TickerScreenResult, LiveQuote, StrategyMeta,
  BacktestParams, Tearsheet, DailySignal, RebalanceOrder,
} from '../types';

const BASE = `${import.meta.env.VITE_API_URL ?? ''}/api`;

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`API ${res.status}: ${txt}`);
  }
  return res.json();
}

export const api = {
  health:        () => jsonFetch<{ status: string; version: string }>(`${BASE}/health`),

  meta:          () => jsonFetch<{ version: string; copyright: string; disclaimer: string }>(`${BASE}/meta`),

  screenTickers: (tickers: string[]) =>
    jsonFetch<{ tickers: TickerScreenResult[] }>(`${BASE}/tickers/screen`, {
      method: 'POST',
      body:   JSON.stringify({ tickers }),
    }),

  quote:         (ticker: string) =>
    jsonFetch<LiveQuote>(`${BASE}/quote/${ticker}`),

  streamQuote:   (ticker: string, onMsg: (q: LiveQuote) => void): EventSource => {
    const es = new EventSource(`${BASE}/quote/stream/${ticker}`);
    es.onmessage = (e) => {
      try { onMsg(JSON.parse(e.data)); } catch { /* ignore */ }
    };
    return es;
  },

  prices:        (tickers: string[], period: string) =>
    jsonFetch<{ data: Record<string, number | string>[] }>(
      `${BASE}/prices?tickers=${tickers.join(',')}&period=${period}`,
    ),

  strategies:    () =>
    jsonFetch<{ strategies: StrategyMeta[] }>(`${BASE}/strategies`),

  createCustomStrategy: (def: { name: string; description: string; rules: unknown[]; combination: string }) =>
    jsonFetch<{ registered: boolean }>(`${BASE}/strategies/custom`, {
      method: 'POST',
      body:   JSON.stringify(def),
    }),

  backtest:      (params: BacktestParams) =>
    jsonFetch<Tearsheet>(`${BASE}/backtest`, {
      method: 'POST',
      body:   JSON.stringify(params),
    }),

  backtestPdf:   async (params: BacktestParams): Promise<Blob> => {
    const res = await fetch(`${BASE}/backtest/pdf`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    if (!res.ok) throw new Error(`PDF: ${res.status}`);
    return res.blob();
  },

  monteCarlo: (payload: {
    ticker: string; period: string; initial_capital: number;
    n_paths: number; n_days: number; method: 'gbm' | 'bootstrap';
  }) => jsonFetch(`${BASE}/montecarlo`, {
    method: 'POST', body: JSON.stringify(payload),
  }),

  dailySignals:  (tickers: string[]) =>
    jsonFetch<{ signals: DailySignal[] }>(`${BASE}/signals/daily`, {
      method: 'POST', body: JSON.stringify({ tickers }),
    }),

  rebalance:     (payload: {
    positions: Record<string, { shares: number; currency: string; market_cap_eur?: number }>;
    target_weights: Record<string, number>;
    cash_eur: number;
    broker: string;
  }) => jsonFetch<{ orders: RebalanceOrder[]; date: string }>(`${BASE}/signals/rebalance`, {
    method: 'POST', body: JSON.stringify(payload),
  }),
};
