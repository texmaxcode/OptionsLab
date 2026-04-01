 "use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listBacktests,
  deleteBacktest,
  updateBacktest,
  getDashboardSummary,
  type BacktestSummary,
  type DashboardSummary,
  type EquityCurvePoint,
} from "@/lib/labApi";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { EquityCurveChart } from "@/components/EquityCurveChart";

export default function BacktestsListPage() {
  const [backtests, setBacktests] = useState<BacktestSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [backtestToDelete, setBacktestToDelete] =
    useState<BacktestSummary | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [nameInput, setNameInput] = useState("");
  const [savingId, setSavingId] = useState<number | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([listBacktests(), getDashboardSummary()])
      .then(([items, dashboard]) => {
        setBacktests(items);
        setSummary(dashboard);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const handleConfirmDelete = async () => {
    if (!backtestToDelete) return;
    setDeleting(true);
    try {
      await deleteBacktest(backtestToDelete.id);
      setBacktests((prev) => prev.filter((x) => x.id !== backtestToDelete.id));
      setBacktestToDelete(null);
    } catch (err) {
      setError(String(err));
    } finally {
      setDeleting(false);
    }
  };

  const saveRename = (b: BacktestSummary) => {
    const trimmed = nameInput.trim();
    if (!trimmed || trimmed === b.name) {
      setEditingId(null);
      return;
    }
    setSavingId(b.id);
    updateBacktest(b.id, { name: trimmed })
      .then((updated) => {
        setBacktests((prev) =>
          prev.map((x) => (x.id === b.id ? { ...x, name: updated.name } : x))
        );
        setEditingId(null);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setSavingId(null));
  };

  const startEdit = (b: BacktestSummary) => {
    setNameInput(b.name);
    setEditingId(b.id);
  };

  const cancelEdit = () => {
    setEditingId(null);
  };

  const overall = summary?.overall;
  const overallTrades = summary?.overall_trade_stats;
  const equityTrades = summary?.equity_trade_stats;
  const optionsTrades = summary?.options_trade_stats;

  return (
    <div className="space-y-3 min-w-0">
      <ConfirmDialog
        open={!!backtestToDelete}
        onClose={() => setBacktestToDelete(null)}
        title="Delete backtest"
        message={
          backtestToDelete
            ? `Delete "${backtestToDelete.name}"${
                backtestToDelete.from_date && backtestToDelete.to_date
                  ? ` (${backtestToDelete.from_date} \u2192 ${backtestToDelete.to_date})`
                  : ""
              } and all associated trades and data? This cannot be undone.`
            : ""
        }
        confirmLabel="Delete"
        cancelLabel="Cancel"
        onConfirm={handleConfirmDelete}
        variant="danger"
        loading={deleting}
      />

      <PageHeader
        title="Backtests"
        subtitle="Saved runs, stats, and equity curves."
        actions={
          <Link
            href="/dashboard/backtests/new"
            className="inline-flex items-center justify-center rounded-md bg-emerald-600 px-2.5 py-1.5 text-sm font-medium text-white hover:bg-emerald-700"
          >
            Create backtest
          </Link>
        }
      />

      {error && (
        <div className="flex items-start gap-2 rounded-md border border-red-700/50 bg-red-900/20 px-3 py-2.5 text-sm text-red-300">
          <svg className="h-4 w-4 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
          </svg>
          {error}
        </div>
      )}

      {summary && backtests.length > 0 && (
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <Card>
              <CardBody className="space-y-0.5">
                <p className="text-sm sm:text-xs font-medium text-zinc-500 dark:text-zinc-400">
                  Total backtests
                </p>
                <p className="text-2xl sm:text-xl md:text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
                  {overall?.total ?? 0}
                </p>
                <p className="text-sm sm:text-xs text-zinc-500 dark:text-zinc-400">
                  Completed: {overall?.completed ?? 0} · Avg return:{" "}
                  {overall?.avg_return_pct != null
                    ? `${overall.avg_return_pct.toFixed(1)}%`
                    : "—"}
                </p>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="space-y-0.5">
                <p className="text-sm sm:text-xs font-medium text-zinc-500 dark:text-zinc-400">
                  Equity win rate
                </p>
                <p className="text-2xl sm:text-xl md:text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
                  {summary.equity ? summary.equity.win_rate.toFixed(1) : "0.0"}%
                </p>
                <p className="text-sm sm:text-xs text-zinc-500 dark:text-zinc-400">
                  Stock strategies. Avg:{" "}
                  {summary.equity?.avg_return_pct != null
                    ? `${summary.equity.avg_return_pct.toFixed(1)}%`
                    : "—"}
                </p>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="space-y-0.5">
                <p className="text-sm sm:text-xs font-medium text-zinc-500 dark:text-zinc-400">
                  Options win rate
                </p>
                <p className="text-2xl sm:text-xl md:text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
                  {summary.options
                    ? summary.options.win_rate.toFixed(1)
                    : "0.0"}%
                </p>
                <p className="text-sm sm:text-xs text-zinc-500 dark:text-zinc-400">
                  Options strategies. Avg:{" "}
                  {summary.options?.avg_return_pct != null
                    ? `${summary.options.avg_return_pct.toFixed(1)}%`
                    : "—"}
                </p>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="space-y-0.5">
                <p className="text-sm sm:text-xs font-medium text-zinc-500 dark:text-zinc-400">
                  Best &amp; worst backtests
                </p>
                <p className="text-2xl sm:text-xl md:text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
                  {overall?.best_return_pct != null
                    ? `${overall.best_return_pct.toFixed(1)}%`
                    : "—"}
                </p>
                <p className="text-sm sm:text-xs text-zinc-500 dark:text-zinc-400">
                  Worst:{" "}
                  {overall?.worst_return_pct != null
                    ? `${overall.worst_return_pct.toFixed(1)}%`
                    : "—"}
                </p>
              </CardBody>
            </Card>
          </div>

          {overallTrades && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              <Card>
                <CardBody className="space-y-0.5">
                  <p className="text-sm sm:text-xs font-medium text-zinc-500 dark:text-zinc-400">
                    Overall trades
                  </p>
                  <p className="text-2xl sm:text-xl md:text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
                    {overallTrades.trade_count}
                  </p>
                  <p className="text-sm sm:text-xs text-zinc-500 dark:text-zinc-400">
                    Win rate: {overallTrades.win_rate.toFixed(1)}%, PF:{" "}
                    {overallTrades.profit_factor != null
                      ? overallTrades.profit_factor.toFixed(2)
                      : "—"}
                  </p>
                </CardBody>
              </Card>
              <Card>
                <CardBody className="space-y-0.5">
                  <p className="text-sm sm:text-xs font-medium text-zinc-500 dark:text-zinc-400">
                    Equity trades
                  </p>
                  <p className="text-2xl sm:text-xl md:text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
                    {equityTrades?.trade_count ?? 0}
                  </p>
                  <p className="text-sm sm:text-xs text-zinc-500 dark:text-zinc-400">
                    Win rate:{" "}
                    {equityTrades
                      ? equityTrades.win_rate.toFixed(1)
                      : "0.0"}%, PF:{" "}
                    {equityTrades?.profit_factor != null
                      ? equityTrades.profit_factor.toFixed(2)
                      : "—"}
                  </p>
                </CardBody>
              </Card>
              <Card>
                <CardBody className="space-y-0.5">
                  <p className="text-sm sm:text-xs font-medium text-zinc-500 dark:text-zinc-400">
                    Options trades
                  </p>
                  <p className="text-2xl sm:text-xl md:text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
                    {optionsTrades?.trade_count ?? 0}
                  </p>
                  <p className="text-sm sm:text-xs text-zinc-500 dark:text-zinc-400">
                    Win rate:{" "}
                    {optionsTrades
                      ? optionsTrades.win_rate.toFixed(1)
                      : "0.0"}%, PF:{" "}
                    {optionsTrades?.profit_factor != null
                      ? optionsTrades.profit_factor.toFixed(2)
                      : "—"}
                  </p>
                </CardBody>
              </Card>
            </div>
          )}

          {summary.overall_equity_curve && (
            <Card className="overflow-visible">
              <CardBody className="space-y-2 overflow-visible">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 className="text-base sm:text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                    Backtest equity over time
                  </h2>
                  <Badge tone="gray">Sequential runs, normalized</Badge>
                </div>
                <p className="text-sm sm:text-xs text-zinc-600 dark:text-zinc-400">
                  Hypothetical equity: full capital per run, in order.
                </p>
                <EquityCurveChart
                  data={summary.overall_equity_curve as EquityCurvePoint[]}
                  className="mt-1"
                />
              </CardBody>
            </Card>
          )}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-zinc-600 dark:text-zinc-400">Loading…</p>
      ) : backtests.length === 0 ? (
        <EmptyState
          title="No backtests yet"
          description="Create your first backtest to see it here."
          action={
            <Link
              href="/dashboard/backtests/new"
              className="inline-flex items-center justify-center rounded-md bg-emerald-600 px-2.5 py-1.5 text-sm font-medium text-white hover:bg-emerald-700"
            >
                Create backtest
            </Link>
          }
        />
      ) : (
        <Card className="overflow-hidden">
          <CardBody className="p-0">
            <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
              {backtests.map((b) => {
                const pnl =
                  b.start_value != null && b.end_value != null
                    ? b.end_value - b.start_value
                    : null;
                const pnlClass =
                  pnl == null
                    ? "text-zinc-500"
                    : pnl >= 0
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-red-600 dark:text-red-400";
                const statusTone =
                  b.status === "completed"
                    ? "green"
                    : b.status === "failed"
                      ? "red"
                      : "gray";
                return (
                  <li key={b.id} className="hover:bg-zinc-50/60 dark:hover:bg-zinc-950/40">
                    <div className="px-4 py-4 sm:px-5 sm:py-4">
                      <div className="flex flex-wrap items-start justify-between gap-4">
                        <div className="min-w-0 flex-1 space-y-1">
                          {editingId === b.id ? (
                            <div className="flex items-center gap-2">
                              <input
                                type="text"
                                value={nameInput}
                                onChange={(e) => setNameInput(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") saveRename(b);
                                  else if (e.key === "Escape") cancelEdit();
                                }}
                                onBlur={() => saveRename(b)}
                                autoFocus
                                className="rounded border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 px-2 py-1 text-base font-medium text-zinc-900 dark:text-zinc-100 min-w-[160px]"
                              />
                              {savingId === b.id && (
                                <span className="text-xs text-zinc-500">Saving…</span>
                              )}
                            </div>
                          ) : (
                            <div className="flex items-center gap-1.5">
                              <Link
                                href={`/dashboard/backtests/${b.id}`}
                                className="text-base font-medium text-emerald-700 dark:text-emerald-300 hover:underline block"
                              >
                                {b.name}
                              </Link>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.preventDefault();
                                  startEdit(b);
                                }}
                                className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 p-0.5 rounded"
                                aria-label="Rename"
                              >
                                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125" />
                                </svg>
                              </button>
                            </div>
                          )}
                          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-zinc-600 dark:text-zinc-400">
                            <span>{b.strategy}</span>
                            <span>{b.underlying}</span>
                            <span>
                              {b.from_date ?? "—"} → {b.to_date ?? "—"}
                            </span>
                          </div>
                        </div>
                        <div className="flex flex-wrap items-center gap-3 shrink-0">
                          <span className={`font-mono text-sm font-medium ${pnlClass}`}>
                            {pnl == null
                              ? "—"
                              : pnl >= 0
                                ? `+${pnl.toFixed(0)}`
                                : pnl.toFixed(0)}
                          </span>
                          <Badge tone={statusTone}>{b.status}</Badge>
                          <button
                            type="button"
                            onClick={() => setBacktestToDelete(b)}
                            className="text-sm text-red-600 dark:text-red-400 hover:underline"
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          </CardBody>
        </Card>
      )}
    </div>
  );
}

