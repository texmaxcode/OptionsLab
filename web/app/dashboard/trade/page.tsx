"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  getTradingAccounts,
  getTradingAccountBalance,
  getTradingOrders,
  cancelTradingOrder,
  placeTradingEquityOrder,
  placeTradingOptionOrder,
  type TradingMode,
  type PlaceEquityOrderParams,
  type PlaceOptionOrderParams,
} from "@/lib/tradingApi";
import { getSymbols } from "@/lib/api";
import { getUserSettings } from "@/lib/settingsApi";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { SelectField } from "@/components/ui/SelectField";

type TradingAccountSummary = {
  id: string;
  label: string;
  accountId?: string;
  accountDesc?: string;
  accountMode?: string;
  accountType?: string;
  institutionType?: string;
};

/** Extract account list from the active broker response. */
function parseAccounts(
  response: Record<string, unknown>,
  mode: TradingMode
): TradingAccountSummary[] {
  if (mode === "paper") {
    const id = String(response.id ?? response.account_number ?? "alpaca-paper");
    const status = response.status != null ? String(response.status) : undefined;
    const currency = response.currency != null ? String(response.currency) : undefined;
    return [
      {
        id,
        label: [response.account_number, status, id].filter(Boolean).join(" · "),
        accountId:
          response.account_number != null
            ? String(response.account_number)
            : undefined,
        accountDesc:
          response.account_number != null
            ? `Alpaca paper account ${String(response.account_number)}`
            : "Alpaca paper account",
        accountMode: "Paper",
        accountType: response.account_type != null ? String(response.account_type) : undefined,
        institutionType: currency ? `Alpaca · ${currency}` : "Alpaca",
      },
    ];
  }
  const arr = response?.AccountListResponse as Record<string, unknown> | undefined;
  const accounts = arr?.Accounts as Record<string, unknown> | undefined;
  const list = accounts?.Account;
  if (!Array.isArray(list)) return [];
  return list.map((acc: Record<string, unknown>) => {
    const key = String(acc.accountIdKey ?? acc.accountId ?? "");
    const desc = [acc.accountDesc, acc.accountMode, key].filter(Boolean).join(" · ");
    return {
      id: key,
      label: desc || key,
      accountId: acc.accountId != null ? String(acc.accountId) : undefined,
      accountDesc: acc.accountDesc != null ? String(acc.accountDesc) : undefined,
      accountMode: acc.accountMode != null ? String(acc.accountMode) : undefined,
      accountType: acc.accountType != null ? String(acc.accountType) : undefined,
      institutionType: acc.institutionType != null ? String(acc.institutionType) : undefined,
    };
  });
}

/** Extract order list from the active broker response. */
function parseOrders(
  response: Record<string, unknown>[] | Record<string, unknown>,
  mode: TradingMode
): Record<string, unknown>[] {
  if (mode === "paper") {
    return Array.isArray(response) ? response : [];
  }
  const orderList =
    ((response as Record<string, unknown>)?.OrdersResponse as
      | Record<string, unknown>
      | undefined) ??
    ((response as Record<string, unknown>)?.OrderListResponse as
      | Record<string, unknown>
      | undefined);
  const list = orderList?.Order;
  if (Array.isArray(list)) return list as Record<string, unknown>[];
  if (list && typeof list === "object") return [list as Record<string, unknown>];
  return [];
}

function getOrderStatus(order: Record<string, unknown>, mode: TradingMode): string {
  if (mode === "paper") {
    const value = String(order.status ?? "UNKNOWN").toLowerCase();
    if (
      ["new", "accepted", "pending_new", "accepted_for_bidding", "partially_filled", "held", "pending_cancel", "pending_replace"].includes(value)
    ) {
      return "OPEN";
    }
    if (value === "filled") return "EXECUTED";
    if (["canceled", "cancelled", "expired"].includes(value)) return "CANCELLED";
    return value.toUpperCase();
  }
  const maybeStatus =
    order.status ??
    order.orderStatus ??
    (order.OrderDetail as Record<string, unknown>[] | undefined)?.[0]?.status;
  return String(maybeStatus ?? "UNKNOWN");
}

