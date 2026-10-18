"""Field-selection replies are not extra filters or implied category values."""

import json

import pytest

from execplus.domain.intent import cohort_scope_needs_clarification, route_response
from execplus.domain.profiling import profile
from execplus.domain.semantics import dataset_view
from test_patterns import prepared
from test_record_counts import crop_table

QUESTION = "can you tell me about what factor effect the most in crop growth?"


def comparison():
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
    return intent, view


@pytest.mark.parametrize(
    "question",
    [
        QUESTION,
        QUESTION + " Crop_Growth_Stage",
        "Which conditions differ for Crop_Growth_Stage?",
        "Which conditions differ in the crop growth? Crop_Growth_Stage",
    ],
)
def test_terminal_outcome_field_reference_is_not_an_extra_row_predicate(question):
    intent, view = comparison()
    assert not cohort_scope_needs_clarification(question, intent, view)
    # Scope validation never invents a target. The routing layer must separately
    # require a user-selected label before constructing this comparison intent.
    assert intent.target_value == "Harvest"


@pytest.mark.parametrize(
    "suffix",
    [
        " not Harvest",
        " excluding Rice",
        " in East",
        " before last year",
        " with Soil_Moisture above 20",
        " compared to Growing",
        " by Crop_Type",
    ],
)
def test_field_reference_does_not_consume_following_real_restrictions(suffix):
    intent, view = comparison()
    assert cohort_scope_needs_clarification(QUESTION + suffix + " Crop_Growth_Stage", intent, view)


def test_shared_field_alias_is_not_assumed_to_be_selected_outcome():
    context, _ = prepared(
        ("Crop_Growth_Stage", "Crop_Growth_Region", "reading"),
        [("Harvest", "East", 10), ("Growing", "West", 20)],
    )
    intent = route_response(
        json.dumps(
            {
                "kind": "cohort_comparison",
                "target_column": "Crop_Growth_Stage",
                "target_value": "Harvest",
            }
        ),
        context.view,
    )
    assert cohort_scope_needs_clarification(QUESTION + " Crop_Growth_Stage", intent, context.view)
