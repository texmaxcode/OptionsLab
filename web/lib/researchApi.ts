import { fetchApi } from "./apiBase";

export interface ForecastPoint {
  step: number;
  value: number;
}

export interface ForecastResponse {
  success: boolean;
  symbol: string;
  from_date: string;
  to_date: string;
  horizon: number;
  model: string;
  direction: string;
  forecast: ForecastPoint[];
  error?: string | null;
}

export interface ForecastRunRecord {
  model_id: string;
  symbol: string;
  from_date: string;
  to_date: string;
  horizon: number;
  model_type: string;
  metrics?: Record<string, number>;
}

export interface PayoffPoint {
  underlying: number;
  payoff: number;
}

export interface StrategyEvaluateResponse {
  success: boolean;
  strategy_type: string;
  expected_value: number;
  probability_of_profit: number;
  max_loss: number;
  max_gain: number;
  payoff_diagram: PayoffPoint[];
  breakeven_prices: number[];
  error?: string | null;
  historical_backtest_return?: number | null;
  historical_backtest_drawdown?: number | null;
  historical_backtest_error?: string | null;
}

export interface ResearchAnalyzeResponse {
  success: boolean;
  symbol: string;
  forecast_direction?: string | null;
  forecast_mean?: number | null;
  strategy_results?: Array<Record<string, unknown>>;
  explanation?: string | null;
}

export interface ResearchExplainResponse {
  success: boolean;
  explanation: string;
  error?: string | null;
}

export async function runForecast(body: {
  symbol: string;
  from_date: string;
  to_date: string;
  horizon?: number;
  model?: string;
}): Promise<ForecastResponse> {
  return fetchApi<ForecastResponse>("/forecast/run", {
    method: "POST",
    body: JSON.stringify({
      symbol: body.symbol,
      from_date: body.from_date,
      to_date: body.to_date,
      horizon: body.horizon ?? 1,
      model: body.model ?? "arima",
    }),
  });
}

export async function listForecastRuns(params?: {
  symbol?: string;
  model_type?: string;
  limit?: number;
}): Promise<ForecastRunRecord[]> {
  const search = new URLSearchParams();
  if (params?.symbol) search.set("symbol", params.symbol);
  if (params?.model_type) search.set("model_type", params.model_type);
  if (params?.limit != null) search.set("limit", String(params.limit));
  const q = search.toString();
  return fetchApi<ForecastRunRecord[]>(`/forecast/runs${q ? `?${q}` : ""}`);
}

export async function evaluateStrategy(body: {
  strategy_type: string;
  forecast_mean: number;
  forecast_std?: number | null;
  long_strike?: number | null;
  short_strike?: number | null;
  strike?: number | null;
  put_long?: number | null;
  put_short?: number | null;
  call_short?: number | null;
  call_long?: number | null;
  net_debit?: number | null;
  premium_paid?: number | null;
  symbol?: string | null;
  from_date?: string | null;
  to_date?: string | null;
  include_backtest?: boolean;
}): Promise<StrategyEvaluateResponse> {
  return fetchApi<StrategyEvaluateResponse>("/strategy-engine/evaluate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function researchAnalyze(body: {
  symbol: string;
  from_date: string;
  to_date: string;
  horizon?: number;
  strategy_types?: string[];
  strategy_params?: Record<string, unknown> | null;
}): Promise<ResearchAnalyzeResponse> {
  return fetchApi<ResearchAnalyzeResponse>("/research/analyze", {
    method: "POST",
    body: JSON.stringify({
      symbol: body.symbol,
      from_date: body.from_date,
      to_date: body.to_date,
      horizon: body.horizon ?? 1,
      strategy_types: body.strategy_types ?? [],
      strategy_params: body.strategy_params ?? undefined,
    }),
  });
}

export async function researchExplain(body: {
  forecast_summary?: string | null;
  strategy_summary?: string | null;
  include_risk?: boolean;
}): Promise<ResearchExplainResponse> {
  return fetchApi<ResearchExplainResponse>("/research/explain", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
