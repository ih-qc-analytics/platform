import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from app.auth import verify_token
from app.main import app
from app.schemas.pdf import VentasTotalesPDFPayload
from app.schemas.reports import (
    ComparisonMeta,
    GeoPoint,
    MetricDelta,
    ProductMix,
    ReportFilters,
    TotalSalesBase,
    TotalSalesComparison,
    TotalSalesResponse,
    TrendPoint,
)
from app.enums import ComparisonMode
from app.services.exports.pdf_helpers import (
    filters_summary,
    format_growth,
    scale_series,
)
from app.services.total_sales.total_sales import build_ventas_totales_pdf_payload
from app.services.utils.currency_rates import (
    build_country_rates_for_mxn,
    build_country_rates_derived_table,
)


_MOCK_BASE = TotalSalesBase(
    total_clients=3,
    total_exams=6,
    exam_revenue=6000.0,
    total_books=3,
    book_revenue=900.0,
    total_courses=1,
    course_revenue=500.0,
    total_otros=2,
    otros_revenue=400.0,
    total_revenue=7800.0,
    expected_revenue=7300.0,
    expected_cost=3200.0,
    uncategorized_revenue=800.0,
    unknown_site_revenue=0.0,
    unknown_site_expected_revenue=0.0,
    profit_margin=52.7,
    trend_points=[
        TrendPoint(month="2025-01", revenue=2300.0),
        TrendPoint(month="2025-02", revenue=4600.0),
    ],
    geo_points=[
        GeoPoint(dimension="México", revenue=3900.0),
        GeoPoint(dimension="Colombia", revenue=1950.0),
    ],
    product_mix=ProductMix(exams_pct=76.9, books_pct=11.5, courses_pct=6.4, unknown_pct=10.3),
)

MOCK_RESPONSE = TotalSalesResponse(
    current=_MOCK_BASE,
    comparison=TotalSalesComparison(
        meta=ComparisonMeta(
            mode=ComparisonMode.PREVIOUS_YEAR,
            date_from="2024-01-01",
            date_to="2024-03-31",
        ),
        data=_MOCK_BASE.model_copy(update={"total_revenue": 7400.0}),
        deltas={
            "total_revenue": MetricDelta(comparison_value=7400.0, pct_change=5.4054054054),
        },
    ),
)


@pytest.mark.asyncio(loop_scope="session")
async def test_build_ventas_totales_pdf_payload_formats_kpis_and_scales_series():
    filters = ReportFilters(
        date_from="2025-01-01",
        date_to="2025-03-31",
        countries=["México"],
        zones=["IH Mexico"],
    )

    with patch(
        "app.services.total_sales.total_sales.get_total_sales_data",
        new=AsyncMock(return_value=MOCK_RESPONSE),
    ):
        payload = await build_ventas_totales_pdf_payload(filters)

    assert payload.header.title == "Ventas Totales"
    assert payload.header.filters_summary == {
        "Desde": "01/01/2025",
        "Hasta": "31/03/2025",
        "País": "México",
        "Sede": "IH Mexico",
        "Vs.": "01/01/2024 – 31/03/2024",
    }
    # With comparison active, KPIs without explicit deltas show "N/A"
    assert [item.model_dump() for item in payload.kpis[:4]] == [
        {"label": "Total Clientes", "value": "3", "growth": "N/A", "growth_positive": None},
        {"label": "Total Exámenes", "value": "6", "growth": "N/A", "growth_positive": None},
        {
            "label": "Ingreso Exámenes",
            "value": "$6,000",
            "growth": "N/A",
            "growth_positive": None,
        },
        {"label": "Total Libros", "value": "3", "growth": "N/A", "growth_positive": None},
    ]
    assert any(item.label == "Otros" and item.value == "2" for item in payload.kpis)
    assert any(item.label == "Ingreso Otros" and item.value == "$400" for item in payload.kpis)
    assert any(item.label == "Ingreso Esperado" and item.value == "$7,300" for item in payload.kpis)
    assert any(item.label == "Sin Categorizar" and item.value == "$800" for item in payload.kpis)
    assert any(
        item.label == "Ingreso Total" and item.growth == "+5.4%" and item.growth_positive is True
        for item in payload.kpis
    )
    assert payload.trend_points[0].model_dump() == {
        "label": "Ene 2025",
        "value": 2300.0,
        "scaled": 0.5,
        "comparison_value": 2300.0,
        "comparison_scaled": 0.5,
    }
    assert payload.trend_points[1].scaled == 1.0
    assert payload.geo_points[0].label == "México"
    assert payload.geo_points[0].scaled == 1.0
    assert payload.geo_points[1].scaled == 0.5


