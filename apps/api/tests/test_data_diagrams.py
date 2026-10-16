"""Use case: Protects source-grounded diagram routing, privacy and immutable reopening.

What it does: Reproduces the reported request and checks real tool plans, exact saved
meanings, paraphrases, unreviewed fields, model bounds, historical replay and stale publication.
"""

import asyncio
import copy
import json
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update

from execplus.domain.agent_capabilities import capability_catalog
from execplus.domain.analysis_plan import diagram_conversation_plan
from execplus.domain.data_diagram import (
    DiagramClarification,
    DiagramRequest,
    build_diagram,
    diagram_request,
)
from execplus.domain.ingestion import IngestionError
from execplus.domain.intent import route_response
from execplus.domain.models import QuestionKind
from execplus.domain.semantics import DatasetView, SemanticColumn
from execplus.infrastructure.persistence import schema as s
from execplus.presentation.routes.analytics import get_intent_router_service
from test_conversation_jobs import job_path, process, submit
from test_conversational_explorer import ScriptedModel
from test_conversational_explorer import prepare as prepare_conversation
from test_dataset_guidance import ask, description
from test_dataset_reading import prepare
from test_pattern_conversations import setup as job_setup
from test_studies import add_member
from test_understanding import confirm, context


def prepare_saved_roles(env):
    model = ScriptedModel()
    owner, wid, root = prepare_conversation(
        env,
        model,
        content=(
            b"Record_ID,rating,internal_note,category,revenue\n"
            b"R1,1,private-one,North,10\nR2,2,private-two,South,20\n"
        ),
    )
    current = context(env, owner, root)
    roles = ("identifier", "ordinal", "ignored", "dimension", "metric")
    for column, role in zip(current["definition"]["columns"], roles, strict=True):
        column["role"] = role
        column["meaning"] = "Confirmed " + column["name"]
        column["unit"] = "units" if role == "metric" else ""
    response = confirm(env, owner, root, current)
    assert response.status_code == 201, response.text
    tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    return owner, root, f"/workspaces/{wid}/threads/{tid}", model


def test_v2_maps_every_saved_role_without_query_role_normalization(integration):
    env = integration
    owner, root, path, model = prepare_saved_roles(env)
    before = context(env, owner, root)
    result = ask(env, owner, path, "can you show me a diagram of how our data converge")
    answer = result["answer"]
    assert answer["model_route"] == "deterministic:dataset-structure-v2"
    diagram = answer["diagram"]
    assert diagram["version"] == "dataset-structure-v2"
    fields = {node["label"]: node for node in diagram["nodes"] if node["kind"] == "field"}
    for column in before["definition"]["columns"]:
        field = fields[column["name"]]
        assert field["role"] == column["role"]
        assert field["meaning"] == column["meaning"]
        assert field["unit"] == column["unit"]
        assert {
            "source": "role-" + column["role"],
            "target": field["id"],
            "relation": "contains",
        } in diagram["edges"]
    assert "private-one" not in json.dumps(answer)
    assert context(env, owner, root) == before and not model.requests
    assert (
        env.client.get(path + f"/turns/{result['turn']['id']}/answer", headers=owner).json()
        == answer
    )


@pytest.mark.parametrize(
    "role_words,expected",
    [
        ("identifiers", "Record_ID"),
        ("ordered categories", "rating"),
        ("ordinal fields", "rating"),
        ("ignored fields", "internal_note"),
        ("categories", "category"),
        ("measures", "revenue"),
    ],
)
def test_role_subset_uses_confirmed_roles_instead_of_query_groups(
    integration, role_words, expected
):
    owner, _, path, model = prepare_saved_roles(integration)
    answer = ask(integration, owner, path, "Draw a diagram for " + role_words)["answer"]
    assert answer["diagram"]["shown_fields"] == 1
    assert answer["diagram"]["scope"] == "selected_fields"
    assert [node["label"] for node in answer["diagram"]["nodes"] if node["kind"] == "field"] == [
        expected
    ]
    assert not model.requests


