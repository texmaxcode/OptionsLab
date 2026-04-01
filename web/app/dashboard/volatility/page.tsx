"use client";

import { useEffect, useState } from "react";
import { getVolatilityMetrics, VolatilityData } from "@/lib/volatilityApi";
import { getSymbols } from "@/lib/api";
import { getUserSettings } from "@/lib/settingsApi";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { VolatilityChart, VolSeries } from "@/components/VolatilityChart";

// Consistent with app-wide dark-mode input styling
const labelClass = "block text-sm font-medium text-zinc-300 mb-1";
const inputClass =
  "w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-emerald-500";

function IVRankGauge({ value }: { value: number | null }) {
  if (value === null) return <span className="text-zinc-500 text-lg font-semibold">—</span>;

  const color =
    value >= 70 ? "text-red-400" : value >= 40 ? "text-yellow-400" : "text-emerald-400";
  const bgBar =
    value >= 70 ? "bg-red-500" : value >= 40 ? "bg-yellow-500" : "bg-emerald-500";
  const label = value >= 70 ? "High" : value >= 40 ? "Moderate" : "Low";

  return (
    <div className="space-y-1">
      <div className={`text-lg font-semibold ${color}`}>
        {value.toFixed(0)} / 100
        <span className="ml-2 text-xs font-medium px-1.5 py-0.5 rounded-full border border-current opacity-75">
          {label}
        </span>
      </div>
      {/* Progress bar */}
      <div className="h-1.5 w-full rounded-full bg-zinc-700 overflow-hidden">
        <div
          className={`h-full rounded-full ${bgBar} transition-all`}
          style={{ width: `${Math.min(100, value)}%` }}
        />
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  accent?: "green" | "yellow" | "red";
}) {
  const borderColor =
    accent === "green"
      ? "border-emerald-500/40 bg-emerald-500/5"
      : accent === "yellow"
        ? "border-yellow-500/40 bg-yellow-500/5"
        : accent === "red"
          ? "border-red-500/40 bg-red-500/5"
          : "border-zinc-700 bg-zinc-900";
  return (
    <div className={`rounded-lg border ${borderColor} px-4 py-3`}>
      <div className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-1.5">{label}</div>
      <div className="text-base font-semibold text-zinc-100 leading-snug">{value}</div>
      {sub && <div className="text-xs text-zinc-500 mt-1">{sub}</div>}
    </div>
  );
}

function pct(v: number | null, decimals = 1): string {
  return v !== null ? `${(v * 100).toFixed(decimals)}%` : "—";
}

