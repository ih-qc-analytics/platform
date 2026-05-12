from functools import lru_cache

from app.enums import BroadExamCategory, SpecificExamCategory

EXAM_CATEGORY_ORDER = [category.value for category in BroadExamCategory]

EXAM_NAME_ORDER = [
    SpecificExamCategory.PRE_A1_STARTERS.value,
    SpecificExamCategory.A1_MOVERS.value,
    SpecificExamCategory.A2_FLYERS.value,
    SpecificExamCategory.A2_KEY.value,
    SpecificExamCategory.A2_KEY_FOR_SCHOOLS.value,
    SpecificExamCategory.B1_PRELIMINARY.value,
    SpecificExamCategory.B1_PRELIMINARY_FOR_SCHOOLS.value,
    SpecificExamCategory.B2_FIRST.value,
    SpecificExamCategory.B2_FIRST_FOR_SCHOOLS.value,
    SpecificExamCategory.C1_ADVANCED.value,
    SpecificExamCategory.C2_PROFICIENCY.value,
    SpecificExamCategory.LINGUASKILL.value,
    SpecificExamCategory.TKT.value,
    SpecificExamCategory.DELTA.value,
    SpecificExamCategory.CELTA.value,
    SpecificExamCategory.IELTS.value,
    SpecificExamCategory.MET.value,
    SpecificExamCategory.MET_GO.value,
    SpecificExamCategory.TEA.value,
]

RAW_SPECIFIC_EXAM_MAP = {
    "Pre-A1 Starters Digital": SpecificExamCategory.PRE_A1_STARTERS,
    "Pre-A1 Starters Papel ": SpecificExamCategory.PRE_A1_STARTERS,
    "A1 Movers Digital": SpecificExamCategory.A1_MOVERS,
    "A1 Movers Papel ": SpecificExamCategory.A1_MOVERS,
    "A2 Flyers Digital": SpecificExamCategory.A2_FLYERS,
    "A2 Flyers Papel": SpecificExamCategory.A2_FLYERS,
    "A2 Key Digital": SpecificExamCategory.A2_KEY,
    "Key English Test 2020": SpecificExamCategory.A2_KEY,
    "A2 Key for Schools Digital": SpecificExamCategory.A2_KEY_FOR_SCHOOLS,
    "A2 Key for Schools Pepel": SpecificExamCategory.A2_KEY_FOR_SCHOOLS,
    "B1 Preliminary Digital": SpecificExamCategory.B1_PRELIMINARY,
    "Preliminary English Test 2020": SpecificExamCategory.B1_PRELIMINARY,
    "B1 Preliminary for Schools Digital": SpecificExamCategory.B1_PRELIMINARY_FOR_SCHOOLS,
    "B1 Preliminary for Schools Papel": SpecificExamCategory.B1_PRELIMINARY_FOR_SCHOOLS,
    "B2 First Digital": SpecificExamCategory.B2_FIRST,
    "B2 First Papel": SpecificExamCategory.B2_FIRST,
    "B2 First for Schools  Digital": SpecificExamCategory.B2_FIRST_FOR_SCHOOLS,
    "B2 First for Schools Papel": SpecificExamCategory.B2_FIRST_FOR_SCHOOLS,
    "C1 Advanced  Papel": SpecificExamCategory.C1_ADVANCED,
    "C1 Advanced Digital": SpecificExamCategory.C1_ADVANCED,
    "C2 Proficiency Digital": SpecificExamCategory.C2_PROFICIENCY,
    "C2 Proficiency Papel": SpecificExamCategory.C2_PROFICIENCY,
    "Linguaskill 1 Skills (Writing)": SpecificExamCategory.LINGUASKILL,
    "Linguaskill 2 Skill Bundle (Reading and Listening)": SpecificExamCategory.LINGUASKILL,
    "TKT Content and Language Integrated Learning Papel": SpecificExamCategory.TKT,
    "TKT Module 1 Papel": SpecificExamCategory.TKT,
    "TKT Module 2 Papel": SpecificExamCategory.TKT,
    "TKT Module 3 Papel": SpecificExamCategory.TKT,
    "TKT Young Learners Papel": SpecificExamCategory.TKT,
    "Delta Module One": SpecificExamCategory.DELTA,
    "Delta Module Two": SpecificExamCategory.DELTA,
    "Delta Module Three Option 1": SpecificExamCategory.DELTA,
    "Delta Module Three Option 2": SpecificExamCategory.DELTA,
    "IELTS ACADEMIC ": SpecificExamCategory.IELTS,
    "IELTS GENERAL TRAINING": SpecificExamCategory.IELTS,
    "IELTS ON COMPUTER": SpecificExamCategory.IELTS,
    "MET Digital": SpecificExamCategory.MET,
    "MET Digital Retake": SpecificExamCategory.MET,
    "MET Go Digital": SpecificExamCategory.MET_GO,
    "MET Go! 4 Skills Papel": SpecificExamCategory.MET_GO,
    "CAMBRIDGE PLACEMENT TEST (CEPT)": SpecificExamCategory.OTHER,
    "CAMBRIDGE YOUNG LEARNERS PLACEMENT TEST (YLPT)": SpecificExamCategory.OTHER,
    "CEST GENERAL  1 SKILL (WRITING)": SpecificExamCategory.OTHER,
    "CEST GENERAL 2 SKILL BUNDLE (LISTENING & READING)": SpecificExamCategory.OTHER,
    "CEST GENERAL 4 SKILL BUNDLE": SpecificExamCategory.OTHER,
    "GET 2 SKILLS": SpecificExamCategory.OTHER,
    "IH LEVEL TEST": SpecificExamCategory.OTHER,
    # Compatibility aliases still used by tests / callers.
    "KET": SpecificExamCategory.A2_KEY,
    "PET": SpecificExamCategory.B1_PRELIMINARY,
    "FCE": SpecificExamCategory.B2_FIRST,
    "IELTS Academic": SpecificExamCategory.IELTS,
    "Placement Tests": SpecificExamCategory.OTHER,
    "MET Go!": SpecificExamCategory.MET_GO,
    "TEA": SpecificExamCategory.TEA,
}

