"use client";

import { useEffect, useState, useRef } from "react";
import {
  getUserSettings,
  updateUserSettings,
  type UserSettings,
} from "@/lib/settingsApi";
import { getStrategies, type StrategyInfo } from "@/lib/api";
import {
  disconnectEtradeOAuth,
  exchangeEtradeOAuthAccessToken,
  requestEtradeOAuthRequestToken,
} from "@/lib/tradingApi";
import { DateField } from "@/components/ui/DateField";
import { Button } from "@/components/ui/Button";
import { SelectField } from "@/components/ui/SelectField";
import { Card, CardBody } from "@/components/ui/Card";

/** Input with an optional show/hide eye toggle for sensitive fields. */
function SecretInput({
  label,
  value,
  onChange,
  placeholder,
  hint,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  hint?: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <div>
      <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-0.5">
        {label}
      </label>
      <div className="relative">
        <input
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 py-2 pr-10 text-sm text-zinc-900 dark:text-zinc-100 font-mono"
          autoComplete="off"
        />
        <button
          type="button"
          onClick={() => setShow((s) => !s)}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-300 focus:outline-none"
          aria-label={show ? "Hide value" : "Show value"}
          tabIndex={-1}
        >
          {show ? (
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" aria-hidden>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 0 0 1.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.451 10.451 0 0 1 12 4.5c4.756 0 8.773 3.162 10.065 7.498a10.522 10.522 0 0 1-4.293 5.774M6.228 6.228 3 3m3.228 3.228 3.65 3.65m7.894 7.894L21 21m-3.228-3.228-3.65-3.65m0 0a3 3 0 1 0-4.243-4.243m4.242 4.242L9.88 9.88" />
            </svg>
          ) : (
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" aria-hidden>
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
            </svg>
          )}
        </button>
      </div>
      {hint && <p className="mt-0.5 text-xs text-zinc-500">{hint}</p>}
    </div>
  );
}

// Persist form state across remounts (e.g. React Strict Mode) so typing is not lost
let cachedSettings: UserSettings | null = null;
let cachedStrategies: StrategyInfo[] | null = null;
let initialLoadApplied = false;

