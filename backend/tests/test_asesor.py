from types import SimpleNamespace

from app.services.por_asesor.product_grouping import (
    canonical_exam_category,
    canonical_exam_name,
)
from app.services.por_pais.por_pais import build_detail_counts, build_summary_rows


def test_canonical_exam_category_and_name_cover_aliases_and_none_labels():
    assert canonical_exam_category("FCE") == "Cambridge English (Main Suite)"
    assert canonical_exam_category("TKT Module 1 Papel") == "Cambridge Teaching & Skills"
    assert canonical_exam_category("IELTS Academic") == "IELTS"
    assert canonical_exam_category("MET Go!") == "Michigan (MET)"
    assert canonical_exam_category("TEA") == "TEA (Test of English for Aviation)"
    assert canonical_exam_category(None) == "Placement & Otros"

    assert canonical_exam_name("KET") == "A2 Key"
    assert canonical_exam_name("PET") == "B1 Preliminary"
    assert canonical_exam_name("FCE") == "B2 First"
    assert canonical_exam_name("IELTS Academic") == "IELTS"
    assert canonical_exam_name("Placement Tests") == "Other"
    assert canonical_exam_name(None) == "Other"


def test_canonical_exam_category_and_name_collapse_known_exam_families():
    assert canonical_exam_name("A1 Movers Papel ") == "A1 Movers"
    assert canonical_exam_name("A2 Key for Schools Pepel") == "A2 Key for Schools"
    assert canonical_exam_name("B2 First for Schools  Digital") == "B2 First for Schools"
    assert canonical_exam_name("Delta Module Three Option 1") == "Delta"
    assert canonical_exam_name("MET Digital Retake") == "MET"
    assert canonical_exam_name("MET Go Digital") == "MET Go!"
    assert canonical_exam_name("CAMBRIDGE PLACEMENT TEST (CEPT)") == "Other"
    assert canonical_exam_category("Linguaskill 1 Skills (Writing)") == "Cambridge Teaching & Skills"


def test_por_pais_summary_and_detail_helpers_treat_missing_exam_labels_as_other():
    summary_rows = build_summary_rows(
        [SimpleNamespace(country="mexico", total_schools=1)],
        [SimpleNamespace(country="mexico", exam_name=None, exam_count=3)],
    )
    assert [row.model_dump() for row in summary_rows] == [
        {
            "country": "mexico",
            "total_schools": 1,
            "cambridge": 0,
            "ielts": 0,
            "michigan": 0,
            "tea": 0,
            "other": 3,
        }
    ]

    detail_counts = build_detail_counts(
        [SimpleNamespace(country="mexico", exam_name=None, exam_count=3)],
        "mexico",
    )
    assert detail_counts["Other"] == 3