SPECIFIC_TO_BROAD = {
    SpecificExamCategory.PRE_A1_STARTERS: BroadExamCategory.CAMBRIDGE_MAIN,
    SpecificExamCategory.A1_MOVERS: BroadExamCategory.CAMBRIDGE_MAIN,
    SpecificExamCategory.A2_FLYERS: BroadExamCategory.CAMBRIDGE_MAIN,
    SpecificExamCategory.A2_KEY: BroadExamCategory.CAMBRIDGE_MAIN,
    SpecificExamCategory.A2_KEY_FOR_SCHOOLS: BroadExamCategory.CAMBRIDGE_MAIN,
    SpecificExamCategory.B1_PRELIMINARY: BroadExamCategory.CAMBRIDGE_MAIN,
    SpecificExamCategory.B1_PRELIMINARY_FOR_SCHOOLS: BroadExamCategory.CAMBRIDGE_MAIN,
    SpecificExamCategory.B2_FIRST: BroadExamCategory.CAMBRIDGE_MAIN,
    SpecificExamCategory.B2_FIRST_FOR_SCHOOLS: BroadExamCategory.CAMBRIDGE_MAIN,
    SpecificExamCategory.C1_ADVANCED: BroadExamCategory.CAMBRIDGE_MAIN,
    SpecificExamCategory.C2_PROFICIENCY: BroadExamCategory.CAMBRIDGE_MAIN,
    SpecificExamCategory.LINGUASKILL: BroadExamCategory.CAMBRIDGE_TEACHING,
    SpecificExamCategory.TKT: BroadExamCategory.CAMBRIDGE_TEACHING,
    SpecificExamCategory.DELTA: BroadExamCategory.CAMBRIDGE_TEACHING,
    SpecificExamCategory.CELTA: BroadExamCategory.CAMBRIDGE_TEACHING,
    SpecificExamCategory.IELTS: BroadExamCategory.IELTS,
    SpecificExamCategory.MET: BroadExamCategory.MICHIGAN_MET,
    SpecificExamCategory.MET_GO: BroadExamCategory.MICHIGAN_MET,
    SpecificExamCategory.TEA: BroadExamCategory.TEA,
    SpecificExamCategory.OTHER: BroadExamCategory.OTHER,
}


def _specific_from_contains(label: str) -> SpecificExamCategory:
    if "MET Go" in label or "MET Go!" in label:
        return SpecificExamCategory.MET_GO
    if "MET" in label:
        return SpecificExamCategory.MET
    if "IELTS" in label:
        return SpecificExamCategory.IELTS
    if "Linguaskill" in label:
        return SpecificExamCategory.LINGUASKILL
    if "TKT" in label:
        return SpecificExamCategory.TKT
    if "Delta" in label:
        return SpecificExamCategory.DELTA
    if "CELTA" in label:
        return SpecificExamCategory.CELTA
    if "TEA" in label:
        return SpecificExamCategory.TEA
    if "A2 Key for Schools" in label or "Key for Schools" in label:
        return SpecificExamCategory.A2_KEY_FOR_SCHOOLS
    if "A2 Key" in label or "Key English Test" in label:
        return SpecificExamCategory.A2_KEY
    if "B1 Preliminary for Schools" in label or "Preliminary for Schools" in label:
        return SpecificExamCategory.B1_PRELIMINARY_FOR_SCHOOLS
    if "B1 Preliminary" in label or "Preliminary English Test" in label:
        return SpecificExamCategory.B1_PRELIMINARY
    if "B2 First for Schools" in label or "First for Schools" in label:
        return SpecificExamCategory.B2_FIRST_FOR_SCHOOLS
    if "B2 First" in label or "First Certificate" in label:
        return SpecificExamCategory.B2_FIRST
    if "Pre-A1 Starters" in label or "Starters" in label:
        return SpecificExamCategory.PRE_A1_STARTERS
    if "A1 Movers" in label or "Movers" in label:
        return SpecificExamCategory.A1_MOVERS
    if "A2 Flyers" in label or "Flyers" in label:
        return SpecificExamCategory.A2_FLYERS
    if "C1 Advanced" in label:
        return SpecificExamCategory.C1_ADVANCED
    if "C2 Proficiency" in label:
        return SpecificExamCategory.C2_PROFICIENCY
    if (
        "CEPT" in label
        or "YLPT" in label
        or "IH LEVEL TEST" in label
        or "CEST" in label
        or "GET 2 SKILLS" in label
    ):
        return SpecificExamCategory.OTHER
    return SpecificExamCategory.OTHER


@lru_cache(maxsize=256)
def _specific_exam_enum(label: str | None) -> SpecificExamCategory:
    if not label:
        return SpecificExamCategory.OTHER
    if label in RAW_SPECIFIC_EXAM_MAP:
        return RAW_SPECIFIC_EXAM_MAP[label]
    stripped = label.strip()
    if stripped in RAW_SPECIFIC_EXAM_MAP:
        return RAW_SPECIFIC_EXAM_MAP[stripped]
    return _specific_from_contains(stripped)


@lru_cache(maxsize=256)
def canonical_exam_name(label: str | None) -> str:
    return _specific_exam_enum(label).value


@lru_cache(maxsize=256)
def canonical_exam_category(label: str | None) -> str:
    return SPECIFIC_TO_BROAD[_specific_exam_enum(label)].value
