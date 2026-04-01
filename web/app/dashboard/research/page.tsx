"use client";

import { useEffect, useState } from "react";
import {
  runForecast,
  listForecastRuns,
  evaluateStrategy,
  researchAnalyze,
  type ForecastResponse,
  type StrategyEvaluateResponse,
  type ResearchAnalyzeResponse,
} from "@/lib/researchApi";
import { calculatePositionSize, type PositionSizeResult } from "@/lib/riskApi";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DateField } from "@/components/ui/DateField";
import { SelectField } from "@/components/ui/SelectField";
import { PayoffDiagramChart } from "@/components/PayoffDiagramChart";
import { getSymbols } from "@/lib/api";
import { getUserSettings } from "@/lib/settingsApi";

const STRATEGY_TYPES = [
  { id: "straddle", label: "Straddle" },
  { id: "vertical_spread_call", label: "Bull call spread" },
  { id: "vertical_spread_put", label: "Bear put spread" },
  { id: "iron_condor", label: "Iron condor" },
  { id: "calendar_spread_call", label: "Calendar call" },
  { id: "calendar_spread_put", label: "Calendar put" },
];

const inputClass =
  "w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-emerald-500";
const labelClass = "block text-sm font-medium text-zinc-300 mb-1";

export default function ResearchPage() {
  const [symbols, setSymbols] = useState<string[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<string>("");
  const [fromDate, setFromDate] = useState("2024-01-01");
  const [toDate, setToDate] = useState("2024-06-30");
  const [model, setModel] = useState<"arima" | "gb">("arima");
  const [horizon, setHorizon] = useState(1);

  const [forecastLoading, setForecastLoading] = useState(false);
  const [forecastResult, setForecastResult] = useState<ForecastResponse | null>(null);

  const [strategyType, setStrategyType] = useState("straddle");
  const [forecastMean, setForecastMean] = useState("100");
  const [forecastStd, setForecastStd] = useState("5");
  const [strike, setStrike] = useState("100");
  const [longStrike, setLongStrike] = useState("98");
  const [shortStrike, setShortStrike] = useState("102");
  const [putLong, setPutLong] = useState("95");
  const [putShort, setPutShort] = useState("98");
  const [callShort, setCallShort] = useState("102");
  const [callLong, setCallLong] = useState("105");
  const [netDebit, setNetDebit] = useState("0");
  const [premiumPaid, setPremiumPaid] = useState("");
  const [includeBacktest, setIncludeBacktest] = useState(false);

  // Position sizing state
  const [psCapital, setPsCapital] = useState("10000");
  const [psWinRate, setPsWinRate] = useState("0.55");
  const [psAvgWin, setPsAvgWin] = useState("500");
  const [psAvgLoss, setPsAvgLoss] = useState("300");
  const [psMaxRisk, setPsMaxRisk] = useState("1");
  const [psMaxLoss, setPsMaxLoss] = useState("");
  const [psLoading, setPsLoading] = useState(false);
  const [psResult, setPsResult] = useState<PositionSizeResult | null>(null);

  const [strategyLoading, setStrategyLoading] = useState(false);
  const [strategyResult, setStrategyResult] = useState<StrategyEvaluateResponse | null>(null);

  const [analyzeLoading, setAnalyzeLoading] = useState(false);
  const [analyzeResult, setAnalyzeResult] = useState<ResearchAnalyzeResponse | null>(null);

  const [runs, setRuns] = useState<Array<{ model_id: string; symbol: string; from_date: string; to_date: string; horizon: number; model_type: string }>>([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getUserSettings(), getSymbols()])
      .then(([settings, syms]) => {
        if (settings.default_from_date) setFromDate(settings.default_from_date);
        if (settings.default_to_date) setToDate(settings.default_to_date);

        const list = syms ?? [];
        setSymbols(list);
        const preferred =
          (settings.default_symbol && list.includes(settings.default_symbol)
            ? settings.default_symbol
            : list[0]) ?? "";
        setSelectedSymbol(preferred);
      })
      .catch(() => {
        // Best-effort only; fall back to hard-coded defaults on error.
      });
  }, []);

  const loadSymbols = () => {
    getSymbols()
      .then((s) => {
        const list = s ?? [];
        setSymbols(list);
        if (!selectedSymbol && list.length) setSelectedSymbol(list[0]!);
      })
      .catch(() => {});
  };

  const handleRunForecast = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setForecastResult(null);
    setForecastLoading(true);
    try {
      const res = await runForecast({
        symbol: selectedSymbol,
        from_date: fromDate,
        to_date: toDate,
        horizon,
        model,
      });
      setForecastResult(res);
      setForecastMean(res.forecast?.length ? String(res.forecast[res.forecast.length - 1]?.value ?? 100) : "100");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setForecastLoading(false);
    }
  };

  const handleEvaluateStrategy = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setStrategyResult(null);
    setStrategyLoading(true);
    try {
      const body: Parameters<typeof evaluateStrategy>[0] = {
        strategy_type: strategyType,
        forecast_mean: parseFloat(forecastMean) || 100,
        forecast_std: forecastStd ? parseFloat(forecastStd) : undefined,
        premium_paid: premiumPaid ? parseFloat(premiumPaid) : undefined,
        include_backtest: includeBacktest && !!selectedSymbol,
        symbol: includeBacktest ? (selectedSymbol || undefined) : undefined,
        from_date: includeBacktest ? fromDate : undefined,
        to_date: includeBacktest ? toDate : undefined,
      };
      if (strategyType === "straddle" || strategyType.startsWith("calendar")) {
        body.strike = parseFloat(strike) || 100;
        if (strategyType.startsWith("calendar")) body.net_debit = parseFloat(netDebit) || 0;
      }
      if (strategyType.includes("vertical_spread")) {
        body.long_strike = parseFloat(longStrike) || 98;
        body.short_strike = parseFloat(shortStrike) || 102;
      }
      if (strategyType === "iron_condor") {
        body.put_long = parseFloat(putLong);
        body.put_short = parseFloat(putShort);
        body.call_short = parseFloat(callShort);
        body.call_long = parseFloat(callLong);
      }
      const res = await evaluateStrategy(body);
      setStrategyResult(res);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setStrategyLoading(false);
    }
  };

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setAnalyzeResult(null);
    setAnalyzeLoading(true);
    try {
      const res = await researchAnalyze({
        symbol: selectedSymbol,
        from_date: fromDate,
        to_date: toDate,
        horizon,
        strategy_types: [strategyType],
      });
      setAnalyzeResult(res);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setAnalyzeLoading(false);
    }
  };

  const loadRuns = () => {
    setRunsLoading(true);
    listForecastRuns({ limit: 20 })
      .then(setRuns)
      .catch(() => setRuns([]))
      .finally(() => setRunsLoading(false));
  };

  return (
    <div className="space-y-5 min-w-0">
      <div>
        <h1 className="text-xl sm:text-2xl font-semibold text-zinc-100">
          Research &amp; AI
        </h1>
        <p className="text-sm text-zinc-400 mt-0.5">
          Run forecasts, evaluate options strategies, and get AI explanations.
        </p>
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          <svg className="h-4 w-4 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
          </svg>
          {error}
        </div>
      )}

      <Card className="bg-zinc-900/80 border-zinc-800">
        <CardBody className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-zinc-100">Run forecast</h2>
            <Badge tone="gray">Same data as backtests</Badge>
          </div>
          <p className="text-sm text-zinc-400">
            Sync data first for your symbol/range. Returns direction (up/down/flat) and point forecast.
          </p>
          <form onSubmit={handleRunForecast} className="space-y-3">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-[1fr_1fr_1fr_auto_auto_auto]">
              <SelectField
                label="Symbol"
                value={selectedSymbol}
                onFocus={loadSymbols}
                onChange={(e) => setSelectedSymbol(e.target.value)}
              >
                {symbols.length ? symbols.map((s) => (
                  <option key={s} value={s}>{s}</option>
                )) : (
                  <option value="" disabled>No symbols in DB</option>
                )}
              </SelectField>
              <DateField label="From" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
              <DateField label="To" value={toDate} onChange={(e) => setToDate(e.target.value)} />
              <SelectField
                label="Model"
                value={model}
                onChange={(e) => setModel(e.target.value as "arima" | "gb")}
              >
                <option value="arima">ARIMA</option>
                <option value="gb">Gradient Boost</option>
              </SelectField>
              <div>
                <label className={labelClass}>Horizon</label>
                <input type="number" min={1} max={30} value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} className={inputClass} />
              </div>
              <div className="flex items-end">
                <Button type="submit" disabled={forecastLoading || !selectedSymbol} className="w-full">
                  {forecastLoading ? "Running…" : "Run"}
                </Button>
              </div>
            </div>
          </form>
          {forecastResult && (
            <div className="rounded-lg border border-zinc-700 bg-zinc-800/60 px-4 py-3 space-y-1 text-sm">
              <div className="flex flex-wrap gap-4 items-center">
                <span className="text-zinc-400">
                  Direction:{" "}
                  <Badge tone={forecastResult.direction === "up" ? "green" : forecastResult.direction === "down" ? "red" : "gray"}>
                    {forecastResult.direction}
                  </Badge>
                </span>
                {forecastResult.forecast?.length ? (
                  <span className="text-zinc-400">
                    Forecast value:{" "}
                    <strong className="text-zinc-100">
                      {forecastResult.forecast[forecastResult.forecast.length - 1]?.value.toFixed(2)}
                    </strong>
                  </span>
                ) : null}
              </div>
              {forecastResult.error && <p className="text-red-400">{forecastResult.error}</p>}
            </div>
          )}
        </CardBody>
      </Card>

      <Card className="bg-zinc-900/80 border-zinc-800">
        <CardBody className="space-y-3">
          <h2 className="text-base font-semibold text-zinc-100">Evaluate strategy</h2>
          <p className="text-sm text-zinc-400">
            Use a forecast mean (and optional std) to compute expected payoff, probability of profit, and payoff diagram.
          </p>
          <form onSubmit={handleEvaluateStrategy} className="space-y-4">
            {/* Row 1: strategy + forecast params */}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <SelectField label="Strategy" value={strategyType} onChange={(e) => setStrategyType(e.target.value)}>
                {STRATEGY_TYPES.map((s) => (
                  <option key={s.id} value={s.id}>{s.label}</option>
                ))}
              </SelectField>
              <div>
                <label className={labelClass}>Forecast mean</label>
                <input type="number" step="any" value={forecastMean} onChange={(e) => setForecastMean(e.target.value)} className={inputClass} />
              </div>
              <div>
                <label className={labelClass}>Forecast std <span className="text-zinc-500 font-normal">(optional)</span></label>
                <input type="number" step="any" value={forecastStd} onChange={(e) => setForecastStd(e.target.value)} className={inputClass} placeholder="e.g. 5" />
              </div>
              <div>
                <label className={labelClass}>Premium paid ($) <span className="text-zinc-500 font-normal">(optional)</span></label>
                <input
                  type="number"
                  step="any"
                  value={premiumPaid}
                  onChange={(e) => setPremiumPaid(e.target.value)}
                  className={inputClass}
                  placeholder="for break-even calc"
                />
              </div>
            </div>

            {/* Row 2: strategy-specific strike fields */}
            {(strategyType === "straddle" || strategyType.startsWith("calendar")) && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div>
                  <label className={labelClass}>Strike</label>
                  <input type="number" step="any" value={strike} onChange={(e) => setStrike(e.target.value)} className={inputClass} />
                </div>
                {strategyType.startsWith("calendar") && (
                  <div>
                    <label className={labelClass}>Net debit</label>
                    <input type="number" step="any" value={netDebit} onChange={(e) => setNetDebit(e.target.value)} className={inputClass} />
                  </div>
                )}
              </div>
            )}
            {strategyType.includes("vertical_spread") && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div>
                  <label className={labelClass}>Long strike</label>
                  <input type="number" step="any" value={longStrike} onChange={(e) => setLongStrike(e.target.value)} className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>Short strike</label>
                  <input type="number" step="any" value={shortStrike} onChange={(e) => setShortStrike(e.target.value)} className={inputClass} />
                </div>
              </div>
            )}
            {strategyType === "iron_condor" && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div>
                  <label className={labelClass}>Put long</label>
                  <input type="number" step="any" value={putLong} onChange={(e) => setPutLong(e.target.value)} className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>Put short</label>
                  <input type="number" step="any" value={putShort} onChange={(e) => setPutShort(e.target.value)} className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>Call short</label>
                  <input type="number" step="any" value={callShort} onChange={(e) => setCallShort(e.target.value)} className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>Call long</label>
                  <input type="number" step="any" value={callLong} onChange={(e) => setCallLong(e.target.value)} className={inputClass} />
                </div>
              </div>
            )}

            {/* Row 3: options + submit */}
            <div className="flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-2 text-sm text-zinc-400 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={includeBacktest}
                  onChange={(e) => setIncludeBacktest(e.target.checked)}
                  className="rounded border-zinc-600 bg-zinc-800 text-emerald-500 focus:ring-emerald-500"
                />
                Include historical backtest comparison
              </label>
              <Button type="submit" disabled={strategyLoading}>
                {strategyLoading ? "Evaluating…" : "Evaluate strategy"}
              </Button>
            </div>
          </form>
          {strategyResult && (
            <div className="space-y-4 rounded-lg border border-zinc-700 bg-zinc-800/60 p-4">
              <div className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">Results</div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {[
                  { label: "Expected value", value: `$${strategyResult.expected_value.toFixed(2)}`, color: "text-zinc-100" },
                  { label: "P(profit)", value: `${(strategyResult.probability_of_profit * 100).toFixed(1)}%`, color: "text-zinc-100" },
                  { label: "Max loss", value: `$${strategyResult.max_loss.toFixed(2)}`, color: "text-red-400" },
                  { label: "Max gain", value: `$${strategyResult.max_gain.toFixed(2)}`, color: "text-emerald-400" },
                ].map(({ label, value, color }) => (
                  <div key={label} className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2">
                    <div className="text-xs text-zinc-500 mb-0.5">{label}</div>
                    <div className={`text-sm font-semibold ${color}`}>{value}</div>
                  </div>
                ))}
              </div>
              {strategyResult.historical_backtest_return != null && (
                <p className="text-sm text-zinc-400">
                  Historical backtest return:{" "}
                  <strong className="text-zinc-100">
                    {(strategyResult.historical_backtest_return * 100).toFixed(2)}%
                  </strong>
                </p>
              )}
              {strategyResult.breakeven_prices?.length > 0 && (
                <div className="flex flex-wrap gap-2 items-center text-sm">
                  <span className="text-zinc-500 text-xs">Break-even at expiry:</span>
                  {strategyResult.breakeven_prices.map((p) => (
                    <span
                      key={p}
                      className="inline-flex items-center px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-300 font-mono text-xs"
                    >
                      ${p.toFixed(2)}
                    </span>
                  ))}
                </div>
              )}
              {strategyResult.payoff_diagram?.length > 0 && (
                <PayoffDiagramChart data={strategyResult.payoff_diagram} />
              )}
              {strategyResult.error && <p className="text-red-400 text-sm">{strategyResult.error}</p>}
            </div>
          )}
        </CardBody>
      </Card>

      <Card className="bg-zinc-900/80 border-zinc-800">
        <CardBody className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-zinc-100">Full analysis</h2>
            <Badge tone="green">Forecast → Strategies → Explanation</Badge>
          </div>
          <p className="text-sm text-zinc-400">
            Run the full pipeline: load data, forecast, evaluate strategies, and generate an AI explanation (placeholder if no OPENAI_API_KEY).
          </p>
          <form onSubmit={handleAnalyze} className="grid grid-cols-2 gap-3 sm:grid-cols-[1fr_1fr_1fr_auto_auto]">
            <SelectField label="Symbol" value={selectedSymbol} onFocus={loadSymbols} onChange={(e) => setSelectedSymbol(e.target.value)}>
              {symbols.length ? symbols.map((s) => <option key={s} value={s}>{s}</option>) : <option value="" disabled>No symbols in DB</option>}
            </SelectField>
            <DateField label="From" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
            <DateField label="To" value={toDate} onChange={(e) => setToDate(e.target.value)} />
            <div>
              <label className={labelClass}>Horizon</label>
              <input type="number" min={1} max={30} value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} className={inputClass} />
            </div>
            <div className="flex items-end">
              <Button type="submit" disabled={analyzeLoading || !selectedSymbol} className="w-full">
                {analyzeLoading ? "Running…" : "Analyze"}
              </Button>
            </div>
          </form>
          {analyzeResult && (
            <div className="rounded-lg border border-zinc-700 bg-zinc-800/60 p-4 space-y-2 text-sm">
              {analyzeResult.forecast_direction != null && (
                <p className="text-zinc-300">Forecast direction: <Badge tone="gray">{analyzeResult.forecast_direction}</Badge></p>
              )}
              {analyzeResult.forecast_mean != null && (
                <p className="text-zinc-300">Forecast mean: <strong>{analyzeResult.forecast_mean.toFixed(2)}</strong></p>
              )}
              {analyzeResult.strategy_results?.length ? (
                <p className="text-zinc-400">Strategies evaluated: {analyzeResult.strategy_results.length}</p>
              ) : null}
              {analyzeResult.explanation && (
                <div className="pt-2 border-t border-zinc-700">
                  <p className="text-zinc-500 text-xs font-medium uppercase tracking-wide mb-1">Explanation</p>
                  <p className="text-zinc-300 whitespace-pre-wrap">{analyzeResult.explanation}</p>
                </div>
              )}
            </div>
          )}
        </CardBody>
      </Card>

      <Card className="bg-zinc-900/80 border-zinc-800">
        <CardBody className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-zinc-100">Recent forecast runs</h2>
            <Button variant="secondary" size="sm" onClick={loadRuns} disabled={runsLoading}>
              {runsLoading ? "Loading…" : "Refresh"}
            </Button>
          </div>
          {runs.length === 0 && !runsLoading && (
            <p className="text-sm text-zinc-500">No runs yet. Run a forecast above to register.</p>
          )}
          {runs.length > 0 && (
            <ul className="text-sm text-zinc-400 space-y-1 max-h-40 overflow-y-auto">
              {runs.slice(0, 15).map((r) => (
                <li key={r.model_id} className="flex flex-wrap gap-2">
                  <span className="text-zinc-300">{r.symbol}</span>
                  <span>{r.from_date} → {r.to_date}</span>
                  <span>· {r.model_type}</span>
                  <span>· h={r.horizon}</span>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      {/* ── Position Sizing Calculator ──────────────────────────────── */}
      <Card className="bg-zinc-900/80 border-zinc-800">
        <CardBody className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-zinc-100">Position Sizing</h2>
            <Badge tone="gray">Kelly Criterion</Badge>
          </div>
          <p className="text-sm text-zinc-400">
            Enter your historical win rate and average win/loss to compute the Kelly-optimal position size.
            Half-Kelly (recommended) cuts variance significantly while preserving most long-run edge.
          </p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div>
              <label className={labelClass}>Capital ($)</label>
              <input type="number" step="any" value={psCapital} onChange={(e) => setPsCapital(e.target.value)} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Win rate</label>
              <input type="number" step="0.01" min="0.01" max="0.99" value={psWinRate} onChange={(e) => setPsWinRate(e.target.value)} className={inputClass} placeholder="0.55" />
            </div>
            <div>
              <label className={labelClass}>Avg win ($)</label>
              <input type="number" step="any" value={psAvgWin} onChange={(e) => setPsAvgWin(e.target.value)} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Avg loss ($)</label>
              <input type="number" step="any" value={psAvgLoss} onChange={(e) => setPsAvgLoss(e.target.value)} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Max risk %</label>
              <input type="number" step="0.1" min="0.1" max="20" value={psMaxRisk} onChange={(e) => setPsMaxRisk(e.target.value)} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Max loss/contract ($)</label>
              <input type="number" step="any" value={psMaxLoss} onChange={(e) => setPsMaxLoss(e.target.value)} className={inputClass} placeholder="optional" />
            </div>
          </div>
          <Button
            disabled={psLoading}
            onClick={async () => {
              setPsLoading(true);
              setPsResult(null);
              try {
                const res = await calculatePositionSize({
                  capital: parseFloat(psCapital) || 10000,
                  win_rate: parseFloat(psWinRate) || 0.55,
                  avg_win: parseFloat(psAvgWin) || 500,
                  avg_loss: parseFloat(psAvgLoss) || 300,
                  max_risk_pct: parseFloat(psMaxRisk) || 1,
                  max_loss_per_contract: psMaxLoss ? parseFloat(psMaxLoss) : null,
                });
                setPsResult(res);
              } catch (e: unknown) {
                setPsResult({ success: false, error: e instanceof Error ? e.message : String(e), kelly_fraction: null, half_kelly_fraction: null, kelly_dollar_risk: null, half_kelly_dollar_risk: null, fixed_risk_dollar: null, fixed_risk_units: null, max_contracts: null });
              } finally {
                setPsLoading(false);
              }
            }}
          >
            {psLoading ? "Calculating…" : "Calculate"}
          </Button>
          {psResult && psResult.success && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-1">
              {[
                { label: "Full Kelly %", value: psResult.kelly_fraction !== null ? `${(psResult.kelly_fraction * 100).toFixed(1)}%` : "—", sub: psResult.kelly_dollar_risk !== null ? `$${psResult.kelly_dollar_risk.toFixed(0)} at risk` : undefined, color: "text-yellow-400" },
                { label: "Half Kelly % ✓", value: psResult.half_kelly_fraction !== null ? `${(psResult.half_kelly_fraction * 100).toFixed(1)}%` : "—", sub: psResult.half_kelly_dollar_risk !== null ? `$${psResult.half_kelly_dollar_risk.toFixed(0)} at risk` : undefined, color: "text-emerald-400" },
                { label: `Fixed Risk (${psMaxRisk}%)`, value: psResult.fixed_risk_dollar !== null ? `$${psResult.fixed_risk_dollar.toFixed(0)}` : "—", sub: psResult.fixed_risk_units !== null ? `${psResult.fixed_risk_units.toFixed(1)} units` : undefined, color: "text-zinc-200" },
                { label: "Max contracts", value: psResult.max_contracts !== null ? `${psResult.max_contracts}` : "—", sub: "per fixed risk budget", color: "text-zinc-200" },
              ].map(({ label, value, sub, color }) => (
                <div key={label} className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2">
                  <div className="text-xs text-zinc-500 mb-0.5">{label}</div>
                  <div className={`text-base font-semibold ${color}`}>{value}</div>
                  {sub && <div className="text-xs text-zinc-500 mt-0.5">{sub}</div>}
                </div>
              ))}
            </div>
          )}
          {psResult && !psResult.success && (
            <p className="text-sm text-red-400">{psResult.error}</p>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
