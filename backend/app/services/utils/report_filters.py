from app.enums import PaymentStatus, ProductType
from app.services.shared import build_geo_where_clause, coerce_iso_date_param


def payment_date_expr(payment_alias: str = "pay") -> str:
    return f"COALESCE({payment_alias}.paymentDate, DATE({payment_alias}.createdAt))"


def add_approved_payment_condition(
    conditions: list[str],
    params: dict[str, object],
    payment_alias: str = "pay",
    param_name: str = "payment_status_aprobado",
) -> None:
    conditions.append(f"{payment_alias}.status = :{param_name}")
    params[param_name] = PaymentStatus.APROBADO.value


def add_payment_date_range_conditions(
    filters,
    conditions: list[str],
    params: dict[str, object],
    payment_alias: str = "pay",
) -> None:
    payment_date = payment_date_expr(payment_alias)
    if getattr(filters, "date_from", None):
        conditions.append(f"{payment_date} >= :date_from")
        params["date_from"] = coerce_iso_date_param(filters.date_from)
    if getattr(filters, "date_to", None):
        conditions.append(f"{payment_date} <= :date_to")
        params["date_to"] = coerce_iso_date_param(filters.date_to)


def add_payment_year_condition(
    year: int,
    conditions: list[str],
    params: dict[str, object],
    payment_alias: str = "pay",
    param_name: str = "year",
) -> None:
    conditions.append(f"YEAR({payment_date_expr(payment_alias)}) = :{param_name}")
    params[param_name] = year


def add_exam_product_condition(
    conditions: list[str],
    params: dict[str, object],
    product_alias: str = "p",
    param_name: str = "product_type_exam",
) -> None:
    conditions.append(f"{product_alias}.productType = :{param_name}")
    params[param_name] = ProductType.EXAM.value


def build_payment_fact_where_clause(
    filters,
    *,
    year: int | None = None,
    include_date_range: bool = True,
    payment_alias: str = "pay",
) -> tuple[str, dict[str, object], list[str]]:
    conditions, params, expanding_keys = build_geo_where_clause(filters)
    conditions.extend(
        [
            "sl.deletedAt IS NULL",
            "l.deletedAt IS NULL",
        ]
    )
    add_approved_payment_condition(conditions, params, payment_alias=payment_alias)
    if year is not None:
        add_payment_year_condition(year, conditions, params, payment_alias=payment_alias)
    elif include_date_range:
        add_payment_date_range_conditions(filters, conditions, params, payment_alias=payment_alias)
    return " AND ".join(conditions), params, expanding_keys


def build_student_payment_fact_where_clause(
    filters,
    *,
    year: int | None = None,
    include_date_range: bool = True,
    include_exam_product: bool = False,
    payment_alias: str = "pay",
    product_alias: str = "p",
) -> tuple[str, dict[str, object], list[str]]:
    conditions, params, expanding_keys = build_geo_where_clause(filters)
    conditions.extend(
        [
            "cp.deletedAt IS NULL",
            "sl.deletedAt IS NULL",
            "l.deletedAt IS NULL",
        ]
    )
    if include_exam_product:
        add_exam_product_condition(conditions, params, product_alias=product_alias)
    add_approved_payment_condition(conditions, params, payment_alias=payment_alias)
    if year is not None:
        add_payment_year_condition(year, conditions, params, payment_alias=payment_alias)
    elif include_date_range:
        add_payment_date_range_conditions(filters, conditions, params, payment_alias=payment_alias)
    return " AND ".join(conditions), params, expanding_keys
