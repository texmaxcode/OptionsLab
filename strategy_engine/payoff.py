"""
Payoff at expiry for options strategies.

All functions take underlying price at expiry S_T and strategy parameters;
return payoff in account currency (per contract or per share as noted).
European-style: no early exercise. Used with forecast distribution for expected value.
"""


def payoff_vertical_spread_call(
    underlying_at_expiry: float,
    long_strike: float,
    short_strike: float,
) -> float:
    """
    Bull call spread: long call at long_strike, short call at short_strike.
    Requires long_strike < short_strike. Payoff per share.
    """
    if long_strike >= short_strike:
        raise ValueError("Bull call spread requires long_strike < short_strike")
    long_payoff = max(0.0, underlying_at_expiry - long_strike)
    short_payoff = -max(0.0, underlying_at_expiry - short_strike)
    return long_payoff + short_payoff


def payoff_vertical_spread_put(
    underlying_at_expiry: float,
    long_strike: float,
    short_strike: float,
) -> float:
    """
    Bear put spread: long put at long_strike, short put at short_strike.
    Requires long_strike > short_strike. Payoff per share.
    """
    if long_strike <= short_strike:
        raise ValueError("Bear put spread requires long_strike > short_strike")
    long_payoff = max(0.0, long_strike - underlying_at_expiry)
    short_payoff = -max(0.0, short_strike - underlying_at_expiry)
    return long_payoff + short_payoff


def payoff_straddle(
    underlying_at_expiry: float,
    strike: float,
) -> float:
    """
    Long straddle: long call + long put at same strike.
    Payoff per share (combined).
    """
    call_payoff = max(0.0, underlying_at_expiry - strike)
    put_payoff = max(0.0, strike - underlying_at_expiry)
    return call_payoff + put_payoff


def payoff_iron_condor(
    underlying_at_expiry: float,
    put_short: float,
    put_long: float,
    call_short: float,
    call_long: float,
) -> float:
    """
    Iron condor: short put spread (sell put at put_short, buy put at put_long)
    + short call spread (sell call at call_short, buy call at call_long).
    Requires put_long < put_short < call_short < call_long. Payoff per share.
    """
    if not (put_long < put_short < call_short < call_long):
        raise ValueError(
            "Iron condor requires put_long < put_short < call_short < call_long"
        )
    # Short put spread: sell put at put_short, buy put at put_long
    put_sell_payoff = -max(0.0, put_short - underlying_at_expiry)
    put_buy_payoff = max(0.0, put_long - underlying_at_expiry)
    # Short call spread: sell call at call_short, buy call at call_long
    call_sell_payoff = -max(0.0, underlying_at_expiry - call_short)
    call_buy_payoff = max(0.0, underlying_at_expiry - call_long)
    return put_sell_payoff + put_buy_payoff + call_sell_payoff + call_buy_payoff


def payoff_calendar_call(
    underlying_at_expiry: float,
    strike: float,
    net_debit: float,
) -> float:
    """
    Simplified calendar spread (long back-month call, short front-month call, same strike).
    At back-month expiry: long call payoff minus net cost. net_debit > 0 = paid for spread.
    """
    return max(0.0, underlying_at_expiry - strike) - net_debit


def payoff_calendar_put(
    underlying_at_expiry: float,
    strike: float,
    net_debit: float,
) -> float:
    """
    Simplified calendar spread (long back-month put, short front-month put, same strike).
    At back-month expiry: long put payoff minus net cost.
    """
    return max(0.0, strike - underlying_at_expiry) - net_debit


# Alias for backward compatibility with __init__ (vertical_spread can be call or put)
def payoff_vertical_spread(
    underlying_at_expiry: float,
    long_strike: float,
    short_strike: float,
    *,
    is_call: bool = True,
) -> float:
    """Vertical spread: call (bull) or put (bear)."""
    if is_call:
        return payoff_vertical_spread_call(
            underlying_at_expiry, long_strike, short_strike
        )
    return payoff_vertical_spread_put(
        underlying_at_expiry, long_strike, short_strike
    )
