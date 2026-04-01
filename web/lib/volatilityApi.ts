import { fetchApi } from "./apiBase";

export interface IVDataPoint {
  date: string;
  iv: number;
}

export interface HVDataPoint {
  date: string;
  hv: number;
}

export interface VolatilityData {
  success: boolean;
  symbol: string;
  from_date: string;
  to_date: string;
  current_price: number | null;
  current_iv: number | null;
  hv_10: number | null;
  hv_20: number | null;
  hv_30: number | null;
  hv_60: number | null;
  iv_rank: number | null;
  iv_percentile: number | null;
  expected_move_30d_dollar: number | null;
  expected_move_30d_pct: number | null;
  iv_series: IVDataPoint[];
  hv_20_series: HVDataPoint[];
  error?: string | null;
}

export async function getVolatilityMetrics(
  symbol: string,
  fromDate: string,
  toDate: string,
): Promise<VolatilityData> {
  const params = new URLSearchParams({ from_date: fromDate, to_date: toDate });
  return fetchApi<VolatilityData>(`/volatility/${encodeURIComponent(symbol)}?${params}`);
}
