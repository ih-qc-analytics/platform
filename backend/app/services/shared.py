from datetime import date, datetime

from app.enums import PaymentStatus


def coerce_iso_date_param(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def payment_date_expr(alias: str = "") -> str:
    prefix = f"{alias}." if alias else ""
    return f"COALESCE({prefix}payment_date, DATE({prefix}created_at))"


def line_item_date_expr(alias: str = "") -> str:
    """
    The single date column for report_line_items.

    first_payment_date = MIN(allocation.payment_date) across all
    report_payment_allocations rows for this cart_product_id. It represents
    the earliest date on which any payment was applied to this product —
    i.e. the date the product's quantity enters a reporting period.

    A product contracted in Nov 2025 but first paid Jan 2026 will have
    first_payment_date = 2026-01-xx and correctly appear only in 2026 filters.
    """
    prefix = f"{alias}." if alias else ""
    return f"{prefix}first_payment_date"


def build_geo_where_clause(filters) -> tuple[str, dict]:
    """
    Build a WHERE clause for report_line_items (single-table, no joins).
    Always filters: is_active = TRUE AND payment_status = 'Aprobado'.
    All list params use PostgreSQL's = ANY(:param) — no expanding bindparams needed.
    """
    conditions = [
        "is_active = TRUE",
        "payment_status = :payment_status",
    ]
    params: dict = {
        "payment_status": PaymentStatus.APROBADO.value,
    }

    if getattr(filters, "countries", None):
        conditions.append("site = ANY(:countries)")
        params["countries"] = list(filters.countries)
    if getattr(filters, "zones", None):
        conditions.append("zone_name = ANY(:zones)")
        params["zones"] = list(filters.zones)
    if getattr(filters, "states", None):
        conditions.append("COALESCE(state_names, ARRAY[]::text[]) && CAST(:states AS text[])")
        params["states"] = list(filters.states)
    if getattr(filters, "cities", None):
        conditions.append("COALESCE(city_names, ARRAY[]::text[]) && CAST(:cities AS text[])")
        params["cities"] = list(filters.cities)
    if getattr(filters, "date_from", None):
        conditions.append(f"{line_item_date_expr()} >= :date_from")
        params["date_from"] = coerce_iso_date_param(filters.date_from)
    if getattr(filters, "date_to", None):
        conditions.append(f"{line_item_date_expr()} <= :date_to")
        params["date_to"] = coerce_iso_date_param(filters.date_to)
    if getattr(filters, "year", None):
        conditions.append("year = :year")
        params["year"] = filters.year

    return " AND ".join(conditions), params


def build_payment_where_clause(filters, *, alias: str = "") -> tuple[str, dict]:
    prefix = f"{alias}." if alias else ""
    conditions = [
        f"{prefix}is_active = TRUE",
        f"{prefix}payment_status = :payment_status",
    ]
    params: dict = {"payment_status": PaymentStatus.APROBADO.value}

    if getattr(filters, "countries", None):
        conditions.append(f"{prefix}site = ANY(:countries)")
        params["countries"] = list(filters.countries)
    if getattr(filters, "zones", None):
        conditions.append(f"{prefix}zone_name = ANY(:zones)")
        params["zones"] = list(filters.zones)
    if getattr(filters, "states", None):
        conditions.append(
            f"COALESCE({prefix}all_states, ARRAY[]::text[]) && CAST(:states AS text[])"
        )
        params["states"] = list(filters.states)
    if getattr(filters, "cities", None):
        conditions.append(
            f"COALESCE({prefix}all_cities, ARRAY[]::text[]) && CAST(:cities AS text[])"
        )
        params["cities"] = list(filters.cities)
    if getattr(filters, "date_from", None):
        conditions.append(f"{payment_date_expr(alias)} >= :date_from")
        params["date_from"] = coerce_iso_date_param(filters.date_from)
    if getattr(filters, "date_to", None):
        conditions.append(f"{payment_date_expr(alias)} <= :date_to")
        params["date_to"] = coerce_iso_date_param(filters.date_to)
    if getattr(filters, "year", None):
        conditions.append(f"{prefix}year = :year")
        params["year"] = filters.year

    return " AND ".join(conditions), params


def build_line_item_where_clause(
    filters,
    *,
    alias: str = "",
    require_product_breakdown: bool = False,
) -> tuple[str, dict]:
    prefix = f"{alias}." if alias else ""
    conditions = [
        f"{prefix}is_active = TRUE",
        f"{prefix}payment_status = :payment_status",
    ]
    if require_product_breakdown:
        conditions.append(f"{prefix}include_in_product_breakdown = TRUE")
    params: dict = {"payment_status": PaymentStatus.APROBADO.value}

    if getattr(filters, "countries", None):
        conditions.append(f"{prefix}site = ANY(:countries)")
        params["countries"] = list(filters.countries)
    if getattr(filters, "zones", None):
        conditions.append(f"{prefix}zone_name = ANY(:zones)")
        params["zones"] = list(filters.zones)
    if getattr(filters, "states", None):
        conditions.append(
            f"COALESCE({prefix}all_states, ARRAY[]::text[]) && CAST(:states AS text[])"
        )
        params["states"] = list(filters.states)
    if getattr(filters, "cities", None):
        conditions.append(
            f"COALESCE({prefix}all_cities, ARRAY[]::text[]) && CAST(:cities AS text[])"
        )
        params["cities"] = list(filters.cities)
    if getattr(filters, "date_from", None):
        conditions.append(f"{line_item_date_expr(alias)} >= :date_from")
        params["date_from"] = coerce_iso_date_param(filters.date_from)
    if getattr(filters, "date_to", None):
        conditions.append(f"{line_item_date_expr(alias)} <= :date_to")
        params["date_to"] = coerce_iso_date_param(filters.date_to)
    if getattr(filters, "year", None):
        conditions.append(f"{prefix}year = :year")
        params["year"] = filters.year

    return " AND ".join(conditions), params


def build_alloc_where_clause(filters, *, alias: str = "rpa") -> tuple[str, dict]:
    """
    Build a WHERE clause for report_payment_allocations.
    Always filters: is_active = TRUE.
    """
    prefix = f"{alias}." if alias else ""
    conditions = [f"{prefix}is_active = TRUE"]
    params: dict = {}

    if getattr(filters, "countries", None):
        conditions.append(f"{prefix}site = ANY(:countries)")
        params["countries"] = list(filters.countries)
    if getattr(filters, "date_from", None):
        conditions.append(f"{prefix}payment_date >= :date_from")
        params["date_from"] = coerce_iso_date_param(filters.date_from)
    if getattr(filters, "date_to", None):
        conditions.append(f"{prefix}payment_date <= :date_to")
        params["date_to"] = coerce_iso_date_param(filters.date_to)

    return " AND ".join(conditions), params
