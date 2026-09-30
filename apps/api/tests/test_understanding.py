"""Use case: Proves business definitions affect exact answers without changing historical evidence.

What it does: Checks inference, mappings, privacy and revision conflicts.
"""

import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import delete

from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.ingestion import IngestionError
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import AggregationKind, MetricRequest, dataset_view
from execplus.domain.understanding import (
    apply_definition,
    governed_request,
    infer_definition,
    validate_definition,
)
from execplus.infrastructure.persistence import schema as s
from test_conversational_explorer import ScriptedModel, prepare
from test_workspace_integration import accept, dataset, identity, invite, upload, workspace


def test_inference_distinguishes_identifiers_ratings_and_order_items():
    table = TableData(("order_id", "rating", "revenue"), (("1", "4", "10"), ("1", "5", "20")))
    definition = infer_definition(profile(table))
    assert definition["grain"] == "order_item"
    assert [column["role"] for column in definition["columns"]] == [
        "identifier",
        "ordinal",
        "metric",
    ]
    definition["grain"] = "order"
    with pytest.raises(IngestionError, match="Repeated or missing"):
        validate_definition(definition, table, profile(table), "confirmed")


@pytest.mark.parametrize(
    "mutation",
    [
        lambda definition: definition["columns"][0].update(role="metric"),
        lambda definition: definition["columns"][1].update(currency="??"),
        lambda definition: definition["columns"][1].update(unit_column="unknown"),
        lambda definition: definition["columns"][1].update(timezone="Not/AZone"),
        lambda definition: definition["columns"][1].update(tags=["arbitrary"]),
        lambda definition: definition.update(grain="unknown"),
        lambda definition: definition["columns"].append(definition["columns"][0]),
    ],
)
def test_invalid_or_ambiguous_definitions_are_not_confirmed(mutation):
    table = TableData(("city", "value"), (("Karachi", "10"),))
    definition = infer_definition(profile(table))
    definition["grain"] = "record"
    mutation(definition)
    with pytest.raises(IngestionError):
        validate_definition(definition, table, profile(table), "confirmed")


def test_mixed_units_and_review_required_missing_values_cannot_be_summed():
    table = TableData(("amount", "currency"), (("10", "PKR"), ("20", "USD")))
    request = MetricRequest("amount", AggregationKind.SUM)
    with pytest.raises(ClarificationRequiredError, match="currency"):
        governed_request(dataset_view(profile(table)), table, request)
    table = TableData(("amount",), (("10",), ("",)))
    definition = infer_definition(profile(table))
    definition["columns"][0]["missing_policy"] = "needs_review"
    with pytest.raises(ClarificationRequiredError, match="missing-value"):
        governed_request(apply_definition(dataset_view(profile(table)), definition), table, request)