@pytest.mark.asyncio(loop_scope="session")
async def test_build_ventas_totales_pdf_payload_handles_empty_dataset():
    empty_base = _MOCK_BASE.model_copy(
        update={
            "total_clients": 0,
            "total_exams": 0,
            "exam_revenue": 0.0,
            "total_books": 0,
            "book_revenue": 0.0,
            "total_courses": 0,
            "course_revenue": 0.0,
            "total_otros": 0,
            "otros_revenue": 0.0,
            "total_revenue": 0.0,
            "expected_revenue": 0.0,
            "expected_cost": 0.0,
            "uncategorized_revenue": 0.0,
            "unknown_site_revenue": 0.0,
            "unknown_site_expected_revenue": 0.0,
            "profit_margin": 0.0,
            "trend_points": [],
            "geo_points": [],
            "product_mix": None,
        }
    )
    empty_response = TotalSalesResponse(current=empty_base)

    with patch(
        "app.services.total_sales.total_sales.get_total_sales_data",
        new=AsyncMock(return_value=empty_response),
    ):
        payload = await build_ventas_totales_pdf_payload(ReportFilters())

    assert payload.trend_points == []
    assert payload.geo_points == []
    assert all(item.growth is None for item in payload.kpis if item.label == "Ingreso Total")
    assert not any(item.label == "Ingreso Año Anterior" for item in payload.kpis)


def test_filters_summary_includes_active_dates_and_geo_filters():
    summary = filters_summary(
        ReportFilters(
            date_from="2025-05-01",
            date_to="2025-05-31",
            countries=["México", "Perú"],
            states=["CDMX"],
            cities=["Mexico City"],
        )
    )
    assert summary == {
        "Desde": "01/05/2025",
        "Hasta": "31/05/2025",
        "País": "México, Perú",
        "Estado": "CDMX",
        "Ciudad": "Mexico City",
    }


def test_scale_series_and_growth_formatting_cover_edge_cases():
    assert scale_series([0.0, 0.0]) == [0.0, 0.0]
    assert scale_series([1.0, 2.0, 4.0]) == [0.25, 0.5, 1.0]
    assert format_growth(12.34) == ("+12.3%", True)
    assert format_growth(0.0) == ("+0.0%", True)
    assert format_growth(None) == (None, None)


def test_country_rate_helpers_build_country_mapping_and_derived_sql():
    rates = build_country_rates_for_mxn({"COP": 20.0, "PEN": 5.0})
    sql, params = build_country_rates_derived_table(rates)

    assert rates == {
        "mexico": 1.0,
        "colombia": 0.05,
        "peru": 0.2,
    }
    assert "country_key" in sql
    assert "rate_to_base" in sql
    assert params["fx_country_0"] == "mexico"


@pytest.mark.asyncio(loop_scope="session")
async def test_pdf_export_endpoint_returns_payload_shape():
    with patch(
        "app.routers.total_sales.build_ventas_totales_pdf_payload",
        new=AsyncMock(
            return_value=VentasTotalesPDFPayload(
                header={
                    "title": "Ventas Totales",
                    "subtitle": "Resumen general de ventas por período y región",
                    "generated_at": "11/05/2026 17:00",
                    "filters_summary": {"Desde": "01/01/2025"},
                },
                kpis=[{"label": "Total Clientes", "value": "3"}],
                trend_points=[{"label": "Ene 2025", "value": 100.0, "scaled": 1.0}],
                geo_points=[{"label": "México", "value": 100.0, "scaled": 1.0}],
            )
        ),
    ):
        app.dependency_overrides[verify_token] = lambda: {"sub": "test-user"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:  # type: ignore[arg-type]
            response = await client.post("/reports/ventas-totales/export/pdf", json={})
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
