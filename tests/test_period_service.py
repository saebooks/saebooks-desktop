"""Unit tests for saebooks_desktop.services.period — the period-picker date resolver.

Pure-function tests, no Qt / APIClient fixtures needed. Mirrors
saebooks-web's test_period.py — same math, same engine, same rule.
"""
from __future__ import annotations

from datetime import date

from saebooks_desktop.services import period


class TestFyBoundsContaining:
    def test_au_default_within_fy(self):
        start, end = period.fy_bounds_containing(date(2026, 7, 21), fin_year_start_month=7)
        assert start == date(2026, 7, 1)
        assert end == date(2027, 6, 30)

    def test_au_default_before_fy_start(self):
        start, end = period.fy_bounds_containing(date(2026, 3, 1), fin_year_start_month=7)
        assert start == date(2025, 7, 1)
        assert end == date(2026, 6, 30)

    def test_calendar_year_fy(self):
        start, end = period.fy_bounds_containing(date(2026, 3, 1), fin_year_start_month=1)
        assert start == date(2026, 1, 1)
        assert end == date(2026, 12, 31)

    def test_leap_day_start_clamped(self):
        start, _end = period.fy_bounds_containing(
            date(2026, 3, 1), fin_year_start_month=2, fin_year_start_day=29
        )
        assert start == date(2026, 2, 28)


class TestSubtractOneYear:
    def test_normal(self):
        assert period.subtract_one_year(date(2026, 7, 21)) == date(2025, 7, 21)

    def test_leap_day_clamped(self):
        assert period.subtract_one_year(date(2024, 2, 29)) == date(2023, 2, 28)


class TestResolvePeriod:
    TODAY = date(2026, 7, 21)

    def test_this_fy(self):
        from_, to_, active = period.resolve_period(
            "this_fy", fin_year_start_month=7, today=self.TODAY
        )
        assert (from_, to_, active) == ("2026-07-01", "2026-07-21", "this_fy")

    def test_last_fy(self):
        from_, to_, active = period.resolve_period(
            "last_fy", fin_year_start_month=7, today=self.TODAY
        )
        assert (from_, to_, active) == ("2025-07-01", "2026-06-30", "last_fy")

    def test_calendar_ytd(self):
        from_, to_, active = period.resolve_period(
            "calendar_ytd", fin_year_start_month=7, today=self.TODAY
        )
        assert (from_, to_, active) == ("2026-01-01", "2026-07-21", "calendar_ytd")

    def test_trailing_12(self):
        from_, to_, active = period.resolve_period(
            "trailing_12", fin_year_start_month=7, today=self.TODAY
        )
        assert (from_, to_, active) == ("2025-07-21", "2026-07-21", "trailing_12")

    def test_this_quarter(self):
        from_, to_, active = period.resolve_period(
            "this_quarter", fin_year_start_month=7, today=self.TODAY
        )
        assert (from_, to_, active) == ("2026-07-01", "2026-07-21", "this_quarter")

    def test_custom_range_passthrough(self):
        from_, to_, active = period.resolve_period(
            "custom", "2026-01-01", "2026-03-31", today=self.TODAY
        )
        assert (from_, to_, active) == ("2026-01-01", "2026-03-31", "custom")

    def test_non_au_fin_year_start_month(self):
        from_, to_, active = period.resolve_period(
            "this_fy", fin_year_start_month=1, today=self.TODAY
        )
        assert (from_, to_, active) == ("2026-01-01", "2026-07-21", "this_fy")
