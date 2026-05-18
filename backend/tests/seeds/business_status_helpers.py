from datetime import datetime

from sqlalchemy import text

from app.database import SessionLocal
from app.enums import PaymentStatus

_BASE_ID = 9000
_counter = 0


def _next_id() -> int:
    global _counter
    _counter += 1
    return _BASE_ID + _counter


async def seed_lead_with_payment(
    *,
    year_current: bool,
    year_prior: bool,
    cancelled_current: bool = False,
) -> int:
    lead_id = _next_id()
    seller_lead_id = _next_id()
    current_year = datetime.now().year

    async with SessionLocal() as session:
        async with session.begin():
            await session.execute(text("""
                INSERT INTO `lead` (id, name, site, zoneId, campaign)
                VALUES (:id, :name, :site, :zone_id, :campaign)
            """), {
                "id": lead_id,
                "name": f"Business Status Lead {lead_id}",
                "site": "mexico",
                "zone_id": 1,
                "campaign": "business-status-tests",
            })
            await session.execute(text("""
                INSERT INTO seller_lead (id, sellerId, leadId, businessStatus)
                VALUES (:id, :seller_id, :lead_id, :business_status)
            """), {
                "id": seller_lead_id,
                "seller_id": 1,
                "lead_id": lead_id,
                "business_status": "Carga de lead",
            })

            if year_prior:
                await _insert_cart_with_payment(
                    session,
                    seller_lead_id=seller_lead_id,
                    created_at=f"{current_year - 1}-06-15 10:00:00",
                    payment_date=f"{current_year - 1}-06-16",
                    status=PaymentStatus.APROBADO.value,
                )

            if year_current:
                await _insert_cart_with_payment(
                    session,
                    seller_lead_id=seller_lead_id,
                    created_at=f"{current_year}-06-15 10:00:00",
                    payment_date=f"{current_year}-06-16",
                    status=PaymentStatus.APROBADO.value,
                )
            elif cancelled_current:
                await _insert_cart_with_payment(
                    session,
                    seller_lead_id=seller_lead_id,
                    created_at=f"{current_year}-06-15 10:00:00",
                    payment_date=f"{current_year}-06-16",
                    status=PaymentStatus.CANCELADO.value,
                )

    return lead_id


async def _insert_cart_with_payment(
    session,
    *,
    seller_lead_id: int,
    created_at: str,
    payment_date: str,
    status: str,
) -> None:
    cart_id = _next_id()
    payment_id = _next_id()

    await session.execute(text("""
        INSERT INTO cart (
            id, sellerLeadId, total, cost, createdAt, updatedAt, deletedAt,
            billingStatus, bookCommission, examCommission
        ) VALUES (
            :id, :seller_lead_id, :total, :cost, :created_at, :updated_at, NULL,
            :billing_status, :book_commission, :exam_commission
        )
    """), {
        "id": cart_id,
        "seller_lead_id": seller_lead_id,
        "total": 1000,
        "cost": 500,
        "created_at": created_at,
        "updated_at": created_at,
        "billing_status": "Aprobado",
        "book_commission": 0,
        "exam_commission": 0,
    })
    await session.execute(text("""
        INSERT INTO payment (
            id, quantity, status, createdAt, updatedAt, cartId, `use`, comments,
            billingStatus, studentId, paymentDate
        ) VALUES (
            :id, :quantity, :status, :created_at, :updated_at, :cart_id, :use_value, :comments,
            :billing_status, :student_id, :payment_date
        )
    """), {
        "id": payment_id,
        "quantity": 1000,
        "status": status,
        "created_at": created_at,
        "updated_at": created_at,
        "cart_id": cart_id,
        "use_value": "",
        "comments": "",
        "billing_status": "",
        "student_id": 0,
        "payment_date": payment_date,
    })
