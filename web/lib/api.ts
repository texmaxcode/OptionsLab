import { fetchApi } from "./apiBase";

export interface StrategyInfo {
  id: string;
  label: string;
  equity_only: boolean;
}

export interface ContractInfo {
  id: number;
  underlying_symbol: string;
  expiration: string;
  strike: number;
  option_type: string;
  contract_symbol: string;
}

export async function getStrategies(): Promise<StrategyInfo[]> {
  return fetchApi<StrategyInfo[]>("/strategies");
}

export async function getSymbols(): Promise<string[]> {
  return fetchApi<string[]>("/symbols");
}

export interface DeleteSymbolResult {
  symbol: string;
  underlying_bars_deleted: number;
  options_contracts_deleted: number;
}

export async function deleteSymbolData(symbol: string): Promise<DeleteSymbolResult> {
  return fetchApi<DeleteSymbolResult>(`/symbols/${encodeURIComponent(symbol)}`, {
    method: "DELETE",
  });
}

export interface ContractsPage {
  items: ContractInfo[];
  total: number;
}

export async function getContracts(
  underlying: string,
  page = 1,
  pageSize = 100
): Promise<ContractsPage> {
  const params = new URLSearchParams({
    underlying,
    page: String(page),
    page_size: String(pageSize),
  });
  return fetchApi<ContractsPage>(`/contracts?${params.toString()}`);
}

export interface UnderlyingBarInfo {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface UnderlyingBarsPage {
  items: UnderlyingBarInfo[];
  total: number;
}

const BARS_PAGE_SIZE = 500;

export async function getUnderlyingBars(
  symbol: string,
  page = 1,
  pageSize = 100
): Promise<UnderlyingBarsPage> {
  const params = new URLSearchParams({
    symbol,
    page: String(page),
    page_size: String(pageSize),
  });
  return fetchApi<UnderlyingBarsPage>(`/bars?${params.toString()}`);
}

/** Fetch all underlying bars for a symbol by paginating. No filtering. */
export async function getAllUnderlyingBars(
  symbol: string
): Promise<UnderlyingBarInfo[]> {
  const all: UnderlyingBarInfo[] = [];
  let page = 1;
  let total = 0;
  do {
    const res = await getUnderlyingBars(symbol, page, BARS_PAGE_SIZE);
    all.push(...res.items);
    total = res.total;
    page++;
  } while (all.length < total);
  return all;
}