def test_v1_saved_answer_reopens_with_exact_legacy_graph_and_model_route(integration):
    env = integration
    owner, root, path, _ = prepare_saved_roles(env)
    result = ask(env, owner, path, "Draw a diagram")
    legacy = copy.deepcopy(result["answer"])
    legacy["model_route"] = "deterministic:dataset-structure-v1"
    diagram = legacy["diagram"]
    diagram["version"] = "dataset-structure-v1"
    nodes = {node["id"]: node for node in diagram["nodes"]}
    nodes["field-0"]["role"] = nodes["field-1"]["role"] = "dimension"
    diagram["nodes"] = [
        nodes[node_id]
        for node_id in (
            "dataset",
            "role-dimension",
            "field-0",
            "field-1",
            "role-ignored",
            "field-2",
            "field-3",
            "role-metric",
            "field-4",
        )
    ]
    diagram["edges"] = [
        {"source": source, "target": target, "relation": "contains"}
        for source, target in (
            ("dataset", "role-dimension"),
            ("role-dimension", "field-0"),
            ("role-dimension", "field-1"),
            ("dataset", "role-ignored"),
            ("role-ignored", "field-2"),
            ("role-dimension", "field-3"),
            ("dataset", "role-metric"),
            ("role-metric", "field-4"),
        )
    ]
    turn_id = UUID(result["turn"]["id"])
    with env.engine.begin() as connection:
        evidence = copy.deepcopy(
            connection.execute(
                select(s.thread_turns.c.evidence).where(s.thread_turns.c.id == turn_id)
            ).scalar_one()
        )
        evidence["diagram"]["result"] = diagram
        connection.execute(
            update(s.thread_turns)
            .where(s.thread_turns.c.id == turn_id)
            .values(evidence=evidence, model_route=legacy["model_route"])
        )
    current = context(env, owner, root)
    current["definition"]["columns"][0]["role"] = "ignored"
    assert confirm(env, owner, root, current).status_code == 201
    reopened = env.client.get(path + f"/turns/{turn_id}/answer", headers=owner)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json() == legacy
    with env.engine.begin() as connection:
        evidence["diagram"]["result"]["version"] = "dataset-structure-v999"
        connection.execute(
            update(s.thread_turns).where(s.thread_turns.c.id == turn_id).values(evidence=evidence)
        )
    assert env.client.get(path + f"/turns/{turn_id}/answer", headers=owner).status_code == 409


def test_unconfirmed_saved_roles_are_not_displayed_as_confirmed(integration):
    env = integration
    owner, root, path, _ = prepare_saved_roles(env)
    current = context(env, owner, root)
    assert confirm(env, owner, root, current, state="inferred").status_code == 201
    answer = ask(env, owner, path, "Draw a diagram")["answer"]
    fields = [node for node in answer["diagram"]["nodes"] if node["kind"] == "field"]
    assert all(node["role"] == "unreviewed" and node["meaning"] == "" for node in fields)
    subset = ask(env, owner, path, "Draw a diagram for identifiers")
    assert subset["answer"] is None and "not been confirmed" in subset["turn"]["message"]


@pytest.mark.parametrize(
    "question",
    [
        "can you show me a diagram of how our data converge",
        "Draw a diagram",
        "Show a visual representation of the data",
        "How do these fields connect?",
        "Visualize the file structure",
        "Draw an interactive diagram to help me understand how these fields fit together",
        "Show a diagram of how it all ties together visually",
    ],
)
def test_structural_paraphrases_choose_real_diagram_tool(question):
    assert diagram_request(question, description()) == DiagramRequest()


@pytest.mark.parametrize(
    "question",
    [
        "Visualize revenue by date",
        "Plot total revenue by city",
        "Show total revenue as a diagram",
    ],
)
def test_value_chart_requests_are_not_replaced_by_membership_maps(question):
    ctx = replace(
        description(),
        view=DatasetView(
            (SemanticColumn("revenue", "decimal", "metric"),), frozenset({"revenue"}), frozenset()
        ),
    )
    assert diagram_request(question, ctx) is None


@pytest.mark.parametrize(
    "question",
    [
        "Diagram what causes revenue",
        "Draw a diagram joining files",
        "Diagram revenue where city is Karachi",
    ],
)
def test_unsupported_causal_join_or_filtered_diagrams_clarify(question):
    with pytest.raises(DiagramClarification):
        diagram_request(question, description())


