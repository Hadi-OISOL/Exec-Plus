"""Procedural explanations may name inputs without claiming analytical findings."""

import json

import pytest

from execplus.domain.intent import route_response
from execplus.domain.models import QuestionKind
from test_intent import view


def proposal(message, **extra):
    return {
        "kind": "overview",
        "focus": "clarification",
        "columns": [],
        "message": message,
        **extra,
    }


@pytest.mark.parametrize(
    "message",
    [
        "A filtered file contains only the records matching the condition you choose. "
        "The comparison needs the records prepared first; it does not apply that extra condition.",
        "By region, I mean the field used to select which records belong in your comparison. "
        "Please choose the group you want to examine.",
        "A unit tells us what revenue measures, such as a currency. Please confirm the actual "
        "unit before interpreting a calculation.",
        "Filtered file ka matlab sirf woh rows jo aap ki condition se match karti hain. "
        "Pehle woh rows select karni hongi.",
        "A filtered file means keeping only the rows you want to compare. "
        "I have not changed your file.",
    ],
)
def test_valid_procedural_explanation_preserves_model_wording(message):
    routed = route_response(json.dumps(proposal(message)), view())
    assert routed.kind == QuestionKind.OVERVIEW
    assert routed.guide_focus == "clarification"
    assert routed.guide_columns == ()
    assert routed.message == message
    assert routed.request is None


def test_schema_names_are_only_allowed_in_explanation_not_social_reply():
    message = "By region, I mean the field used to choose a group."
    assert route_response(json.dumps(proposal(message)), view()).kind == QuestionKind.OVERVIEW
    social = proposal(message, focus="conversation")
    assert route_response(json.dumps(social), view()).kind == QuestionKind.UNSUPPORTED


@pytest.mark.parametrize(
    "message",
    [
        "Revenue doubled because demand improved.",
        "Revenue is highest in the North.",
        "The data shows a clear improvement.",
        "I saved your preferences.",
        "I have just analyzed the dataset.",
        "I remember your previous request.",
        "Your confidential goal is to cut payroll.",
        "The chosen group has 12 records.",
        "Go to https://example.test to filter the file.",
        "<script>alert('x')</script>",
        "Hello\nfriend",
        "a" * 701,
        "",
        ["filtered file"],
        None,
    ],
)
def test_explanation_cannot_bypass_noncalculation_claim_boundary(message):
    routed = route_response(json.dumps(proposal(message)), view())
    assert routed.kind == QuestionKind.UNSUPPORTED
    assert routed.message == "The clarification explanation could not be validated."


@pytest.mark.parametrize(
    "extra",
    [
        {"columns": ["revenue"]},
        {"columns": "revenue"},
        {"plan": {"metric": "revenue", "aggregation": "sum"}},
        {"evidence": "invented"},
        {"sources": []},
    ],
)
def test_explanation_contract_cannot_smuggle_calculation_or_evidence(extra):
    routed = route_response(json.dumps(proposal("Please choose a group.", **extra)), view())
    assert routed.kind == QuestionKind.UNSUPPORTED


def test_unknown_nontext_focus_is_refused_without_parser_exception():
    assert route_response(json.dumps(proposal("Hello", focus=[])), view()).kind == (
        QuestionKind.UNSUPPORTED
    )
