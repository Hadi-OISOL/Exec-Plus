"""Use case: Verifies measured discoveries use private conversation evidence.

What it does: Checks job routing, source guards, replay, privacy and meaningful no-date handoffs.
"""

from copy import deepcopy
from uuid import UUID

import pytest
from sqlalchemy import select, update

from execplus.domain.analysis_plan import AnalysisPlan, AnalysisStep, pattern_conversation_plan
from execplus.domain.ingestion import IngestionError
from execplus.domain.jobs import ResourceBudget
from execplus.domain.pattern_requests import pattern_filter_needs_clarification, wants_patterns
from execplus.infrastructure.persistence import schema as s
from test_context_reuse import saved
from test_conversation_jobs import job_path, process, submit
from test_dataset_guidance import ask
from test_studies import add_member, prepare
from test_understanding import confirm, context


def setup(env):
    content = b"city,amount,cost\n" + b"".join(
        f"{'North' if i < 20 else 'South'},{i + 1},{2 * i + 3}\n".encode() for i in range(40)
    )
    owner, _, wid, _, _, root = prepare(env, content)
    saved(env, owner, root)
    tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    return owner, wid, root, f"/workspaces/{wid}/threads/{tid}"


def test_pattern_job_uses_one_private_receipt_and_reopens_exactly(integration):
    env = integration
    owner, wid, root, path = setup(env)
    before = context(env, owner, root)
    job = submit(env, owner, path, "Find patterns in this data")
    assert process(env) == {"processed": 1}
    response = env.client.get(job_path(job) + "/result", headers=owner)
    assert response.status_code == 200, response.text
    result = response.json()
    answer = result["answer"]
    assert answer is not None, result
    assert answer["kind"] == "patterns"
    assert answer["patterns"]["coverage"]["filtered_rows"] == 40
    assert answer["patterns"]["findings"]
    restored = env.client.get(path + f"/turns/{result['turn']['id']}/answer", headers=owner)
    assert restored.status_code == 200, restored.text
    assert restored.json() == answer
    assert context(env, owner, root) == before
    with env.engine.connect() as conn:
        assert len(conn.execute(select(s.query_executions)).all()) == 1
        plan = conn.execute(select(s.jobs.c.plan)).scalar_one()["value"]
        assert [step["operation"] for step in plan["steps"]] == [
            "explore_patterns",
            "assemble_evidence",
        ]
    events = env.client.get(job_path(job) + "/events", headers=owner).json()["events"]
    assert sum(e["stage"] == "executing_query" and e["status"] == "started" for e in events) == 1
    member, _ = add_member(env, owner, wid, "admin")
    assert env.client.get(job_path(job) + "/result", headers=member).status_code == 404
    assert env.client.get(path, headers=member).status_code == 404
    qid = answer["pattern_evidence"]["query_id"]
    assert (
        env.client.post(f"/workspaces/{wid}/queries/{qid}/replay", headers=member).status_code
        == 404
    )


def test_pattern_scope_clarifies_then_runs_whole_file_and_stale_choice_refuses(integration):
    env = integration
    owner, _, root, path = setup(env)
    first = ask(env, owner, path, "Find patterns only where city is North")
    assert first["turn"]["kind"] == "ambiguous"
    second = ask(env, owner, path, "Find patterns across the whole file")
    assert second["answer"]["kind"] == "patterns", second
    ask(env, owner, path, "Find patterns only where city is North")
    current = context(env, owner, root)
    current["definition"]["description"] = "Changed field observations"
    assert confirm(env, owner, root, current).status_code == 201
    refused = ask(env, owner, path, "Find patterns across the whole file")
    assert refused["answer"] is None and "changed" in refused["turn"]["message"]


