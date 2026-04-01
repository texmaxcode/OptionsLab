"""
Risk management tools: position sizing and trade-level risk controls.

See docs/RISK_TOOLS.md for usage and integration.
"""

from risk.metrics import max_drawdown, volatility_annualized, var_historical
from risk.position_sizing import (
    kelly_fraction,
    half_kelly_fraction,
    fixed_risk_size,
    max_contracts,
)

__all__ = [
    "max_drawdown",
    "volatility_annualized",
    "var_historical",
    "kelly_fraction",
    "half_kelly_fraction",
    "fixed_risk_size",
    "max_contracts",
]
