"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  getLatestStoredEconomicSeries,
  getStoredEconomicSeries,
  type EconomicSeriesPoint,
  type StoredEconomicSeriesInfo,
} from "@/lib/economicApi";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { EconomicSeriesChart } from "@/components/EconomicSeriesChart";

export default function DashboardHome() {
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [macroLatest, setMacroLatest] = useState<StoredEconomicSeriesInfo[]>([]);
  const [macroSeries, setMacroSeries] = useState<
    Record<string, EconomicSeriesPoint[]>
  >({});

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    getLatestStoredEconomicSeries({ limit: 6 })
      .then(async (res) => {
        setMacroLatest(res.items);
        const entries = await Promise.all(
          res.items.map(async (s) => {
            const key = `${s.source}:${s.series_id}`;
            try {
              const resp = await getStoredEconomicSeries({
                source: s.source,
                series_id: s.series_id,
              });
              return [key, resp.points as EconomicSeriesPoint[]] as const;
            } catch {
              return [key, [] as EconomicSeriesPoint[]] as const;
            }
          })
        );
        setMacroSeries(
          entries.reduce<Record<string, EconomicSeriesPoint[]>>(
            (acc, [k, v]) => {
              acc[k] = v;
              return acc;
            },
            {}
          )
        );
      })
      .catch(() => {
        setError("Failed to load latest macro data.");
        setMacroLatest([]);
        setMacroSeries({});
      })
      .finally(() => setLoading(false));
  }, []);

  const macroWithTrend = useMemo(() => {
    const now = new Date();
    const oneYearAgo = new Date(now);
    oneYearAgo.setFullYear(now.getFullYear() - 1);

    return macroLatest.map((s) => {
      const key = `${s.source}:${s.series_id}`;
      const pts = macroSeries[key] ?? [];
      const filtered = pts.filter((p) => {
        const d = new Date(p.date);
        return !Number.isNaN(d.getTime()) && d >= oneYearAgo && d <= now;
      });

      let dir: "up" | "down" | "flat" | null = null;
      if (pts.length >= 2) {
        const last = pts[pts.length - 1]?.value;
        const prev = pts[pts.length - 2]?.value;
        if (last != null && prev != null) {
          if (last > prev) dir = "up";
          else if (last < prev) dir = "down";
          else dir = "flat";
        }
      }

      return { info: s, key, points: filtered, dir };
    });
  }, [macroLatest, macroSeries]);

  return (
    <div className="space-y-4 min-w-0">
      <div>
        <h1 className="text-xl sm:text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
          Overview
        </h1>
        <p className="text-base sm:text-sm text-zinc-600 dark:text-zinc-400 mt-0.5">
          Quick access to all modules &mdash; backtests, research, macro data, and trading.
        </p>
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-md border border-red-700/50 bg-red-900/20 px-3 py-2.5 text-sm text-red-300">
          <svg className="h-4 w-4 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
          </svg>
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <Card>
          <CardBody className="space-y-1.5">
            <h2 className="text-base sm:text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              Backtest history
            </h2>
            <p className="text-sm sm:text-xs text-zinc-600 dark:text-zinc-400">
              Browse and inspect previous backtests.
            </p>
            <Link
              href="/dashboard/backtests"
              className="inline-flex items-center justify-center rounded-md bg-zinc-900 px-3 py-2 text-sm sm:text-xs font-medium text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
            >
              View backtests
            </Link>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="space-y-1.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base sm:text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                Research &amp; AI
              </h2>
              <Badge tone="green">Forecast &amp; strategies</Badge>
            </div>
            <p className="text-sm sm:text-xs text-zinc-600 dark:text-zinc-400">
              Run forecasts, evaluate options strategies, get AI explanations.
            </p>
            <Link
              href="/dashboard/research"
              className="inline-flex items-center justify-center rounded-md bg-emerald-600 px-3 py-2 text-sm sm:text-xs font-medium text-white hover:bg-emerald-700"
            >
              Open Research
            </Link>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="space-y-1.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base sm:text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                Macro &amp; economic data
              </h2>
              <Badge tone="gray">6 indicators</Badge>
            </div>
            <p className="text-sm sm:text-xs text-zinc-600 dark:text-zinc-400">
              Visualize key macro indicators alongside your backtests.
            </p>
            <Link
              href="/dashboard/economic"
              className="inline-flex items-center justify-center rounded-md bg-zinc-900 px-3 py-2 text-sm sm:text-xs font-medium text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
            >
              Open macro dashboard
            </Link>
          </CardBody>
        </Card>
      </div>

      {loading ? (
        <Card>
          <CardBody className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <div className="h-4 w-44 rounded bg-zinc-800 animate-pulse" />
              <div className="h-5 w-8 rounded bg-zinc-800 animate-pulse" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {[1, 2, 3].map((i) => (
                <Card key={i}>
                  <CardBody className="space-y-2">
                    <div className="h-3 w-3/4 rounded bg-zinc-800 animate-pulse" />
                    <div className="h-6 w-1/2 rounded bg-zinc-800 animate-pulse" />
                    <div className="h-3 w-full rounded bg-zinc-800 animate-pulse" />
                    <div className="h-[80px] w-full rounded bg-zinc-800/50 animate-pulse mt-2" />
                  </CardBody>
                </Card>
              ))}
            </div>
          </CardBody>
        </Card>
      ) : macroWithTrend.length > 0 ? (
        <Card className="overflow-visible">
          <CardBody className="space-y-2 overflow-visible">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base sm:text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                Latest macro data (stored)
              </h2>
              <Badge tone="blue">DB</Badge>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {macroWithTrend.map(({ info: s, key, points, dir }) => {
                const macroKey = `${s.source}:${s.series_id}`;
                const friendlyLabel =
                  ({
                    "fred:GDP": "Real GDP (quarterly)",
                    "fred:CPIAUCSL": "CPI, all urban consumers",
                    "fred:UNRATE": "Unemployment rate (U.S.)",
                    "fred:IPMAN": "Manufacturing production (IPMAN index)",
                    "fred:DGS10": "10-year Treasury yield",
                    "fred:DEXUSEU": "EUR/USD exchange rate",
                    "fred:VIXCLS": "VIX volatility index",
                    "bls:CUUR0000SA0": "CPI-U, all items (BLS)",
                    "bls:LNS14000000": "Unemployment rate (BLS, household survey)",
                    "bea:T10101": "U.S. GDP (BEA NIPA T10101)",
                  } as Record<string, string>)[macroKey] ?? null;
                const title =
                  friendlyLabel ??
                  s.label ??
                  `${s.source.toUpperCase()} \u00b7 ${s.series_id}`;
                const codeLine = `${s.source.toUpperCase()} \u00b7 ${s.series_id}`;
                return (
                  <Card key={key}>
                    <CardBody className="space-y-1 overflow-visible">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm sm:text-xs font-medium text-zinc-500 dark:text-zinc-400">
                          {title}
                        </p>
                        {dir && dir !== "flat" && (
                          <span
                            className="text-zinc-400 text-lg"
                            aria-label={dir === "up" ? "Rising" : "Falling"}
                          >
                            {dir === "up" ? "\u25b2" : "\u25bc"}
                          </span>
                        )}
                      </div>
                      <p className="text-xl sm:text-lg md:text-xl font-semibold text-zinc-900 dark:text-zinc-100 font-mono">
                        {s.last_value != null
                          ? Number(s.last_value).toFixed(3)
                          : "\u2014"}
                      </p>
                      <p className="text-xs sm:text-[11px] text-zinc-500 dark:text-zinc-400">
                        {codeLine}
                      </p>
                      <p className="text-xs sm:text-[11px] text-zinc-500 dark:text-zinc-400">
                        Date: {s.last_date ?? "\u2014"} &middot; Points: {s.point_count}
                      </p>
                      {points.length > 1 && (
                        <div className="mt-1 -mx-3 -mb-3">
                          <EconomicSeriesChart
                            data={points}
                            height={220}
                            compactDates
                            className="w-full"
                          />
                        </div>
                      )}
                    </CardBody>
                  </Card>
                );
              })}
            </div>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Tip: open the Macro dashboard and click &ldquo;Load live&rdquo; to
              refresh stored values for any series.
            </p>
          </CardBody>
        </Card>
      ) : (
        <Card>
          <CardBody className="flex flex-col items-center gap-3 py-8 text-center">
            <svg className="h-10 w-10 text-zinc-600" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" aria-hidden>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
            </svg>
            <div className="space-y-1">
              <p className="text-sm font-medium text-zinc-300">No macro data stored yet</p>
              <p className="text-xs text-zinc-500">Import economic indicators to see them here.</p>
            </div>
            <Link
              href="/dashboard/economic"
              className="inline-flex items-center justify-center rounded-md bg-zinc-800 px-3 py-1.5 text-sm font-medium text-zinc-200 hover:bg-zinc-700"
            >
              Go to Macro dashboard
            </Link>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
