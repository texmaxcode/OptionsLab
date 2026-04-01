"""Tests for strategies.option_expiry_utils.is_expired_or_near."""

from datetime import datetime

from strategies.option_expiry_utils import is_expired_or_near


def test_is_expired_or_near_false_when_flag_disabled() -> None:
    """exit_before_expiry=False always returns False."""
    now = datetime(2024, 6, 1)
    exp = datetime(2024, 6, 5)
    assert is_expired_or_near(now, exp, False, 10) is False


def test_is_expired_or_near_true_within_threshold() -> None:
    """Returns True when current date within expiry_days_before of expiration."""
    now = datetime(2024, 6, 1)
    exp = datetime(2024, 6, 5)
    # 4 days to expiry, threshold 5 -> True
    assert is_expired_or_near(now, exp, True, 5) is True


def test_is_expired_or_near_false_outside_threshold() -> None:
    """Returns False when current date is earlier than threshold."""
    now = datetime(2024, 6, 1)
    exp = datetime(2024, 6, 10)
    # 9 days to expiry, threshold 5 -> False
    assert is_expired_or_near(now, exp, True, 5) is False


def test_is_expired_or_near_parses_string_expiration() -> None:
    """Supports expiration provided as YYYY-MM-DD string."""
    now = datetime(2024, 6, 1)
    exp_str = "2024-06-03"
    assert is_expired_or_near(now, exp_str, True, 3) is True

