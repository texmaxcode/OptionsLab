import { fetchApi } from "./apiBase";

export interface PositionSizeRequest {
  capital: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  max_risk_pct?: number;
  max_loss_per_contract?: number | null;
  contract_multiplier?: number;
}

export interface PositionSizeResult {
  success: boolean;
  kelly_fraction: number | null;
  half_kelly_fraction: number | null;
  kelly_dollar_risk: number | null;
  half_kelly_dollar_risk: number | null;
  fixed_risk_dollar: number | null;
  fixed_risk_units: number | null;
  max_contracts: number | null;
  error?: string | null;
}

export async function calculatePositionSize(
  req: PositionSizeRequest,
): Promise<PositionSizeResult> {
  return fetchApi<PositionSizeResult>("/risk/position-size", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