def context(env, headers, root):
    response = env.client.get(root + "/understanding", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def confirm(env, headers, root, current, definition=None, state="confirmed"):
    value = copy.deepcopy(definition or current["definition"])
    value["grain"] = "record"
    return env.client.post(
        root + "/understanding",
        headers=headers,
        json=dict(
            revision_id=current["revision_id"],
            expected_version=current["version"],
            state=state,
            definition=value,
        ),
    )


def test_definition_changes_query_and_historical_receipt_remains_replayable(integration):
    env = integration
    plan = {"kind": "numerical", "plan": {"metric": "amount", "aggregation": "sum"}}
    primary = ScriptedModel(plan, plan)
    headers, wid, root = prepare(
        env,
        primary,
        content=b"city,amount,status,custno\nKarachi,0.10,paid,1001\nKarachi,0.20,cancelled,1002\n",
    )
    original = env.client.post(root + "/ask", headers=headers, json={"question": "Total amount?"})
    assert original.status_code == 200, original.text
    data = context(env, headers, root)
    data["definition"]["columns"][3]["role"] = "identifier"
    data["definition"]["metrics"] = [
        dict(
            name="paid revenue",
            column="amount",
            aggregation="sum",
            filters=[dict(column="status", operator="eq", value="paid")],
        )
    ]
    saved = confirm(env, headers, root, data)
    assert saved.status_code == 201, saved.text
    answer = env.client.post(root + "/ask", headers=headers, json={"question": "Paid revenue?"})
    assert answer.status_code == 200, answer.text
    assert str(answer.json()["value"]).startswith("0.1")
    assert "paid revenue" in primary.requests[-1].messages[-1].content
    assert (
        answer.json()["lineage"]["receipt"]["sources"][0]["understanding_id"] == saved.json()["id"]
    )
    unsupported = env.client.post(
        root + "/query", headers=headers, json={"metric": "custno", "aggregation": "sum"}
    )
    assert unsupported.status_code == 422
    next_context = context(env, headers, root)
    next_context["definition"]["metrics"][0]["filters"][0]["value"] = "cancelled"
    assert confirm(env, headers, root, next_context).status_code == 201
    for result in [original, answer]:
        query_id = result.json()["lineage"]["query_id"]
        replay = env.client.post(f"/workspaces/{wid}/queries/{query_id}/replay", headers=headers)
        assert replay.status_code == 200, replay.text
    assert len(context(env, headers, root)["history"]) == 2
    original_definition = env.client.get(
        f"{root.split('/uploads/')[0]}/understandings/{saved.json()['id']}", headers=headers
    )
    assert original_definition.status_code == 200
    assert original_definition.json()["definition"]["metrics"][0]["filters"][0]["value"] == "paid"
    audit = env.client.get(f"/workspaces/{wid}/audit-events", headers=headers).text
    assert "paid revenue" not in audit and "cancelled" not in audit


def test_stale_writes_rejected_and_private_preferences_do_not_leak(integration):
    env = integration
    owner, _ = identity(env, "owner-context@example.test")
    wid = workspace(env, owner)
    did = dataset(env, owner, wid)
    uid = upload(env, owner, wid, did).json()["id"]
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{uid}"
    member, member_user = identity(env, "member-context@example.test")
    iid = invite(env, owner, wid, member_user.email).json()["id"]
    accept(env, member, wid, iid)
    personal = env.client.post(
        f"/workspaces/{wid}/datasets/{did}/preferences",
        headers=owner,
        json={"domain_hint": "research", "goal": "Private acquisition review"},
    )
    assert personal.status_code == 200
    current = context(env, owner, root)
    assert current["definition"]["domain"] == "research"
    assert context(env, member, root)["preference"]["goal"] == ""
    assert confirm(env, member, root, current).status_code == 403
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: confirm(env, owner, root, current), range(2)))
    assert sorted(result.status_code for result in responses) == [201, 409]
    assert confirm(env, owner, root, current).status_code == 409
    foreign, _ = identity(env, "foreign-context@example.test")
    for path in [root + "/understanding"]:
        assert env.client.get(path, headers=foreign).status_code == 404
    with env.engine.begin() as connection:
        connection.execute(
            delete(s.memberships).where(
                s.memberships.c.workspace_id == UUID(wid), s.memberships.c.user_id == member_user.id
            )
        )
    assert env.client.get(root + "/understanding", headers=member).status_code == 404


def test_new_upload_requires_review_without_overwriting_human_definition(integration):
    env = integration
    headers, _ = identity(env, "versions@example.test")
    wid = workspace(env, headers)
    did = dataset(env, headers, wid)
    uid = upload(env, headers, wid, did).json()["id"]
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{uid}"
    initial = context(env, headers, root)
    initial["definition"]["description"] = "Approved business meaning"
    assert confirm(env, headers, root, initial).status_code == 201
    next_uid = upload(env, headers, wid, did, b"item,amount,city\na,20,Lahore\n").json()["id"]
    next_root = f"/workspaces/{wid}/datasets/{did}/uploads/{next_uid}"
    pending = context(env, headers, next_root)
    assert pending["state"] == "needs_review"
    assert pending["definition"]["description"] == "Approved business meaning"
    query = env.client.post(
        next_root + "/query", headers=headers, json={"metric": "amount", "aggregation": "sum"}
    )
    assert query.status_code == 422, query.text
    assert query.json()["error"]["code"] == "clarification_required"
    assert confirm(env, headers, next_root, pending).status_code == 201
    assert (
        env.client.post(
            next_root + "/query", headers=headers, json={"metric": "amount", "aggregation": "sum"}
        ).status_code
        == 200
    )
    current = context(env, headers, next_root)
    assert confirm(env, headers, next_root, current, state="rejected").status_code == 201
    assert (
        env.client.post(
            next_root + "/query", headers=headers, json={"metric": "amount", "aggregation": "sum"}
        ).status_code
        == 422
    )


def test_dashboard_uses_confirmed_average_and_required_filter(integration):
    env = integration
    headers, _, root = prepare(
        env,
        ScriptedModel(),
        content=b"city,value,status\nKarachi,10,paid\nKarachi,20,paid\nLahore,100,cancelled\n",
    )
    current = context(env, headers, root)
    current["definition"]["metrics"] = [
        dict(
            name="Average paid value",
            column="value",
            aggregation="avg",
            filters=[dict(column="status", operator="eq", value="paid")],
        )
    ]
    assert confirm(env, headers, root, current).status_code == 201
    result = env.client.post(root + "/dashboard", headers=headers, json={})
    assert result.status_code == 200, result.text
    body = result.json()
    assert Decimal(body["cards"][0]["rows"][0][0]) == Decimal("15")
    assert body["cards"][0]["lineage"]["aggregation"] == "avg"
    assert Decimal(body["breakdown"]["rows"][0][-1]) == Decimal("15")
    wrong = env.client.post(
        root + "/query", headers=headers, json={"metric": "value", "aggregation": "sum"}
    )
    assert wrong.status_code == 422