function getOrderDescription(
  order: Record<string, unknown>,
  mode: TradingMode
): string {
  if (mode === "paper") {
    const symbol = order.symbol;
    const side = order.side != null ? String(order.side).toUpperCase() : undefined;
    const qty = order.qty ?? order.filled_qty;
    const type = order.type != null ? String(order.type).toUpperCase() : undefined;
    return [symbol, qty ? `${String(qty)}x` : undefined, side, type]
      .filter(Boolean)
      .join(" · ");
  }
  const details = Array.isArray(order.OrderDetail)
    ? (order.OrderDetail as Record<string, unknown>[])
    : [];
  const instruments =
    details.length > 0 && Array.isArray(details[0]?.Instrument)
      ? (details[0].Instrument as Record<string, unknown>[])
      : [];
  const product =
    instruments.length > 0 && instruments[0]?.Product && typeof instruments[0].Product === "object"
      ? (instruments[0].Product as Record<string, unknown>)
      : undefined;
  const symbol =
    order.symbolDescription ??
    product?.symbol ??
    (product?.productId && typeof product.productId === "object"
      ? (product.productId as Record<string, unknown>).symbol
      : undefined);
  const priceType = order.priceType ?? details[0]?.priceType;
  const orderTerm = order.orderTerm ?? details[0]?.orderTerm;
  return [symbol, orderTerm, priceType].filter(Boolean).join(" · ");
}

function dedupeOrders(items: Record<string, unknown>[]): Record<string, unknown>[] {
  const seen = new Set<string>();
  const out: Record<string, unknown>[] = [];
  for (const item of items) {
    const id = getOrderId(item);
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push(item);
  }
  return out;
}

function getOrderId(order: Record<string, unknown>): string {
  return String(order.orderId ?? order.orderNum ?? order.id ?? "");
}

function pickNestedValue(source: unknown, paths: string[][]): unknown {
  for (const path of paths) {
    let cur: unknown = source;
    let ok = true;
    for (const key of path) {
      if (cur && typeof cur === "object" && key in (cur as Record<string, unknown>)) {
        cur = (cur as Record<string, unknown>)[key];
      } else {
        ok = false;
        break;
      }
    }
    if (ok && cur != null && cur !== "") return cur;
  }
  return undefined;
}

function parseBalanceItems(
  response: Record<string, unknown>,
  mode: TradingMode
): { label: string; value: string }[] {
  if (mode === "paper") {
    const fields = [
      ["Equity", response.equity],
      ["Last equity", response.last_equity],
      ["Cash", response.cash],
      ["Buying power", response.buying_power],
      ["Portfolio value", response.portfolio_value],
      ["Multiplier", response.multiplier],
      ["Daytrade count", response.daytrade_count],
    ] as const;
    return fields
      .filter(([, value]) => value != null && value !== "")
      .map(([label, value]) => ({ label, value: String(value) }));
  }
  const balanceRoot =
    (response.BalanceResponse as Record<string, unknown> | undefined) ?? response;

  const fields: { label: string; paths: string[][] }[] = [
    {
      label: "Net account value",
      paths: [
        ["Computed", "netAccountValue"],
        ["Computed", "NetAccountValue"],
        ["Balance", "netAccountValue"],
        ["Balance", "NetAccountValue"],
      ],
    },
    {
      label: "Cash available",
      paths: [
        ["Computed", "cashAvailableForInvestment"],
        ["Computed", "CashAvailableForInvestment"],
        ["Balance", "cashAvailableForInvestment"],
        ["Balance", "CashAvailableForInvestment"],
      ],
    },
    {
      label: "Cash buying power",
      paths: [
        ["Computed", "cashBuyingPower"],
        ["Computed", "CashBuyingPower"],
        ["Balance", "cashBuyingPower"],
        ["Balance", "CashBuyingPower"],
      ],
    },
    {
      label: "Margin buying power",
      paths: [
        ["Computed", "marginBuyingPower"],
        ["Computed", "MarginBuyingPower"],
        ["Balance", "marginBuyingPower"],
        ["Balance", "MarginBuyingPower"],
      ],
    },
    {
      label: "Settled cash",
      paths: [
        ["Computed", "settledCashForInvestment"],
        ["Computed", "SettledCashForInvestment"],
        ["Balance", "settledCashForInvestment"],
        ["Balance", "SettledCashForInvestment"],
      ],
    },
    {
      label: "Day-trade buying power",
      paths: [
        ["Computed", "dtBuyingPower"],
        ["Computed", "DtBuyingPower"],
        ["Balance", "dtBuyingPower"],
        ["Balance", "DtBuyingPower"],
      ],
    },
  ];

  return fields
    .map((field) => {
      const value = pickNestedValue(balanceRoot, field.paths);
      return value != null ? { label: field.label, value: String(value) } : null;
    })
    .filter((item): item is { label: string; value: string } => item != null);
}

