import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.schemas.pdf import (
    AsesorDetailPDFPayload,
    DetalleAsesorPDFPayload,
    PorAsesorPDFPayload,
    PorPaisDetailPDFPayload,
    PorPaisPDFPayload,
)
from app.schemas.reports import (
    AsesorFilters,
    AsesorDetail,
    AsesorReportResponse,
    AsesorRow,
    BusinessStatusDetail,
    DetalleFilters,
    DetalleReportResponse,
    DetalleRow,
    ExamBrandDetail,
    PorPaisFilters,
    PorPaisDetailResponse,
    PorPaisReportResponse,
    PorPaisStatusRow,
    PorPaisSummaryRow,
)
from app.services.por_asesor.product_grouping import EXAM_CATEGORY_ORDER
from app.services.por_asesor.por_asesor import build_asesor_detail_pdf_payload
from app.services.detalle_asesor.detalle_asesor import build_detalle_asesor_pdf_payload
from app.services.por_asesor.por_asesor import build_por_asesor_pdf_payload
from app.services.por_pais.por_pais import (
    build_por_pais_detail_pdf_payload,
    build_por_pais_pdf_payload,
)


@pytest.mark.asyncio(loop_scope="session")
async def test_build_por_asesor_pdf_payload_formats_summary():
    report = AsesorReportResponse(
        rows=[
            AsesorRow(
                seller_id=1,
                seller_name="Ana Garcia",
                exam_breakdown={
                    "Cambridge English (Main Suite)": 10,
                    "Cambridge Teaching & Skills": 2,
                    "IELTS": 1,
                    "Michigan (MET)": 3,
                    "TEA (Test of English for Aviation)": 1,
                    "Placement & Otros": 4,
                },
                ganados=2,
                perdidos=1,
                mantenidos=3,
                total_revenue=19200.0,
                uncategorized_revenue=1200.0,
            )
        ],
        year=2025,
        next_cursor=None,
        has_more=False,
    )
    with patch(
        "app.services.por_asesor.por_asesor.getAllAsesorReportRows",
        new=AsyncMock(return_value=report),
    ):
        payload = await build_por_asesor_pdf_payload(AsesorFilters(year=2025))

    assert payload.kpis[0].value == "1"
    assert payload.kpis[-1].value == "$19,200"
    assert payload.table.rows[0].cells[1:5] == ["12", "1", "3", "5"]


@pytest.mark.asyncio(loop_scope="session")
async def test_build_detalle_asesor_pdf_payload_uses_landscape_and_split_tables():
    report = DetalleReportResponse(
        rows=[
            DetalleRow(
                id=4,
                seller_name="Ana Garcia",
                school_name="Colegio Uno",
                exam_date="2025-01-15",
                exam_counts={"A2 Key": 2, "Other": 1},
                total=3,
            )
        ],
        next_cursor=None,
        has_more=False,
    )
    with patch(
        "app.services.detalle_asesor.detalle_asesor.getAllDetalleRows",
        new=AsyncMock(return_value=report),
    ):
        payload = await build_detalle_asesor_pdf_payload(
            DetalleFilters(date_from="2025-01-01", date_to="2025-12-31")
        )

    assert payload.orientation == "landscape"
    assert payload.table_identity.rows[0].cells == ["Ana Garcia", "Colegio Uno", "15/01/2025", "3"]
    assert payload.table_exams.rows[0].cells[0] == "Ana Garcia"
    assert payload.table_exams.rows[0].cells[-1] == "3"


@pytest.mark.asyncio(loop_scope="session")
async def test_build_por_pais_pdf_payload_contains_summary_and_status_tables():
    report = PorPaisReportResponse(
        summary_rows=[
            PorPaisSummaryRow(
                country="México",
                total_schools=3,
                total_revenue=12000.0,
                uncategorized_revenue=800.0,
                cambridge=10,
                ielts=2,
                michigan=1,
                tea=1,
                other=4,
            )
        ],
        status_rows=[
            PorPaisStatusRow(
                country="México",
                schools_ganados=1,
                schools_perdidos=0,
                schools_mantenidos=2,
                exams_ganados=3,
                exams_perdidos=0,
                exams_mantenidos=7,
            )
        ],
    )
    with patch(
        "app.services.por_pais.por_pais.getPorPaisReport",
        new=AsyncMock(return_value=report),
    ):
        payload = await build_por_pais_pdf_payload(
            PorPaisFilters(date_from="2025-01-01", date_to="2025-12-31")
        )

    assert payload.kpis[1].value == "3"
    assert payload.summary_table.rows[0].cells[0] == "México"
    assert payload.status_table.rows[0].cells[4] == "3"


@pytest.mark.asyncio(loop_scope="session")
async def test_build_por_pais_detail_pdf_payload_contains_country_breakdown():
    detail = PorPaisDetailResponse(
        country="México",
        exam_counts={
            "A2 Key": 4,
            "IELTS": 2,
            "MET": 1,
            "TEA": 3,
            "Other": 0,
        },
    )
    with patch(
        "app.services.por_pais.por_pais.getPorPaisDetail",
        new=AsyncMock(return_value=detail),
    ):
        payload = await build_por_pais_detail_pdf_payload(
            "México",
            PorPaisFilters(date_from="2025-01-01", date_to="2025-12-31"),
        )

    assert payload.header.title == "Detalle por País - México"
    assert payload.kpis[1].value == "10"
    assert payload.detail_table.rows[0].cells == ["A2 Key", "4"]
    assert all(row.cells[0] != "Other" for row in payload.detail_table.rows)


