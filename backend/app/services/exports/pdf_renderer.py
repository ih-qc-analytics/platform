"""Server-side PDF rendering via Jinja2 + WeasyPrint.

Each public ``render_*`` function accepts an already-built PDF payload (from the
existing ``build_*_pdf_payload`` helpers), renders it to HTML, converts it to PDF
bytes on a thread-pool executor (so the event loop stays unblocked), and returns
a ``StreamingResponse`` ready to be returned directly from a FastAPI route.
"""
from __future__ import annotations

import asyncio
import base64
import unicodedata
import re
from io import BytesIO
from pathlib import Path

import weasyprint
from fastapi.responses import StreamingResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.schemas.pdf import (
    AsesorDetailPDFPayload,
    DetalleAsesorPDFPayload,
    PorAsesorPDFPayload,
    PorPaisDetailPDFPayload,
    PorPaisPDFPayload,
    VentasTotalesPDFPayload,
)

_TEMPLATES_DIR = Path(__file__).parent / "templates" / "pdf"
_LOGO_PATH = Path(__file__).parent / "assets" / "logo.png"


# ── Jinja2 custom filter ──────────────────────────────────────────────────────

def _compact_currency(value: float) -> str:
    """Format a number as compact currency: $1.5k for ≥1000, $500 otherwise."""
    abs_val = abs(value)
    if abs_val >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs_val >= 1_000:
        formatted = f"{value / 1_000:.1f}".rstrip("0").rstrip(".")
        return f"${formatted}k"
    return f"${value:,.0f}"


# ── Module-level setup ────────────────────────────────────────────────────────

def _load_logo_b64() -> str:
    if not _LOGO_PATH.exists():
        return ""
    data = _LOGO_PATH.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{b64}"


_LOGO_B64: str = _load_logo_b64()

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)
_env.filters["compact_currency"] = _compact_currency


# ── Internal helpers ──────────────────────────────────────────────────────────

def _render_html(template_name: str, **context) -> str:
    tpl = _env.get_template(template_name)
    return tpl.render(logo_b64=_LOGO_B64, **context)


def _html_to_pdf(html: str) -> bytes:
    buf = BytesIO()
    weasyprint.HTML(string=html).write_pdf(buf)
    return buf.getvalue()


async def _html_to_pdf_async(html: str) -> bytes:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _html_to_pdf, html)


def _pdf_response(pdf_bytes: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _slugify(text: str, fallback: str) -> str:
    """Normalise accented text to an ASCII filename slug."""
    text = unicodedata.normalize("NFD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or fallback


# ── Public render functions ───────────────────────────────────────────────────

async def render_ventas_totales_pdf(payload: VentasTotalesPDFPayload) -> StreamingResponse:
    html = _render_html(
        "reports/ventas_totales.html",
        payload=payload,
        generated_at=payload.header.generated_at,
    )
    return _pdf_response(await _html_to_pdf_async(html), "ventas-totales.pdf")


async def render_por_asesor_pdf(payload: PorAsesorPDFPayload) -> StreamingResponse:
    html = _render_html(
        "reports/por_asesor.html",
        payload=payload,
        generated_at=payload.header.generated_at,
    )
    return _pdf_response(await _html_to_pdf_async(html), "por-asesor.pdf")


async def render_asesor_detail_pdf(payload: AsesorDetailPDFPayload) -> StreamingResponse:
    slug = _slugify(payload.header.title, "detalle-asesor")
    html = _render_html(
        "reports/asesor_detail.html",
        payload=payload,
        generated_at=payload.header.generated_at,
    )
    return _pdf_response(await _html_to_pdf_async(html), f"detalle-asesor-{slug}.pdf")


async def render_detalle_asesor_pdf(payload: DetalleAsesorPDFPayload) -> StreamingResponse:
    html = _render_html(
        "reports/detalle_asesor.html",
        payload=payload,
        generated_at=payload.header.generated_at,
    )
    return _pdf_response(await _html_to_pdf_async(html), "detalle-asesor.pdf")


async def render_por_pais_pdf(payload: PorPaisPDFPayload) -> StreamingResponse:
    html = _render_html(
        "reports/por_pais.html",
        payload=payload,
        generated_at=payload.header.generated_at,
    )
    return _pdf_response(await _html_to_pdf_async(html), "por-pais.pdf")


async def render_por_pais_detail_pdf(payload: PorPaisDetailPDFPayload) -> StreamingResponse:
    slug = _slugify(payload.header.title, "por-pais-detail")
    html = _render_html(
        "reports/por_pais_detail.html",
        payload=payload,
        generated_at=payload.header.generated_at,
    )
    return _pdf_response(await _html_to_pdf_async(html), f"detalle-por-pais-{slug}.pdf")
