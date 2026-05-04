import unicodedata
from collections.abc import Iterable, Sequence
import re

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
