from fastapi import Request

from app.enums import BaseCurrency

BASE_CURRENCY_HEADER = "X-Base-Currency"


def resolve_base_currency(raw_value: str | None) -> BaseCurrency:
    if not raw_value:
        return BaseCurrency.MXN
    try:
        return BaseCurrency(raw_value.upper())
    except ValueError:
        return BaseCurrency.MXN


def get_request_base_currency(request: Request) -> BaseCurrency:
    return resolve_base_currency(request.headers.get(BASE_CURRENCY_HEADER))


def payment_amount_column(base_currency: BaseCurrency) -> str:
    return "amount_usd" if base_currency == BaseCurrency.USD else "amount_mxn"


def alloc_amount_column(base_currency: BaseCurrency) -> str:
    """Revenue column from report_payment_allocations."""
    return "allocated_amount_usd" if base_currency == BaseCurrency.USD else "allocated_amount_mxn"


def line_expected_total_column(base_currency: BaseCurrency) -> str:
    return "expected_total_usd" if base_currency == BaseCurrency.USD else "expected_total_mxn"


def line_expected_cost_column(base_currency: BaseCurrency) -> str:
    return "expected_cost_usd" if base_currency == BaseCurrency.USD else "expected_cost_mxn"