@pytest.mark.parametrize("kind", ["numerical", "grouped", "rows"])
def test_changed_definition_during_model_planning_never_executes(integration, kind):
    env = integration
    response = {"kind": "numerical", "plan": {"metric": "amount", "aggregation": "sum"}}
    if kind == "grouped":
        response["plan"]["group_by"] = ["city"]
    elif kind == "rows":
        response = {"kind": "rows", "plan": {"columns": ["city", "amount"], "limit": 10}}

    class ChangingModel(ScriptedModel):
        async def complete(self, request):
            current = await asyncio.to_thread(context, env, headers, root)
            saved = await asyncio.to_thread(confirm, env, headers, root, current)
            assert saved.status_code == 201
            return await super().complete(request)

    headers, _, root = prepare(
        env, ChangingModel(response), content=b"city,amount\nKarachi,10\nLahore,20\n"
    )
    result = env.client.post(root + "/ask", headers=headers, json={"question": "Analyze amount"})
    assert result.status_code == 422, result.text
    assert "changed while planning" in result.text
    with env.engine.connect() as connection:
        assert connection.execute(s.query_executions.select()).first() is None


def test_relationship_review_rejects_duplicate_keys_and_preserves_old_replay(integration):
    env = integration
    headers, _ = identity(env, "relationships@example.test")
    wid = workspace(env, headers)
    left_id, right_id = dataset(env, headers, wid), dataset(env, headers, wid)
    left_uid = upload(env, headers, wid, left_id, b"sku,amount\nA,10\nA,20\nB,30\n").json()["id"]
    right_uid = upload(env, headers, wid, right_id, b"sku,category\nA,Red\nB,Blue\n").json()["id"]
    left_root = f"/workspaces/{wid}/datasets/{left_id}/uploads/{left_uid}"
    right_root = f"/workspaces/{wid}/datasets/{right_id}/uploads/{right_uid}"
    path = env.client.post(
        f"/workspaces/{wid}/join-paths",
        headers=headers,
        json=dict(
            left_dataset_id=left_id,
            left_column="sku",
            right_dataset_id=right_id,
            right_column="sku",
        ),
    )
    assert path.status_code == 201
    path_id = path.json()["id"]
    query_path = f"/workspaces/{wid}/join-paths/{path_id}/query"
    query = dict(
        left_upload_id=left_uid,
        right_upload_id=right_uid,
        metric="amount",
        aggregation="sum",
        group_by=["category"],
    )
    left = context(env, headers, left_root)
    assert left["relationship_options"][0]["id"] == path_id
    left["definition"]["relationships"] = [
        dict(join_path_id=path_id, state="confirmed", cardinality="one_to_one")
    ]
    assert confirm(env, headers, left_root, left).status_code == 422
    left["definition"]["relationships"][0]["cardinality"] = "many_to_one"
    assert confirm(env, headers, left_root, left).status_code == 201
    right = context(env, headers, right_root)
    assert confirm(env, headers, right_root, right).status_code == 201
    assert env.client.post(query_path, headers=headers, json=query).status_code == 422
    right = context(env, headers, right_root)
    right["definition"]["relationships"] = copy.deepcopy(left["definition"]["relationships"])
    assert confirm(env, headers, right_root, right).status_code == 201
    answer = env.client.post(query_path, headers=headers, json=query)
    assert answer.status_code == 200, answer.text
    assert {(row[0], Decimal(row[1])) for row in answer.json()["rows"]} == {
        ("Red", Decimal(30)),
        ("Blue", Decimal(30)),
    }
    left = context(env, headers, left_root)
    left["definition"]["relationships"][0]["state"] = "rejected"
    assert confirm(env, headers, left_root, left).status_code == 201
    assert env.client.post(query_path, headers=headers, json=query).status_code == 422
    query_id = answer.json()["lineage"]["query_id"]
    assert (
        env.client.post(f"/workspaces/{wid}/queries/{query_id}/replay", headers=headers).status_code
        == 200
    )


def test_category_hint_does_not_change_types_and_ambiguous_dates_prompt_review():
    table = TableData(
        ("survey_date", "person_id", "likert", "zqx"),
        (("01/02/2026", "1001", "4", "12"), ("02/03/2026", "1002", "5", "14")),
    )
    from execplus.domain.understanding import questions

    current = profile(table)
    inferred = infer_definition(current, "inventory")
    assert inferred["domain"] == "inventory"
    roles = {column["name"]: column["role"] for column in inferred["columns"]}
    assert roles["person_id"] == "identifier"
    assert roles["likert"] == "ordinal"
    assert roles["zqx"] == "metric"
    assert any("ambiguous dates" in question for question in questions(inferred, current))
