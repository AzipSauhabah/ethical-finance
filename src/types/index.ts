// Shared type definitions for the Ethical Finance Platform frontend.
// © 2024 Sauhabah

export interface TickerScreenResult {
  ticker: string;
  name: string;
  sector: string;
  is_ethical: boolean;
  ethical_score: number;
  ethical_flags: string[];
  currency: string;
  country: string;
  dividend_yield: number;
  beta: number;
  market_cap: number;
}

export interface LiveQuote {
  ticker: string;
  last: number;
  bid: number;
  ask: number;
  volume: number;
  change_pct: number;
  timestamp: string;
  currency: string;
}

export interface StrategyMeta {
  name: string;
  description: string;
  benchmark: string;
  param_space: Record<string, [number, number] | unknown[]>;
}

export interface BacktestParams {
  tickers: string[];
  strategy: string;
  period: string;
  initial_capital: number;
  monthly_contribution: number;
  broker: string;
  account_type: 'CTO' | 'PEA';
  rebalance_frequency: 'daily' | 'weekly' | 'monthly' | 'quarterly';
  max_position_pct: number;
  stop_loss_pct: number | null;
  benchmark: string;
  custom_params?: Record<string, number>;
}

export interface Metrics {
  total_return: number;
  cagr: number;
  annualised_volatility: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  omega_ratio: number;
  max_drawdown: number;
  average_drawdown: number;
  recovery_factor: number;
  var_95: number;
  cvar_95: number;
  var_99: number;
  cvar_99: number;
  var_parametric_95: number;
  skewness: number;
  excess_kurtosis: number;
  tail_ratio: number;
  hit_rate: number;
  profit_factor: number;
  beta?: number;
  alpha_jensen?: number;
  information_ratio?: number;
  treynor_ratio?: number;
}

export interface StressTestResult {
  scenario: string;
  label: string;
  start?: string;
  end?: string;
  n_days: number;
  total_return?: number;
  max_drawdown?: number;
  volatility?: number;
  var_95?: number;
  sharpe?: number;
  benchmark?: {
    total_return: number | null;
    max_drawdown: number | null;
  } | null;
}

export interface NavPoint  { date: string; nav: number }
export interface DDPoint   { date: string; drawdown: number }
export interface Position {
  shares: number;
  price_eur: number;
  value_eur: number;
  unrealised: number;
}

export interface Tearsheet {
  meta: {
    strategy: string;
    generated_at: string;
    copyright: string;
    disclaimer: string;
  };
  metrics: Metrics;
  significance: Record<string, unknown>;
  stress_tests: StressTestResult[];
  cost_summary: {
    total_costs_eur: number;
    total_taxes_eur: number;
    cost_pct_nav: number;
  };
  trades: {
    count: number;
    sample: Record<string, unknown>[];
  };
  nav_chart: NavPoint[];
  drawdown_chart: DDPoint[];
  positions: {
    nav_eur: number;
    cash_eur: number;
    invested_eur: number;
    total_return: number;
    total_costs_eur: number;
    total_taxes_eur: number;
    n_trades: number;
    positions: Record<string, Position>;
  };
}

export interface DailySignal {
  ticker: string;
  signal: -1 | 0 | 1;
  label: 'BUY' | 'SELL' | 'HOLD';
  strength: number;
  indicators: {
    sma_crossover: number;
    rsi: number;
    macd: number;
    momentum: number;
  };
  date: string;
}

export interface RebalanceOrder {
  ticker: string;
  side: 'buy' | 'sell' | 'hold';
  shares: number;
  price_eur: number;
  notional_eur: number;
  current_pct: number;
  target_pct: number;
  drift_pct: number;
  cost_eur: number;
  rationale: string;
}
