from enum import Enum


class BillingStatus(str, Enum):
    APROBADO = "Aprobado"
    APROBACION_COMERCIAL = "Aprobación comercial"
    APROBACION_FINANZAS = "Aprobacion finanzas"
    PROPUESTA = "Propuesta"
    RECHAZADO_FINANZAS = "Rechazado finanzas"
    RECHAZADO_COMERCIAL = "Rechazado comercial"


class PaymentStatus(str, Enum):
    APROBADO = "Aprobado"
    CANCELADO = "Cancelado"
    PENDIENTE = "Pendiente"
    RECHAZADO = "Rechazado"


class ProductType(str, Enum):
    EXAM = "exam"
    BOOK = "book"
    COURSE = "course"