@pytest.mark.parametrize(
    "question",
    [
        "Draw a diagram of attock_erp and profit",
        "Draw a diagram of profit",
        'Draw a diagram of "attock_erp" and "profit"',
        "Draw a diagram of 'profit'",
        'Draw a diagram of "measures"',
        "Draw a diagram only Karachi",
        "Draw a diagram of attock_erp only for Karachi",
        "Draw a diagram except Karachi",
        "Draw a diagram since 2024",
        "Draw a diagram before 2024",
        "Draw a diagram after 2024",
        "Draw a diagram excluding item_code",
        "Draw a diagram without attock_erp",
        "Draw a diagram of attock_erp between 1 and 5",
        "Draw a diagram of attock_erp > attock_erp_value",
        "Draw a diagram of attock_erp = attock_erp_value",
    ],
)
def test_unknown_fields_and_row_restrictions_are_never_silently_dropped(question):
    with pytest.raises(DiagramClarification):
        diagram_request(question, description())


@pytest.mark.parametrize(
    "question,expected",
    [
        ("Draw a diagram only attock_erp", ("attock_erp",)),
        ('Draw a diagram of "attock_erp_value"', ("attock_erp_value",)),
        ("Draw a diagram of 'item_code'", ("item_code",)),
        ("Draw a diagram of attock_erp and item_code", ("item_code", "attock_erp")),
    ],
)
def test_explicit_known_field_subsets_keep_exact_requested_columns(question, expected):
    assert diagram_request(question, description()) == DiagramRequest(expected)


def test_real_field_names_are_not_mistaken_for_row_scope_words():
    ctx = replace(
        description(),
        view=DatasetView(
            tuple(SemanticColumn(name, "text", "dimension") for name in ("before", "after")),
            frozenset(),
            frozenset(),
        ),
    )
    assert diagram_request('Draw a diagram of "before" and "after"', ctx) == DiagramRequest(
        ("before", "after")
    )


def test_bounded_diagram_keeps_unreviewed_fields_and_never_infers_units_or_edges():
    ctx = description()
    result = build_diagram(ctx, DiagramRequest()).body()
    fields = [node for node in result["nodes"] if node["kind"] == "field"]
    assert len(fields) == len(ctx.view.columns)
    assert all(
        node["role"] == "unreviewed" and node["meaning"] == node["unit"] == "" for node in fields
    )
    assert all(edge["relation"] == "contains" for edge in result["edges"])
    assert "PrivateItem" not in json.dumps(result)
    wide = replace(
        ctx,
        view=DatasetView(
            tuple(SemanticColumn(f"field_{i}", "text", "dimension") for i in range(81)),
            frozenset(),
            frozenset(),
        ),
    )
    with pytest.raises(DiagramClarification, match="eighty"):
        diagram_request("Draw a diagram", wide)
    subset = diagram_request("Draw a diagram of field_80", wide)
    assert build_diagram(wide, subset).shown_fields == 1
    assert build_diagram(wide, subset).total_fields == 81


def test_model_diagram_grammar_and_tool_catalog_reject_unavailable_or_executable_claims():
    view = description().view
    for extra in ({"columns": ["missing"]}, {"code": "print(1)"}, {"columns": ["attock_erp"] * 2}):
        assert (
            route_response(json.dumps({"kind": "diagram", **extra}), view).kind
            == QuestionKind.UNSUPPORTED
        )
    routed = route_response('{"kind":"diagram","columns":[]}', view)
    assert routed.kind == QuestionKind.DIAGRAM
    plan = diagram_conversation_plan((), ())
    assert plan.steps[0].operation == "map_dataset_structure"
    assert plan.steps[0].verification == "source_checksum"
    with pytest.raises(IngestionError):
        replace(
            plan,
            steps=(replace(plan.steps[0], parameters={"columns": [], "code": "x"}), plan.steps[1]),
        )
    minimal = capability_catalog(patterns=False, documents=False)
    assert {item["operation"] for item in minimal} == {
        "query",
        "inspect_profile",
        "map_dataset_structure",
    }
    full = capability_catalog(patterns=True, documents=True, reports=True)
    assert {item["operation"] for item in full} == {
        "query",
        "inspect_profile",
        "map_dataset_structure",
        "explore_patterns",
        "compare_group_relationship",
        "retrieve_documents",
        "export_report",
    }


