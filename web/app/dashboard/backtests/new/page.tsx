"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getStrategies,
  getSymbols,
  getContracts,
  type StrategyInfo,
  type ContractInfo,
} from "@/lib/api";
import { getUserSettings } from "@/lib/settingsApi";
import { createBacktest } from "@/lib/labApi";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { DateField } from "@/components/ui/DateField";
import { SelectField } from "@/components/ui/SelectField";

export default function NewBacktestPage() {
  const router = useRouter();
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [symbols, setSymbols] = useState<string[]>([]);
  const [contracts, setContracts] = useState<ContractInfo[]>([]);
  const [loadingMeta, setLoadingMeta] = useState(true);
  const [loadingContracts, setLoadingContracts] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [strategy, setStrategy] = useState("single_leg");
  const [underlying, setUnderlying] = useState("AAPL");
  const [fromDate, setFromDate] = useState("2024-01-01");
  const [toDate, setToDate] = useState("2024-12-31");
  const [cash, setCash] = useState(100_000);
  const [contractChoice, setContractChoice] = useState<"first" | "id">("first");
  const [contractId, setContractId] = useState<number | "">("");
  const [needContracts, setNeedContracts] = useState(false);

  useEffect(() => {
    Promise.all([getStrategies(), getSymbols(), getUserSettings()])
      .then(([s, sym, settings]) => {
        setStrategies(s);
        const symbolList = sym.length ? sym : ["AAPL"];
        setSymbols(symbolList);
        const defaultStrategy =
          settings.default_strategy &&
          s.some((x) => x.id === settings.default_strategy)
            ? settings.default_strategy
            : "single_leg";
        setStrategy(defaultStrategy);
        const defaultSymbol =
          settings.default_symbol && symbolList.includes(settings.default_symbol)
            ? settings.default_symbol
            : symbolList[0];
        setUnderlying(defaultSymbol);
        if (settings.default_from_date) setFromDate(settings.default_from_date);
        if (settings.default_to_date) setToDate(settings.default_to_date);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoadingMeta(false));
  }, []);

  useEffect(() => {
    if (!needContracts || !underlying) return;
    setLoadingContracts(true);
    getContracts(underlying, 1, 500)
      .then((res) => setContracts(res.items))
      .catch((e) => setError(String(e)))
      .finally(() => setLoadingContracts(false));
  }, [needContracts, underlying]);

  const selectedStrategy = strategies.find((s) => s.id === strategy);
  const isEquityOnly = selectedStrategy?.equity_only ?? false;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    setRunning(true);
    try {
      const res = await createBacktest({
        name,
        strategy,
        underlying,
        from_date: isEquityOnly || fromDate ? fromDate : null,
        to_date: isEquityOnly || toDate ? toDate : null,
        cash,
        first_contract: !isEquityOnly && contractChoice === "first",
        contract_id:
          !isEquityOnly && contractChoice === "id" && contractId !== ""
            ? Number(contractId)
            : null,
      });
      router.push(`/dashboard/backtests/${res.id}`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="max-w-xl space-y-4 min-w-0">
      <PageHeader
        title="Create backtest"
        subtitle="Configure and run. Results are saved to history."
      />

      {error && (
        <div className="rounded-lg bg-red-50 dark:bg-red-900/20 px-3 py-2 text-sm text-red-800 dark:text-red-200">
          {error}
        </div>
      )}

      {loadingMeta ? (
        <p className="text-sm text-zinc-600 dark:text-zinc-400">Loading…</p>
      ) : (
        <Card>
          <CardBody>
            <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-0.5">
              Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 pl-3 pr-8 py-2 text-sm text-zinc-900 dark:text-zinc-100"
              placeholder="e.g. AAPL SMA crossover 2024"
            />
          </div>

          <SelectField
            label="Strategy"
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
          >
            {strategies.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </SelectField>

          <SelectField
            label="Underlying symbol"
            value={underlying}
            onChange={(e) => {
              setUnderlying(e.target.value);
              setContracts([]);
            }}
          >
            {symbols.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </SelectField>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <DateField
              label="From date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
            />
            <DateField
              label="To date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-0.5">
              Starting cash
            </label>
            <input
              type="number"
              min={0}
              step={1000}
              value={cash}
              onChange={(e) => setCash(Number(e.target.value))}
              className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 pl-3 pr-8 py-2 text-sm text-zinc-900 dark:text-zinc-100"
            />
          </div>

          {!isEquityOnly && (
            <div className="space-y-2">
              <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Contract selection
              </p>
              <div className="flex gap-4 text-sm">
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="contractChoice"
                    checked={contractChoice === "first"}
                    onChange={() => {
                      setContractChoice("first");
                      setNeedContracts(false);
                    }}
                  />
                  <span>First contract</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="contractChoice"
                    checked={contractChoice === "id"}
                    onChange={() => {
                      setContractChoice("id");
                      setNeedContracts(true);
                      setContractId("");
                    }}
                  />
                  <span>Choose by ID</span>
                </label>
              </div>

              {contractChoice === "id" && (
                <div>
                  {loadingContracts ? (
                    <p className="text-xs text-zinc-500">Loading contracts…</p>
                  ) : contracts.length === 0 ? (
                    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-3 text-xs text-zinc-600 dark:text-zinc-400">
                      No contracts for {underlying}. Sync options or use First contract.
                    </div>
                  ) : (
                    <SelectField
                      label="Contract ID"
                      value={contractId === "" ? "" : String(contractId)}
                      onChange={(e) =>
                        setContractId(e.target.value ? Number(e.target.value) : "")
                      }
                    >
                      <option value="">Select…</option>
                      {contracts.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.id} • {c.option_type} {c.strike} • {c.expiration}
                        </option>
                      ))}
                    </SelectField>
                  )}
                </div>
              )}
            </div>
          )}

              <Button type="submit" disabled={running} className="w-full py-2">
                {running ? "Running…" : "Run backtest"}
              </Button>
            </form>
          </CardBody>
        </Card>
      )}
    </div>
  );
}

