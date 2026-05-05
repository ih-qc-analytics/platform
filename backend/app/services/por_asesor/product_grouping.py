import unicodedata
from collections.abc import Iterable, Sequence
from functools import lru_cache
import re

EXAM_CATEGORY_ORDER = [
    "Cambridge English (Main Suite)",
    "Cambridge Teaching & Skills",
    "IELTS",
    "Michigan (MET)",
    "TEA (Test of English for Aviation)",
    "Placement & Otros",
]

EXAM_CATEGORY_ALIASES = {
    "Cambridge English (Main Suite)": [
        "Pre-A1 Starters",
        "Starters",
        "A1 Movers",
        "Movers",
        "A2 Flyers",
        "Flyers",
        "A2 Key (KET)",
        "KET",
        "A2 Key for Schools (KETfs)",
        "KETfs",
        "B1 Preliminary (PET)",
        "PET",
        "B1 Preliminary for Schools (PETfs)",
        "PETfs",
        "B2 First (FCE)",
        "FCE",
        "B2 First for Schools (FCEfs)",
        "FCEfs",
        "C1 Advanced (CAE)",
        "CAE",
        "C2 Proficiency (CPE)",
        "CPE",
        "A1",
        "A2",
        "B1",
        "B2",
        "C1",
        "C2",
    ],
    "Cambridge Teaching & Skills": [
        "Linguaskill",
        "TKT",
        "Delta",
        "CELTA",
        "CAM",
        "Cambridge Teaching & Skills",
    ],
    "IELTS": [
        "IELTS Academic",
        "IELTS General Training",
        "IELTS on Computer",
        "IELTS",
    ],
    "Michigan (MET)": [
        "MET",
        "MET Go!",
        "Michigan",
        "Michigan (MET)",
    ],
    "TEA (Test of English for Aviation)": [
        "TEA",
        "Test of English for Aviation",
        "TEA (Test of English for Aviation)",
    ],
    "Placement & Otros": [
        "Placement Tests",
        "CEPT",
        "YLPT",
        "IH Level Test",
        "CEST General",
        "Placement",
        "Otros",
    ],
}

def normalize_exam_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_only).strip()


def exam_label_tokens(value: str) -> set[str]:
    normalized = normalize_exam_label(value).casefold()
    return set(re.findall(r"[a-z0-9]+", normalized))


def exam_labels_are_similar(left: str, right: str) -> bool:
    left_normalized = normalize_exam_label(left)
    right_normalized = normalize_exam_label(right)
    if left_normalized.casefold() == right_normalized.casefold():
        return True

    left_tokens = exam_label_tokens(left)
    right_tokens = exam_label_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    if left_tokens == right_tokens:
        return True
    if left_tokens.issubset(right_tokens) or right_tokens.issubset(left_tokens):
        return True

    intersection = left_tokens & right_tokens
    union = left_tokens | right_tokens
    return bool(intersection) and (len(intersection) / len(union) >= 0.6)


def choose_canonical_exam_label(labels: Iterable[str]) -> str:
    best_label = sorted(
        labels,
        key=lambda label: (
            -len(exam_label_tokens(label)),
            -len(normalize_exam_label(label)),
            normalize_exam_label(label).casefold(),
        ),
    )[0]
    return format_canonical_exam_label(best_label, labels)


def format_canonical_exam_label(best_label: str, labels: Iterable[str]) -> str:
    normalized = normalize_exam_label(best_label)
    return normalized.upper()


def build_exam_label_groups(labels: Sequence[str]) -> list[list[str]]:
    groups: list[list[str]] = []
    visited: set[str] = set()

    for label in labels:
        if label in visited:
            continue
        queue = [label]
        component: list[str] = []
        visited.add(label)

        while queue:
            current = queue.pop()
            component.append(current)
            for candidate in labels:
                if candidate in visited:
                    continue
                if exam_labels_are_similar(current, candidate):
                    visited.add(candidate)
                    queue.append(candidate)

        groups.append(component)

    return groups


def label_matches_alias(label: str, alias: str) -> bool:
    label_normalized = normalize_exam_label(label).casefold()
    alias_normalized = normalize_exam_label(alias).casefold()
    if label_normalized == alias_normalized:
        return True

    label_tokens = exam_label_tokens(label)
    alias_tokens = exam_label_tokens(alias)
    if not label_tokens or not alias_tokens:
        return False
    if label_tokens == alias_tokens:
        return True
    if label_tokens.issubset(alias_tokens) or alias_tokens.issubset(label_tokens):
        return True

    intersection = label_tokens & alias_tokens
    union = label_tokens | alias_tokens
    return bool(intersection) and (len(intersection) / len(union) >= 0.5)


@lru_cache(maxsize=256)
def canonical_exam_category(label: str) -> str:
    for category in EXAM_CATEGORY_ORDER:
        aliases = EXAM_CATEGORY_ALIASES.get(category, [])
        if any(label_matches_alias(label, alias) for alias in aliases):
            return category
    return "Placement & Otros"


