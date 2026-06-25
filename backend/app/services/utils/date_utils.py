from __future__ import annotations

from datetime import date, timedelta

from app.enums import ComparisonMode
from app.schemas.reports import ComparisonMeta


def rewind_date_range_one_year(date_from: str, date_to: str) -> tuple[str, str]:
    start = date.fromisoformat(date_from)
    end = date.fromisoformat(date_to)
    return (
        start.replace(year=start.year - 1).isoformat(),
        end.replace(year=end.year - 1).isoformat(),
    )


def previous_period_date_range(date_from: str, date_to: str) -> tuple[str, str]:
    start_date = date.fromisoformat(date_from)
    end_date = date.fromisoformat(date_to)
    days = (end_date - start_date).days + 1
    comparison_end = start_date - timedelta(days=1)
    comparison_start = comparison_end - timedelta(days=days - 1)
    return comparison_start.isoformat(), comparison_end.isoformat()


def resolve_comparison_range(filters) -> ComparisonMeta | None:
    if not getattr(filters, "show_comparison", False):
        return None

    current_from = getattr(filters, "date_from", None)
    current_to = getattr(filters, "date_to", None)
    if not current_from or not current_to:
        return None

    mode = getattr(filters, "comparison_mode", ComparisonMode.PREVIOUS_YEAR)
    if mode == ComparisonMode.CUSTOM:
        comparison_from = getattr(filters, "comparison_date_from", None)
        comparison_to = getattr(filters, "comparison_date_to", None)
        if not comparison_from or not comparison_to:
            raise ValueError("Custom comparison mode requires comparison_date_from and comparison_date_to")
    elif mode == ComparisonMode.PREVIOUS_PERIOD:
        comparison_from, comparison_to = previous_period_date_range(current_from, current_to)
    else:
        comparison_from, comparison_to = rewind_date_range_one_year(current_from, current_to)

    return ComparisonMeta(
        mode=mode,
        date_from=comparison_from,
        date_to=comparison_to,
    )


def current_year_to_date_range(today: date | None = None) -> tuple[str, str]:
    current_day = today or date.today()
    return date(current_day.year, 1, 1).isoformat(), current_day.isoformat()


def percent_change(current_value: float | int, comparison_value: float | int | None) -> float | None:
    if comparison_value is None:
        return None
    comparison_number = float(comparison_value)
    if comparison_number == 0:
        return None
    return ((float(current_value) - comparison_number) / comparison_number) * 100
