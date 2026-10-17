"""Independent guards against silently broadening a cohort question."""

import json

import pytest

from execplus.domain.intent import cohort_scope_needs_clarification, route_response
from test_patterns import prepared


def proposed_comparison():
    context, _ = prepared(
        ("stage", "reading", "crop"),
        [("Ready", 2, "A")] * 10
        + [("Growing", 4, "B")] * 10
        + [("Starting", 8, "C")] * 10,
    )
    intent = route_response(
        json.dumps(
            {
                "kind": "cohort_comparison",
                "target_column": "stage",
                "target_value": "Ready",
                "columns": ["reading"],
            }
        ),
        context.view,
    )
    return intent, context.view


@pytest.mark.parametrize(
    "question",
    [
        "Compare Ready stage records with others, reading above 3",
        "Compare Ready stage records with other records; reading > 3",
        "Compare Ready stage records with other records; reading less than 3",
        "Compare Ready with Growing",
        "Compare Ready stage records against Growing stage records",
    ],
)
def test_unsupported_restrictions_and_named_comparators_cannot_be_dropped(question):
    intent, view = proposed_comparison()
    assert cohort_scope_needs_clarification(question, intent, view)


@pytest.mark.parametrize(
    "question",
    [
        'Compare records where "stage" equals "Ready" with other records',
        "What differs for Ready stage records?",
        "How do Ready records differ from others?",
        "Compare Ready with other records",
    ],
)
def test_plain_selected_group_versus_every_other_group_stays_supported(question):
    intent, view = proposed_comparison()
    assert not cohort_scope_needs_clarification(question, intent, view)