def test_reported_diagram_request_uses_saved_meanings_without_model_rows_or_new_definitions(
    integration,
):
    env = integration
    owner, _, root, path, model = prepare(env)
    before = context(env, owner, root)
    result = ask(env, owner, path, "can you show me a diagram of how our data converge")
    answer = result["answer"]
    assert answer["kind"] == "diagram" and result["turn"]["kind"] == "overview"
    diagram = answer["diagram"]
    assert diagram["definition_state"] == "confirmed"
    assert diagram["description"] == before["definition"]["description"]
    fields = {node["label"]: node for node in diagram["nodes"] if node["kind"] == "field"}
    for column in before["definition"]["columns"]:
        assert fields[column["name"]]["meaning"] == column["meaning"]
        assert fields[column["name"]]["role"] == column["role"]
    assert "PrivateCustomer" not in json.dumps(answer)
    assert not model.requests and context(env, owner, root) == before
    assert (
        env.client.get(path + f"/turns/{result['turn']['id']}/answer", headers=owner).json()
        == answer
    )
    with env.engine.connect() as conn:
        assert conn.execute(select(s.query_executions)).first() is None


def test_model_can_choose_diagram_for_unlisted_paraphrase_and_receives_capability_limits(
    integration,
):
    owner, _, _, path, model = prepare(integration, {"kind": "diagram", "columns": ["city"]})
    answer = ask(integration, owner, path, "Sketch the arrangement of this source")["answer"]
    assert answer["kind"] == "diagram" and answer["diagram"]["shown_fields"] == 1
    prompt = model.requests[-1].messages[1].content
    assert "map_dataset_structure" in prompt and "Eighty fields" in prompt
    assert "private personal memory" not in prompt.lower()


@pytest.mark.parametrize(
    "question",
    ["Sketch the arrangement of revenue", "Sketch the arrangement of all columns"],
)
def test_model_diagram_cannot_change_an_explicit_field_scope(integration, question):
    owner, _, _, path, model = prepare(integration, {"kind": "diagram", "columns": ["city"]})
    result = ask(integration, owner, path, question)
    assert model.requests
    assert result["answer"] is None and result["turn"]["kind"] == "ambiguous"
    assert "exactly the fields you requested" in result["turn"]["message"]


@pytest.mark.parametrize(
    "question",
    [
        "Draw a diagram of revenue and profit",
        "Draw a diagram only Karachi",
        "Draw a diagram of revenue before 2024",
    ],
)
def test_unknown_or_filtered_diagram_clarifies_before_any_model_or_data_query(
    integration, question
):
    env = integration
    owner, _, root, path, model = prepare(env)
    before = context(env, owner, root)
    result = ask(env, owner, path, question)
    assert result["answer"] is None and result["turn"]["kind"] == "ambiguous"
    assert not model.requests
    assert context(env, owner, root) == before
    with env.engine.connect() as connection:
        assert connection.execute(select(s.query_executions)).first() is None
    choice = result["turn"]["clarification"]["choices"][0]
    answer = ask(env, owner, path, choice)["answer"]
    assert answer["kind"] == "diagram" and answer["diagram"]["scope"] == "all_fields"
    assert answer["diagram"]["shown_fields"] == len(before["definition"]["columns"])


def test_visual_value_query_keeps_requested_sum_and_exact_result(integration):
    plan = {
        "kind": "numerical",
        "plan": {"metric": "revenue", "aggregation": "sum", "group_by": ["city"]},
    }
    owner, _, _, path, _ = prepare(integration, plan)
    answer = ask(integration, owner, path, "Visualize total revenue by city")["answer"]
    assert answer["lineage"]["aggregation"] == "sum" and answer["lineage"]["grouping"] == ["city"]
    assert {tuple(row) for row in answer["rows"]} == {
        ("KARACHI", "0.200000000000"),
        ("Karachi", "0.100000000000"),
        ("Lahore", "7.750000000000"),
    }


def test_model_cannot_replace_requested_calculation_with_diagram(integration):
    owner, _, _, path, _ = prepare(integration, {"kind": "diagram", "columns": []})
    result = ask(integration, owner, path, "Visualize total revenue by city")
    assert result["answer"] is None and result["turn"]["kind"] == "ambiguous"
    assert "calculated values" in result["turn"]["message"]


