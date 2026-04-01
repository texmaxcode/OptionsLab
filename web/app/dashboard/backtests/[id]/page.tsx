"use client";

import { Fragment, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { getBacktest, deleteBacktest, updateBacktest, type BacktestDetail } from "@/lib/labApi";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EquityCurveChart } from "@/components/EquityCurveChart";
import { DrawdownChart } from "@/components/DrawdownChart";
import { PriceIndicatorsChart } from "@/components/PriceIndicatorsChart";
import { ReturnsChart } from "@/components/ReturnsChart";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";

export default function BacktestDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [backtest, setBacktest] = useState<BacktestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null);
  const [selectedReturnDate, setSelectedReturnDate] = useState<string | null>(null);
  const [editingName, setEditingName] = useState(false);
  const [nameInput, setNameInput] = useState("");
  const [savingName, setSavingName] = useState(false);

  useEffect(() => {
    const idNum = Number(params.id);
    if (!idNum) {
      setError("Invalid backtest id");
      setLoading(false);
      return;
    }
    getBacktest(idNum)
      .then(setBacktest)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [params.id]);

  if (loading) {
    return <p className="text-sm text-zinc-600 dark:text-zinc-400">Loading…</p>;
  }

  if (error || !backtest) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-red-600 dark:text-red-400">
          {error ?? "Backtest not found"}
        </p>
        <Link
          href="/dashboard/backtests"
          className="text-sm text-emerald-600 hover:text-emerald-700"
        >
          Back to backtests
        </Link>
      </div>
    );
  }

  const hasValues =
    backtest.start_value != null && backtest.end_value != null;
  const pnl =
    hasValues && backtest.start_value != null && backtest.end_value != null
      ? backtest.end_value - backtest.start_value
      : null;
  const totalReturnPct =
    hasValues &&
    backtest.start_value != null &&
    backtest.end_value != null &&
    backtest.start_value !== 0
      ? ((backtest.end_value - backtest.start_value) / backtest.start_value) * 100
      : null;
  const maxDrawdownPct =
    backtest.drawdown_curve && backtest.drawdown_curve.length > 0
      ? backtest.drawdown_curve.reduce(
          (max, p) => (p.drawdown > max ? p.drawdown : max),
          0
        )
      : null;
  const periodReturns = backtest.time_returns?.map((r) => r.period_return) ?? [];
  const avgPeriodReturn =
    periodReturns.length > 0
      ? periodReturns.reduce((sum, r) => sum + r, 0) / periodReturns.length
      : null;
  const stdDevPeriodReturn =
    periodReturns.length > 1 && avgPeriodReturn != null
      ? Math.sqrt(
          periodReturns.reduce((sum, r) => sum + (r - avgPeriodReturn) ** 2, 0) /
            (periodReturns.length - 1)
        )
      : null;
  const annualizedVolatility =
    stdDevPeriodReturn != null ? stdDevPeriodReturn * Math.sqrt(252) : null;
  const sharpeRatio =
    avgPeriodReturn != null && stdDevPeriodReturn && stdDevPeriodReturn > 0
      ? (avgPeriodReturn / stdDevPeriodReturn) * Math.sqrt(252)
      : null;
  const statusTone =
    backtest.status === "completed"
      ? "green"
      : backtest.status === "failed"
        ? "red"
        : "gray";
  const tradesWithId =
    backtest.trades?.map((t, idx) => ({
      ...t,
      id: `${t.entry_date}-${t.exit_date ?? ""}-${idx}`,
    })) ?? [];

  const selectedTrade = selectedTradeId ? tradesWithId.find((t) => t.id === selectedTradeId) : null;
  const chartDateDomain = (() => {
    const series = backtest.price_series?.length
      ? backtest.price_series
      : backtest.equity_curve?.length
        ? backtest.equity_curve.map((p) => ({ date: p.date }))
        : [];
    if (series.length === 0 && backtest.from_date && backtest.to_date) {
      return { from: backtest.from_date, to: backtest.to_date };
    }
    if (series.length === 0) return undefined;
    const dates = series.map((p) => p.date).sort();
    return { from: dates[0]!, to: dates[dates.length - 1]! };
  })();
  const highlightRange =
    selectedTrade?.entry_date != null && selectedTrade?.exit_date != null
      ? { from: selectedTrade.entry_date, to: selectedTrade.exit_date }
      : selectedTrade?.entry_date != null
        ? { from: selectedTrade.entry_date, to: selectedTrade.entry_date }
        : null;

  const priceSeries = backtest.price_series ?? [];
  const getPriceAtDate = (dateStr: string): number | null => {
    if (!priceSeries.length) return null;
    const t = new Date(dateStr).getTime();
    let best = priceSeries[0];
    let bestDiff = Math.abs(new Date(best.date).getTime() - t);
    for (const p of priceSeries) {
      const diff = Math.abs(new Date(p.date).getTime() - t);
      if (diff < bestDiff) {
        bestDiff = diff;
        best = p;
      }
    }
    return best.close;
  };

  const exitPrice = (t: (typeof tradesWithId)[number]): number | null => {
    if (t.exit_price != null) return t.exit_price;
    if (t.size !== 0) return t.entry_price + t.pnl / t.size;
    if (t.exit_date != null) return getPriceAtDate(t.exit_date);
    return null;
  };
  const exitPriceDisplay = (t: (typeof tradesWithId)[number]): string => {
    const ep = exitPrice(t);
    return ep != null ? ep.toFixed(2) : "—";
  };

  return (
    <div className="space-y-4 max-w-6xl min-w-0">
      <ConfirmDialog
        open={deleteDialogOpen}
        onClose={() => !deleting && setDeleteDialogOpen(false)}
        title="Delete backtest"
        message="Delete this backtest and all data? Cannot be undone."
        confirmLabel="Delete"
        cancelLabel="Cancel"
        onConfirm={async () => {
          setDeleting(true);
          setDeleteError(null);
          try {
            await deleteBacktest(backtest.id);
            router.push("/dashboard/backtests");
          } catch (e) {
            setDeleteError(String(e));
          } finally {
            setDeleting(false);
          }
        }}
        variant="danger"
        loading={deleting}
      />

      <PageHeader
        title={
          editingName ? (
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={nameInput}
                onChange={(e) => setNameInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    setEditingName(false);
                    if (nameInput.trim() && nameInput.trim() !== backtest.name) {
                      setSavingName(true);
                      updateBacktest(backtest.id, { name: nameInput.trim() })
                        .then((updated) => setBacktest(updated))
                        .finally(() => setSavingName(false));
                    }
                  } else if (e.key === "Escape") {
                    setNameInput(backtest.name);
                    setEditingName(false);
                  }
                }}
                onBlur={() => {
                  setEditingName(false);
                  if (nameInput.trim() && nameInput.trim() !== backtest.name) {
                    setSavingName(true);
                    updateBacktest(backtest.id, { name: nameInput.trim() })
                      .then((updated) => setBacktest(updated))
                      .finally(() => setSavingName(false));
                  } else {
                    setNameInput(backtest.name);
                  }
                }}
                autoFocus
                className="rounded border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 px-2 py-1 text-xl sm:text-2xl font-semibold text-zinc-900 dark:text-zinc-100 min-w-[200px]"
              />
              {savingName && <span className="text-sm text-zinc-500">Saving…</span>}
            </div>
          ) : (
            <button
              type="button"
              onClick={() => {
                setNameInput(backtest.name);
                setEditingName(true);
              }}
              className="group inline-flex items-center gap-1.5 text-left hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded px-1 -ml-1 transition-colors"
            >
              {backtest.name}
              <svg className="h-4 w-4 opacity-50 group-hover:opacity-100 shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" aria-hidden>
                <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125" />
              </svg>
            </button>
          )
        }
        subtitle={`${backtest.strategy} on ${backtest.underlying}`}
        actions={
          <div className="flex items-center gap-2">
            <Link
              href="/dashboard/backtests"
              className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 dark:bg-emerald-500/20 hover:bg-emerald-500/20 dark:hover:bg-emerald-500/30 hover:text-emerald-700 dark:hover:text-emerald-300 transition-colors"
            >
              <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" aria-hidden>
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
              </svg>
              Back
            </Link>
            <Button
              type="button"
              variant="danger"
              size="sm"
              onClick={() => setDeleteDialogOpen(true)}
              disabled={deleting}
            >
              Delete
            </Button>
          </div>
        }
      />

      {deleteError && (
        <p className="text-sm text-red-600 dark:text-red-400">{deleteError}</p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Card>
          <CardBody className="space-y-2 text-base sm:text-sm">
            <div className="flex justify-between gap-2">
              <span className="text-zinc-600 dark:text-zinc-400">Dates</span>
              <span className="text-zinc-900 dark:text-zinc-100">
                {backtest.from_date ?? "—"} → {backtest.to_date ?? "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-600 dark:text-zinc-400">Cash</span>
              <span className="font-mono text-zinc-900 dark:text-zinc-100">
                {backtest.cash.toLocaleString()}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-600 dark:text-zinc-400">Status</span>
              <Badge tone={statusTone}>{backtest.status}</Badge>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-600 dark:text-zinc-400">Start value</span>
              <span className="font-mono text-zinc-900 dark:text-zinc-100">
                {backtest.start_value?.toLocaleString() ?? "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-600 dark:text-zinc-400">End value</span>
              <span className="font-mono text-zinc-900 dark:text-zinc-100">
                {backtest.end_value?.toLocaleString() ?? "—"}
              </span>
            </div>
            <div className="flex justify-between border-t border-zinc-200 dark:border-zinc-800 pt-2">
              <span className="text-zinc-600 dark:text-zinc-400">PnL</span>
              <span
                className={`font-mono ${
                  pnl == null
                    ? "text-zinc-500"
                    : pnl >= 0
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-red-600 dark:text-red-400"
                }`}
              >
                {pnl == null
                  ? "—"
                  : `${pnl >= 0 ? "+" : ""}${pnl.toLocaleString(undefined, {
                      maximumFractionDigits: 0,
                    })}`}
              </span>
            </div>
            {backtest.error && (
              <div className="mt-2 rounded-md bg-red-50 dark:bg-red-900/20 px-3 py-2 text-xs text-red-800 dark:text-red-200">
                {backtest.error}
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardBody className="space-y-2 text-base sm:text-sm">
            <div className="flex justify-between gap-2">
              <span className="text-zinc-600 dark:text-zinc-400">Total return</span>
              <span className="font-mono text-zinc-900 dark:text-zinc-100">
                {totalReturnPct == null
                  ? "—"
                  : `${totalReturnPct >= 0 ? "+" : ""}${totalReturnPct.toFixed(2)}%`}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-600 dark:text-zinc-400">Max drawdown</span>
              <span className="font-mono text-zinc-900 dark:text-zinc-100">
                {maxDrawdownPct == null ? "—" : `${maxDrawdownPct.toFixed(2)}%`}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-600 dark:text-zinc-400">
                Annualized volatility
              </span>
              <span className="font-mono text-zinc-900 dark:text-zinc-100">
                {annualizedVolatility == null
                  ? "—"
                  : `${(annualizedVolatility * 100).toFixed(2)}%`}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-600 dark:text-zinc-400">Sharpe ratio</span>
              <span className="font-mono text-zinc-900 dark:text-zinc-100">
                {sharpeRatio == null ? "—" : sharpeRatio.toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-600 dark:text-zinc-400">Periods</span>
              <span className="font-mono text-zinc-900 dark:text-zinc-100">
                {periodReturns.length}
              </span>
            </div>
          </CardBody>
        </Card>
      </div>

      {backtest.trade_stats && (
        <Card>
          <CardBody className="space-y-2 text-sm">
            <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              Trade statistics
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 min-w-0">
              <div className="min-w-0">
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Trades</p>
                <p className="font-mono text-zinc-900 dark:text-zinc-100">
                  {backtest.trade_stats.trade_count}
                </p>
              </div>
              <div className="min-w-0">
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Win rate</p>
                <p className="font-mono text-zinc-900 dark:text-zinc-100">
                  {backtest.trade_stats.win_rate.toFixed(2)}%
                </p>
              </div>
              <div className="min-w-0">
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Profit factor</p>
                <p className="font-mono text-zinc-900 dark:text-zinc-100">
                  {backtest.trade_stats.profit_factor != null
                    ? backtest.trade_stats.profit_factor.toFixed(2)
                    : "—"}
                </p>
              </div>
              <div className="min-w-0">
                <p className="text-xs text-zinc-500 dark:text-zinc-400">
                  Avg PnL/trade
                </p>
                <p className="font-mono text-zinc-900 dark:text-zinc-100">
                  {backtest.trade_stats.avg_pnl != null
                    ? backtest.trade_stats.avg_pnl.toFixed(2)
                    : "—"}
                </p>
              </div>
              <div className="min-w-0">
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Avg win</p>
                <p className="font-mono text-zinc-900 dark:text-zinc-100">
                  {backtest.trade_stats.avg_win != null
                    ? backtest.trade_stats.avg_win.toFixed(2)
                    : "—"}
                </p>
              </div>
              <div className="min-w-0">
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Avg loss</p>
                <p className="font-mono text-zinc-900 dark:text-zinc-100">
                  {backtest.trade_stats.avg_loss != null
                    ? backtest.trade_stats.avg_loss.toFixed(2)
                    : "—"}
                </p>
              </div>
              <div className="min-w-0">
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Best trade</p>
                <p className="font-mono text-zinc-900 dark:text-zinc-100">
                  {backtest.trade_stats.best_trade_pnl != null
                    ? backtest.trade_stats.best_trade_pnl.toFixed(2)
                    : "—"}
                </p>
              </div>
              <div className="min-w-0">
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Worst trade</p>
                <p className="font-mono text-zinc-900 dark:text-zinc-100">
                  {backtest.trade_stats.worst_trade_pnl != null
                    ? backtest.trade_stats.worst_trade_pnl.toFixed(2)
                    : "—"}
                </p>
              </div>
              <div className="min-w-0">
                <p className="text-xs text-zinc-500 dark:text-zinc-400">
                  Avg hold (days)
                </p>
                <p className="font-mono text-zinc-900 dark:text-zinc-100">
                  {backtest.trade_stats.avg_hold_days != null
                    ? backtest.trade_stats.avg_hold_days.toFixed(2)
                    : "—"}
                </p>
              </div>
            </div>
          </CardBody>
        </Card>
      )}

      {(backtest.price_series?.length ?? 0) > 0 && (
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-3 sm:p-4 min-w-0 overflow-visible">
          <h2 className="text-base sm:text-sm md:text-base font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
            Price, indicators &amp; trades
          </h2>
          <PriceIndicatorsChart
            priceSeries={backtest.price_series ?? []}
            indicatorSeries={backtest.indicator_series ?? null}
            trades={tradesWithId}
            activeTradeId={selectedTradeId}
            onSelectTrade={(id) => setSelectedTradeId(id)}
            highlightRange={highlightRange}
            className="w-full"
          />
        </div>
      )}

      {tradesWithId.length > 0 && (
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-3 sm:p-4 min-w-0 overflow-hidden">
          <h2 className="text-base sm:text-sm md:text-base font-semibold text-zinc-900 dark:text-zinc-100 mb-3">
            Trades
          </h2>
          <ul className="space-y-3">
            {tradesWithId.map((t) => (
              <Fragment key={t.id}>
                <li
                  className={`rounded-lg border cursor-pointer transition-colors ${
                    t.id === selectedTradeId
                      ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20 dark:border-emerald-600"
                      : "border-zinc-200 dark:border-zinc-700 hover:bg-zinc-50 dark:hover:bg-zinc-900/40"
                  }`}
                  onMouseEnter={() => {
                    const markers = document.querySelectorAll<SVGElement>(
                      `[data-trade-id=\"${t.id}\"]`
                    );
                    markers.forEach((el) => {
                      el.classList.add("ring-2", "ring-emerald-500");
                    });
                  }}
                  onMouseLeave={() => {
                    const markers = document.querySelectorAll<SVGElement>(
                      ".trade-entry, .trade-exit"
                    );
                    markers.forEach((el) => {
                      el.classList.remove("ring-2", "ring-emerald-500");
                    });
                  }}
                  onClick={() =>
                    setSelectedTradeId((prev) => (prev === t.id ? null : t.id))
                  }
                >
                  <div className="px-4 py-3 sm:px-5 sm:py-4">
                    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 sm:gap-4">
                      <div>
                        <p className="text-sm sm:text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wide">Entry</p>
                        <p className="font-mono text-sm text-zinc-900 dark:text-zinc-100 mt-0.5">{t.entry_date}</p>
                        <p className="font-mono text-base sm:text-sm font-medium text-zinc-900 dark:text-zinc-100">{t.entry_price.toFixed(2)}</p>
                      </div>
                      <div>
                        <p className="text-sm sm:text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wide">Exit</p>
                        <p className="font-mono text-sm text-zinc-900 dark:text-zinc-100 mt-0.5">{t.exit_date ?? "—"}</p>
                        <p className="font-mono text-sm font-medium text-zinc-900 dark:text-zinc-100">{exitPriceDisplay(t)}</p>
                      </div>
                      <div>
                        <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wide">Dir</p>
                        <p className="text-sm capitalize text-zinc-900 dark:text-zinc-100 mt-0.5">{t.direction}</p>
                      </div>
                      <div>
                        <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wide">Size</p>
                        <p className="font-mono text-sm text-zinc-900 dark:text-zinc-100 mt-0.5">{t.size.toFixed(2)}</p>
                      </div>
                      <div>
                        <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wide">PnL</p>
                        <p
                          className={`font-mono text-sm font-medium mt-0.5 ${
                            t.pnl > 0
                              ? "text-emerald-600 dark:text-emerald-400"
                              : t.pnl < 0
                                ? "text-red-600 dark:text-red-400"
                                : "text-zinc-600 dark:text-zinc-300"
                          }`}
                        >
                          {t.pnl.toFixed(2)}
                          {t.pnl_pct != null ? ` (${t.pnl_pct.toFixed(2)}%)` : ""}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wide">Days</p>
                        <p className="font-mono text-sm text-zinc-900 dark:text-zinc-100 mt-0.5">
                          {t.duration_days != null ? t.duration_days : "—"}
                        </p>
                      </div>
                    </div>
                  </div>
                </li>
                {t.id === selectedTradeId && (
                  <li className="rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900/40 px-4 py-3 sm:px-5 sm:py-4">
                    <p className="text-xs font-semibold text-zinc-700 dark:text-zinc-200 mb-3">
                      {t.direction.toUpperCase()} × {t.size.toFixed(2)}
                    </p>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800/50 px-4 py-3">
                        <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wide">Entry</p>
                        <p className="font-mono text-sm text-zinc-900 dark:text-zinc-100 mt-1">{t.entry_date}</p>
                        <p className="font-mono text-sm font-medium text-zinc-900 dark:text-zinc-100">{t.entry_price.toFixed(2)}</p>
                      </div>
                      <div className="rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800/50 px-4 py-3">
                        <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wide">Exit</p>
                        <p className="font-mono text-sm text-zinc-900 dark:text-zinc-100 mt-1">{t.exit_date ?? "—"}</p>
                        <p className="font-mono text-sm font-medium text-zinc-900 dark:text-zinc-100">{exitPriceDisplay(t)}</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1 mt-3">
                      <div>
                        <span className="text-xs text-zinc-500 dark:text-zinc-400">PnL</span>{" "}
                        <span
                          className={`font-mono text-sm font-medium ${
                            t.pnl > 0
                              ? "text-emerald-600 dark:text-emerald-400"
                              : t.pnl < 0
                                ? "text-red-600 dark:text-red-400"
                                : "text-zinc-600 dark:text-zinc-300"
                          }`}
                        >
                          {t.pnl.toFixed(2)}
                          {t.pnl_pct != null ? ` (${t.pnl_pct.toFixed(2)}%)` : ""}
                        </span>
                      </div>
                      {t.duration_days != null && (
                        <div>
                          <span className="text-xs text-zinc-500 dark:text-zinc-400">Hold</span>{" "}
                          <span className="font-mono text-sm text-zinc-900 dark:text-zinc-100">{t.duration_days} days</span>
                        </div>
                      )}
                    </div>
                  </li>
                )}
              </Fragment>
            ))}
          </ul>
        </div>
      )}

      {backtest.equity_curve && backtest.equity_curve.length > 0 && (
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-3 sm:p-4 min-w-0 overflow-visible">
          <h2 className="text-sm sm:text-base font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
            Equity curve
          </h2>
          <EquityCurveChart data={backtest.equity_curve} highlightRange={highlightRange} className="w-full" />
        </div>
      )}

      {backtest.drawdown_curve && backtest.drawdown_curve.length > 0 && (
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-3 sm:p-4 min-w-0 overflow-visible">
          <h2 className="text-sm sm:text-base font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
            Drawdown
          </h2>
          <DrawdownChart data={backtest.drawdown_curve} highlightRange={highlightRange} className="w-full" />
        </div>
      )}

      {(() => {
        const timeReturnsNonZero =
          backtest.time_returns?.filter((r) => r.period_return !== 0) ?? [];
        if (timeReturnsNonZero.length === 0) return null;

        const returnsHighlightRange = selectedTrade
          ? {
              from: selectedTrade.entry_date,
              to: selectedTrade.exit_date ?? selectedTrade.entry_date,
            }
          : selectedReturnDate
            ? { from: selectedReturnDate, to: selectedReturnDate }
            : null;

        const timeReturnsInRange = selectedTrade
          ? timeReturnsNonZero.filter((r) => {
              const entry = selectedTrade.entry_date;
              const exit = selectedTrade.exit_date ?? selectedTrade.entry_date;
              return r.date >= entry && r.date <= exit;
            })
          : timeReturnsNonZero;

        return (
          <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-3 sm:p-4 min-w-0 overflow-hidden">
            <h2 className="text-base sm:text-sm md:text-base font-semibold text-zinc-900 dark:text-zinc-100 mb-3">
              Period returns
              {selectedTrade && (
                <span className="ml-2 text-sm font-normal text-zinc-500 dark:text-zinc-400">
                  (trade: {selectedTrade.entry_date} → {selectedTrade.exit_date ?? "—"})
                </span>
              )}
            </h2>
            <ReturnsChart
              data={timeReturnsNonZero}
              dateDomain={chartDateDomain}
              highlightRange={returnsHighlightRange}
              selectedDate={selectedReturnDate}
              onSelectPoint={(date) => setSelectedReturnDate(date)}
              className="w-full"
            />
            <ul className="space-y-3 mt-4">
              {timeReturnsInRange.map((r, idx) => {
                const isSelected = selectedReturnDate === r.date;
                const isPositive = r.period_return > 0;
                return (
                  <li
                    key={`period-return-${idx}`}
                    role="button"
                    tabIndex={0}
                    onClick={() =>
                      setSelectedReturnDate((prev) => (prev === r.date ? null : r.date))
                    }
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setSelectedReturnDate((prev) => (prev === r.date ? null : r.date));
                      }
                    }}
                    className={`rounded-lg border cursor-pointer transition-colors border-l-4 ${
                      isSelected
                        ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20 dark:border-emerald-600 border-l-emerald-500"
                        : isPositive
                          ? "border-zinc-200 dark:border-zinc-700 border-l-emerald-500 hover:bg-emerald-50/50 dark:hover:bg-emerald-900/10"
                          : "border-zinc-200 dark:border-zinc-700 border-l-red-500 hover:bg-red-50/50 dark:hover:bg-red-900/10"
                    }`}
                  >
                    <div className="px-4 py-3 sm:px-5 sm:py-4">
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
                        <div>
                          <p className="text-sm sm:text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wide">
                            Date
                          </p>
                          <p className="font-mono text-sm text-zinc-900 dark:text-zinc-100 mt-0.5">
                            {r.date}
                          </p>
                        </div>
                        <div>
                          <p className="text-sm sm:text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wide">
                            Return
                          </p>
                          <p
                            className={`font-mono text-sm font-medium mt-0.5 ${
                              isPositive
                                ? "text-emerald-600 dark:text-emerald-400"
                                : "text-red-600 dark:text-red-400"
                            }`}
                          >
                            {r.period_return >= 0 ? "+" : ""}
                            {(r.period_return * 100).toFixed(2)}%
                          </p>
                        </div>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })()}
    </div>
  );
}