export default function VolatilityPage() {
  const [symbols, setSymbols] = useState<string[]>([]);
  const [symbol, setSymbol] = useState("");
  const [fromDate, setFromDate] = useState("2024-01-01");
  const [toDate, setToDate] = useState("2024-12-31");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<VolatilityData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function init() {
      try {
        const [syms, settings] = await Promise.all([getSymbols(), getUserSettings()]);
        setSymbols(syms);
        if (syms.length > 0) setSymbol(syms[0]!);
        if (settings.default_from_date) setFromDate(settings.default_from_date);
        if (settings.default_to_date) setToDate(settings.default_to_date);
      } catch {
        // non-critical — use defaults
      }
    }
    init();
  }, []);

  async function handleRun() {
    if (!symbol) return;
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const result = await getVolatilityMetrics(symbol, fromDate, toDate);
      if (!result.success) {
        setError(result.error ?? "Unknown error");
      } else {
        setData(result);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const chartSeries: VolSeries[] = [];
  if (data?.iv_series?.length) {
    chartSeries.push({
      label: "IV",
      color: "rgb(251 146 60)",
      data: data.iv_series.map((p) => ({ date: p.date, value: p.iv })),
    });
  }
  if (data?.hv_20_series?.length) {
    chartSeries.push({
      label: "HV-20",
      color: "rgb(34 197 94)",
      data: data.hv_20_series.map((p) => ({ date: p.date, value: p.hv })),
    });
  }

  const ivRank = data?.iv_rank ?? null;
  const rankAccent =
    ivRank === null ? undefined : ivRank >= 70 ? "red" : ivRank >= 40 ? "yellow" : "green";

  return (
    <div className="space-y-5 min-w-0">
      <PageHeader
        title="Volatility Dashboard"
        subtitle="Historical Volatility, IV Rank, IV Percentile, and Expected Move — know the vol environment before picking a strategy."
      />

      {/* ── Controls ─────────────────────────────────────────────────── */}
      <Card className="bg-zinc-900/80 border-zinc-800">
        <CardBody>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_1fr_1fr_auto]">
            <div>
              <label className={labelClass}>Symbol</label>
              <select value={symbol} onChange={(e) => setSymbol(e.target.value)} className={inputClass}>
                {symbols.length === 0 && (
                  <option value="" disabled>No symbols — sync data first</option>
                )}
                {symbols.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelClass}>From date</label>
              <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>To date</label>
              <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} className={inputClass} />
            </div>
            <div className="flex items-end">
              <Button onClick={handleRun} disabled={loading || !symbol} className="w-full sm:w-auto px-6">
                {loading ? "Analyzing…" : "Analyze"}
              </Button>
            </div>
          </div>
        </CardBody>
      </Card>

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          <svg className="h-4 w-4 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
          </svg>
          {error}
        </div>
      )}

      {data && (
        <>
          {/* ── Primary volatility metrics ──────────────────────────── */}
          <Card className="bg-zinc-900/80 border-zinc-800">
            <CardBody className="space-y-3">
              <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wide">
                Current levels
              </h2>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                <MetricCard
                  label="Price"
                  value={data.current_price !== null ? `$${data.current_price.toFixed(2)}` : "—"}
                />
                <MetricCard
                  label="Implied Vol (IV)"
                  value={data.current_iv !== null ? pct(data.current_iv) : "—"}
                  sub="Latest avg across contracts"
                />
                <MetricCard
                  label="IV Rank"
                  value={<IVRankGauge value={ivRank} />}
                  sub="52-week range"
                  accent={rankAccent}
                />
                <MetricCard
                  label="IV Percentile"
                  value={data.iv_percentile !== null ? `${data.iv_percentile.toFixed(0)}%` : "—"}
                  sub="Days IV was lower"
                />
                <MetricCard
                  label="Expected Move (30d)"
                  value={
                    data.expected_move_30d_dollar !== null
                      ? `±$${data.expected_move_30d_dollar.toFixed(2)}`
                      : "—"
                  }
                  sub={
                    data.expected_move_30d_pct !== null
                      ? `±${data.expected_move_30d_pct.toFixed(1)}% · 1σ`
                      : "Needs IV data"
                  }
                />
              </div>
            </CardBody>
          </Card>

          {/* ── Historical Volatility ───────────────────────────────── */}
          <Card className="bg-zinc-900/80 border-zinc-800">
            <CardBody className="space-y-3">
              <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wide">
                Historical Volatility (annualized)
              </h2>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {(
                  [
                    ["HV-10", data.hv_10, "10-day lookback"],
                    ["HV-20", data.hv_20, "20-day lookback"],
                    ["HV-30", data.hv_30, "30-day lookback"],
                    ["HV-60", data.hv_60, "60-day lookback"],
                  ] as [string, number | null, string][]
                ).map(([label, val, sub]) => (
                  <MetricCard key={label} label={label} value={pct(val)} sub={sub} />
                ))}
              </div>
              <p className="text-xs text-zinc-600">
                HV measures how much the stock has moved historically.
                Compare to IV to see if options are over- or under-priced relative to realized volatility.
              </p>
            </CardBody>
          </Card>

          {/* ── Strategy guidance ───────────────────────────────────── */}
          {ivRank !== null && (
            <Card className="bg-zinc-900/80 border-zinc-800">
              <CardBody>
                <div className="flex items-start gap-3">
                  <div
                    className={`mt-0.5 h-2.5 w-2.5 rounded-full shrink-0 ${
                      ivRank >= 60
                        ? "bg-red-400"
                        : ivRank >= 35
                          ? "bg-yellow-400"
                          : "bg-emerald-400"
                    }`}
                  />
                  <div>
                    <div className="text-sm font-semibold text-zinc-200 mb-0.5">Strategy Guidance</div>
                    {ivRank >= 60 ? (
                      <p className="text-sm text-zinc-400">
                        <span className="text-red-400 font-medium">IV Rank is elevated ({ivRank.toFixed(0)}/100).</span>{" "}
                        Options are relatively expensive. Favor{" "}
                        <span className="text-zinc-200 font-medium">premium-selling</span> — iron condors, credit spreads, covered calls.
                      </p>
                    ) : ivRank >= 35 ? (
                      <p className="text-sm text-zinc-400">
                        <span className="text-yellow-400 font-medium">IV Rank is moderate ({ivRank.toFixed(0)}/100).</span>{" "}
                        Options are neutrally priced. Strategy choice depends more on directional outlook.
                      </p>
                    ) : (
                      <p className="text-sm text-zinc-400">
                        <span className="text-emerald-400 font-medium">IV Rank is low ({ivRank.toFixed(0)}/100).</span>{" "}
                        Options are relatively cheap. Favor{" "}
                        <span className="text-zinc-200 font-medium">premium-buying</span> — straddles, debit spreads, calendars.
                      </p>
                    )}
                  </div>
                </div>
              </CardBody>
            </Card>
          )}

          {/* ── IV vs HV Chart ──────────────────────────────────────── */}
          <Card className="bg-zinc-900/80 border-zinc-800">
            <CardBody className="space-y-2">
              <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wide">
                IV vs HV-20 — historical comparison
              </h2>
              {chartSeries.length > 0 ? (
                <>
                  <VolatilityChart
                    series={chartSeries}
                    height={280}
                    yLabel="Volatility"
                    formatY={(v) => `${(v * 100).toFixed(1)}%`}
                    className="w-full"
                  />
                  <p className="text-xs text-zinc-600">
                    IV above HV → options pricing in more movement than realized (elevated premium) ·
                    IV below HV → options are cheap relative to realized vol.
                  </p>
                </>
              ) : (
                <EmptyState
                  title="No IV time series available"
                  description="Sync options contracts with implied volatility data to see the IV vs HV chart."
                />
              )}
            </CardBody>
          </Card>
        </>
      )}

      {!data && !loading && !error && (
        <Card className="bg-zinc-900/80 border-zinc-800">
          <CardBody>
            <EmptyState
              title="Select a symbol and click Analyze"
              description="Computes Historical Volatility at 10/20/30/60-day windows, IV Rank, IV Percentile, and the 30-day Expected Move."
            />
          </CardBody>
        </Card>
      )}
    </div>
  );
}
