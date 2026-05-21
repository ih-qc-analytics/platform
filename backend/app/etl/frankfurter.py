from __future__ import annotations

from datetime import date, datetime

import httpx

FRANKFURTER_RATE_URL = "https://api.frankfurter.dev/v2/rate/{base}/{quote}"
FRANKFURTER_RATES_URL = "https://api.frankfurter.dev/v2/rates"


class FXRateFetchError(RuntimeError):
    pass


async def fetch_frankfurter_rate(
    base_currency: str,
    quote_currency: str,
    rate_date: date,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[date, float]:
    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30, follow_redirects=True)

    try:
        response = await http_client.get(
            FRANKFURTER_RATE_URL.format(base=base_currency, quote=quote_currency),
            params={"date": rate_date.isoformat()},
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        raise FXRateFetchError(
            "Frankfurter rate fetch failed "
            f"for {base_currency}/{quote_currency} on {rate_date.isoformat()} "
            f"with status {error.response.status_code}: {_response_summary(error.response)}"
        ) from error
    except httpx.HTTPError as error:
        raise FXRateFetchError(
            "Frankfurter transport error "
            f"for {base_currency}/{quote_currency} on {rate_date.isoformat()}: {error}"
        ) from error
    finally:
        if owns_client:
            await http_client.aclose()

    try:
        payload = response.json()
    except ValueError as error:
        raise FXRateFetchError(
            "Frankfurter returned non-JSON payload "
            f"for {base_currency}/{quote_currency} on {rate_date.isoformat()}: {_response_summary(response)}"
        ) from error

    if not isinstance(payload, dict):
        raise FXRateFetchError(
            "Frankfurter returned unexpected payload shape "
            f"for {base_currency}/{quote_currency} on {rate_date.isoformat()}: {payload!r}"
        )

    payload_base = payload.get("base")
    payload_quote = payload.get("quote")
    payload_rate = payload.get("rate")
    payload_date = _coerce_date(payload.get("date"))

    if payload_base != base_currency or payload_quote != quote_currency:
        raise FXRateFetchError(
            "Frankfurter returned mismatched pair "
            f"for {base_currency}/{quote_currency} on {rate_date.isoformat()}: "
            f"base={payload_base!r}, quote={payload_quote!r}"
        )

    if payload_date is None:
        raise FXRateFetchError(
            "Frankfurter returned invalid date "
            f"for {base_currency}/{quote_currency} on {rate_date.isoformat()}: {payload!r}"
        )

    try:
        rate = float(payload_rate)
    except (TypeError, ValueError) as error:
        raise FXRateFetchError(
            "Frankfurter returned invalid rate "
            f"for {base_currency}/{quote_currency} on {rate_date.isoformat()}: {payload!r}"
        ) from error

    return payload_date, rate


async def fetch_frankfurter_time_series(
    base_currency: str,
    quote_currencies: list[str],
    start_date: date,
    end_date: date,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, object]]:
    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30, follow_redirects=True)

    try:
        response = await http_client.get(
            FRANKFURTER_RATES_URL,
            params={
                "base": base_currency,
                "quotes": ",".join(quote_currencies),
                "from": start_date.isoformat(),
                "to": end_date.isoformat(),
            },
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        raise FXRateFetchError(
            "Frankfurter time-series fetch failed "
            f"for {base_currency}/{','.join(quote_currencies)} "
            f"from {start_date.isoformat()} to {end_date.isoformat()} "
            f"with status {error.response.status_code}: {_response_summary(error.response)}"
        ) from error
    except httpx.HTTPError as error:
        raise FXRateFetchError(
            "Frankfurter transport error "
            f"for {base_currency}/{','.join(quote_currencies)} "
            f"from {start_date.isoformat()} to {end_date.isoformat()}: {error}"
        ) from error
    finally:
        if owns_client:
            await http_client.aclose()

    try:
        payload = response.json()
    except ValueError as error:
        raise FXRateFetchError(
            "Frankfurter returned non-JSON payload "
            f"for {base_currency}/{','.join(quote_currencies)} "
            f"from {start_date.isoformat()} to {end_date.isoformat()}: {_response_summary(response)}"
        ) from error

    if not isinstance(payload, list):
        raise FXRateFetchError(
            "Frankfurter returned unexpected payload shape "
            f"for {base_currency}/{','.join(quote_currencies)} "
            f"from {start_date.isoformat()} to {end_date.isoformat()}: {payload!r}"
        )

    expected_quotes = set(quote_currencies)
    rows: list[dict[str, object]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise FXRateFetchError(
                "Frankfurter returned malformed time-series item "
                f"for {base_currency}/{','.join(quote_currencies)}: {item!r}"
            )

        payload_base = item.get("base")
        payload_quote = item.get("quote")
        payload_rate = item.get("rate")
        payload_date = _coerce_date(item.get("date"))

        if payload_base != base_currency or payload_quote not in expected_quotes:
            raise FXRateFetchError(
                "Frankfurter returned mismatched time-series row "
                f"for {base_currency}/{','.join(quote_currencies)}: {item!r}"
            )
        if payload_date is None:
            raise FXRateFetchError(
                "Frankfurter returned invalid time-series date "
                f"for {base_currency}/{','.join(quote_currencies)}: {item!r}"
            )
        try:
            rate = float(payload_rate)
        except (TypeError, ValueError) as error:
            raise FXRateFetchError(
                "Frankfurter returned invalid time-series rate "
                f"for {base_currency}/{','.join(quote_currencies)}: {item!r}"
            ) from error

        rows.append(
            {
                "date": payload_date,
                "from_currency": base_currency,
                "to_currency": payload_quote,
                "rate": rate,
            }
        )

    return rows


def _response_summary(response: httpx.Response) -> str:
    body = response.text.strip()
    if len(body) > 200:
        body = f"{body[:200]}..."
    return body or "<empty body>"


def _coerce_date(value: date | datetime | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
