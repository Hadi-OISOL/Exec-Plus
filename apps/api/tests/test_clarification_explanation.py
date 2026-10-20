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


@pytest.mark.asyncio
async def test_social_label_for_bound_explanation_revalidates_and_preserves_pending(integration):
    from test_harness_context import query
    from test_harness_context_integration import setup

    pending = {
        "kind": "ambiguous",
        "message": "Choose the region whose records should be compared.",
        "options": ["North", "South"],
    }
    message = (
        "A filtered file keeps the records for the region you choose. Nothing has been changed."
    )
    actor, wid, did, uid, model, threads = setup(
        integration,
        query(),
        pending,
        proposal(message, focus="conversation"),
        proposal(
            "The region selects which records belong in your comparison.", focus="conversation"
        ),
    )
    thread = await threads.start_thread(actor, wid, did, uid)
    _, old = await threads.ask(actor, wid, thread.id, "total revenue")
    await threads.ask(actor, wid, thread.id, "Which outcome is better?")
    answer, turn = await threads.ask(actor, wid, thread.id, "filtered file? what do u mean")
    assert answer.message == message
    assert answer.focus == "conversation"
    assert turn.query_id is None
    assert "clarification-context normalization" in turn.model_route
    assert turn.evidence["clarification"]["question"] == "Which outcome is better?"
    assert str(old.query_id) not in json.dumps(turn.evidence)
    restored = await threads.resolve(actor, wid, thread.id, turn.id)
    assert restored.message == answer.message
    assert restored.sources == answer.sources
    assert restored.focus == answer.focus
    assert restored.model_route == answer.model_route
    answer, why = await threads.ask(actor, wid, thread.id, "why")
    assert why.query_id is None
    assert answer.message.startswith("The region selects")
    assert len(model.requests) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("context_kind", ["missing", "empty_question", "stale"])
async def test_social_field_prose_requires_current_pending_context(integration, context_kind):
    from execplus.application.services.intent_router import ClarificationContext
    from execplus.domain.errors import ClarificationRequiredError, UnsupportedQuestionError
    from test_harness_context_integration import setup

    actor, wid, did, uid, model, threads = setup(
        integration, proposal("Choose the region to compare.", focus="conversation")
    )
    router = threads.intent_router
    context = await router._describe(actor, wid, did, uid)
    pending = None
    if context_kind != "missing":
        pending = ClarificationContext(
            "" if context_kind == "empty_question" else "Which outcome matters?",
            "Choose a region.",
            () if context_kind == "stale" else context.view.sources,
        )
    with pytest.raises((ClarificationRequiredError, UnsupportedQuestionError)):
        await router.ask(
            actor, wid, did, uid, "filtered file? what do u mean", prior_clarification=pending
        )
    assert len(model.requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,question",
    [
        (proposal("Choose the region.", focus="conversation"), "Now calculate total revenue"),
        (proposal("Choose the region.", focus="conversation"), "Filter to North"),
        (proposal("Choose the region.", focus="conversation", hidden="extra"), "what do u mean"),
        (proposal("The region contains 12 records.", focus="conversation"), "what do u mean"),
        (proposal("I saved your preferences.", focus="conversation"), "what do u mean"),
        (proposal("Revenue doubled.", focus="conversation"), "what do u mean"),
    ],
)
async def test_context_normalization_never_bypasses_action_or_payload_guards(
    integration, payload, question
):
    from test_harness_context_integration import setup

    pending = {"kind": "ambiguous", "message": "Which region?", "options": ["North", "South"]}
    actor, wid, did, uid, model, threads = setup(integration, pending, payload)
    thread = await threads.start_thread(actor, wid, did, uid)
    await threads.ask(actor, wid, thread.id, "Which outcome is better?")
    answer, turn = await threads.ask(actor, wid, thread.id, question)
    assert answer is None
    assert turn.kind in {"ambiguous", "unsupported"}
    assert turn.query_id is None
    assert "clarification-context normalization" not in (turn.model_route or "")
    assert len(model.requests) == 2


@pytest.mark.asyncio
async def test_valid_social_reply_does_not_become_pending_explanation(integration):
    from test_harness_context_integration import setup

    pending = {"kind": "ambiguous", "message": "Which region?", "options": ["North", "South"]}
    social = proposal("I'm here and ready to help. How are you doing?", focus="conversation")
    actor, wid, did, uid, model, threads = setup(integration, pending, social)
    thread = await threads.start_thread(actor, wid, did, uid)
    await threads.ask(actor, wid, thread.id, "Which outcome is better?")
    answer, turn = await threads.ask(actor, wid, thread.id, "How are you doing?")
    assert answer.message == social["message"]
    assert answer.focus == "conversation"
    assert answer.pending_clarification is None
    assert "clarification" not in turn.evidence
    assert "clarification-context normalization" not in turn.model_route
    assert turn.query_id is None
    assert len(model.requests) == 2
