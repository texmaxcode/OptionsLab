"""GET /strategies - list available strategy names and metadata."""

from fastapi import APIRouter

from api.schemas import StrategyInfo
from api.services.run_backtest import STRATEGIES, EQUITY_ONLY_STRATEGIES

router = APIRouter(prefix="/strategies", tags=["strategies"])

# Human-readable labels for the UI
STRATEGY_LABELS = {
    "single_leg": "Single Leg Options",
    "sma_crossover": "SMA Crossover",
    "sma_rsi": "SMA + RSI",
    "covered_call": "Covered Call",
    "protective_put": "Protective Put",
}


@router.get("", response_model=list[StrategyInfo])
def list_strategies():
    """Return all available strategies with id, label, and whether they are equity-only."""
    return [
        StrategyInfo(
            id=name,
            label=STRATEGY_LABELS.get(name, name.replace("_", " ").title()),
            equity_only=(name in EQUITY_ONLY_STRATEGIES),
        )
        for name in STRATEGIES
    ]