def test_diagram_job_records_real_tool_and_private_replay(integration):
    env = integration
    owner, wid, _, path = job_setup(env)
    job = submit(env, owner, path, "Draw a diagram")
    assert process(env) == {"processed": 1}
    result = env.client.get(job_path(job) + "/result", headers=owner).json()
    assert result["answer"]["kind"] == "diagram"
    with env.engine.connect() as conn:
        plan = conn.execute(select(s.jobs.c.plan)).scalar_one()["value"]
        assert [step["operation"] for step in plan["steps"]] == [
            "map_dataset_structure",
            "assemble_evidence",
        ]
        assert conn.execute(select(s.query_executions)).first() is None
    events = env.client.get(job_path(job) + "/events", headers=owner).json()["events"]
    assert any(
        event["stage"] == "verifying_evidence" and event["status"] == "completed"
        for event in events
    )
    member, _ = add_member(env, owner, wid, "admin")
    assert env.client.get(path, headers=member).status_code == 404
    assert (
        env.client.get(path + f"/turns/{result['turn']['id']}/answer", headers=member).status_code
        == 404
    )
    assert env.client.get(job_path(job) + "/result", headers=member).status_code == 404
    assert env.client.get(path.replace(str(wid), str(uuid4())), headers=owner).status_code == 404


def test_diagram_old_meaning_reopens_unchanged_and_tampered_graph_is_rejected(integration):
    env = integration
    owner, _, root, path, _ = prepare(env)
    first = ask(env, owner, path, "Draw a diagram")
    current = context(env, owner, root)
    current["definition"]["columns"][0]["meaning"] = "A revised meaning"
    assert confirm(env, owner, root, current).status_code == 201
    answer_path = path + f"/turns/{first['turn']['id']}/answer"
    assert env.client.get(answer_path, headers=owner).json() == first["answer"]
    fresh = ask(env, owner, path, "Draw a diagram")
    assert fresh["answer"] != first["answer"]
    with env.engine.begin() as conn:
        tid = UUID(first["turn"]["id"])
        evidence = copy.deepcopy(
            conn.execute(
                select(s.thread_turns.c.evidence).where(s.thread_turns.c.id == tid)
            ).scalar_one()
        )
        evidence["diagram"]["result"]["edges"][0]["relation"] = "causes"
        conn.execute(
            update(s.thread_turns).where(s.thread_turns.c.id == tid).values(evidence=evidence)
        )
    assert env.client.get(answer_path, headers=owner).status_code == 409


def test_definition_change_during_diagram_build_prevents_publication(integration, monkeypatch):
    env = integration
    owner, _, root, path, _ = prepare(env)
    router = env.client.app.dependency_overrides[get_intent_router_service]()
    original = router.analytics.recheck_description

    def changed(*args):
        current = context(env, owner, root)
        current["definition"]["description"] = "Changed while mapping"
        assert confirm(env, owner, root, current).status_code == 201
        original(*args)

    monkeypatch.setattr(router.analytics, "recheck_description", changed)
    result = ask(env, owner, path, "Draw a diagram")
    assert result["answer"] is None and result["turn"]["kind"] == "ambiguous"
    assert "changed" in result["turn"]["message"]


def test_meaning_change_after_diagram_return_is_rechecked_at_publication(integration, monkeypatch):
    env = integration
    owner, _, root, path = job_setup(env)
    original = env.runtime.intent_router.ask

    def change_meaning():
        current = context(env, owner, root)
        current["definition"]["description"] = "Changed before publication"
        assert confirm(env, owner, root, current).status_code == 201

    async def changed_after_result(*args, **kwargs):
        answer = await original(*args, **kwargs)
        await asyncio.to_thread(change_meaning)
        return answer

    monkeypatch.setattr(env.runtime.intent_router, "ask", changed_after_result)
    response = env.client.post(
        path + "/ask",
        headers=owner,
        json={"question": "Draw a diagram", "request_id": str(uuid4())},
    )
    assert response.status_code == 409
    with env.engine.connect() as connection:
        turn = connection.execute(select(s.thread_turns)).mappings().one()
    assert turn["status"] == "failed" and turn["evidence"] == {} and turn["query_id"] is None


def test_diagram_clarification_choice_cannot_use_changed_definition(integration):
    env = integration
    owner, _, root, path, _ = prepare(env)
    first = ask(env, owner, path, "Draw a diagram of what causes revenue")
    assert first["turn"]["clarification"]["choices"]
    current = context(env, owner, root)
    current["definition"]["description"] = "Changed while choosing"
    assert confirm(env, owner, root, current).status_code == 201
    result = ask(env, owner, path, first["turn"]["clarification"]["choices"][0])
    assert result["answer"] is None and "changed" in result["turn"]["message"]
