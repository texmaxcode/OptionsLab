"""POST /backtests/run - run a backtest (non-persisted)."""

from fastapi import APIRouter

from api.schemas import RunBacktestRequest, RunBacktestResponse
from api.services.run_backtest import run_backtest

router = APIRouter(tags=["backtests"])


@router.post("/backtests/run", response_model=RunBacktestResponse)
def run_backtest_endpoint(body: RunBacktestRequest):
    """Run a backtest with the given parameters. Returns start/end portfolio value or error."""
    result = run_backtest(
        strategy=body.strategy,
        underlying=body.underlying,
        from_date=body.from_date,
        to_date=body.to_date,
        cash=body.cash,
        contract_id=body.contract_id,
        contract_symbol=body.contract_symbol,
        first_contract=body.first_contract,
        no_plot=True,
    )
    return RunBacktestResponse(
        success=result["success"],
        start_value=result.get("start_value"),
        end_value=result.get("end_value"),
        error=result.get("error"),
    )

