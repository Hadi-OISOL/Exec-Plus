"""Use case: Verifies explicit group comparisons in the private conversation pipeline.

What it does: Checks bounded routing, budgets, durable evidence and source/publication guards.
"""

import asyncio
import json

import pytest
from sqlalchemy import select

from execplus.domain.analysis_plan import AnalysisPlan, AnalysisStep, pattern_conversation_plan
from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.ingestion import IngestionError
from execplus.domain.jobs import ResourceBudget
from execplus.domain.pattern_requests import group_relationship_selection, wants_group_relationship
from execplus.infrastructure.persistence import schema as s
from test_conversation_jobs import job_path, process, submit
from test_dataset_guidance import ask
from test_pattern_conversations import setup
from test_studies import add_member
from test_understanding import confirm, context

QUESTION = 'Compare the relationship between "amount" and "cost" within groups of "city".'


@pytest.mark.parametrize(
    "names",
    [
        ("amount", "cost", "city"),
        ('Measure "A"', "cost\\per unit", "region"),
        ("total", "policy", "when"),
        ("rain; drop table", "soil\nmoisture", "地域"),
    ],
)
def test_explicit_field_names_are_values_not_instructions(names):
    left, right, group = (json.dumps(name) for name in names)
    question = f"Compare the relationship between {left} and {right} within groups of {group}."
    assert wants_group_relationship(question)
    assert group_relationship_selection(question, names) == names


@pytest.mark.parametrize(
    "question",
    [
        QUESTION + " Only where city is North",
        QUESTION.replace('"cost"', '"amount"'),
        QUESTION.replace('"city"', '"unknown"'),
        "Compare correlations between amount and cost by city",
        "Find relationships within groups only for the last week",
    ],
)
def test_group_requests_never_silently_drop_fields_or_row_restrictions(question):
    assert wants_group_relationship(question)
    with pytest.raises(ClarificationRequiredError):
        group_relationship_selection(question, ("amount", "cost", "city"))


@pytest.mark.parametrize(
    "question",
    [
        "According to the policy, explain relationships within groups",
        "What is total amount by city?",
        "Find patterns in this data",
        "Show records with correlations by region",
    ],
)
def test_group_recognition_preserves_other_question_routes(question):
    assert not wants_group_relationship(question)


def test_group_plan_validates_exact_fields_and_one_query_budget():
    plan = pattern_conversation_plan(("amount", "cost"), (), group_by="city")
    assert plan.steps[0].operation == "compare_group_relationship"
    assert plan.steps[0].parameters == {"columns": ["amount", "cost"], "group_by": "city"}
    for columns, group in [((), "city"), (("amount",), "city"), (("amount", "cost"), "amount")]:
        with pytest.raises(IngestionError):
            pattern_conversation_plan(columns, (), group_by=group)
    with pytest.raises(IngestionError):
        AnalysisPlan(
            "conversation-plan-v1",
            (),
            (
                plan.steps[0],
                AnalysisStep(
                    "another",
                    "explore_patterns",
                    (),
                    {"columns": []},
                    "patterns",
                    "analysis_receipt",
                ),
                AnalysisStep(
                    "answer",
                    "assemble_evidence",
                    ("patterns", "another"),
                    {},
                    "answer",
                    "authorized_evidence",
                ),
            ),
            ResourceBudget(),
        )


def test_group_job_keeps_one_private_receipt_and_reopens(integration):
    env = integration
    owner, wid, root, path = setup(env)
    before = context(env, owner, root)
    job = submit(env, owner, path, QUESTION)
    assert process(env) == {"processed": 1}
    response = env.client.get(job_path(job) + "/result", headers=owner)
    assert response.status_code == 200, response.text
    result = response.json()
    answer = result["answer"]
    assert answer is not None, result
    assert answer["patterns"]["version"] == "group-relationship-comparison-v1"
    assert answer["patterns"]["coverage"]["covered_rows"] == 40
    assert answer["model_route"] == "deterministic:group-relationship-comparison-v1"
    assert (
        env.client.get(path + f"/turns/{result['turn']['id']}/answer", headers=owner).json()
        == answer
    )
    assert context(env, owner, root) == before
    with env.engine.connect() as conn:
        assert len(conn.execute(select(s.query_executions)).all()) == 1
        plan = conn.execute(select(s.jobs.c.plan)).scalar_one()["value"]
        assert [step["operation"] for step in plan["steps"]] == [
            "compare_group_relationship",
            "assemble_evidence",
        ]
    member, _ = add_member(env, owner, wid, "admin")
    assert env.client.get(job_path(job) + "/result", headers=member).status_code == 404
    assert env.client.get(path, headers=member).status_code == 404
    qid = answer["pattern_evidence"]["query_id"]
    assert (
        env.client.post(f"/workspaces/{wid}/queries/{qid}/replay", headers=member).status_code
        == 404
    )


def test_ambiguous_group_request_clarifies_and_stale_choice_cannot_execute(integration):
    env = integration
    owner, _, root, path = setup(env)
    first = ask(env, owner, path, QUESTION + " only in North")
    assert first["turn"]["kind"] == "ambiguous"
    with env.engine.connect() as conn:
        assert not conn.execute(select(s.query_executions)).all()
    meaning = context(env, owner, root)
    meaning["definition"]["description"] = "A changed meaning after clarification"
    assert confirm(env, owner, root, meaning).status_code == 201
    refused = ask(env, owner, path, QUESTION)
    assert refused["answer"] is None and "changed" in refused["turn"]["message"]


def test_group_source_change_before_publication_clears_unpublished_evidence(
    integration, monkeypatch
):
    env = integration
    owner, _, root, path = setup(env)
    original = env.runtime.intent_router.ask

    def change():
        meaning = context(env, owner, root)
        meaning["definition"]["description"] = "Changed after computing the group comparison"
        assert confirm(env, owner, root, meaning).status_code == 201

    async def changed(*args, **kwargs):
        answer = await original(*args, **kwargs)
        await asyncio.to_thread(change)
        return answer

    monkeypatch.setattr(env.runtime.intent_router, "ask", changed)
    response = env.client.post(path + "/ask", headers=owner, json={"question": QUESTION})
    assert response.status_code == 409, response.text
    with env.engine.connect() as conn:
        turn = conn.execute(select(s.thread_turns)).mappings().one()
        assert turn["status"] == "failed" and turn["query_id"] is None and turn["evidence"] == {}
