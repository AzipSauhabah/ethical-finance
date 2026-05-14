// © 2024 Sauhabah

export interface ScreenCheck {
  name: string;
  passed: boolean;
  value: number | null;
  threshold: number | null;
  description: string;
}

export interface ScreenResult {
  passed: boolean;
  score: number;
  checks: ScreenCheck[];
}

export interface TickerScreenResult {
  ticker: string;
  name: string;
  sector: string;
  industry: string;
  currency: string;
  exchange: string;
  country: string;
  market_cap: number;
  beta: number;
  dividend_yield: number;
  is_ethical: boolean;
  is_sharia: boolean;
  ethical: ScreenResult;
  sharia:  ScreenResult;
}

export interface LiveQuote {
  ticker: string; last: number; bid: number; ask: number;
  volume: number; change_pct: number; timestamp: string; currency: string;
}

export interface StrategyMeta {
  name: string; description: string; benchmark: string;
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
  require_ethical: boolean;
  require_sharia: boolean;
}

export interface Metrics {
  total_return: number; cagr: number; annualised_volatility: number;
  sharpe_ratio: number; sortino_ratio: number; calmar_ratio: number;
  omega_ratio: number; max_drawdown: number; average_drawdown: number;
  recovery_factor: number; var_95: number; cvar_95: number;
  var_99: number; cvar_99: number; var_parametric_95: number;
  skewness: number; excess_kurtosis: number; tail_ratio: number;
  hit_rate: number; profit_factor: number;
  beta?: number; alpha_jensen?: number;
  information_ratio?: number; treynor_ratio?: number;
}

export interface StressTestResult {
  scenario: string; label: string; start?: string; end?: string;
  n_days: number; total_return?: number; max_drawdown?: number;
  volatility?: number; var_95?: number; sharpe?: number;
  benchmark?: { total_return: number | null; max_drawdown: number | null } | null;
}

export interface NavPoint   { date: string; nav: number }
export interface DDPoint    { date: string; drawdown: number }
export interface CostPoint  { date: string; costs: number; taxes: number; total: number }
export interface AllocPoint { date: string; cash: number; invested: number }

export interface CostBreakdown {
  commission: number; slippage: number; fx_spread: number; ttf: number;
}

export interface Position {
  shares: number; price_eur: number; value_eur: number;
  unrealised: number; avg_cost?: number;
}

export interface Tearsheet {
  meta: { strategy: string; generated_at: string; copyright: string; disclaimer: string };
  metrics: Metrics;
  significance: Record<string, unknown>;
  stress_tests: StressTestResult[];
  cost_summary: { total_costs_eur: number; total_taxes_eur: number; cost_pct_nav: number };
  cost_breakdown: CostBreakdown;
  trades: { count: number; sample: Record<string, unknown>[] };
  nav_chart: NavPoint[];
  benchmark_chart: NavPoint[];
  drawdown_chart: DDPoint[];
  cost_chart: CostPoint[];
  allocation_chart: AllocPoint[];
  positions: {
    nav_eur: number; cash_eur: number; invested_eur: number;
    total_return: number; total_costs_eur: number; total_taxes_eur: number;
    n_trades: number; positions: Record<string, Position>;
  };
}

export interface DailySignal {
  ticker: string; signal: -1 | 0 | 1; label: 'BUY' | 'SELL' | 'HOLD';
  strength: number;
  indicators: { sma_crossover: number; rsi: number; macd: number; momentum: number };
  date: string;
}

export interface RebalanceOrder {
  ticker: string; side: 'buy' | 'sell' | 'hold';
  shares: number; price_eur: number; notional_eur: number;
  current_pct: number; target_pct: number; drift_pct: number;
  cost_eur: number; rationale: string;
}
