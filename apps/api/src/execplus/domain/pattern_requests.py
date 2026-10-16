"""Use case: Recognizes requests for measured relationships instead of a file description.

What it does: Recognizes exploratory intent while preserving calculation and document requests.
"""

import json
import re

from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.guidance import words

_QUOTED_FIELD = r'"(?:[^"\\]|\\.)*"'
_GROUP_COMPARISON = re.compile(
    rf"Compare the relationship between ({_QUOTED_FIELD}) and ({_QUOTED_FIELD}) "
    rf"within groups of ({_QUOTED_FIELD})\.?",
    re.IGNORECASE,
)


def wants_group_relationship(question: str) -> bool:
    """Recognize a grouped request without treating field names as instructions."""
    text = words(re.sub(_QUOTED_FIELD, "selected field", question))
    if re.search(r"\b(document|policy|according|total|sum|average|mean|count|records)\b", text):
        return False
    return bool(
        re.search(r"\b(relationships?|correlations?|associations?)\b", text)
        and re.search(r"\b(within|inside|groups?|grouped|per|by)\b", text)
    )


def group_relationship_selection(
    question: str, known_columns: tuple[str, ...]
) -> tuple[str, str, str]:
    """Accept the explicit chooser's whole-file request, never silently drop filters."""
    match = _GROUP_COMPARISON.fullmatch(question.strip())
    if match is None:
        raise ClarificationRequiredError(
            "Choose two measures and a category in Compare groups. This comparison uses "
            "all eligible rows; prepare a filtered source first if you need fewer rows."
        )
    try:
        names = tuple(json.loads(value) for value in match.groups())
    except (ValueError, TypeError):
        raise ClarificationRequiredError("Choose the fields again in Compare groups.") from None
    if (
        len(set(names)) != 3
        or any(not isinstance(name, str) or not name or len(name) > 200 for name in names)
        or any(name not in known_columns for name in names)
    ):
        raise ClarificationRequiredError(
            "Choose two different measures and a different category from the current file."
        )
    return names[0], names[1], names[2]


def wants_patterns(question: str) -> bool:
    text = words(question)
    if re.search(
        r"\b(document|policy|according|total|sum|average|mean|count|list|records)\b", text
    ):
        return False
    return bool(
        re.search(
            r"\b(patterns?|relationships?|correlations?|associations?)\b"
            r"|\b(move|go|occur) together\b|\bwhat tends to\b",
            text,
        )
    )


def pattern_filter_needs_clarification(question: str, columns: tuple[str, ...] = ()) -> bool:
    text = words(question)
    for column in sorted(columns, key=len, reverse=True):
        text = re.sub(r"\b" + re.escape(words(column)) + r"\b", "selected field", text)
    if re.search(
        r"\b(only|where|when|if|after|before|during|excluding|except|without|above|below|greater|less)\b",
        text,
    ) or re.search(r"[<>]", question):
        return True
    scope = re.search(r"\b(in|for|from|with|to|between|of)\s+(.+)$", text)
    if scope is None:
        return False
    allowed = {
        "a",
        "all",
        "and",
        "any",
        "data",
        "dataset",
        "field",
        "fields",
        "file",
        "here",
        "it",
        "me",
        "my",
        "our",
        "selected",
        "the",
        "these",
        "this",
        "whole",
        "patterns",
        "relationships",
        "correlations",
        "associations",
        "please",
        "in",
        "for",
        "from",
        "with",
        "to",
        "between",
        "of",
    }
    return bool(set(scope.group(2).split()) - allowed)