# ─────────────────────────────────────────────
# Canonical exam name mapping (Report 3)
# Maps any raw exam_cat.name to one of 19 specific column names, or "Other".
#
# Ordering constraints (label_matches_alias uses a subset rule, so a shorter
# alias whose tokens are all present in a longer label will match):
#
#   • Each base exam (A2 Key, B1 Preliminary, B2 First) is checked BEFORE
#     its "for Schools" sibling.  The base aliases intentionally include a
#     distinguishing extra token (e.g. "A2 Key (KET)" has "ket") so that a
#     "for Schools" label with 0.4 Jaccard similarity does not match them.
#     The bare descriptive form ("A2 Key", "B1 Preliminary", "B2 First") is
#     NOT listed as an alias — the parenthesised alias catches it via the
#     subset rule without leaking to the for-Schools variant.
#
#   • MET is checked BEFORE MET Go!.  "MET" alone is not listed as an alias;
#     "Michigan (MET)" catches it via subset without leaking to "MET Go!".
# ─────────────────────────────────────────────

EXAM_NAME_ORDER = [
    "Pre-A1 Starters",
    "A1 Movers",
    "A2 Flyers",
    "A2 Key",               # before A2 Key for Schools
    "A2 Key for Schools",
    "B1 Preliminary",       # before B1 Preliminary for Schools
    "B1 Preliminary for Schools",
    "B2 First",             # before B2 First for Schools
    "B2 First for Schools",
    "C1 Advanced",
    "C2 Proficiency",
    "Linguaskill",
    "TKT",
    "Delta",
    "CELTA",
    "IELTS",
    "MET",                  # before MET Go!
    "MET Go!",
    "TEA",
]

EXAM_NAME_ALIASES: dict[str, list[str]] = {
    "Pre-A1 Starters": [
        "Pre-A1 Starters",
        "Starters",
        "YLE Starters",
        "Pre A1 Starters",
        "Pre-A1",
    ],
    "A1 Movers": [
        "A1 Movers",
        "Movers",
        "YLE Movers",
    ],
    "A2 Flyers": [
        "A2 Flyers",
        "Flyers",
        "YLE Flyers",
    ],
    # "A2 Key" alone is NOT listed: "A2 Key (KET)" catches it via subset
    # ({a2,key} ⊆ {a2,key,ket}) without matching the for-Schools variant
    # (jaccard 2/5 = 0.4 < threshold).
    "A2 Key": [
        "KET",
        "A2 Key (KET)",
        "Key English Test",
    ],
    "A2 Key for Schools": [
        "KETfs",
        "Key for Schools",
        "A2 Key for Schools (KETfs)",
    ],
    # "B1 Preliminary" alone is NOT listed: "B1 Preliminary (PET)" catches it.
    "B1 Preliminary": [
        "PET",
        "B1 Preliminary (PET)",
        "Preliminary English Test",
    ],
    "B1 Preliminary for Schools": [
        "PETfs",
        "Preliminary for Schools",
        "B1 Preliminary for Schools (PETfs)",
    ],
    # "B2 First" alone is NOT listed: "B2 First (FCE)" catches it.
    "B2 First": [
        "FCE",
        "B2 First (FCE)",
        "First Certificate",
        "First Certificate in English",
    ],
    "B2 First for Schools": [
        "FCEfs",
        "First for Schools",
        "B2 First for Schools (FCEfs)",
    ],
    "C1 Advanced": [
        "CAE",
        "C1 Advanced (CAE)",
        "Certificate in Advanced English",
        "Advanced",
    ],
    "C2 Proficiency": [
        "CPE",
        "C2 Proficiency (CPE)",
        "Certificate of Proficiency in English",
        "Proficiency",
    ],
    "Linguaskill": [
        "Linguaskill",
        "Linguaskill Business",
        "Linguaskill General",
    ],
    "TKT": [
        "TKT",
        "Teaching Knowledge Test",
        "TKT Module",
        "TKT CLIL",
        "TKT Young Learners",
        "TKT YL",
    ],
    "Delta": [
        "Delta",
        "Delta Module",
    ],
    "CELTA": [
        "CELTA",
    ],
    "IELTS": [
        "IELTS",
        "IELTS Academic",
        "IELTS General Training",
        "IELTS General",
        "IELTS on Computer",
        "IELTS GT",
        "IELTS AC",
        "International English Language Testing System",
    ],
    # "MET" alone is NOT listed: "Michigan (MET)" catches it via subset
    # ({met} ⊆ {michigan,met}) without matching "MET Go!" (jaccard 1/3 < threshold).
    "MET": [
        "Michigan",
        "Michigan (MET)",
        "Michigan English Test",
        "Michigan English Test (MET)",
    ],
    "MET Go!": [
        "MET Go!",
        "MET Go",
        "Michigan MET Go",
    ],
    "TEA": [
        "TEA",
        "Test of English for Aviation",
        "TEA (Test of English for Aviation)",
    ],
}


@lru_cache(maxsize=256)
def canonical_exam_name(label: str) -> str:
    for name in EXAM_NAME_ORDER:
        aliases = EXAM_NAME_ALIASES.get(name, [])
        if any(label_matches_alias(label, alias) for alias in aliases):
            return name
    return "Other"
