"""Use case: Recognizes requests for measured relationships instead of a file description.

What it does: Recognizes exploratory intent while preserving calculation and document requests.
"""

import re

from execplus.domain.guidance import words


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
