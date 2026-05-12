from datetime import datetime
from typing import Optional

from app.schemas.pdf import PDFHeader

MONTH_LABELS = {
    "01": "Ene",
    "02": "Feb",
    "03": "Mar",
    "04": "Abr",
    "05": "May",
    "06": "Jun",
    "07": "Jul",
    "08": "Ago",
    "09": "Sep",
    "10": "Oct",
    "11": "Nov",
    "12": "Dic",
}


def format_currency(value: float) -> str:
    return f"${value:,.0f}"


def format_percent(value: float) -> str:
    return f"{value:.1f}%"


def format_growth(value: Optional[float]) -> tuple[Optional[str], Optional[bool]]:
    if value is None:
        return None, None
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%", value >= 0


def format_date(date_str: str) -> str:
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")


def format_month_label(month_str: str) -> str:
    year, month = month_str.split("-")
    return f"{MONTH_LABELS.get(month, month)} {year}"


def scale_series(values: list[float]) -> list[float]:
    if not values:
        return []
    max_value = max(values)
    if max_value <= 0:
        return [0.0 for _ in values]
    return [value / max_value for value in values]


def format_integer(value: int | float) -> str:
    return f"{int(value):,}"


def filters_summary(filters) -> dict[str, str]:
    summary: dict[str, str] = {}
    if getattr(filters, "date_from", None):
        summary["Desde"] = format_date(filters.date_from)
    if getattr(filters, "date_to", None):
        summary["Hasta"] = format_date(filters.date_to)
    if getattr(filters, "countries", None):
        summary["País"] = ", ".join(filters.countries)
    if getattr(filters, "zones", None):
        summary["Sede"] = ", ".join(filters.zones)
    if getattr(filters, "states", None):
        summary["Estado"] = ", ".join(filters.states)
    if getattr(filters, "cities", None):
        summary["Ciudad"] = ", ".join(filters.cities)
    return summary


def build_pdf_header(title: str, subtitle: str, filters) -> PDFHeader:
    return PDFHeader(
        title=title,
        subtitle=subtitle,
        generated_at=datetime.now().strftime("%d/%m/%Y %H:%M"),
        filters_summary=filters_summary(filters),
    )
