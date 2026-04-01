"""Pydantic request/response models for the API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ----- Strategies -----
class StrategyInfo(BaseModel):
    id: str
    label: str
    equity_only: bool = False


# ----- Contracts -----
class ContractInfo(BaseModel):
    id: int
    underlying_symbol: str
    expiration: str  # ISO date
    strike: float
    option_type: str
    contract_symbol: str


class ContractsPage(BaseModel):
    """Paginated list of options contracts."""

    items: list[ContractInfo]
    total: int


class UnderlyingBarInfo(BaseModel):
    """One OHLCV bar for the underlying."""

    date: str  # ISO date
    open: float
    high: float
    low: float
    close: float
    volume: int


class UnderlyingBarsPage(BaseModel):
    """Paginated list of underlying bars."""

    items: list[UnderlyingBarInfo]
    total: int


# ----- Economic data -----
class EconomicSeriesPoint(BaseModel):
    date: str  # ISO date
    value: float | None


class EconomicSeriesResponse(BaseModel):
    source: str
    series_id: str
    points: list[EconomicSeriesPoint]
    # Optionally include raw payload for debugging/inspection; may be None when parsing text-only formats.
    raw: Any | None = None


class StoredEconomicSeriesInfo(BaseModel):
    source: str
    series_id: str
    label: str | None = None
    point_count: int
    first_date: str | None = None
    last_date: str | None = None
    last_value: float | None = None


class StoredEconomicSeriesListResponse(BaseModel):
    items: list[StoredEconomicSeriesInfo]


class StoredEconomicSeriesDeleteResponse(BaseModel):
    source: str
    series_id: str
    deleted_series: bool
    deleted_points: int


# ----- Backtests (run-only) -----
class RunBacktestRequest(BaseModel):
    strategy: str = Field(..., description="Strategy name (e.g. single_leg, sma_crossover)")
    underlying: str = Field(..., description="Underlying symbol (e.g. AAPL)")
    from_date: str | None = Field(
        None, description="Start date YYYY-MM-DD (required for equity strategies)"
    )
    to_date: str | None = Field(
        None, description="End date YYYY-MM-DD (required for equity strategies)"
    )
    cash: float = Field(100_000.0, ge=0, description="Starting cash")
    contract_id: int | None = Field(None, description="Options contract ID in DB")
    contract_symbol: str | None = Field(None, description="Options contract symbol")
    first_contract: bool = Field(False, description="Use first contract found for underlying")


class RunBacktestResponse(BaseModel):
    success: bool
    start_value: float | None = None
    end_value: float | None = None
    error: str | None = None


# ----- User settings -----
SETTINGS_MASK = "••••••••"  # Shown when credential is set; PUT with this value means "keep existing"


class UserSettings(BaseModel):
    default_symbol: str | None = None
    default_strategy: str | None = None
    default_from_date: str | None = None
    default_to_date: str | None = None
    # API keys (stored in DB; masked on GET; env vars used when not in settings)
    massive_api_key: str | None = None
    alpaca_api_key: str | None = None
    alpaca_api_secret: str | None = None
    etrade_consumer_key: str | None = None
    etrade_consumer_secret: str | None = None
    etrade_access_token: str | None = None
    etrade_access_secret: str | None = None
    etrade_sandbox: bool | None = None  # True = sandbox, False = live
    # Economic data API keys (optional, override env when set)
    fred_api_key: str | None = None
    bls_api_key: str | None = None
    bea_api_key: str | None = None
    # LLM key (optional, override OPENAI_API_KEY env var when set)
    openai_api_key: str | None = None


class UserSettingsUpdate(UserSettings):
    pass


# ----- Backtests lab (persisted) -----
class BacktestCreateRequest(RunBacktestRequest):
    name: str = Field(..., description="Display name for the backtest")


class BacktestUpdateRequest(BaseModel):
    name: str | None = Field(None, description="New display name")


class BacktestSummary(BaseModel):
    id: int
    name: str
    created_at: datetime
    strategy: str
    underlying: str
    from_date: str | None
    to_date: str | None
    cash: float
    status: str
    start_value: float | None
    end_value: float | None


class EquityCurvePoint(BaseModel):
    date: str
    value: float


class DrawdownPoint(BaseModel):
    date: str
    drawdown: float


class TimeReturnPoint(BaseModel):
    date: str
    period_return: float = 0.0


class PricePoint(BaseModel):
    date: str
    close: float


class IndicatorPoint(BaseModel):
    date: str
    indicators: dict[str, float]


class Trade(BaseModel):
    entry_date: str
    exit_date: str
    direction: str
    size: float
    entry_price: float
    exit_price: float | None = None
    pnl: float
    pnl_pct: float | None = None
    duration_days: int | None = None


class TradeStats(BaseModel):
    trade_count: int
    win_rate: float  # 0-100 (% of trades profitable)
    avg_pnl: float | None = None
    avg_win: float | None = None
    avg_loss: float | None = None
    best_trade_pnl: float | None = None
    worst_trade_pnl: float | None = None
    profit_factor: float | None = None
    avg_hold_days: float | None = None
    long_trades: int | None = None
    short_trades: int | None = None


class BacktestDetail(BacktestSummary):
    contract_id: int | None = None
    contract_symbol: str | None = None
    first_contract: bool
    error: str | None = None
    equity_curve: list[EquityCurvePoint] | None = None
    drawdown_curve: list[DrawdownPoint] | None = None
    time_returns: list[TimeReturnPoint] | None = None
    price_series: list[PricePoint] | None = None
    indicator_series: list[IndicatorPoint] | None = None
    trades: list[Trade] | None = None
    trade_stats: TradeStats | None = None


# ----- Dashboard summary -----
class SegmentStats(BaseModel):
    total: int
    completed: int
    win_rate: float  # 0-100 (%)
    avg_return_pct: float | None = None
    best_return_pct: float | None = None
    worst_return_pct: float | None = None


class DashboardSummary(BaseModel):
    overall: SegmentStats
    equity: SegmentStats
    options: SegmentStats
    overall_equity_curve: list[EquityCurvePoint] | None = None
    equity_equity_curve: list[EquityCurvePoint] | None = None
    options_equity_curve: list[EquityCurvePoint] | None = None
    overall_trade_stats: TradeStats | None = None
    equity_trade_stats: TradeStats | None = None
    options_trade_stats: TradeStats | None = None


# ----- Data sync -----
class SyncRequest(BaseModel):
    source: str = Field(..., description="Data source: massive or etrade")
    symbols: str = Field(..., description="Comma-separated symbols (e.g. AAPL,MSFT)")
    from_date: str | None = Field(None, description="Start date YYYY-MM-DD (Massive only)")
    to_date: str | None = Field(None, description="End date YYYY-MM-DD (Massive only)")
    underlying_only: bool = Field(False, description="Only sync underlying bars (Massive only)")
    options: bool = Field(False, description="Also sync option chain (E*TRADE only)")
    max_contracts: int | None = Field(None, description="Max option contracts to fetch")


class SyncResult(BaseModel):
    symbol: str
    underlying_bars: int
    options_contracts: int | None = None
    options_bars: int | None = None
    error: str | None = None


class SyncResponse(BaseModel):
    success: bool
    total_underlying_bars: int
    results: list[SyncResult]
    error: str | None = None


# ----- E*TRADE trading (lab) -----
class EtradeEquityOrderRequest(BaseModel):
    account_id_key: str = Field(..., description="E*TRADE account key")
    symbol: str = Field(..., description="Underlying symbol (e.g. AAPL)")
    order_action: str = Field(..., description="BUY, SELL, BUY_TO_COVER, SELL_SHORT")
    quantity: int = Field(..., ge=1, description="Share quantity")
    price_type: str = Field("MARKET", description="MARKET, LIMIT, STOP, STOP_LIMIT")
    limit_price: float | None = Field(None, description="Limit price when price_type is LIMIT/STOP_LIMIT")
    stop_price: float | None = Field(None, description="Stop price when price_type is STOP/STOP_LIMIT")


class EtradeOptionOrderRequest(BaseModel):
    account_id_key: str = Field(..., description="E*TRADE account key")
    symbol: str = Field(..., description="Underlying symbol (e.g. AAPL)")
    call_put: str = Field(..., description="CALL or PUT")
    expiry_date: str = Field(..., description="Expiration YYYY-MM-DD")
    strike_price: float = Field(..., gt=0, description="Strike price")
    order_action: str = Field(..., description="BUY_OPEN, SELL_CLOSE, etc.")
    quantity: int = Field(..., ge=1, description="Contract quantity")
    price_type: str = Field("MARKET", description="MARKET or LIMIT")
    limit_price: float | None = Field(None, description="Limit price when price_type is LIMIT")


class EtradeCancelRequest(BaseModel):
    account_id_key: str = Field(..., description="E*TRADE account key")
    order_id: str = Field(..., description="Order ID to cancel")


class EtradeCancelResponse(BaseModel):
    success: bool
    account_id_key: str
    order_id: str


# ----- Alpaca paper trading (lab) -----
class AlpacaEquityOrderRequest(BaseModel):
    account_id_key: str = Field(..., description="Logical account key from UI")
    symbol: str = Field(..., description="Underlying symbol (e.g. AAPL)")
    order_action: str = Field(..., description="BUY, SELL, BUY_TO_COVER, SELL_SHORT")
    quantity: int = Field(..., ge=1, description="Share quantity")
    price_type: str = Field("MARKET", description="MARKET, LIMIT, STOP, STOP_LIMIT")
    limit_price: float | None = Field(None, description="Limit price when price_type is LIMIT/STOP_LIMIT")
    stop_price: float | None = Field(None, description="Stop price when price_type is STOP/STOP_LIMIT")


class AlpacaOptionOrderRequest(BaseModel):
    account_id_key: str = Field(..., description="Logical account key from UI")
    symbol: str = Field(..., description="Underlying symbol (e.g. AAPL)")
    call_put: str = Field(..., description="CALL or PUT")
    expiry_date: str = Field(..., description="Expiration YYYY-MM-DD")
    strike_price: float = Field(..., gt=0, description="Strike price")
    order_action: str = Field(..., description="BUY_OPEN, SELL_CLOSE, etc.")
    quantity: int = Field(..., ge=1, description="Contract quantity")
    price_type: str = Field("MARKET", description="MARKET, LIMIT, STOP, STOP_LIMIT")
    limit_price: float | None = Field(None, description="Limit price when price_type is LIMIT/STOP_LIMIT")
    stop_price: float | None = Field(None, description="Stop price when price_type is STOP/STOP_LIMIT")


class AlpacaCancelRequest(BaseModel):
    account_id_key: str = Field(..., description="Logical account key from UI")
    order_id: str = Field(..., description="Alpaca order ID to cancel")


# ----- E*TRADE OAuth (consumer key/secret -> access token/secret) -----
class EtradeOAuthRequestTokenResponse(BaseModel):
    authorization_url: str
    sandbox: bool


class EtradeOAuthExchangeAccessTokenRequest(BaseModel):
    # OAuth Verification Code shown on the E*TRADE authorization page.
    verifier: str = Field(..., description="OAuth verifier code (copy from E*TRADE authorization page)")


class EtradeOAuthExchangeAccessTokenResponse(BaseModel):
    success: bool


class EtradeOAuthDisconnectResponse(BaseModel):
    success: bool


# ----- Forecasting (TSF Options AI) -----
class ForecastRequest(BaseModel):
    """Request to run a time-series forecast. Uses same data as backtesting."""

    symbol: str = Field(..., description="Underlying symbol (e.g. AAPL)")
    from_date: str = Field(..., description="Start date YYYY-MM-DD for fitting")
    to_date: str = Field(..., description="End date YYYY-MM-DD for fitting")
    horizon: int = Field(1, ge=1, le=30, description="Forecast horizon in periods")
    model: str = Field("arima", description="Model id: arima (default), gb (gradient boosting)")
    include_macro: bool = Field(
        False,
        description=(
            "If true, join stored macro/economic series onto OHLCV features before fitting. "
            "Macro data must be synced via the economic data routes first."
        ),
    )


class ForecastPoint(BaseModel):
    """One forecast step."""

    step: int
    value: float


class ForecastResponse(BaseModel):
    """Forecast result. Same symbol/range as backtests for comparison."""

    success: bool
    symbol: str
    from_date: str
    to_date: str
    horizon: int
    model: str
    direction: str = Field(..., description="up, down, or flat")
    forecast: list[ForecastPoint] = Field(default_factory=list)
    macro_enriched: bool = Field(False, description="True if macro features were joined before fitting")
    error: str | None = None


class EvaluateForecastRequest(BaseModel):
    """Request to evaluate forecast quality on a holdout period."""

    symbol: str = Field(..., description="Underlying symbol")
    from_date: str = Field(..., description="Train start YYYY-MM-DD")
    to_date: str = Field(..., description="Train end YYYY-MM-DD")
    holdout_days: int = Field(5, ge=1, le=60, description="Holdout period for evaluation")


class EvaluateForecastResponse(BaseModel):
    """Evaluation metrics: directional accuracy, RMSE, backtest return."""

    success: bool
    symbol: str
    directional_accuracy: float
    rmse: float
    mae: float
    n_observations: int
    backtest_return: float | None = None
    backtest_win_rate: float | None = None
    error: str | None = None


# ----- Strategy Engine (forecast-based options evaluation) -----
class StrategyEvaluateRequest(BaseModel):
    """Evaluate an options strategy using a forecast distribution."""

    strategy_type: str = Field(
        ...,
        description="vertical_spread_call, vertical_spread_put, straddle, iron_condor, calendar_spread_call, calendar_spread_put",
    )
    forecast_mean: float = Field(..., description="Point forecast of underlying at expiry")
    forecast_std: float | None = Field(
        None,
        description="Std for distribution; if None, single-point (no uncertainty)",
    )
    # Strategy params (depend on strategy_type)
    long_strike: float | None = Field(None, description="Long option strike (vertical spreads)")
    short_strike: float | None = Field(None, description="Short option strike (vertical spreads)")
    strike: float | None = Field(None, description="Strike (straddle)")
    put_long: float | None = Field(None, description="Long put strike (iron condor)")
    put_short: float | None = Field(None, description="Short put strike (iron condor)")
    call_short: float | None = Field(None, description="Short call strike (iron condor)")
    call_long: float | None = Field(None, description="Long call strike (iron condor)")
    net_debit: float | None = Field(
        None,
        description="Net cost of calendar spread (positive = debit, negative = credit)",
    )
    # Optional: net premium paid (positive = debit) for break-even computation
    premium_paid: float | None = Field(
        None,
        description=(
            "Net premium paid (debit > 0, credit < 0). "
            "When provided, break-even price(s) are computed and returned."
        ),
    )
    # Optional: compare to historical backtest (same symbol/period)
    symbol: str | None = Field(None, description="Underlying symbol for optional historical backtest")
    from_date: str | None = Field(None, description="Start date YYYY-MM-DD for optional backtest")
    to_date: str | None = Field(None, description="End date YYYY-MM-DD for optional backtest")
    include_backtest: bool = Field(False, description="If true and symbol/dates set, run equity backtest and attach comparison")


class PayoffPoint(BaseModel):
    underlying: float
    payoff: float


class StrategyEvaluateResponse(BaseModel):
    """Expected value, risk, and payoff diagram from forecast-based evaluation."""

    success: bool
    strategy_type: str
    expected_value: float
    probability_of_profit: float
    max_loss: float
    max_gain: float
    payoff_diagram: list[PayoffPoint] = Field(default_factory=list)
    # Break-even price(s) at expiry (populated when premium_paid is provided)
    breakeven_prices: list[float] = Field(default_factory=list)
    error: str | None = None
    # Optional comparison to historical backtest (when include_backtest=True)
    historical_backtest_return: float | None = None
    historical_backtest_drawdown: float | None = None
    historical_backtest_error: str | None = None


# ----- Strategy Discovery (automated ranking) -----
class StrategyDiscoverRequest(BaseModel):
    """Discover and rank all strategy types for a symbol/period via auto-forecast."""

    symbol: str = Field(..., description="Underlying symbol (e.g. AAPL)")
    from_date: str = Field(..., description="Start date YYYY-MM-DD")
    to_date: str = Field(..., description="End date YYYY-MM-DD")
    horizon: int = Field(5, ge=1, le=30, description="Forecast horizon in periods")
    model: str = Field("arima", description="Forecasting model: arima or gb")
    # Optional spread width as pct of forecast_mean (default 2%)
    spread_width_pct: float = Field(0.02, ge=0.001, le=0.2, description="Spread width as fraction of forecast mean")


class StrategyDiscoverResult(BaseModel):
    strategy_type: str
    expected_value: float
    probability_of_profit: float
    max_loss: float
    max_gain: float
    params: dict[str, Any]
    rank: int


class StrategyDiscoverResponse(BaseModel):
    """Ranked list of all strategy evaluations for a given forecast."""

    success: bool
    symbol: str
    forecast_direction: str | None = None
    forecast_mean: float | None = None
    forecast_std: float | None = None
    results: list[StrategyDiscoverResult] = Field(default_factory=list)
    error: str | None = None


# ----- Research Assistant (LLM) -----
class ResearchExplainRequest(BaseModel):
    """Request an explanation of forecast and/or strategy evaluation."""

    forecast_summary: str | None = Field(None, description="Short forecast summary (symbol, direction, horizon)")
    strategy_summary: str | None = Field(None, description="Strategy name and expected value / risk")
    include_risk: bool = Field(True, description="Ask LLM to summarize risk")


class ResearchExplainResponse(BaseModel):
    """LLM-generated explanation."""

    success: bool
    explanation: str = ""
    error: str | None = None


# ----- Research E2E (forecast + strategies + explanation) -----
class ResearchAnalyzeRequest(BaseModel):
    """Run full pipeline: forecast → strategy evaluation → explanation."""

    symbol: str = Field(..., description="Underlying symbol")
    from_date: str = Field(..., description="Train start YYYY-MM-DD")
    to_date: str = Field(..., description="Train end YYYY-MM-DD")
    horizon: int = Field(1, ge=1, le=30)
    strategy_types: list[str] = Field(
        default_factory=list,
        description="Strategy types to evaluate (e.g. straddle, vertical_spread_call)",
    )
    strategy_params: dict[str, Any] | None = Field(
        None,
        description="Optional shared params (e.g. strike) for strategies",
    )


class ResearchAnalyzeResponse(BaseModel):
    """Combined forecast, strategy results, and explanation."""

    success: bool
    symbol: str
    forecast_direction: str | None = None
    forecast_mean: float | None = None
    strategy_results: list[dict[str, Any]] = Field(default_factory=list)
    explanation: str | None = None
    error: str | None = None


# ----- Auth -----
class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthUserInfo(BaseModel):
    id: int
    email: str


# ----- Volatility Dashboard -----

class IVDataPoint(BaseModel):
    date: str
    iv: float


class HVDataPoint(BaseModel):
    date: str
    hv: float


class VolatilityResponse(BaseModel):
    """Volatility analytics response for a symbol and date range."""

    success: bool
    symbol: str
    from_date: str
    to_date: str
    # Current levels (latest data point)
    current_price: float | None = None
    current_iv: float | None = None
    hv_10: float | None = None
    hv_20: float | None = None
    hv_30: float | None = None
    hv_60: float | None = None
    # IV rank / percentile (0–100 scale)
    iv_rank: float | None = None
    iv_percentile: float | None = None
    # Expected move over 30 calendar days (1σ)
    expected_move_30d_dollar: float | None = None
    expected_move_30d_pct: float | None = None
    # Time series for charting
    iv_series: list[IVDataPoint] = Field(default_factory=list)
    hv_20_series: list[HVDataPoint] = Field(default_factory=list)
    error: str | None = None


# ----- Position Sizing (Risk Tools) -----

class PositionSizeRequest(BaseModel):
    """Inputs for Kelly / fixed-risk position sizing."""

    capital: float = Field(..., gt=0, description="Total trading capital in $")
    win_rate: float = Field(
        ..., ge=0.01, le=0.99,
        description="Historical win rate as a decimal (0.55 = 55 %)",
    )
    avg_win: float = Field(..., gt=0, description="Average winning trade in $")
    avg_loss: float = Field(..., gt=0, description="Average losing trade in $")
    max_risk_pct: float = Field(
        1.0, ge=0.1, le=20.0,
        description="Maximum risk per trade as % of capital",
    )
    max_loss_per_contract: float | None = Field(
        None, gt=0,
        description="Max loss per options contract in $ (for contract count calc)",
    )
    contract_multiplier: int = Field(
        100, ge=1, description="Options contract multiplier (default 100 shares)"
    )


class PositionSizeResponse(BaseModel):
    """Position sizing results."""

    success: bool
    # Kelly Criterion
    kelly_fraction: float | None = None
    half_kelly_fraction: float | None = None
    kelly_dollar_risk: float | None = None
    half_kelly_dollar_risk: float | None = None
    # Fixed risk (risk_pct % of capital)
    fixed_risk_dollar: float | None = None
    fixed_risk_units: float | None = None
    # Max contracts (if max_loss_per_contract provided)
    max_contracts: int | None = None
    error: str | None = None


# ----- Break-Even (extends StrategyEvaluateResponse) -----

class BreakevenRequest(BaseModel):
    """Compute break-even prices for a strategy given its premium/credit."""

    strategy_type: str = Field(..., description="Strategy kind (e.g. straddle, iron_condor)")
    premium_paid: float | None = Field(
        None,
        description=(
            "Net premium paid (positive = debit, negative = credit). "
            "Straddle / debit spreads: positive. Iron condor / credit spreads: negative."
        ),
    )
    # Strategy params (same keys as StrategyEvaluateRequest)
    strike: float | None = None
    long_strike: float | None = None
    short_strike: float | None = None
    put_long: float | None = None
    put_short: float | None = None
    call_short: float | None = None
    call_long: float | None = None
    net_debit: float | None = None


class BreakevenResponse(BaseModel):
    success: bool
    strategy_type: str
    breakeven_prices: list[float] = Field(default_factory=list)
    premium_paid: float | None = None
    error: str | None = None
