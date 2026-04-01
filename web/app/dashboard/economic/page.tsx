"use client";

import { useEffect, useMemo, useState } from "react";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DateField } from "@/components/ui/DateField";
import { SelectField } from "@/components/ui/SelectField";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EconomicSeriesChart } from "@/components/EconomicSeriesChart";
import {
  deleteStoredEconomicSeries,
  getEconomicSeries,
  getStoredEconomicSeries,
  listStoredEconomicSeries,
  type EconomicSeriesPoint,
  type EconomicSource,
  type StoredEconomicSeriesInfo,
} from "@/lib/economicApi";
import { getUserSettings } from "@/lib/settingsApi";

const PRESETS: Record<
  EconomicSource,
  { id: string; label: string }[]
> = {
  fred: [
    { id: "GDP", label: "Real GDP (quarterly)" },
    { id: "CPIAUCSL", label: "CPI, all urban consumers" },
    { id: "UNRATE", label: "Unemployment rate (U.S.)" },
    { id: "IPMAN", label: "Manufacturing production (IPMAN index)" },
    { id: "DGS10", label: "10-year Treasury yield" },
    { id: "DEXUSEU", label: "EUR/USD exchange rate" },
    { id: "VIXCLS", label: "VIX volatility index" },
  ],
  bls: [
    { id: "CUUR0000SA0", label: "CPI-U, all items (BLS)" },
    { id: "LNS14000000", label: "Unemployment rate (BLS, household survey)" },
  ],
  bea: [{ id: "T10101", label: "U.S. GDP (BEA NIPA T10101)" }],
};

const SOURCE_LABELS: Record<EconomicSource, string> = {
  fred: "FRED (macro)",
  bls: "BLS (labor & CPI)",
  bea: "BEA (GDP & accounts)",
};

