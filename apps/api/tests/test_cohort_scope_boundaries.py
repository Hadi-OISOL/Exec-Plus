"""Independent guards against silently broadening a cohort question."""

import json

import pytest

from execplus.domain.intent import cohort_scope_needs_clarification, route_response
from execplus.domain.profiling import profile
from execplus.domain.semantics import dataset_view
from test_patterns import prepared
from test_record_counts import crop_table


def proposed_comparison():
    context, _ = prepared(
        ("stage", "reading", "crop"),
        [("Ready", 2, "A")] * 10 + [("Growing", 4, "B")] * 10 + [("Starting", 8, "C")] * 10,
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


HARVEST_PURPOSE_QUESTION = (
    "i meant how does one crop end up into harvest?? like what did the crops in harvest "
    "did that others should do in order to end up here"
)


@pytest.mark.parametrize(
    "question",
    [
        HARVEST_PURPOSE_QUESTION,
        "What differs for crops in Harvest in order to reach this stage?",
        "What did Harvest crops do IN ORDER TO get here?",
    ],
)
def test_purpose_phrase_does_not_add_a_cohort_filter(question):
    view = dataset_view(profile(crop_table()))
    intent = route_response(
        json.dumps(
            {
                "kind": "cohort_comparison",
                "target_column": "Crop_Growth_Stage",
                "target_value": "Harvest",
            }
        ),
        view,
    )
    assert not cohort_scope_needs_clarification(question, intent, view)


@pytest.mark.parametrize(
    "restriction",
    [
        " in East",
        " from last 7 days",
        " during 2025",
        " only maize",
        " excluding Rice",
        " except Wheat",
        " where stage is not Harvest",
        " where Soil_Moisture > 20",
        " with Soil_Moisture above 20 and below 40",
        " compared to Growing",
        " by Crop_Type",
        " within 2 weeks",
    ],
)
def test_purpose_phrase_does_not_hide_real_scope_restrictions(restriction):
    view = dataset_view(profile(crop_table()))
    intent = route_response(
        json.dumps(
            {
                "kind": "cohort_comparison",
                "target_column": "Crop_Growth_Stage",
                "target_value": "Harvest",
            }
        ),
        view,
    )
    assert cohort_scope_needs_clarification(HARVEST_PURPOSE_QUESTION + restriction, intent, view)
