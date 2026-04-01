"""Shared helpers for option strategies that exit before expiry."""

from datetime import datetime


def is_expired_or_near(
    current_dt,
    expiration,
    exit_before_expiry: bool,
    expiry_days_before: int,
) -> bool:
    """Return True if the option is at or within expiry_days_before of expiration."""
    if not exit_before_expiry or not expiration:
        return False
    try:
        exp = (
            expiration
            if isinstance(expiration, datetime)
            else datetime.strptime(str(expiration)[:10], "%Y-%m-%d")
        )
    except Exception:
        return False
    cur_date = current_dt.date() if hasattr(current_dt, "date") else current_dt
    exp_date = exp.date() if hasattr(exp, "date") else exp
    delta = (
        (exp_date - cur_date).days
        if hasattr(exp_date, "__sub__")
        else 999
    )
    return delta <= expiry_days_before
