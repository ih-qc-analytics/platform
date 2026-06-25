from enum import Enum


class BillingStatus(str, Enum):
    APROBADO = "Aprobado"
    APROBACION_COMERCIAL = "Aprobación comercial"
    APROBACION_FINANZAS = "Aprobacion finanzas"
    PROPUESTA = "Propuesta"
    RECHAZADO_FINANZAS = "Rechazado finanzas"
    RECHAZADO_COMERCIAL = "Rechazado comercial"
    UNCATEGORIZED = "UNCATEGORIZED"


class PaymentStatus(str, Enum):
    APROBADO = "Aprobado"
    CANCELADO = "Cancelado"
    PENDIENTE = "Pendiente"
    RECHAZADO = "Rechazado"
    UNCATEGORIZED = "UNCATEGORIZED"


class ETLJobName(str, Enum):
    STARTUP_BACKFILL = "startup_backfill"
    UPSERT = "upsert"
    DIMENSIONAL_REFRESH = "dimensional_refresh"


class ComparisonMode(str, Enum):
    PREVIOUS_YEAR = "PREVIOUS_YEAR"
    PREVIOUS_PERIOD = "PREVIOUS_PERIOD"
    CUSTOM = "CUSTOM"


class BaseCurrency(str, Enum):
    MXN = "MXN"
    USD = "USD"


class ProductType(str, Enum):
    EXAM = "exam"
    BOOK = "book"
    COURSE = "course"
    UNCATEGORIZED = "UNCATEGORIZED"


class BusinessStatus(str, Enum):
    GANADO = "ganado"
    PERDIDO = "perdido"
    MANTENIDO = "mantenido"
    UNCATEGORIZED = "UNCATEGORIZED"


class ExamCategory(str, Enum):
    CAMBRIDGE_ENGLISH = "Cambridge English (Main Suite)"
    CAMBRIDGE_TEACHING = "Cambridge Teaching & Skills"
    IELTS = "IELTS"
    MICHIGAN = "Michigan (MET)"
    TEA = "TEA (Test of English for Aviation)"
    PLACEMENT = "Placement & Otros"
    UNCATEGORIZED = "UNCATEGORIZED"


class BroadExamCategory(str, Enum):
    CAMBRIDGE_MAIN = "Cambridge English (Main Suite)"
    CAMBRIDGE_TEACHING = "Cambridge Teaching & Skills"
    IELTS = "IELTS"
    MICHIGAN_MET = "Michigan (MET)"
    TEA = "TEA (Test of English for Aviation)"
    OTHER = "Placement & Otros"


class SpecificExamCategory(str, Enum):
    PRE_A1_STARTERS = "Pre-A1 Starters"
    A1_MOVERS = "A1 Movers"
    A2_FLYERS = "A2 Flyers"
    A2_KEY = "A2 Key"
    A2_KEY_FOR_SCHOOLS = "A2 Key for Schools"
    B1_PRELIMINARY = "B1 Preliminary"
    B1_PRELIMINARY_FOR_SCHOOLS = "B1 Preliminary for Schools"
    B2_FIRST = "B2 First"
    B2_FIRST_FOR_SCHOOLS = "B2 First for Schools"
    C1_ADVANCED = "C1 Advanced"
    C2_PROFICIENCY = "C2 Proficiency"
    LINGUASKILL = "Linguaskill"
    TKT = "TKT"
    DELTA = "Delta"
    CELTA = "CELTA"
    IELTS = "IELTS"
    MET = "MET"
    MET_GO = "MET Go!"
    TEA = "TEA"
    OTHER = "Other"
