"""Use case: Regression tests for clickable clarification choices and hidden plan-validator text.

What it does: Replays observed invalid or ambiguous model replies (D14, D17, D24) through a
scripted planner and the real thread, router and query services, then clicks an offered choice
and checks it executes deterministically, while stale clarifications still refuse to run.
"""

import copy
import json

import pytest

from execplus.domain.intent import INVALID_PLAN, canonical_question, route_response
from execplus.domain.models import QuestionKind
from execplus.domain.offline_planner import working_choices
from test_conversational_explorer import ScriptedModel
from test_dataset_guidance import ask
from test_dataset_guidance import setup as guidance_setup
from test_harness_context import query
from test_harness_context_integration import setup
from test_intent import view
from test_understanding import confirm, context

RANK_WITHOUT_GROUP = query(order="desc", limit=5)
PERIOD_WITHOUT_DATE = query("avg", group_by=["region"], period="month")
VALIDATOR_TEXT = ("Rank groups", "calendar period", "order asc", "validation", "model proposed")


def test_validator_failures_are_marked_but_model_refusals_keep_their_own_words():
    for plan in (RANK_WITHOUT_GROUP, PERIOD_WITHOUT_DATE, {"kind": "numerical"}):
        routed = route_response(json.dumps(plan), view())
        assert routed.kind == QuestionKind.UNSUPPORTED
        assert routed.validation_issue == INVALID_PLAN
    refusal = route_response(json.dumps({"kind": "unsupported", "message": "Not here."}), view())
    assert (refusal.message, refusal.validation_issue) == ("Not here.", "")


def test_lowest_group_template_plans_ascending_and_working_choices_all_plan():
    planned = canonical_question("Which region has the lowest total revenue?", view())
    assert planned is not None and planned.request is not None
    assert (planned.request.group_by, planned.request.order) == (("region",), "asc")
    choices = working_choices("Show daily average revenue trend", view())
    assert 2 <= len(choices) <= 3
    assert choices[0] == "What is the average of revenue?"
    for choice in choices:
        routed = canonical_question(choice, view())
        assert routed is not None and routed.kind != QuestionKind.UNSUPPORTED


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [RANK_WITHOUT_GROUP, PERIOD_WITHOUT_DATE])
async def test_repeated_invalid_plan_offers_friendly_working_choices(integration, bad):
    actor, wid, did, uid, model, threads = setup(integration, bad, bad)
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "Show monthly average revenue")
    assert answer is None and turn.query_id is None
    assert turn.kind == "ambiguous"
    assert "failed validation" in model.requests[1].messages[-1].content
    assert not any(text in (turn.message or "") for text in VALIDATOR_TEXT)
    choices = turn.evidence["clarification"]["choices"]
    assert choices[0] == "What is the average of revenue?"
    answer, turn = await threads.ask(actor, wid, thread.id, choices[0])
    assert turn.status == "complete"
    assert turn.model_route == "deterministic:offered-question-v1"
    assert str(answer.value) == "116.666666666667"
    assert len(model.requests) == 2


@pytest.mark.asyncio
async def test_invalid_plan_gets_one_correction_round(integration):
    actor, wid, did, uid, _, threads = setup(
        integration, RANK_WITHOUT_GROUP, query(group_by=["region"], order="desc")
    )
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "Which region sells the most?")
    assert turn.status == "complete"
    assert "(plan correction)" in turn.model_route
    assert answer[0].rows[0][0] == "South"


@pytest.mark.asyncio
async def test_model_choices_become_executable_buttons(integration):
    ambiguous = {
        "kind": "ambiguous",
        "message": "Which result should I rank?",
        "options": ["Which region has the lowest total revenue?", "revenue ÷ visits", "region"],
    }
    actor, wid, did, uid, model, threads = setup(integration, ambiguous)
    thread = await threads.start_thread(actor, wid, did, uid)
    answer, turn = await threads.ask(actor, wid, thread.id, "Which region is worst?")
    assert answer is None and turn.kind == "ambiguous"
    assert "Candidates" not in turn.message
    choices = turn.evidence["clarification"]["choices"]
    assert choices == ["Which region has the lowest total revenue?", "region"]
    answer, turn = await threads.ask(actor, wid, thread.id, choices[0])
    assert turn.model_route == "deterministic:offered-question-v1"
    assert [row[0] for row in answer[0].rows] == ["North", "South"]
    assert len(model.requests) == 1


@pytest.mark.asyncio
async def test_unusable_model_choices_fall_back_to_working_questions(integration):
    ambiguous = {
        "kind": "ambiguous",
        "message": "Conversion rate needs two parts.",
        "options": ["purchases ÷ visits", "purchases ÷ clicks"],
    }
    actor, wid, did, uid, _, threads = setup(integration, ambiguous)
    thread = await threads.start_thread(actor, wid, did, uid)
    _, turn = await threads.ask(actor, wid, thread.id, "What is the revenue conversion rate?")
    choices = turn.evidence["clarification"]["choices"]
    assert choices and choices[0] == "What is the total of revenue?"
    assert "÷" not in " ".join(choices)


def test_stale_clarification_choice_does_not_run(integration):
    bad = {
        "kind": "numerical",
        "plan": {"metric": "attock_erp", "aggregation": "sum", "order": "desc"},
    }
    owner, _, root, path, model = guidance_setup(integration, ScriptedModel(bad, bad))
    first = ask(integration, owner, path, "rank attock_erp")
    assert first["turn"]["kind"] == "ambiguous"
    choice = first["turn"]["clarification"]["choices"][0]
    assert choice == "What is the total of attock_erp?"
    current = context(integration, owner, root)
    definition = copy.deepcopy(current["definition"])
    saved = confirm(integration, owner, root, current, definition, state="needs_review")
    assert saved.status_code == 201
    reply = ask(integration, owner, path, choice)
    assert reply["answer"] is None
    assert "changed while clarifying" in reply["turn"]["message"]
    assert len(model.requests) == 2