@pytest.mark.asyncio(loop_scope="session")
async def test_build_asesor_detail_pdf_payload_contains_drawer_sections():
    detail = AsesorDetail(
        seller_name="Ana Garcia",
        countries=["México"],
        zones=["IH Mexico"],
        states=["CDMX"],
        cities=["Mexico City"],
        total_schools=3,
        total_exams=22,
        total_revenue=19200.0,
        uncategorized_revenue=1200.0,
        exam_breakdown={
            category: ExamBrandDetail(
                exams=10 if index == 0 else 0,
                schools=3 if index == 0 else 0,
                revenue=18000.0 if index == 0 else 0.0,
            )
            for index, category in enumerate(EXAM_CATEGORY_ORDER)
        },
        ganados=BusinessStatusDetail(schools=2, exams=16, revenue=14600.0),
        perdidos=BusinessStatusDetail(schools=0, exams=0, revenue=0.0),
        mantenidos=BusinessStatusDetail(schools=1, exams=6, revenue=4600.0),
    )
    with patch(
        "app.services.por_asesor.por_asesor.getAsesorDetail",
        new=AsyncMock(return_value=detail),
    ):
        payload = await build_asesor_detail_pdf_payload(1, AsesorFilters(year=2025))

    assert payload.header.title == "Ana Garcia"
    assert payload.kpis[0].value == "3"
    assert payload.geo_table.rows[0].cells == ["México", "IH Mexico", "CDMX", "Mexico City"]
    assert payload.categories_table.rows[0].cells[-1] == "$18,000"
    assert payload.status_table.rows[0].cells == ["Ganados", "2", "16", "$14,600"]


@pytest.mark.asyncio(loop_scope="session")
async def test_pdf_endpoints_return_payload_shapes():
    with (
        patch(
            "app.routers.por_asesor.build_por_asesor_pdf_payload",
            new=AsyncMock(
                return_value=PorAsesorPDFPayload(
                    header={
                        "title": "Por Asesor",
                        "subtitle": "x",
                        "generated_at": "12/05/2026 10:00",
                        "filters_summary": {},
                    },
                    kpis=[{"label": "Asesores", "value": "1"}],
                    table={"headers": ["A"], "rows": [{"cells": ["b"]}], "column_widths": [1]},
                )
            ),
        ),
        patch(
            "app.routers.por_asesor.build_asesor_detail_pdf_payload",
            new=AsyncMock(
                return_value=AsesorDetailPDFPayload(
                    header={
                        "title": "Ana Garcia",
                        "subtitle": "x",
                        "generated_at": "12/05/2026 10:00",
                        "filters_summary": {},
                    },
                    kpis=[{"label": "Total Colegios", "value": "3"}],
                    geo_table={"headers": ["A"], "rows": [{"cells": ["b"]}], "column_widths": [1]},
                    categories_table={
                        "headers": ["A"],
                        "rows": [{"cells": ["b"]}],
                        "column_widths": [1],
                    },
                    status_table={
                        "headers": ["A"],
                        "rows": [{"cells": ["b"]}],
                        "column_widths": [1],
                    },
                )
            ),
        ),
        patch(
            "app.routers.detalle_asesor.build_detalle_asesor_pdf_payload",
            new=AsyncMock(
                return_value=DetalleAsesorPDFPayload(
                    header={
                        "title": "Detalle",
                        "subtitle": "x",
                        "generated_at": "12/05/2026 10:00",
                        "filters_summary": {},
                    },
                    table_identity={
                        "headers": ["A"],
                        "rows": [{"cells": ["b"]}],
                        "column_widths": [1],
                    },
                    table_exams={
                        "headers": ["A"],
                        "rows": [{"cells": ["b"]}],
                        "column_widths": [1],
                    },
                    orientation="landscape",
                )
            ),
        ),
        patch(
            "app.routers.por_pais.build_por_pais_pdf_payload",
            new=AsyncMock(
                return_value=PorPaisPDFPayload(
                    header={
                        "title": "Por Pais",
                        "subtitle": "x",
                        "generated_at": "12/05/2026 10:00",
                        "filters_summary": {},
                    },
                    kpis=[{"label": "Países", "value": "1"}],
                    summary_table={
                        "headers": ["A"],
                        "rows": [{"cells": ["b"]}],
                        "column_widths": [1],
                    },
                    status_table={
                        "headers": ["A"],
                        "rows": [{"cells": ["b"]}],
                        "column_widths": [1],
                    },
                )
            ),
        ),
        patch(
            "app.routers.por_pais.build_por_pais_detail_pdf_payload",
            new=AsyncMock(
                return_value=PorPaisDetailPDFPayload(
                    header={
                        "title": "México",
                        "subtitle": "x",
                        "generated_at": "12/05/2026 10:00",
                        "filters_summary": {},
                    },
                    kpis=[{"label": "País", "value": "México"}],
                    detail_table={
                        "headers": ["A"],
                        "rows": [{"cells": ["b"]}],
                        "column_widths": [1],
                    },
                )
            ),
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:  # type: ignore[arg-type]
            por_asesor = await client.post("/reports/por-asesor/export/pdf", json={"year": 2025})
            asesor_detail = await client.post(
                "/reports/por-asesor/1/export/pdf", json={"year": 2025}
            )
            detalle = await client.post(
                "/reports/detalle-asesor/export/pdf",
                json={"date_from": "2025-01-01", "date_to": "2025-12-31"},
            )
            por_pais = await client.post(
                "/reports/por-pais/export/pdf",
                json={"date_from": "2025-01-01", "date_to": "2025-12-31"},
            )
            por_pais_detail = await client.post(
                "/reports/por-pais/mexico/export/pdf",
                json={"date_from": "2025-01-01", "date_to": "2025-12-31"},
            )

    assert por_asesor.status_code == 200
    assert asesor_detail.status_code == 200
    assert detalle.status_code == 200
    assert por_pais.status_code == 200
    assert por_pais_detail.status_code == 200
