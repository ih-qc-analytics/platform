import unicodedata
from collections.abc import Mapping

FALLBACK_EXCHANGE_RATE = 999999999.0

COUNTRY_TO_RATE_SOURCE = {
    "mexico": None,
    "colombia": "COP",
    "peru": "PEN",
}


def normalize_country_key(country: str | None) -> str:
    if not country:
        return ""
    normalized = unicodedata.normalize("NFKD", country)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_only.strip().lower()


def sql_normalized_country_expr(column_expr: str) -> str:
    return f"""
        LOWER(
            TRIM(
                REPLACE(
                    REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(
                                    REPLACE(COALESCE({column_expr}, ''), 'á', 'a'),
                                    'é', 'e'
                                ),
                                'í', 'i'
                            ),
                            'ó', 'o'
                        ),
                        'ú', 'u'
                    ),
                    'ñ', 'n'
                )
            )
        )
    """


def build_country_rates_for_mxn(
    raw_rates: Mapping[str, float] | None,
    *,
    identity_fallback: bool = False,
) -> dict[str, float]:
    if identity_fallback:
        return {country: 1.0 for country in COUNTRY_TO_RATE_SOURCE}

    rates = {"mexico": 1.0}
    for country, quote in COUNTRY_TO_RATE_SOURCE.items():
        if quote is None:
            continue
        raw_value = raw_rates.get(quote) if raw_rates else None
        if raw_value:
            rates[country] = 1 / float(raw_value)
    return rates


def build_country_rates_derived_table(
    country_rates: Mapping[str, float],
) -> tuple[str, dict[str, float]]:
    rows: list[str] = []
    params: dict[str, float] = {}
    normalized_rates = {
        normalize_country_key(country): float(rate)
        for country, rate in country_rates.items()
        if normalize_country_key(country)
    }

    if not normalized_rates:
        normalized_rates = {"__missing__": FALLBACK_EXCHANGE_RATE}

    for index, (country, rate) in enumerate(normalized_rates.items()):
        country_param = f"fx_country_{index}"
        rate_param = f"fx_rate_{index}"
        rows.append(f"SELECT :{country_param} AS country_key, :{rate_param} AS rate_to_base")
        params[country_param] = country
        params[rate_param] = rate

    return " UNION ALL ".join(rows), params
