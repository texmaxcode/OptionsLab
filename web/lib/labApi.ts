import { fetchApi } from "./apiBase";

export interface BacktestSummary {
  id: number;
  name: string;
  created_at: string;
  strategy: string;
  underlying: string;
  from_date: string | null;
  to_date: string | null;
  cash: number;
  status: string;
  start_value: number | null;
  end_value: number | null;
}

export interface EquityCurvePoint {
  date: string;
  value: number;
}

export interface DrawdownPoint {
  date: string;
  drawdown: number;
}

export interface TimeReturnPoint {
  date: string;
  period_return: number;
}

export interface PricePoint {
  date: string;
  close: number;
}

export interface IndicatorPoint {
  date: string;
  indicators: Record<string, number>;
}

export interface Trade {
  entry_date: string;
  exit_date: string;
  direction: string;
  size: number;
  entry_price: number;
  exit_price: number | null;
  pnl: number;
  pnl_pct: number | null;
  duration_days: number | null;
}

export interface TradeStats {
  trade_count: number;
  win_rate: number;
  avg_pnl: number | null;
  avg_win: number | null;
  avg_loss: number | null;
  best_trade_pnl: number | null;
  worst_trade_pnl: number | null;
  profit_factor: number | null;
  avg_hold_days: number | null;
  long_trades: number | null;
  short_trades: number | null;
}

export interface BacktestDetail extends BacktestSummary {
  contract_id: number | null;
  contract_symbol: string | null;
  first_contract: boolean;
  error: string | null;
  equity_curve: EquityCurvePoint[] | null;
  drawdown_curve: DrawdownPoint[] | null;
  time_returns: TimeReturnPoint[] | null;
  price_series: PricePoint[] | null;
  indicator_series: IndicatorPoint[] | null;
  trades: Trade[] | null;
  trade_stats: TradeStats | null;
}

export interface SegmentStats {
  total: number;
  completed: number;
  win_rate: number;
  avg_return_pct: number | null;
  best_return_pct: number | null;
  worst_return_pct: number | null;
}

export interface DashboardSummary {
  overall: SegmentStats;
  equity: SegmentStats;
  options: SegmentStats;
  overall_equity_curve?: EquityCurvePoint[] | null;
  equity_equity_curve?: EquityCurvePoint[] | null;
  options_equity_curve?: EquityCurvePoint[] | null;
  overall_trade_stats?: TradeStats | null;
  equity_trade_stats?: TradeStats | null;
  options_trade_stats?: TradeStats | null;
}

export interface BacktestCreateRequest {
  name: string;
  strategy: string;
  underlying: string;
  from_date?: string | null;
  to_date?: string | null;
  cash?: number;
  contract_id?: number | null;
  contract_symbol?: string | null;
  first_contract?: boolean;
}

export async function listBacktests(): Promise<BacktestSummary[]> {
  return fetchApi<BacktestSummary[]>("/lab/backtests");
}

export async function createBacktest(
  body: BacktestCreateRequest
): Promise<BacktestDetail> {
  return fetchApi<BacktestDetail>("/lab/backtests", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getBacktest(id: number): Promise<BacktestDetail> {
  return fetchApi<BacktestDetail>(`/lab/backtests/${id}`);
}

export async function updateBacktest(
  id: number,
  patch: { name?: string }
): Promise<BacktestDetail> {
  return fetchApi<BacktestDetail>(`/lab/backtests/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function deleteBacktest(id: number): Promise<void> {
  await fetchApi<void>(`/lab/backtests/${id}`, {
    method: "DELETE",
    allowEmpty: true,
  });
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  return fetchApi<DashboardSummary>("/lab/summary");
}

export interface SyncRequest {
  source: "massive" | "etrade";
  symbols: string;
  from_date?: string | null;
  to_date?: string | null;
  underlying_only?: boolean;
  options?: boolean;
  max_contracts?: number | null;
}

export interface SyncResult {
  symbol: string;
  underlying_bars: number;
  options_contracts?: number | null;
  options_bars?: number | null;
  error?: string | null;
}

export interface SyncResponse {
  success: boolean;
  total_underlying_bars: number;
  results: SyncResult[];
  error?: string | null;
}

export async function runSync(body: SyncRequest): Promise<SyncResponse> {
  return fetchApi<SyncResponse>("/lab/sync", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