def test_pattern_thread_tamper_is_detected(integration):
    env = integration
    owner, _, _, path = setup(env)
    result = ask(env, owner, path, "Find patterns")
    tid = UUID(result["turn"]["id"])
    with env.engine.begin() as conn:
        evidence = deepcopy(
            conn.execute(
                select(s.thread_turns.c.evidence).where(s.thread_turns.c.id == tid)
            ).scalar_one()
        )
        evidence["patterns"]["result"]["findings"] = []
        conn.execute(
            update(s.thread_turns).where(s.thread_turns.c.id == tid).values(evidence=evidence)
        )
    assert env.client.get(path + f"/turns/{tid}/answer", headers=owner).status_code == 409


def test_no_date_handoff_preserves_measure_and_daily_assumptions(integration):
    env = integration
    owner, _, _, path = setup(env)
    forecast = ask(env, owner, path, "Forecast amount")["answer"]
    actions = forecast["guidance"]["actions"]
    assert actions[0]["tool"] == "patterns"
    assert actions[1]["metric"] == "amount" and actions[1]["scenario_mode"] == "daily_change"
    daily = ask(env, owner, path, "What happens to amount after 7 days?")["answer"]
    assert daily["guidance"]["actions"][0]["scenario_mode"] == "daily_change"
    assert "not a learned forecast" in daily["message"]


@pytest.mark.parametrize(
    "question",
    [
        "What is the total patterns?",
        "According to the policy, explain correlations",
        "List records with pattern labels",
        "What is average relationship?",
    ],
)
def test_pattern_words_never_steal_calculations_or_documents(question):
    assert not wants_patterns(question)


@pytest.mark.parametrize(
    "question,columns,clarify",
    [
        ("Find patterns in North", (), True),
        ("Find patterns after rainfall", ("rainfall",), True),
        ("Find patterns between cost and amount", ("cost", "amount"), False),
        ("Find patterns in this data", (), False),
        ("Find relationships for last seven days", (), True),
        ("Find patterns in days_after_rain", ("days_after_rain",), False),
    ],
)
def test_pattern_scope_never_silently_uses_the_whole_file(question, columns, clarify):
    assert pattern_filter_needs_clarification(question, columns) is clarify


def test_saved_private_pattern_goal_is_used_for_broad_analysis(integration):
    env = integration
    owner, _, root, path = setup(env)
    response = env.client.post(
        root.split("/uploads/")[0] + "/preferences",
        headers=owner,
        json={"domain_hint": "auto", "goal": "Find patterns between cost and amount"},
    )
    assert response.status_code in {200, 201}, response.text
    answer = ask(env, owner, path, "Analyze my data")["answer"]
    assert answer["kind"] == "patterns"
    assert all(
        set(item["columns"]) == {"cost", "amount"} for item in answer["patterns"]["findings"]
    )


def test_no_date_missing_unit_asks_only_for_missing_detail(integration):
    env = integration
    owner, _, root, path = setup(env)
    current = context(env, owner, root)
    for column in current["definition"]["columns"]:
        if column["name"] == "amount":
            column["unit"] = ""
    assert confirm(env, owner, root, current).status_code == 201
    answer = ask(env, owner, path, "Forecast amount")["answer"]
    assert "fixed unit for amount" in answer["message"]
    assert [a["tool"] for a in answer["guidance"]["actions"]] == ["prepare", "patterns"]


def test_pattern_plan_retains_one_query_budget_and_bounded_column_contract():
    plan = pattern_conversation_plan(("amount",), ())
    assert plan.steps[0].operation == "explore_patterns"
    with pytest.raises(IngestionError):
        pattern_conversation_plan(tuple(str(i) for i in range(13)), ())
    with pytest.raises(IngestionError):
        AnalysisPlan(
            "conversation-plan-v1",
            (),
            (
                AnalysisStep(
                    "one", "explore_patterns", (), {"columns": []}, "patterns", "analysis_receipt"
                ),
                AnalysisStep(
                    "two", "explore_patterns", (), {"columns": []}, "patterns", "analysis_receipt"
                ),
                AnalysisStep(
                    "answer",
                    "assemble_evidence",
                    ("one", "two"),
                    {},
                    "answer",
                    "authorized_evidence",
                ),
            ),
            ResourceBudget(),
        )