export default function SettingsPage() {
  const [settings, setSettings] = useState<UserSettings>(() => cachedSettings ?? {});
  const [strategies, setStrategies] = useState<StrategyInfo[]>(() => cachedStrategies ?? []);
  const [loading, setLoading] = useState(!cachedSettings);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [oauthLoading, setOauthLoading] = useState(false);
  const [oauthError, setOauthError] = useState<string | null>(null);
  const [oauthStep, setOauthStep] = useState<"idle" | "verify">("idle");
  const [oauthVerifier, setOauthVerifier] = useState("");
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    if (initialLoadApplied) {
      setLoading(false);
      return () => {
        mountedRef.current = false;
      };
    }
    Promise.all([getUserSettings(), getStrategies()])
      .then(([s, strat]) => {
        if (!mountedRef.current) return;
        if (!initialLoadApplied) {
          initialLoadApplied = true;
          cachedSettings = s;
          cachedStrategies = strat;
          setSettings(s);
          setStrategies(strat);
        }
      })
      .catch((e) => {
        if (mountedRef.current) setError(String(e));
      })
      .finally(() => {
        if (mountedRef.current) setLoading(false);
      });
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const handleChange = (field: keyof UserSettings, value: string | boolean) => {
    setSettings((prev) => {
      const next = {
        ...prev,
        [field]:
          field === "etrade_sandbox"
            ? value
            : value === "" || value === false
              ? null
              : String(value),
      };
      cachedSettings = next;
      return next;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setSaving(true);
    try {
      const updated = await updateUserSettings(settings);
      cachedSettings = updated;
      setSettings(updated);
      setSuccess("Settings saved");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const isEtradeConnected = settings.etrade_access_token != null;

  const reloadSettings = async () => {
    try {
      const s = await getUserSettings();
      cachedSettings = s;
      setSettings(s);
    } catch {
      // Best-effort refresh; keep existing state.
    }
  };

  const handleConnectEtrade = async () => {
    setOauthError(null);
    setOauthLoading(true);
    try {
      const consumerKey = (settings.etrade_consumer_key ?? "").trim();
      const consumerSecret = (settings.etrade_consumer_secret ?? "").trim();
      if (!consumerKey || !consumerSecret) {
        throw new Error("Enter E*TRADE consumer key and consumer secret first.");
      }

      // Persist consumer key/secret before starting the OAuth flow.
      await updateUserSettings(settings);

      const { authorization_url } = await requestEtradeOAuthRequestToken();
      setOauthStep("verify");
      setOauthVerifier("");
      // Open the authorization page so the user can copy the verifier code.
      window.open(authorization_url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setOauthError(String((e as Error).message ?? e));
    } finally {
      setOauthLoading(false);
    }
  };

  const handleExchangeVerifier = async () => {
    setOauthError(null);
    setOauthLoading(true);
    try {
      await exchangeEtradeOAuthAccessToken({ verifier: oauthVerifier });
      setOauthStep("idle");
      setOauthVerifier("");
      await reloadSettings();
    } catch (e) {
      setOauthError(String((e as Error).message ?? e));
    } finally {
      setOauthLoading(false);
    }
  };

  const handleDisconnectEtrade = async () => {
    setOauthError(null);
    setOauthLoading(true);
    try {
      await disconnectEtradeOAuth();
      setOauthStep("idle");
      setOauthVerifier("");
      await reloadSettings();
    } catch (e) {
      setOauthError(String((e as Error).message ?? e));
    } finally {
      setOauthLoading(false);
    }
  };

  if (loading) {
    return <p className="text-sm text-zinc-600 dark:text-zinc-400">Loading…</p>;
  }

  return (
    <div className="max-w-xl space-y-4 min-w-0">
      <div>
        <h1 className="text-xl sm:text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
          Settings
        </h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-0.5">
          Defaults, API keys, and trading credentials.
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
      {success && (
        <div className="flex items-start gap-2 rounded-md border border-emerald-700/50 bg-emerald-900/20 px-3 py-2.5 text-sm text-emerald-300">
          <svg className="h-4 w-4 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
          </svg>
          {success}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">

        {/* --- Defaults --- */}
        <Card>
          <CardBody className="space-y-3">
            <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Backtest defaults</h2>
            <div>
              <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-0.5">
                Default symbol
              </label>
              <input
                type="text"
                value={settings.default_symbol ?? ""}
                onChange={(e) => handleChange("default_symbol", e.target.value)}
                className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-100"
                placeholder="e.g. AAPL"
              />
            </div>
            <SelectField
              label="Default strategy"
              value={settings.default_strategy ?? ""}
              onChange={(e) => handleChange("default_strategy", e.target.value)}
            >
              <option value="">None</option>
              {strategies.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </SelectField>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <DateField
                label="Default from date"
                value={settings.default_from_date ?? ""}
                onChange={(e) => handleChange("default_from_date", e.target.value)}
              />
              <DateField
                label="Default to date"
                value={settings.default_to_date ?? ""}
                onChange={(e) => handleChange("default_to_date", e.target.value)}
              />
            </div>
          </CardBody>
        </Card>

        {/* --- Data sync --- */}
        <Card>
          <CardBody className="space-y-3">
            <div>
              <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Data sync</h2>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                API key for Massive (market data sync).
              </p>
            </div>
            <SecretInput
              label="Massive API key"
              value={settings.massive_api_key ?? ""}
              onChange={(v) => handleChange("massive_api_key", v)}
              placeholder="From massive.com/dashboard/keys"
            />
          </CardBody>
        </Card>

        {/* --- AI / LLM --- */}
        <Card>
          <CardBody className="space-y-3">
            <div>
              <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">AI &amp; Research Assistant</h2>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                OpenAI key enables AI-generated explanations in Research &amp; AI. Without it, structured placeholders are shown. Get a key at{" "}
                <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">
                  platform.openai.com
                </a>.
              </p>
            </div>
            <SecretInput
              label="OpenAI API key"
              value={settings.openai_api_key ?? ""}
              onChange={(v) => handleChange("openai_api_key", v)}
              placeholder="sk-..."
            />
          </CardBody>
        </Card>

        {/* --- Economic data --- */}
        <Card>
          <CardBody className="space-y-3">
            <div>
              <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Economic data APIs</h2>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                Keys for FRED, BLS, and BEA macro data. Can also be set as environment variables.
              </p>
            </div>
            <SecretInput
              label="FRED API key"
              value={settings.fred_api_key ?? ""}
              onChange={(v) => handleChange("fred_api_key", v)}
              placeholder="From fred.stlouisfed.org"
            />
            <SecretInput
              label="BLS API key"
              value={settings.bls_api_key ?? ""}
              onChange={(v) => handleChange("bls_api_key", v)}
              placeholder="From bls.gov/developers"
            />
            <SecretInput
              label="BEA API key"
              value={settings.bea_api_key ?? ""}
              onChange={(v) => handleChange("bea_api_key", v)}
              placeholder="From bea.gov/developers"
            />
          </CardBody>
        </Card>

        {/* --- Trading mode --- */}
        <Card>
          <CardBody className="space-y-3">
            <div>
              <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Trading mode</h2>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                Paper mode uses Alpaca credentials. Live mode uses E*TRADE credentials and OAuth.
              </p>
            </div>
            <SelectField
              label="Active mode"
              value={(settings.etrade_sandbox ?? true) ? "paper" : "live"}
              onChange={(e) => handleChange("etrade_sandbox", e.target.value === "paper")}
            >
              <option value="paper">Paper trading (Alpaca)</option>
              <option value="live">Live trading (E*TRADE)</option>
            </SelectField>
          </CardBody>
        </Card>

        {/* --- Alpaca paper --- */}
        <Card>
          <CardBody className="space-y-3">
            <div>
              <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Alpaca paper trading</h2>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                Used when trading mode is set to Paper. Get keys from{" "}
                <a href="https://alpaca.markets" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">
                  alpaca.markets
                </a>{" "}
                &rarr; Paper trading dashboard.
              </p>
            </div>
            <SecretInput
              label="Alpaca API key"
              value={settings.alpaca_api_key ?? ""}
              onChange={(v) => handleChange("alpaca_api_key", v)}
              placeholder="From Alpaca paper trading dashboard"
            />
            <SecretInput
              label="Alpaca API secret"
              value={settings.alpaca_api_secret ?? ""}
              onChange={(v) => handleChange("alpaca_api_secret", v)}
              placeholder="From Alpaca paper trading dashboard"
            />
          </CardBody>
        </Card>

        {/* --- E*TRADE live --- */}
        <Card>
          <CardBody className="space-y-3">
            <div>
              <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">E*TRADE live trading</h2>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                Used when trading mode is set to Live. Get keys from{" "}
                <a href="https://developer.etrade.com" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">
                  developer.etrade.com
                </a>.
              </p>
            </div>
            <SecretInput
              label="E*TRADE consumer key"
              value={settings.etrade_consumer_key ?? ""}
              onChange={(v) => handleChange("etrade_consumer_key", v)}
              placeholder="From developer.etrade.com"
            />
            <SecretInput
              label="E*TRADE consumer secret"
              value={settings.etrade_consumer_secret ?? ""}
              onChange={(v) => handleChange("etrade_consumer_secret", v)}
              placeholder="E*TRADE consumer secret"
            />

            <div className="border-t border-zinc-800 pt-3 space-y-2">
              <div className="flex items-center gap-2">
                {isEtradeConnected ? (
                  <span className="flex items-center gap-1.5 text-sm text-emerald-300 font-medium">
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" aria-hidden>
                      <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                    </svg>
                    E*TRADE connected
                  </span>
                ) : (
                  <span className="text-sm text-zinc-500">E*TRADE not connected</span>
                )}
              </div>

              {!isEtradeConnected && oauthStep === "idle" && (
                <p className="text-xs text-zinc-500">
                  Steps: 1. Enter keys above and save &rarr; 2. Click &ldquo;Connect&rdquo; &rarr; 3. Authorize on E*TRADE &rarr; 4. Paste the verifier code below.
                </p>
              )}

              <Button
                type="button"
                variant={isEtradeConnected ? "danger" : "primary"}
                onClick={isEtradeConnected ? handleDisconnectEtrade : handleConnectEtrade}
                disabled={
                  oauthLoading ||
                  (!isEtradeConnected &&
                    (!settings.etrade_consumer_key || !settings.etrade_consumer_secret))
                }
                className="w-full"
              >
                {oauthLoading
                  ? isEtradeConnected
                    ? "Disconnecting\u2026"
                    : "Connecting\u2026"
                  : isEtradeConnected
                    ? "Disconnect E*TRADE"
                    : "Connect E*TRADE"}
              </Button>

              {!isEtradeConnected && oauthStep === "verify" && (
                <div className="space-y-2 pt-1">
                  <p className="text-xs text-zinc-400">
                    An E*TRADE authorization page opened in a new tab. After authorizing, copy the verifier code and paste it below.
                  </p>
                  <SecretInput
                    label="OAuth verifier code"
                    value={oauthVerifier}
                    onChange={setOauthVerifier}
                    placeholder="Paste verifier code from E*TRADE"
                  />
                  <Button
                    type="button"
                    onClick={handleExchangeVerifier}
                    disabled={oauthLoading || !oauthVerifier.trim()}
                    className="w-full"
                  >
                    {oauthLoading ? "Exchanging\u2026" : "Exchange for access token"}
                  </Button>
                </div>
              )}

              {oauthError && (
                <div className="flex items-start gap-2 rounded-md border border-red-700/50 bg-red-900/20 px-3 py-2 text-sm text-red-300">
                  <svg className="h-4 w-4 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" aria-hidden>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                  </svg>
                  {oauthError}
                </div>
              )}
            </div>
          </CardBody>
        </Card>

        <button
          type="submit"
          disabled={saving}
          className="w-full rounded-lg bg-emerald-600 px-3 py-2.5 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50 transition-colors"
        >
          {saving ? "Saving\u2026" : "Save settings"}
        </button>
      </form>
    </div>
  );
}