export default function EconomicDashboardPage() {
  const [source, setSource] = useState<EconomicSource>("fred");
  const [seriesId, setSeriesId] = useState(PRESETS.fred[0]?.id ?? "GDP");
  const [fromDate, setFromDate] = useState("2015-01-01");
  const [toDate, setToDate] = useState("2024-12-31");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [points, setPoints] = useState<EconomicSeriesPoint[]>([]);
  const [useStored, setUseStored] = useState(false);
  const [storedList, setStoredList] = useState<StoredEconomicSeriesInfo[]>([]);
  const [storedLoading, setStoredLoading] = useState(false);
  const [listQuery, setListQuery] = useState("");
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{ source: EconomicSource; series_id: string } | null>(null);

  const [importAllRunning, setImportAllRunning] = useState(false);
  const [importAllProgress, setImportAllProgress] = useState<{ done: number; total: number } | null>(null);
  const [importAllResult, setImportAllResult] = useState<
    { source: EconomicSource; series_id: string; ok: boolean; points?: number; error?: string }[] | null
  >(null);

  const refreshStoredList = async () => {
    const ac = new AbortController();
    setStoredLoading(true);
    listStoredEconomicSeries()
      .then((res) => {
        if (!ac.signal.aborted) setStoredList(res.items);
      })
      .catch(() => {
        if (!ac.signal.aborted) setStoredList([]);
      })
      .finally(() => {
        if (!ac.signal.aborted) setStoredLoading(false);
      });
    return () => ac.abort();
  };

  useEffect(() => {
    void refreshStoredList();
  }, []);

  useEffect(() => {
    getUserSettings()
      .then((settings) => {
        if (settings.default_from_date) setFromDate(settings.default_from_date);
        if (settings.default_to_date) setToDate(settings.default_to_date);
      })
      .catch(() => {
        // Best-effort only; fall back to hard-coded defaults on error.
      });
  }, []);

  const storedKeySet = useMemo(() => {
    const s = new Set<string>();
    for (const item of storedList) s.add(`${item.source}:${item.series_id}`);
    return s;
  }, [storedList]);

  const selectedStoredInfo = useMemo(() => {
    return (
      storedList.find((s) => s.source === source && s.series_id === seriesId) ??
      null
    );
  }, [storedList, source, seriesId]);

  const listItems = useMemo(() => {
    // Combine presets + stored series, so common items like GDP/CPI are always selectable.
    const seen = new Set<string>();
    const items: {
      source: EconomicSource;
      series_id: string;
      label: string;
      stored?: StoredEconomicSeriesInfo | null;
      isPreset: boolean;
    }[] = [];

    for (const src of Object.keys(PRESETS) as EconomicSource[]) {
      for (const p of PRESETS[src]) {
        const key = `${src}:${p.id}`;
        if (seen.has(key)) continue;
        seen.add(key);
        const stored = storedList.find((x) => x.source === src && x.series_id === p.id) ?? null;
        items.push({
          source: src,
          series_id: p.id,
          label: p.label,
          stored,
          isPreset: true,
        });
      }
    }

    for (const s of storedList) {
      const key = `${s.source}:${s.series_id}`;
      if (seen.has(key)) continue;
      seen.add(key);
      items.push({
        source: s.source,
        series_id: s.series_id,
        label: s.label ?? s.series_id,
        stored: s,
        isPreset: false,
      });
    }

    const q = listQuery.trim().toLowerCase();
    const filtered = q
      ? items.filter((it) => {
          const hay = `${it.source} ${it.series_id} ${it.label}`.toLowerCase();
          return hay.includes(q);
        })
      : items;

    // Prefer showing current source first, then presets, then stored-only.
    filtered.sort((a, b) => {
      const aSrc = a.source === source ? 0 : 1;
      const bSrc = b.source === source ? 0 : 1;
      if (aSrc !== bSrc) return aSrc - bSrc;
      const aPreset = a.isPreset ? 0 : 1;
      const bPreset = b.isPreset ? 0 : 1;
      if (aPreset !== bPreset) return aPreset - bPreset;
      return a.series_id.localeCompare(b.series_id);
    });

    return filtered;
  }, [storedList, listQuery, source]);

  const handleChangeSource = (value: EconomicSource) => {
    setSource(value);
    const presets = PRESETS[value];
    const nextId = presets?.length ? presets[0].id : "";
    if (nextId) {
      setSeriesId(nextId);
      setError(null);
      const hasStored = storedKeySet.has(`${value}:${nextId}`);
      if (hasStored) {
        void loadStored(value, nextId);
      } else {
        setPoints([]);
        setUseStored(false);
      }
    } else {
      setSeriesId("");
      setPoints([]);
      setUseStored(false);
      setError(null);
    }
  };

  const handleChangeSeriesId = (nextId: string) => {
    setSeriesId(nextId);
    setError(null);
    if (!nextId) {
      setPoints([]);
      setUseStored(false);
      return;
    }
    const hasStored = storedKeySet.has(`${source}:${nextId}`);
    if (hasStored) {
      void loadStored(source, nextId);
    } else {
      setPoints([]);
      setUseStored(false);
    }
  };

  const handleLoad = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setPoints([]);
    try {
      const res = await getEconomicSeries({
        source,
        series_id: seriesId,
        start_date: fromDate,
        end_date: toDate,
      });
      setPoints(res.points);
      setUseStored(false);
      void refreshStoredList();
      if (!res.points.length) {
        setError("No data returned for this series and date range.");
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleImportAllPresets = async () => {
    setImportAllRunning(true);
    setImportAllResult(null);
    setError(null);
    const targets: { source: EconomicSource; series_id: string }[] = [];
    for (const src of Object.keys(PRESETS) as EconomicSource[]) {
      for (const p of PRESETS[src]) targets.push({ source: src, series_id: p.id });
    }
    setImportAllProgress({ done: 0, total: targets.length });

    const results: { source: EconomicSource; series_id: string; ok: boolean; points?: number; error?: string }[] = [];
    for (let i = 0; i < targets.length; i++) {
      const t = targets[i]!;
      try {
        const res = await getEconomicSeries({
          source: t.source,
          series_id: t.series_id,
          start_date: fromDate,
          end_date: toDate,
        });
        results.push({ source: t.source, series_id: t.series_id, ok: true, points: res.points.length });
      } catch (e) {
        results.push({ source: t.source, series_id: t.series_id, ok: false, error: String((e as Error)?.message ?? e) });
      } finally {
        setImportAllProgress({ done: i + 1, total: targets.length });
      }
    }

    setImportAllResult(results);
    void refreshStoredList();
    setImportAllRunning(false);
  };

  const loadLive = async (src: EconomicSource, id: string) => {
    setLoading(true);
    setError(null);
    setPoints([]);
    try {
      const res = await getEconomicSeries({
        source: src,
        series_id: id,
        start_date: fromDate,
        end_date: toDate,
      });
      setPoints(res.points);
      setUseStored(false);
      void refreshStoredList();
      if (!res.points.length) setError("No data returned for this series and date range.");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const loadStored = async (src: EconomicSource, id: string) => {
    setLoading(true);
    setError(null);
    setPoints([]);
    try {
      const res = await getStoredEconomicSeries({
        source: src,
        series_id: id,
      });
      setPoints(res.points);
      setUseStored(true);
      void refreshStoredList();
      if (!res.points.length) setError("No stored data found in the database for this series.");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4 min-w-0">
      <div className="space-y-1.5">
        <h1 className="text-xl sm:text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
          Macro &amp; economic data
        </h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Pull GDP, inflation, labor, rates, FX, and volatility time-series directly into your trading dashboard.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="gray">GDP · inflation · jobs · rates · FX · volatility</Badge>
          <Badge tone="blue">{storedList.length} stored series</Badge>
        </div>
      </div>

      <Card className="bg-zinc-900/80 border-zinc-800">
          <CardBody className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-zinc-100">Load economic series</h2>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="secondary"
                disabled={loading || importAllRunning}
                onClick={handleImportAllPresets}
              >
                {importAllRunning
                  ? `Importing…${importAllProgress ? ` ${importAllProgress.done}/${importAllProgress.total}` : ""}`
                  : "Import all presets"}
              </Button>
            </div>
          </div>
          <form onSubmit={handleLoad} className="space-y-3">
            <div className="flex flex-wrap gap-3 items-end">
              <div className="w-52 min-w-[180px]">
                <SelectField
                  label="Source"
                  value={source}
                  onChange={(e) => handleChangeSource(e.target.value as EconomicSource)}
                >
                  <option value="fred">{SOURCE_LABELS.fred}</option>
                  <option value="bls">{SOURCE_LABELS.bls}</option>
                  <option value="bea">{SOURCE_LABELS.bea}</option>
                </SelectField>
              </div>
              <div className="w-52 min-w-[200px]">
                <SelectField
                  label="Preset"
                  value={
                    PRESETS[source].some((p) => p.id === seriesId) ? seriesId : "custom"
                  }
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val === "custom") return;
                    handleChangeSeriesId(val);
                  }}
                >
                  {PRESETS[source].map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                  <option value="custom">Custom…</option>
                </SelectField>
              </div>
              <div className="w-64 min-w-[220px]">
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-0.5">
                  Series ID / code
                </label>
                <input
                  type="text"
                  value={seriesId}
                  onChange={(e) => handleChangeSeriesId(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-100"
                  placeholder={
                    source === "fred"
                      ? "e.g. GDP (Real GDP), CPIAUCSL (CPI), UNRATE (Unemployment)"
                      : source === "bls"
                      ? "e.g. CUUR0000SA0 (CPI-U all items)"
                      : source === "bea"
                      ? "e.g. T10101 (GDP table)"
                      : "Series identifier"
                  }
                />
              </div>
              <div className="w-40">
                <DateField label="From" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
              </div>
              <div className="w-40">
                <DateField label="To" value={toDate} onChange={(e) => setToDate(e.target.value)} />
              </div>
              <div className="flex gap-2">
                <Button
                  type="submit"
                  disabled={loading}
                  className={
                    selectedStoredInfo
                      ? "bg-red-600 hover:bg-red-700 text-white"
                      : undefined
                  }
                >
                  {loading
                    ? "Loading…"
                    : selectedStoredInfo
                    ? "Overwrite (live)"
                    : "Load live"}
                </Button>
              </div>
            </div>
            {source === "bea" && (
              <p className="text-xs text-amber-400">
                BEA series are currently experimental: values load in the chart, but saving to the
                database may not always succeed.
              </p>
            )}
          </form>
          <div className="text-xs text-zinc-400">
            Stored for this indicator:{" "}
            {selectedStoredInfo?.last_date ? (
              <>
                <span className="font-mono">{selectedStoredInfo.last_date}</span>
                {" · "}
                {selectedStoredInfo.point_count} points
              </>
            ) : (
              "—"
            )}
          </div>
          {!useStored && points.length > 0 && (
            <p className="text-xs text-zinc-400">
              Live loads are automatically saved to the DB and will override stored values for the same series/date.
            </p>
          )}
          {error && (
            <p className="text-sm text-red-400">
              {error}
            </p>
          )}
          {importAllResult && (
            <div className="rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-300">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-medium text-zinc-200">
                  Import all presets finished
                </p>
                <p className="text-zinc-400">
                  {importAllResult.filter((r) => r.ok).length} ok · {importAllResult.filter((r) => !r.ok).length} failed
                </p>
              </div>
              <ul className="mt-2 space-y-1 max-h-40 overflow-auto pr-2">
                {importAllResult.map((r) => (
                  <li key={`${r.source}:${r.series_id}`} className="flex items-center justify-between gap-2">
                    <span className="font-mono text-zinc-300">
                      {r.source}:{r.series_id}
                    </span>
                    <span className={r.ok ? "text-emerald-300" : "text-red-300"}>
                      {r.ok ? `${r.points ?? 0} pts` : (r.error ?? "failed")}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          </CardBody>
      </Card>

      {points.length > 0 && (
        <Card className="bg-zinc-900/80 border-zinc-800 overflow-visible">
          <CardBody className="space-y-2 overflow-visible">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-semibold text-zinc-100">
                {SOURCE_LABELS[source]} –{" "}
                {
                  (
                    PRESETS[source].find((p) => p.id === seriesId) ??
                    { label: seriesId }
                  ).label
                }
              </h2>
              <Badge tone={useStored ? "blue" : "green"}>
                {useStored ? "Stored (DB)" : "Live"}
              </Badge>
            </div>
            <EconomicSeriesChart
              data={points}
              className="mt-1"
            />
          </CardBody>
        </Card>
      )}

      <Card className="bg-zinc-900/80 border-zinc-800">
        <CardBody className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-zinc-100">Macro indicators</h2>
          </div>
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1">
              Search (source / series / label)
            </label>
            <input
              value={listQuery}
              onChange={(e) => setListQuery(e.target.value)}
              placeholder="e.g. GDP (Real GDP), CPI (inflation), UNRATE (unemployment)…"
              className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600"
            />
          </div>
          {storedLoading ? (
            <p className="text-sm text-zinc-400">Loading…</p>
          ) : (
            <div className="space-y-2">
              <div className="rounded-lg border border-zinc-800">
                <ul className="divide-y divide-zinc-800">
                  {listItems.slice(0, 120).map((it) => {
                    const key = `${it.source}:${it.series_id}`;
                    const isSelected =
                      it.source === source && it.series_id === seriesId;
                    const isStored = storedKeySet.has(key);
                    const lastDate = it.stored?.last_date ?? null;
                    const lastValue = it.stored?.last_value ?? null;
                    return (
                      <li
                        key={key}
                        className={`px-3 py-2 text-sm hover:bg-zinc-900/50 ${
                          isSelected ? "bg-zinc-900/50" : ""
                        }`}
                        title={it.label}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="text-xs text-zinc-500 shrink-0 w-10">
                                {it.source.toUpperCase()}
                              </span>
                              <span className="font-mono text-zinc-100 truncate">
                                {it.series_id}
                              </span>
                              {it.isPreset && (
                                <Badge tone="gray" className="shrink-0">
                                  Preset
                                </Badge>
                              )}
                              {isStored && (
                                <Badge tone="blue" className="shrink-0">
                                  DB
                                </Badge>
                              )}
                            </div>
                            <div className="text-xs text-zinc-400 truncate mt-0.5">
                              {it.label}
                            </div>
                          </div>
                          <div className="flex flex-col items-end gap-1 shrink-0">
                            <div className="text-xs text-zinc-400">
                              {lastDate ?? "—"}
                              {it.stored ? ` · ${it.stored.point_count}` : ""}
                            </div>
                            <div className="flex gap-1">
                              <button
                                type="button"
                                className="rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs text-zinc-200 hover:bg-zinc-900"
                                disabled={loading}
                                onClick={() => {
                                  setSource(it.source);
                                  setSeriesId(it.series_id);
                                  loadLive(it.source, it.series_id);
                                }}
                              >
                                Live
                              </button>
                              <button
                                type="button"
                                className="rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs text-zinc-200 hover:bg-zinc-900 disabled:opacity-50 disabled:cursor-not-allowed"
                                disabled={loading || !isStored}
                                onClick={() => {
                                  setSource(it.source);
                                  setSeriesId(it.series_id);
                                  loadStored(it.source, it.series_id);
                                }}
                              >
                                Stored
                              </button>
                              <button
                                type="button"
                                className="rounded-md border border-red-800/60 bg-zinc-950 px-2 py-1 text-xs text-red-200 hover:bg-red-900/20 disabled:opacity-50 disabled:cursor-not-allowed"
                                disabled={loading || !isStored}
                                onClick={() => {
                                  setDeleteTarget({
                                    source: it.source,
                                    series_id: it.series_id,
                                  });
                                  setDeleteError(null);
                                  setDeleteDialogOpen(true);
                                }}
                              >
                                Delete
                              </button>
                            </div>
                            {lastValue != null && (
                              <div className="text-[11px] text-zinc-500 font-mono">
                                {Number(lastValue).toFixed(3)}
                              </div>
                            )}
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </div>
              {listItems.length > 120 && (
                <p className="text-xs text-zinc-500">
                  Showing first 120 matches.
                </p>
              )}
            </div>
          )}
        </CardBody>
      </Card>

      <ConfirmDialog
        open={deleteDialogOpen}
        onClose={() => {
          if (!deleting) {
            setDeleteDialogOpen(false);
            setDeleteError(null);
            setDeleteTarget(null);
          }
        }}
        title="Delete stored macro series?"
        message={
          deleteTarget
            ? `Delete all stored points for ${deleteTarget.source.toUpperCase()} · ${deleteTarget.series_id}? This cannot be undone.`
            : ""
        }
        confirmLabel="Delete"
        cancelLabel="Cancel"
        variant="danger"
        loading={deleting}
        error={deleteError}
        onConfirm={async () => {
          if (!deleteTarget) return;
          setDeleting(true);
          setDeleteError(null);
          try {
            await deleteStoredEconomicSeries(deleteTarget);
            if (
              source === deleteTarget.source &&
              seriesId === deleteTarget.series_id &&
              useStored
            ) {
              setPoints([]);
              setUseStored(false);
            }
            await refreshStoredList();
            setDeleteDialogOpen(false);
            setDeleteTarget(null);
          } catch (e) {
            setDeleteError(String((e as Error).message ?? e));
          } finally {
            setDeleting(false);
          }
        }}
      />

    </div>
  );
}

