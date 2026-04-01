import { fetchApi } from "./apiBase";

/** Paper = sandbox (true), Live = production (false). */
export type TradingMode = "paper" | "live";

function sandboxParam(mode: TradingMode): boolean {
  return mode === "paper";
}

function isPaperMode(mode?: TradingMode): boolean {
  return mode === "paper";
}

export async function getEtradeAccounts(
  mode?: TradingMode
): Promise<Record<string, unknown>> {
  const qs = mode != null ? `?sandbox=${sandboxParam(mode)}` : "";
  return fetchApi<Record<string, unknown>>(`/lab/etrade/accounts${qs}`);
}

export async function getEtradeAccountBalance(
  accountIdKey: string,
  mode?: TradingMode
): Promise<Record<string, unknown>> {
  const params = new URLSearchParams({ account_id_key: accountIdKey });
  if (mode != null) params.set("sandbox", String(sandboxParam(mode)));
  return fetchApi<Record<string, unknown>>(
    `/lab/etrade/accounts/balance?${params.toString()}`
  );
}

export async function getEtradeOrders(
  accountIdKey: string,
  options: { status?: string; count?: number; mode?: TradingMode }
): Promise<Record<string, unknown>> {
  const params = new URLSearchParams({
    account_id_key: accountIdKey,
  });
  if (options.mode != null) params.set("sandbox", String(sandboxParam(options.mode)));
  if (options.status) params.set("status", options.status);
  if (options.count != null) params.set("count", String(options.count));
  return fetchApi<Record<string, unknown>>(
    `/lab/etrade/orders?${params.toString()}`
  );
}

export async function cancelEtradeOrder(
  accountIdKey: string,
  orderId: string,
  mode?: TradingMode
): Promise<Record<string, unknown>> {
  const qs = mode != null ? `?sandbox=${sandboxParam(mode)}` : "";
  return fetchApi<Record<string, unknown>>(
    `/lab/etrade/orders/cancel${qs}`,
    {
      method: "POST",
      body: JSON.stringify({ account_id_key: accountIdKey, order_id: orderId }),
      allowEmpty: true,
    }
  );
}

export interface PlaceEquityOrderParams {
  account_id_key: string;
  symbol: string;
  order_action: string;
  quantity: number;
  price_type?: string;
  limit_price?: number;
  stop_price?: number;
}

export async function placeEtradeEquityOrder(
  params: PlaceEquityOrderParams,
  mode?: TradingMode
): Promise<Record<string, unknown>> {
  const qs = mode != null ? `?sandbox=${sandboxParam(mode)}` : "";
  return fetchApi<Record<string, unknown>>(
    `/lab/etrade/orders/equity${qs}`,
    {
      method: "POST",
      body: JSON.stringify(params),
    }
  );
}

export interface PlaceOptionOrderParams {
  account_id_key: string;
  symbol: string;
  call_put: string;
  expiry_date: string;
  strike_price: number;
  order_action: string;
  quantity: number;
  price_type?: string;
  limit_price?: number;
}

export async function placeEtradeOptionOrder(
  params: PlaceOptionOrderParams,
  mode?: TradingMode
): Promise<Record<string, unknown>> {
  const qs = mode != null ? `?sandbox=${sandboxParam(mode)}` : "";
  return fetchApi<Record<string, unknown>>(
    `/lab/etrade/orders/option${qs}`,
    {
      method: "POST",
      body: JSON.stringify(params),
    }
  );
}

export async function getAlpacaAccounts(): Promise<Record<string, unknown>> {
  return fetchApi<Record<string, unknown>>("/lab/alpaca/accounts");
}

export async function getAlpacaAccountBalance(
  accountIdKey: string
): Promise<Record<string, unknown>> {
  const params = new URLSearchParams({ account_id_key: accountIdKey });
  return fetchApi<Record<string, unknown>>(
    `/lab/alpaca/accounts/balance?${params.toString()}`
  );
}

export async function getAlpacaOrders(
  accountIdKey: string,
  options: { status?: string; count?: number }
): Promise<Record<string, unknown>[]> {
  const params = new URLSearchParams({
    account_id_key: accountIdKey,
  });
  if (options.status) params.set("status", options.status);
  if (options.count != null) params.set("count", String(options.count));
  return fetchApi<Record<string, unknown>[]>(
    `/lab/alpaca/orders?${params.toString()}`
  );
}

export async function cancelAlpacaOrder(
  accountIdKey: string,
  orderId: string
): Promise<Record<string, unknown>> {
  return fetchApi<Record<string, unknown>>("/lab/alpaca/orders/cancel", {
    method: "POST",
    body: JSON.stringify({ account_id_key: accountIdKey, order_id: orderId }),
    allowEmpty: true,
  });
}

export async function placeAlpacaEquityOrder(
  params: PlaceEquityOrderParams
): Promise<Record<string, unknown>> {
  return fetchApi<Record<string, unknown>>("/lab/alpaca/orders/equity", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function placeAlpacaOptionOrder(
  params: PlaceOptionOrderParams
): Promise<Record<string, unknown>> {
  return fetchApi<Record<string, unknown>>("/lab/alpaca/orders/option", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function getTradingAccounts(
  mode?: TradingMode
): Promise<Record<string, unknown>> {
  return isPaperMode(mode) ? getAlpacaAccounts() : getEtradeAccounts(mode);
}

export async function getTradingAccountBalance(
  accountIdKey: string,
  mode?: TradingMode
): Promise<Record<string, unknown>> {
  return isPaperMode(mode)
    ? getAlpacaAccountBalance(accountIdKey)
    : getEtradeAccountBalance(accountIdKey, mode);
}

export async function getTradingOrders(
  accountIdKey: string,
  options: { status?: string; count?: number; mode?: TradingMode }
): Promise<Record<string, unknown>[] | Record<string, unknown>> {
  return isPaperMode(options.mode)
    ? getAlpacaOrders(accountIdKey, options)
    : getEtradeOrders(accountIdKey, options);
}

export async function cancelTradingOrder(
  accountIdKey: string,
  orderId: string,
  mode?: TradingMode
): Promise<Record<string, unknown>> {
  return isPaperMode(mode)
    ? cancelAlpacaOrder(accountIdKey, orderId)
    : cancelEtradeOrder(accountIdKey, orderId, mode);
}

export async function placeTradingEquityOrder(
  params: PlaceEquityOrderParams,
  mode?: TradingMode
): Promise<Record<string, unknown>> {
  return isPaperMode(mode)
    ? placeAlpacaEquityOrder(params)
    : placeEtradeEquityOrder(params, mode);
}

export async function placeTradingOptionOrder(
  params: PlaceOptionOrderParams,
  mode?: TradingMode
): Promise<Record<string, unknown>> {
  return isPaperMode(mode)
    ? placeAlpacaOptionOrder(params)
    : placeEtradeOptionOrder(params, mode);
}

export async function requestEtradeOAuthRequestToken(): Promise<{
  authorization_url: string;
  sandbox: boolean;
}> {
  return fetchApi(`/lab/etrade/oauth/request-token`, { method: "POST" });
}

export async function exchangeEtradeOAuthAccessToken(params: {
  verifier: string;
}): Promise<{ success: boolean }> {
  return fetchApi(`/lab/etrade/oauth/exchange-access-token`, {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function disconnectEtradeOAuth(): Promise<{ success: boolean }> {
  return fetchApi(`/lab/etrade/oauth/disconnect`, {
    method: "POST",
  });
}
