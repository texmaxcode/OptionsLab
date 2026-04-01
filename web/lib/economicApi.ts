"use client";

import { fetchApi } from "./apiBase";

export type EconomicSource = "fred" | "bls" | "bea";

export interface EconomicSeriesPoint {
  date: string;
  value: number | null;
}

export interface EconomicSeriesResponse {
  source: string;
  series_id: string;
  points: EconomicSeriesPoint[];
  raw?: unknown;
}

export interface StoredEconomicSeriesInfo {
  source: EconomicSource;
  series_id: string;
  label?: string | null;
  point_count: number;
  first_date?: string | null;
  last_date?: string | null;
  last_value?: number | null;
}

export interface StoredEconomicSeriesListResponse {
  items: StoredEconomicSeriesInfo[];
}

export interface StoredEconomicSeriesDeleteResponse {
  source: string;
  series_id: string;
  deleted_series: boolean;
  deleted_points: number;
}

export async function getEconomicSeries(params: {
  source: EconomicSource;
  series_id: string;
  start_date?: string;
  end_date?: string;
}): Promise<EconomicSeriesResponse> {
  const search = new URLSearchParams({
    source: params.source,
    series_id: params.series_id,
  });
  if (params.start_date) search.set("start_date", params.start_date);
  if (params.end_date) search.set("end_date", params.end_date);
  return fetchApi<EconomicSeriesResponse>(`/economic/series?${search.toString()}`);
}

export async function getStoredEconomicSeries(params: {
  source: EconomicSource;
  series_id: string;
}): Promise<EconomicSeriesResponse> {
  const search = new URLSearchParams({
    source: params.source,
    series_id: params.series_id,
  });
  return fetchApi<EconomicSeriesResponse>(`/economic/stored?${search.toString()}`);
}

export async function listStoredEconomicSeries(): Promise<StoredEconomicSeriesListResponse> {
  return fetchApi<StoredEconomicSeriesListResponse>(`/economic/stored/list`);
}

export async function getLatestStoredEconomicSeries(params?: {
  limit?: number;
}): Promise<StoredEconomicSeriesListResponse> {
  const search = new URLSearchParams();
  if (params?.limit != null) search.set("limit", String(params.limit));
  const qs = search.toString();
  return fetchApi<StoredEconomicSeriesListResponse>(`/economic/stored/latest${qs ? `?${qs}` : ""}`);
}

export async function deleteStoredEconomicSeries(params: {
  source: EconomicSource;
  series_id: string;
}): Promise<StoredEconomicSeriesDeleteResponse> {
  const search = new URLSearchParams({
    source: params.source,
    series_id: params.series_id,
  });
  return fetchApi<StoredEconomicSeriesDeleteResponse>(`/economic/stored?${search.toString()}`, {
    method: "DELETE",
  });
}

