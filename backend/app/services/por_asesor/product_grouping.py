import unicodedata
from collections.abc import Iterable, Sequence
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


def canonical_exam_category(label: str) -> str:
    for category in EXAM_CATEGORY_ORDER:
        aliases = EXAM_CATEGORY_ALIASES.get(category, [])
        if any(label_matches_alias(label, alias) for alias in aliases):
            return category
    return "Placement & Otros"
