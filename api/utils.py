"""Shared API utilities."""

from datetime import datetime


def parse_iso_date(s: str | None) -> datetime | None:
    """Parse YYYY-MM-DD string to naive datetime. Returns None for None or invalid input."""
    if not s:
        return None
    try:
        return datetime.strptime(s.strip()[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
