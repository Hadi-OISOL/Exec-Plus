"""Use case: Matches typed category values to the labels actually present in a file.

What it does: Resolves case, spacing, plural and small-typo differences ('laptops' -> 'Laptop')
to one existing label, lists the closest labels when nothing matches, and finds labels that
differ only by case or spacing ('Store 1' vs ' store 1 ') so they can be flagged, never merged.
"""

from collections.abc import Iterable


def _key(value: str) -> str:
    return " ".join(value.split()).casefold()


def _singular(value: str) -> str:
    if len(value) > 4 and value.endswith("ies"):
        return value[:-3] + "y"
    if len(value) > 3 and value.endswith("es") and value[-3] in "sxz":
        return value[:-2]
    return value[:-1] if len(value) > 3 and value.endswith("s") else value


def distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def match_label(value: str, labels: Iterable[str]) -> tuple[str | None, tuple[str, ...]]:
    """(the one label meant, ()) or (None, closest labels) when no label is close enough."""
    present = list(dict.fromkeys(label for label in labels if label.strip()))
    key = _key(value)
    for found in (
        [label for label in present if _key(label) == key],
        [label for label in present if _singular(_key(label)) == _singular(key)],
    ):
        if found:
            return found[0], ()
    allowed = 2 if len(key) >= 8 else 1 if len(key) >= 5 else 0
    scored = sorted(
        ((distance(_singular(_key(label)), _singular(key)), label) for label in present),
        key=lambda item: item[0],
    )
    near = [label for score, label in scored if score <= allowed]
    if len(near) == 1 or (near and scored[0][0] < scored[1][0]):
        return near[0], ()
    return None, tuple(label for _, label in scored[:3])


def label_variants(values: Iterable[object]) -> list[tuple[str, ...]]:
    """Groups of distinct labels that differ only by letter case or spacing."""
    groups: dict[str, list[str]] = {}
    for value in values:
        if isinstance(value, str) and value.strip():
            members = groups.setdefault(_key(value), [])
            if value not in members:
                members.append(value)
    return [tuple(members) for members in groups.values() if len(members) > 1]


def variants_note(
    headers: tuple[str, ...], rows: Iterable[tuple[str, ...]], columns: Iterable[str]
) -> str:
    """One plain paragraph naming case/spacing label variants and the existing cleaning step."""
    table = list(rows)
    found = [
        f"{name}: " + " and ".join(f"'{label}'" for label in group[:3])
        for name in columns
        if name in headers
        for group in label_variants(row[headers.index(name)] for row in table)[:2]
    ]
    if not found:
        return ""
    return (
        "Labels that differ only by capital letters or spaces are counted as separate groups: "
        + "; ".join(found[:4])
        + ". The 'Trim surrounding whitespace' cleaning step in Prepare data merges spacing "
        "differences; capital-letter differences need a corrected source file. Nothing is merged "
        "automatically."
    )