function getPlacedOrderMessage(
  response: Record<string, unknown>,
  mode: TradingMode
): string {
  if (mode === "paper") {
    const orderId = response.id ?? response.client_order_id;
    return orderId != null
      ? `Order submitted. Alpaca paper returned order ${String(orderId)}.`
      : "Order submitted to Alpaca paper trading.";
  }
  const placeResponse =
    (response.PlaceOrderResponse as Record<string, unknown> | undefined) ?? response;
  const orderIds =
    placeResponse.OrderIds as Record<string, unknown> | undefined;
  const orderId = orderIds?.orderId ?? orderIds?.orderNum;
  const base = orderId != null
    ? `Order submitted. E*TRADE returned order #${String(orderId)}.`
    : "Order submitted to E*TRADE.";
  return base;
}

export default function TradePage() {
  const [mode, setMode] = useState<TradingMode>("paper");
  const [modeReady, setModeReady] = useState(false);
  const [symbols, setSymbols] = useState<string[]>([]);
  const [accounts, setAccounts] = useState<TradingAccountSummary[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<string>("");
  const [accountBalance, setAccountBalance] = useState<Record<string, unknown> | null>(null);
  const [loadingBalance, setLoadingBalance] = useState(false);
  const [orders, setOrders] = useState<Record<string, unknown>[]>([]);
  const [loadingAccounts, setLoadingAccounts] = useState(false);
  const [loadingOrders, setLoadingOrders] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [orderStatusFilter, setOrderStatusFilter] = useState<"ALL" | "OPEN" | "EXECUTED" | "CANCELLED">("OPEN");
  const [orderTab, setOrderTab] = useState<"equity" | "option">("equity");
  const [placing, setPlacing] = useState(false);
  const [cancelOrderId, setCancelOrderId] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [pendingCancelOrderId, setPendingCancelOrderId] = useState<string | null>(null);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const hasSymbols = symbols.length > 0;

  const loadAccounts = useCallback(async () => {
    if (!modeReady) return;
    setLoadingAccounts(true);
    setError(null);
    try {
      const res = await getTradingAccounts(mode);
      const parsed = parseAccounts(res, mode);
      setAccounts(parsed);
      if (selectedAccountId && !parsed.some((a) => a.id === selectedAccountId)) {
        setSelectedAccountId("");
      }
    } catch (e) {
      setError(String(e));
      setAccounts([]);
    } finally {
      setLoadingAccounts(false);
    }
  }, [mode, modeReady, selectedAccountId]);

  useEffect(() => {
    if (!modeReady) return;
    void loadAccounts();
  }, [loadAccounts, modeReady]);

  useEffect(() => {
    getUserSettings()
      .then((settings) => {
        setMode(settings.etrade_sandbox === false ? "live" : "paper");
      })
      .catch(() => {})
      .finally(() => {
        setModeReady(true);
      });
  }, []);

  useEffect(() => {
    getSymbols()
      .then((sym) => {
        setSymbols(sym.length ? sym : ["AAPL"]);
      })
      .catch(() => {});
  }, []);

  const loadOrders = useCallback(async () => {
    if (!modeReady) return;
    if (!selectedAccountId) {
      setOrders([]);
      return;
    }
    setLoadingOrders(true);
    try {
      if (orderStatusFilter === "ALL") {
        const statuses = [
          "OPEN",
          "EXECUTED",
          "CANCELLED",
          "CANCEL_REQUESTED",
          "REJECTED",
          "EXPIRED",
          "INDIVIDUAL_FILLS",
        ] as const;
        const results = await Promise.all(
          statuses.map((status) =>
            getTradingOrders(selectedAccountId, { status, mode })
              .then((res) => parseOrders(res, mode))
              .catch(() => [])
          )
        );
        setOrders(dedupeOrders(results.flat()));
      } else {
        const res = await getTradingOrders(selectedAccountId, {
          status: orderStatusFilter,
          mode,
        });
        setOrders(parseOrders(res, mode));
      }
    } catch {
      setOrders([]);
    } finally {
      setLoadingOrders(false);
    }
  }, [selectedAccountId, orderStatusFilter, mode, modeReady]);

  useEffect(() => {
    if (!modeReady) return;
    void loadOrders();
  }, [loadOrders, modeReady]);

  useEffect(() => {
    if (!modeReady) return;
    if (!selectedAccountId) {
      setAccountBalance(null);
      return;
    }
    setLoadingBalance(true);
    getTradingAccountBalance(selectedAccountId, mode)
      .then((res) => setAccountBalance(res))
      .catch(() => setAccountBalance(null))
      .finally(() => setLoadingBalance(false));
  }, [selectedAccountId, mode, modeReady]);

  const handleCancelOrder = async () => {
    if (!selectedAccountId || pendingCancelOrderId == null || cancelOrderId != null) return;
    const targetOrderId = pendingCancelOrderId;
    setCancelling(true);
    setCancelError(null);
    setCancelOrderId(targetOrderId);
    try {
      await cancelTradingOrder(selectedAccountId, targetOrderId, mode);

      // E*TRADE cancellations can be asynchronous and may transition through
      // CANCEL_REQUESTED before disappearing from OPEN or settling as CANCELLED.
      // Update the visible list immediately, then re-sync in the background.
      setOrders((prev) => {
        if (orderStatusFilter === "OPEN") {
          return prev.filter((o) => getOrderId(o) !== targetOrderId);
        }
        return prev.map((o) =>
          getOrderId(o) === targetOrderId
            ? mode === "paper"
              ? { ...o, status: "canceled" }
              : { ...o, orderStatus: "CANCEL_REQUESTED" }
            : o
        );
      });

      setCancelOrderId(null);
      setPendingCancelOrderId(null);
      setCancelDialogOpen(false);
      window.setTimeout(() => {
        void loadOrders();
      }, 1500);
      window.setTimeout(() => {
        void loadOrders();
      }, 4000);
    } catch (e) {
      setCancelError(String(e));
      setCancelOrderId(null);
    } finally {
      setCancelling(false);
    }
  };

  const selectedAccount = accounts.find((a) => a.id === selectedAccountId) ?? null;
  const balanceItems = accountBalance ? parseBalanceItems(accountBalance, mode) : [];

  return (
    <div className="space-y-4 max-w-7xl min-w-0">
      <PageHeader
        title={mode === "paper" ? "Paper trading" : "E*TRADE trading"}
        subtitle={
          mode === "paper"
            ? "Place equity and option paper orders using Alpaca paper trading."
            : "Place equity and option orders using the E*TRADE live mode configured in Settings."
        }
        actions={
          <Link
            href="/dashboard/settings"
            className="text-sm text-emerald-600 dark:text-emerald-400 hover:underline"
          >
            Settings (paper and live trading credentials)
          </Link>
        }
      />

      {mode === "live" && (
        <div className="flex items-start gap-3 rounded-md border border-red-600/50 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          <svg className="h-5 w-5 shrink-0 mt-0.5 text-red-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
          </svg>
          <div>
            <p className="font-semibold text-red-200">Live trading mode &mdash; real money at risk</p>
            <p className="mt-0.5 text-red-400/80 text-xs">Orders placed here will be executed on your live E*TRADE account. Double-check every order before submitting.</p>
          </div>
        </div>
      )}

      {error && (
        <div className="flex items-start gap-2 rounded-md border border-red-700/50 bg-red-900/20 px-3 py-2.5 text-sm text-red-300">
          <svg className="h-4 w-4 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
          </svg>
          {error}
        </div>
      )}

      <ConfirmDialog
        open={cancelDialogOpen}
        onClose={() => {
          if (!cancelling) {
            setCancelDialogOpen(false);
            setPendingCancelOrderId(null);
            setCancelError(null);
          }
        }}
        title="Cancel order"
        message={
          pendingCancelOrderId != null
            ? `Cancel order #${pendingCancelOrderId}?`
            : ""
        }
        confirmLabel="Cancel order"
        cancelLabel="Keep order"
        onConfirm={handleCancelOrder}
        variant="danger"
        loading={cancelling}
        error={cancelError}
      />

      <div className="grid gap-4 xl:grid-cols-[340px,minmax(0,1fr)]">
        <Card className="h-fit">
          <CardBody className="space-y-4">
            <div>
              <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
                Mode
              </p>
              <Badge tone={mode === "paper" ? "gray" : "red"}>
                {mode === "paper" ? "Paper (Alpaca)" : "Live (E*TRADE)"}
              </Badge>
            </div>

            <div>
              <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
                Account
              </p>
              {loadingAccounts ? (
                <p className="text-sm text-zinc-500">Loading accounts…</p>
              ) : accounts.length === 0 ? (
                <p className="text-sm text-zinc-500">
                  {mode === "paper"
                    ? "No Alpaca paper account found. Check Alpaca paper credentials in Settings and try again."
                    : "No E*TRADE live account found. Check E*TRADE credentials in Settings and try again."}
                </p>
              ) : (
                <SelectField
                  label="Choose an account"
                  value={selectedAccountId}
                  onChange={(e) => setSelectedAccountId(e.target.value)}
                >
                  <option value="">Select account…</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.label}
                    </option>
                  ))}
                </SelectField>
              )}
            </div>

            {selectedAccount && (
              <div className="rounded-lg border border-zinc-200 dark:border-zinc-700 px-3 py-3 space-y-3">
                <div>
                  <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                    {selectedAccount.accountDesc ?? selectedAccount.label}
                  </p>
                  <div className="mt-1 space-y-0.5 text-xs text-zinc-500 dark:text-zinc-400">
                    <p>Account key: {selectedAccount.id}</p>
                    {selectedAccount.accountId && <p>Account ID: {selectedAccount.accountId}</p>}
                    {selectedAccount.accountType && <p>Type: {selectedAccount.accountType}</p>}
                    {selectedAccount.institutionType && <p>Institution: {selectedAccount.institutionType}</p>}
                    {selectedAccount.accountMode && <p>Mode: {selectedAccount.accountMode}</p>}
                  </div>
                </div>

                <div className="border-t border-zinc-200 dark:border-zinc-700 pt-3">
                  <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">
                    Balance summary
                  </p>
                  {loadingBalance ? (
                    <p className="text-sm text-zinc-500">Loading balance…</p>
                  ) : balanceItems.length === 0 ? (
                    <p className="text-sm text-zinc-500">
                      Balance details unavailable for this account.
                    </p>
                  ) : (
                    <div className="space-y-1.5">
                      {balanceItems.map((item) => (
                        <div key={item.label} className="flex items-start justify-between gap-3 text-sm">
                          <span className="text-zinc-500 dark:text-zinc-400">{item.label}</span>
                          <span className="text-right font-mono text-zinc-900 dark:text-zinc-100 break-all">
                            {item.value}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </CardBody>
        </Card>

        <div className="space-y-4 min-w-0">
          {selectedAccountId && (
            <Card>
              <CardBody>
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                    Recent orders
                  </h2>
                  <div className="flex flex-wrap gap-2">
                    {(["OPEN", "EXECUTED", "CANCELLED", "ALL"] as const).map((status) => (
                      <button
                        key={status}
                        type="button"
                        onClick={() => setOrderStatusFilter(status)}
                        className={`rounded-md px-2.5 py-1 text-xs font-medium ${
                          orderStatusFilter === status
                            ? "bg-emerald-600 text-white"
                            : "bg-zinc-100 text-zinc-700 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700"
                        }`}
                      >
                        {status}
                      </button>
                    ))}
                  </div>
                </div>
                {loadingOrders ? (
                  <p className="text-sm text-zinc-500">Loading…</p>
                ) : orders.length === 0 ? (
                  <p className="text-sm text-zinc-500">No orders for this filter.</p>
                ) : (
                  <ul className="space-y-2">
                    {orders.map((ord) => {
                      const orderId = getOrderId(ord);
                      const desc =
                        getOrderDescription(ord, mode) || `Order #${orderId}`;
                      const status = getOrderStatus(ord, mode);
                      return (
                        <li
                          key={orderId}
                          className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-zinc-200 dark:border-zinc-700 px-3 py-2 text-sm"
                        >
                          <div className="min-w-0">
                            <div className="min-w-0 break-words text-zinc-900 dark:text-zinc-100">
                              {desc}
                            </div>
                            <div className="text-xs text-zinc-500 dark:text-zinc-400">
                              #{orderId} · {status}
                            </div>
                          </div>
                          {status === "OPEN" && (
                            <Button
                              type="button"
                              variant="danger"
                              size="sm"
                              disabled={cancelling && cancelOrderId === orderId}
                              onClick={() => {
                                setPendingCancelOrderId(orderId);
                                setCancelError(null);
                                setCancelDialogOpen(true);
                              }}
                            >
                              {cancelling && cancelOrderId === orderId ? "Cancelling…" : "Cancel"}
                            </Button>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </CardBody>
            </Card>
          )}

          {selectedAccountId && (
            <PlaceOrderSection
              mode={mode}
              accountIdKey={selectedAccountId}
              symbols={symbols}
              orderTab={orderTab}
              setOrderTab={setOrderTab}
              placing={placing}
              setPlacing={setPlacing}
              setError={setError}
              onPlaced={loadOrders}
              placeEquity={placeTradingEquityOrder}
              placeOption={placeTradingOptionOrder}
            />
          )}

          {selectedAccountId && !hasSymbols && (
            <Card>
              <CardBody>
                <p className="text-sm text-zinc-500">
                  No symbols available in the database yet. Sync or import data before placing orders.
                </p>
              </CardBody>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function PlaceOrderSection({
  mode,
  accountIdKey,
  symbols,
  orderTab,
  setOrderTab,
  placing,
  setPlacing,
  setError,
  onPlaced,
  placeEquity,
  placeOption,
}: {
  mode: TradingMode;
  accountIdKey: string;
  symbols: string[];
  orderTab: "equity" | "option";
  setOrderTab: (t: "equity" | "option") => void;
  placing: boolean;
  setPlacing: (v: boolean) => void;
  setError: (e: string | null) => void;
  onPlaced: () => Promise<void>;
  placeEquity: (p: PlaceEquityOrderParams, m: TradingMode) => Promise<Record<string, unknown>>;
  placeOption: (p: PlaceOptionOrderParams, m: TradingMode) => Promise<Record<string, unknown>>;
}) {
  const [symbol, setSymbol] = useState(symbols[0] ?? "");
  const [equityAction, setEquityAction] = useState("BUY");
  const [equityQty, setEquityQty] = useState(10);
  const [equityPriceType, setEquityPriceType] = useState("MARKET");
  const [equityLimit, setEquityLimit] = useState("");
  const [optCallPut, setOptCallPut] = useState("CALL");
  const [optExpiry, setOptExpiry] = useState("");
  const [optStrike, setOptStrike] = useState("");
  const [optAction, setOptAction] = useState("BUY_OPEN");
  const [optQty, setOptQty] = useState(1);
  const [submitMessage, setSubmitMessage] = useState<string | null>(null);

  useEffect(() => {
    if (symbols.length && !symbols.includes(symbol)) setSymbol(symbols[0]);
  }, [symbols, symbol]);

  const submitEquity = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitMessage(null);
    setPlacing(true);
    try {
      const params: PlaceEquityOrderParams = {
        account_id_key: accountIdKey,
        symbol,
        order_action: equityAction,
        quantity: equityQty,
        price_type: equityPriceType,
      };
      if (equityPriceType !== "MARKET" && equityLimit) {
        params.limit_price = Number(equityLimit);
      }
      const response = await placeEquity(params, mode);
      await onPlaced();
      setSubmitMessage(getPlacedOrderMessage(response, mode));
      setError(null);
    } catch (err) {
      setError(String(err));
    } finally {
      setPlacing(false);
    }
  };

  const submitOption = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitMessage(null);
    if (!optExpiry || !optStrike) {
      setError("Expiry and strike are required.");
      return;
    }
    setPlacing(true);
    try {
      const response = await placeOption(
        {
          account_id_key: accountIdKey,
          symbol,
          call_put: optCallPut,
          expiry_date: optExpiry,
          strike_price: Number(optStrike),
          order_action: optAction,
          quantity: optQty,
          price_type: "MARKET",
        },
        mode
      );
      await onPlaced();
      setSubmitMessage(getPlacedOrderMessage(response, mode));
      setError(null);
    } catch (err) {
      setError(String(err));
    } finally {
      setPlacing(false);
    }
  };

  return (
    <Card>
      <CardBody>
        <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
          Place order
        </h2>
        {submitMessage && (
          <div className="mb-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-200">
            {submitMessage}
          </div>
        )}
        <div className="flex flex-wrap gap-2 border-b border-zinc-200 dark:border-zinc-700 mb-3">
          <button
            type="button"
            onClick={() => setOrderTab("equity")}
            className={`px-3 py-1.5 text-sm font-medium rounded-t ${
              orderTab === "equity"
                ? "bg-emerald-600 text-white"
                : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
            }`}
          >
            Equity
          </button>
          <button
            type="button"
            onClick={() => setOrderTab("option")}
            className={`px-3 py-1.5 text-sm font-medium rounded-t ${
              orderTab === "option"
                ? "bg-emerald-600 text-white"
                : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
            }`}
          >
            Option
          </button>
        </div>

        {orderTab === "equity" && (
          <form onSubmit={submitEquity} className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <SelectField label="Symbol" value={symbol} onChange={(e) => setSymbol(e.target.value)}>
                {symbols.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </SelectField>
              <SelectField label="Action" value={equityAction} onChange={(e) => setEquityAction(e.target.value)}>
                <option value="BUY">Buy</option>
                <option value="SELL">Sell</option>
                <option value="BUY_TO_COVER">Buy to cover</option>
                <option value="SELL_SHORT">Sell short</option>
              </SelectField>
              <div>
                <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-0.5">
                  Qty
                </label>
                <input
                  type="number"
                  min={1}
                  value={equityQty}
                  onChange={(e) => setEquityQty(Number(e.target.value) || 1)}
                  className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 py-2 text-sm"
                />
              </div>
              <SelectField label="Price type" value={equityPriceType} onChange={(e) => setEquityPriceType(e.target.value)}>
                <option value="MARKET">Market</option>
                <option value="LIMIT">Limit</option>
              </SelectField>
            </div>
            {equityPriceType === "LIMIT" && (
              <div className="max-w-sm">
                <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-0.5">
                  Limit price
                </label>
                <input
                  type="number"
                  step={0.01}
                  min={0}
                  value={equityLimit}
                  onChange={(e) => setEquityLimit(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 py-2 text-sm"
                  placeholder="e.g. 150.00"
                />
              </div>
            )}
            <Button type="submit" disabled={placing || !symbol}>
              {placing ? "Placing…" : "Place equity order"}
            </Button>
          </form>
        )}

        {orderTab === "option" && (
          <form onSubmit={submitOption} className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <SelectField label="Symbol" value={symbol} onChange={(e) => setSymbol(e.target.value)}>
                {symbols.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </SelectField>
              <SelectField label="Call / Put" value={optCallPut} onChange={(e) => setOptCallPut(e.target.value)}>
                <option value="CALL">Call</option>
                <option value="PUT">Put</option>
              </SelectField>
              <div>
                <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-0.5">
                  Expiry (YYYY-MM-DD)
                </label>
                <input
                  type="text"
                  value={optExpiry}
                  onChange={(e) => setOptExpiry(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 py-2 text-sm"
                  placeholder="2025-01-17"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-0.5">
                  Strike
                </label>
                <input
                  type="number"
                  step={0.5}
                  min={0}
                  value={optStrike}
                  onChange={(e) => setOptStrike(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 py-2 text-sm"
                />
              </div>
              <SelectField label="Action" value={optAction} onChange={(e) => setOptAction(e.target.value)}>
                <option value="BUY_OPEN">Buy to open</option>
                <option value="SELL_CLOSE">Sell to close</option>
                <option value="SELL_OPEN">Sell to open</option>
                <option value="BUY_CLOSE">Buy to close</option>
              </SelectField>
              <div>
                <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-0.5">
                  Contracts
                </label>
                <input
                  type="number"
                  min={1}
                  value={optQty}
                  onChange={(e) => setOptQty(Number(e.target.value) || 1)}
                  className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 py-2 text-sm"
                />
              </div>
            </div>
            <Button type="submit" disabled={placing || !symbol}>
              {placing ? "Placing…" : "Place option order"}
            </Button>
          </form>
        )}
      </CardBody>
    </Card>
  );
}
