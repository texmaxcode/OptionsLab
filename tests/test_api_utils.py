"""Tests for api.utils."""

from api.utils import parse_iso_date


def test_parse_iso_date_valid():
    assert parse_iso_date("2024-01-15") is not None
    assert parse_iso_date("2024-01-15").year == 2024
    assert parse_iso_date("2024-01-15").month == 1
    assert parse_iso_date("2024-01-15").day == 15


def test_parse_iso_date_with_whitespace():
    assert parse_iso_date("  2024-06-01  ") is not None
    assert parse_iso_date("  2024-06-01  ").day == 1


def test_parse_iso_date_none():
    assert parse_iso_date(None) is None


def test_parse_iso_date_empty_string():
    assert parse_iso_date("") is None


def test_parse_iso_date_invalid():
    assert parse_iso_date("not-a-date") is None
    assert parse_iso_date("2024-13-01") is None  # invalid month
