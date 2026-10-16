"""Use case: Verifies opt-in actor-scoped row and column authorization.

What it does: Exercises exact projected calculations, metadata privacy, immutable
receipts, explicit management and policy changes against real isolated services.
"""

import copy
import hashlib
import json
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from execplus.domain.dataset_access import DatasetAccess, project_table, validate_grants
from execplus.domain.ingestion import IngestionError
from execplus.domain.profiling import TableData, profile
from execplus.domain.public_evidence import public_evidence
from execplus.domain.semantics import dataset_view
from execplus.infrastructure.persistence import schema as s
from test_studies import add_member, prepare
from test_workspace_integration import accept, identity, invite

CONTENT = b"city,amount,cost\nKarachi,0.10,10\nKarachi,0.20,20\nLahore,9999,9000\n"


def fixture(env, *, columns=None, conditions=None, owner_grant=True, role="member"):
    owner, actor, wid, did, uid, root = prepare(env, CONTENT)
    member, user = add_member(env, owner, wid, role)
    path = f"/workspaces/{wid}/datasets/{did}/access-policy"
    grants = [dict(user_id=str(actor.id), columns=None, conditions=[])] if owner_grant else []
    grants.append(
        dict(
            user_id=str(user.id),
            columns=columns if columns is not None else ["city", "amount"],
            conditions=conditions
            if conditions is not None
            else [dict(column="city", operator="eq", value="Karachi")],
        )
    )
    raw = dict(expected_version=0, enabled=True, grants=grants)
    saved = env.client.put(path, headers=owner, json=raw)
    assert saved.status_code == 200, saved.text
    return owner, actor, member, user, wid, did, uid, root, path, raw


def query(env, headers, root, **changes):
    return env.client.post(
        root + "/query", headers=headers, json={"metric": "amount", "aggregation": "sum", **changes}
    )


def test_projected_exact_query_rows_profile_schema_dashboard_and_discovery(integration):
    env = integration
    owner, _, member, actor, _, _, _, root, _, _ = fixture(env)
    response = query(env, member, root)
    assert response.status_code == 200, response.text
    answer = response.json()
    assert Decimal(answer["rows"][0][0]) == Decimal("0.30")
    assert answer["records_analyzed"] == 2
    source = answer["lineage"]["receipt"]["sources"][0]
    assert source["access_actor_id"] == str(actor.id) and source["access_policy_version"] == "1"
    rows = env.client.post(root + "/rows", headers=member, json={})
    assert rows.status_code == 200, rows.text
    assert rows.json()["columns"] == ["city", "amount"]
    assert len(rows.json()["rows"]) == 2 and "Lahore" not in rows.text
    for suffix in ("/profile", "/schema", "/discovery", "/insights"):
        limited = env.client.get(root + suffix, headers=member)
        assert limited.status_code == 200, (suffix, limited.text)
        assert '"cost"' not in limited.text and "Lahore" not in limited.text
    dashboard = env.client.post(root + "/dashboard", headers=member, json={})
    assert dashboard.status_code == 200, dashboard.text
    assert '"cost"' not in dashboard.text and "9999" not in dashboard.text
    raw = env.client.get(root + "/content", headers=owner)
    assert raw.content == CONTENT
    original = env.client.get(root + "/profile", headers=owner).json()
    assert original["profile"]["row_count"] == 3


def test_metadata_catalog_and_review_never_return_hidden_fields_values_or_raw_sizes(integration):
    env = integration
    _, _, member, _, wid, did, _, root, _, _ = fixture(env)
    uploaded = env.client.get(root, headers=member)
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["row_count"] == 2 and uploaded.json()["column_count"] == 2
    assert uploaded.json()["size"] is None and uploaded.json()["checksum"] is None
    for suffix in ("/understanding", "/revisions"):
        response = env.client.get(root + suffix, headers=member)
        assert response.status_code == 200, response.text
        assert '"cost"' not in response.text and "Lahore" not in response.text
    catalog = env.client.get(f"/workspaces/{wid}/catalog", headers=member)
    assert catalog.status_code == 200, catalog.text
    assert '"cost"' not in catalog.text
    assert catalog.json()[0]["documents"] == []
    assert env.client.get(root + "/content", headers=member).status_code == 403
    assert env.client.get(root + "/artifacts", headers=member).status_code == 403
    assert (
        env.client.get(f"/workspaces/{wid}/datasets/{did}/documents", headers=member).json() == []
    )


def test_explicit_unknown_field_or_filter_cannot_expand_authorized_population(integration):
    env = integration
    _, _, member, _, _, _, _, root, _, _ = fixture(env)
    hidden = query(env, member, root, metric="cost")
    assert hidden.status_code == 422, hidden.text
    blocked = query(env, member, root, filters=[dict(column="cost", operator="gt", value="0")])
    assert blocked.status_code == 422, blocked.text
    outside = query(env, member, root, filters=[dict(column="city", operator="eq", value="Lahore")])
    assert outside.status_code == 200, outside.text
    assert outside.json()["rows"] == [[None]]


def test_owner_and_admin_have_no_implicit_data_bypass_but_owner_can_recover(integration):
    env = integration
    owner, actor, member, _, wid, did, _, root, path, raw = fixture(
        env, owner_grant=False, role="admin"
    )
    assert query(env, owner, root).status_code == 404
    assert env.client.get(f"/workspaces/{wid}/datasets", headers=owner).json() == []
    assert env.client.get(f"/workspaces/{wid}/dataset-access", headers=owner).json() == {
        "datasets": [{"id": did, "name": "Sales"}]
    }
    assert env.client.get(path, headers=member).status_code == 403
    assert (
        env.client.put(path, headers=member, json={**raw, "expected_version": 1}).status_code == 403
    )
    restored = copy.deepcopy(raw)
    restored["expected_version"] = 1
    restored["grants"].append(dict(user_id=str(actor.id), columns=None, conditions=[]))
    assert env.client.put(path, headers=owner, json=restored).status_code == 200
    assert Decimal(query(env, owner, root).json()["rows"][0][0]) == Decimal("9999.30")
    assert env.client.put(path, headers=owner, json=restored).status_code == 409


def test_receipt_scope_epoch_replay_cross_actor_and_immutable_storage(integration):
    env = integration
    owner, _, member, _, wid, _, _, root, path, raw = fixture(env)
    answer = query(env, member, root).json()
    qid = answer["lineage"]["query_id"]
    query_path = f"/workspaces/{wid}/queries/{qid}"
    assert env.client.post(query_path + "/replay", headers=member).json() == answer
    assert env.client.get(query_path, headers=owner).status_code == 404
    assert env.client.post(query_path + "/replay", headers=owner).status_code == 404
    with env.engine.connect() as connection:
        before = connection.execute(
            select(s.query_executions.c.receipt).where(s.query_executions.c.id == UUID(qid))
        ).scalar_one()
    assert (
        env.client.put(path, headers=owner, json={**raw, "expected_version": 1}).status_code == 200
    )
    assert env.client.get(query_path, headers=member).status_code == 404
    assert env.client.post(query_path + "/replay", headers=member).status_code == 404
    with env.engine.connect() as connection:
        after = connection.execute(
            select(s.query_executions.c.receipt).where(s.query_executions.c.id == UUID(qid))
        ).scalar_one()
    assert before == after


def test_restricted_public_provenance_withholds_original_fingerprints_but_replays(integration):
    env = integration
    owner, _, member, _, wid, _, _, root, _, _ = fixture(env)
    answer = query(env, member, root).json()
    qid = answer["lineage"]["query_id"]
    with env.engine.connect() as connection:
        private_receipt = connection.execute(
            select(s.query_executions.c.receipt).where(s.query_executions.c.id == UUID(qid))
        ).scalar_one()
    original = private_receipt["sources"][0]
    original_hash = hashlib.sha256(CONTENT).hexdigest()
    assert original["source_checksum"] == original_hash
    assert original["output_checksum"]
    assert original["access_restricted"] == "true"
    source = answer["lineage"]["receipt"]["sources"][0]
    assert "source_checksum" not in source and "output_checksum" not in source
    assert source["fingerprints"] == "withheld_for_restricted_access"
    thread = env.client.post(root + "/threads", headers=member).json()
    diagram = env.client.post(
        f"/workspaces/{wid}/threads/{thread['id']}/ask",
        headers=member,
        json={"question": "Draw a diagram of this data"},
    )
    assert diagram.status_code == 200, diagram.text
    paths = [
        root,
        root + "/profile",
        root + "/understanding",
        root + "/revisions",
        root + "/discovery",
        root + "/insights",
        f"/workspaces/{wid}/queries/{qid}",
        f"/workspaces/{wid}/threads/{thread['id']}",
    ]
    bodies = [json.dumps(answer), diagram.text]
    for path in paths:
        response = env.client.get(path, headers=member)
        assert response.status_code == 200, response.text
        bodies.append(response.text)
    replay = env.client.post(f"/workspaces/{wid}/queries/{qid}/replay", headers=member)
    assert replay.status_code == 200 and replay.json() == answer
    bodies.append(replay.text)
    for body in bodies:
        assert original_hash not in body and original["output_checksum"] not in body
    full = query(env, owner, root).json()["lineage"]["receipt"]["sources"][0]
    assert full["source_checksum"] == original_hash and full["access_restricted"] == "false"
    with env.engine.connect() as connection:
        assert (
            connection.execute(
                select(s.query_executions.c.receipt).where(s.query_executions.c.id == UUID(qid))
            ).scalar_one()
            == private_receipt
        )


def test_public_evidence_preserves_private_input_and_unrestricted_result_fingerprints():
    restricted = dict(access_restricted="true", source_checksum="hidden", output_checksum="hidden")
    unrestricted = dict(source_checksum="legacy", output_checksum="legacy")
    original = {"sources": [restricted, unrestricted], "result_checksum": "visible-result"}
    snapshot = copy.deepcopy(original)
    result = public_evidence(original)
    assert original == snapshot
    assert result["sources"][0] == {
        "access_restricted": "true",
        "fingerprints": "withheld_for_restricted_access",
    }
    assert result["sources"][1] == unrestricted
    assert result["result_checksum"] == "visible-result"


def test_removed_then_readded_membership_does_not_reactivate_old_grant(integration):
    env = integration
    owner, _, member, user, wid, _, _, root, _, _ = fixture(env)
    assert (
        env.client.delete(f"/workspaces/{wid}/members/{user.id}", headers=owner).status_code == 204
    )
    assert query(env, member, root).status_code == 404
    invitation = invite(env, owner, wid, user.email).json()
    assert accept(env, member, wid, invitation["id"]).status_code == 200
    assert query(env, member, root).status_code == 404


def test_hidden_filter_column_filters_before_projection_and_empty_scope_stays_empty(integration):
    env = integration
    _, _, member, _, _, _, _, root, _, _ = fixture(
        env, columns=["amount"], conditions=[dict(column="cost", operator="lt", value="100")]
    )
    result = query(env, member, root)
    assert result.status_code == 200, result.text
    assert Decimal(result.json()["rows"][0][0]) == Decimal("0.30")
    rows = env.client.post(root + "/rows", headers=member, json={}).json()
    assert rows["columns"] == ["amount"] and len(rows["rows"]) == 2


@pytest.mark.parametrize(
    "operator,expected",
    [
        ("eq", ("2",)),
        ("ne", ("1", "3")),
        ("lt", ("1",)),
        ("lte", ("1", "2")),
        ("gt", ("3",)),
        ("gte", ("2", "3")),
    ],
)
def test_typed_filter_operators_and_missing_values(operator, expected):
    table = TableData(("amount", "secret"), (("1", "a"), ("2", "b"), ("3", "c"), ("", "d")))
    view = dataset_view(profile(table))
    grants = validate_grants(
        [
            dict(
                user_id="actor",
                columns=["amount"],
                conditions=[dict(column="amount", operator=operator, value="2")],
            )
        ],
        view,
        {"actor"},
    )
    scope = DatasetAccess(uuid4(), columns=("amount",), conditions=tuple(grants[0]["conditions"]))
    assert project_table(table, view, scope).rows == tuple((value,) for value in expected)


@pytest.mark.parametrize(
    "condition",
    [
        dict(column="unknown", operator="eq", value="2"),
        dict(column="amount", operator="SQL", value="2"),
        dict(column="amount", operator="eq", value="NaN"),
        dict(column="amount", operator="eq", value="not a number"),
    ],
)
def test_invalid_policy_values_fail_before_any_policy_is_written(condition):
    view = dataset_view(profile(TableData(("amount",), (("1",), ("2",)))))
    with pytest.raises(IngestionError):
        validate_grants(
            [dict(user_id="actor", columns=None, conditions=[condition])], view, {"actor"}
        )


def test_new_conversation_and_model_planning_receive_only_authorized_fields(integration):
    from test_conversational_explorer import ScriptedModel

    env = integration
    owner, _, member, _, wid, _, _, root, path, raw = fixture(env)
    model = ScriptedModel({"kind": "numerical", "plan": {"metric": "amount", "aggregation": "sum"}})
    env.runtime.intent_router.model = model
    thread = env.client.post(root + "/threads", headers=member).json()
    thread_path = f"/workspaces/{wid}/threads/{thread['id']}"
    response = env.client.post(
        thread_path + "/ask", headers=member, json={"question": "Total amount?"}
    )
    assert response.status_code == 200, response.text
    assert Decimal(response.json()["answer"]["value"]) == Decimal("0.30")
    prompt = " ".join(message.content for request in model.requests for message in request.messages)
    assert '"cost"' not in prompt and "Lahore" not in prompt and "9999" not in prompt
    turn_id = response.json()["turn"]["id"]
    assert (
        env.client.get(thread_path + f"/turns/{turn_id}/answer", headers=member).json()
        == response.json()["answer"]
    )
    diagram = env.client.post(
        thread_path + "/ask", headers=member, json={"question": "Draw a diagram of this data"}
    )
    assert diagram.status_code == 200, diagram.text
    assert diagram.json()["answer"]["kind"] == "diagram"
    assert '"cost"' not in diagram.text
    assert (
        env.client.put(path, headers=owner, json={**raw, "expected_version": 1}).status_code == 200
    )
    assert env.client.get(thread_path, headers=member).status_code == 404
    assert (
        env.client.get(thread_path + f"/turns/{turn_id}/answer", headers=member).status_code == 404
    )
    assert env.client.get(root + "/threads", headers=member).json() == []


def test_queued_job_revoked_before_planning_never_calls_model_or_publishes(integration):
    import asyncio

    from test_conversational_explorer import ScriptedModel

    env = integration
    owner, _, member, _, wid, _, _, root, path, raw = fixture(env)
    model = ScriptedModel({"kind": "numerical", "plan": {"metric": "amount", "aggregation": "sum"}})
    env.runtime.intent_router.model = model
    thread = env.client.post(root + "/threads", headers=member).json()
    thread_path = f"/workspaces/{wid}/threads/{thread['id']}"
    job = env.client.post(
        thread_path + "/jobs",
        headers=member,
        json={"question": "Total amount?", "request_id": str(uuid4())},
    )
    assert job.status_code == 202, job.text
    assert (
        env.client.put(path, headers=owner, json={**raw, "expected_version": 1}).status_code == 200
    )
    assert asyncio.run(env.runtime.jobs.process()) == {"processed": 0}
    assert model.requests == []
    assert (
        env.client.get(
            f"/workspaces/{wid}/jobs/{job.json()['id']}/result", headers=member
        ).status_code
        == 404
    )
    with env.engine.connect() as connection:
        assert connection.execute(select(s.query_executions.c.id)).all() == []
        turn = connection.execute(select(s.thread_turns.c.status)).scalar_one()
        assert turn == "failed"
        assert connection.execute(select(s.jobs.c.failure_code)).scalar_one() == "unauthorized"


@pytest.mark.parametrize("restricted", [False, True])
@pytest.mark.parametrize("model_available", [False, True])
def test_durable_rows_enforces_scope_and_distinguishes_disabled_planning(
    integration, restricted, model_available
):
    import asyncio

    from execplus.infrastructure.models.disabled import DisabledLanguageModel
    from test_conversational_explorer import ScriptedModel

    env = integration
    if restricted:
        _, _, headers, _, wid, _, _, root, _, _ = fixture(env)
    else:
        headers, _, wid, _, _, root = prepare(env, CONTENT)
    env.runtime.intent_router.model = (
        ScriptedModel({"kind": "rows", "plan": {"columns": [], "filters": [], "limit": 10}})
        if model_available
        else DisabledLanguageModel()
    )
    thread = env.client.post(root + "/threads", headers=headers).json()
    thread_path = f"/workspaces/{wid}/threads/{thread['id']}"
    submitted = env.client.post(
        thread_path + "/jobs",
        headers=headers,
        json={"question": "Show the first 10 records", "request_id": str(uuid4())},
    )
    assert submitted.status_code == 202, submitted.text
    assert asyncio.run(env.runtime.jobs.process()) == {"processed": 1}
    path = f"/workspaces/{wid}/jobs/{submitted.json()['id']}"
    status = env.client.get(path, headers=headers).json()
    response = env.client.get(path + "/result", headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()
    events = env.client.get(path + "/events", headers=headers).json()["events"]
    if not model_available:
        assert status["status"] == "failed" and status["failure_code"] == "execution_failed"
        assert result["answer"] is None and result["turn"]["status"] == "failed"
        assert not any(event["stage"] == "executing_query" for event in events)
        with env.engine.connect() as connection:
            assert connection.execute(select(s.query_executions.c.id)).all() == []
        return
    assert status["status"] == "succeeded", status
    answer = result["answer"]
    assert answer["columns"] == (["city", "amount"] if restricted else ["city", "amount", "cost"])
    assert len(answer["rows"]) == (2 if restricted else 3)
    if restricted:
        assert '"cost"' not in response.text and "Lahore" not in response.text
    assert any(event["stage"] == "executing_query" for event in events)
    assert (
        env.client.get(
            thread_path + f"/turns/{result['turn']['id']}/answer", headers=headers
        ).json()
        == answer
    )


def test_policy_change_during_exact_execution_prevents_receipt_publication(
    integration, monkeypatch
):
    env = integration
    _, owner_actor, member, _, wid, did, _, root, _, raw = fixture(env)
    original = env.runtime.analytics.executor.execute

    async def change(*args, **kwargs):
        result = await original(*args, **kwargs)
        env.runtime.access_policies.save(owner_actor, UUID(wid), UUID(did), 1, True, raw["grants"])
        return result

    monkeypatch.setattr(env.runtime.analytics.executor, "execute", change)
    response = query(env, member, root)
    assert response.status_code == 404, response.text
    with env.engine.connect() as connection:
        assert connection.execute(select(s.query_executions.c.id)).all() == []


def test_saved_question_runs_and_shared_scope_never_bypasses_policy(integration):
    env = integration
    owner, _, member, _, wid, _, _, root, path, raw = fixture(env)
    created = env.client.post(
        root + "/saved-items",
        headers=member,
        json={
            "kind": "question",
            "name": "My scoped amount",
            "payload": {"metric": "amount", "aggregation": "sum"},
            "shared": True,
        },
    )
    assert created.status_code == 201, created.text
    item_path = f"/workspaces/{wid}/saved-items/{created.json()['id']}"
    assert "access_reference" not in created.json()["payload"]
    result = env.client.post(item_path + "/run", headers=member)
    assert result.status_code == 200, result.text
    assert Decimal(result.json()["rows"][0][0]) == Decimal("0.30")
    assert env.client.get(item_path, headers=owner).status_code == 404
    assert env.client.get(root + "/saved-items", headers=owner).json() == []
    assert (
        env.client.put(path, headers=owner, json={**raw, "expected_version": 1}).status_code == 200
    )
    assert env.client.get(item_path, headers=member).status_code == 404
    assert env.client.get(root + "/saved-items", headers=member).json() == []


def test_unrelated_workspace_policy_never_changes_other_dataset_access(integration):
    from test_workspace_integration import dataset, upload, workspace

    env = integration
    owner, _, member, _, wid, _, _, _, _, _ = fixture(env)
    other = dataset(env, member, wid)
    uid = upload(env, member, wid, other).json()["id"]
    root = f"/workspaces/{wid}/datasets/{other}/uploads/{uid}"
    assert env.client.get(root + "/content", headers=owner).status_code == 200
    outsider, _ = identity(env, f"outsider-{uuid4().hex}@example.test")
    other_wid = workspace(env, outsider)
    assert (
        env.client.get(root.replace(wid, other_wid) + "/profile", headers=member).status_code == 404
    )


@pytest.mark.parametrize(
    "values,target,expected",
    [
        (("2026-01-01", "2026-01-02", ""), "2026-01-02", ("2026-01-02",)),
        (("true", "false", ""), "true", ("true",)),
        (("North", "north", ""), "North", ("North",)),
    ],
)
def test_date_boolean_and_text_conditions_preserve_declared_type(values, target, expected):
    table = TableData(("field",), tuple((value,) for value in values))
    view = dataset_view(profile(table))
    raw = [
        dict(
            user_id="actor",
            columns=None,
            conditions=[dict(column="field", operator="eq", value=target)],
        )
    ]
    conditions = tuple(validate_grants(raw, view, {"actor"})[0]["conditions"])
    scope = DatasetAccess(uuid4(), conditions=conditions)
    assert project_table(table, view, scope).rows == tuple((value,) for value in expected)


def test_policy_schema_change_never_silently_removes_condition_or_hidden_column():
    table = TableData(("amount", "region"), (("1", "North"), ("2", "South")))
    view = dataset_view(profile(table))
    raw = [
        dict(
            user_id="actor",
            columns=["amount"],
            conditions=[dict(column="region", operator="eq", value="North")],
        )
    ]
    scope = DatasetAccess(
        uuid4(),
        columns=("amount",),
        conditions=tuple(validate_grants(raw, view, {"actor"})[0]["conditions"]),
    )
    changed = TableData(("amount",), (("1",), ("2",)))
    with pytest.raises(IngestionError):
        project_table(changed, dataset_view(profile(changed)), scope)
    changed_type = TableData(("amount", "region"), (("1", "2"), ("2", "3")))
    with pytest.raises(IngestionError):
        project_table(changed_type, dataset_view(profile(changed_type)), scope)


def test_both_row_conditions_are_required_and_exact_decimal_boundary_is_preserved():
    table = TableData(
        ("amount", "region"),
        (("1.00000000000000001", "North"), ("1.00000000000000002", "North"), ("2", "South")),
    )
    view = dataset_view(profile(table))
    raw = [
        dict(
            user_id="actor",
            columns=["amount"],
            conditions=[
                dict(column="region", operator="eq", value="North"),
                dict(column="amount", operator="gt", value="1.00000000000000001"),
            ],
        )
    ]
    grant = validate_grants(raw, view, {"actor"})[0]
    scope = DatasetAccess(uuid4(), columns=("amount",), conditions=tuple(grant["conditions"]))
    assert project_table(table, view, scope).rows == (("1.00000000000000002",),)


def test_full_grants_keep_original_download_and_exact_calculations(integration):
    env = integration
    owner, _, member, _, _, _, _, root, path, raw = fixture(env)
    updated = copy.deepcopy(raw)
    updated["expected_version"] = 1
    updated["grants"][1]["columns"] = None
    updated["grants"][1]["conditions"] = []
    assert env.client.put(path, headers=owner, json=updated).status_code == 200
    assert env.client.get(root + "/content", headers=member).content == CONTENT
    result = query(env, member, root, metric="cost")
    assert result.status_code == 200, result.text
    assert Decimal(result.json()["rows"][0][0]) == Decimal("9030")


def test_restricted_metadata_and_source_mutations_fail_closed_without_leaking(integration):
    env = integration
    _, _, member, _, wid, did, _, root, _, _ = fixture(env, role="admin")
    for suffix in ("/audit-events", "/audit-history", "/usage", "/usage-analytics", "/onboarding"):
        response = env.client.get(f"/workspaces/{wid}" + suffix, headers=member)
        assert response.status_code == 403, (suffix, response.text)
        assert "Lahore" not in response.text and "9999" not in response.text
    for path in (
        f"/workspaces/{wid}/datasets/{did}/refresh",
        f"/workspaces/{wid}/datasets/{did}/monitors",
    ):
        response = env.client.get(path, headers=member)
        assert response.status_code == 403, (path, response.text)
        assert "Lahore" not in response.text
    assert env.client.post(root + "/data-brief", headers=member).status_code == 403
    response = env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads?filename=new.csv",
        headers={**member, "Content-Type": "text/csv"},
        content=b"city,amount,cost\nX,5,6\n",
    )
    assert response.status_code == 403, response.text
    assert (
        env.client.post(
            f"/workspaces/{wid}/datasets/{did}/knowledge/search",
            headers=member,
            json={"query": "payroll"},
        ).status_code
        == 403
    )


def test_policy_migration_preserves_existing_tables_and_refuses_nonempty_downgrade(integration):
    import json

    from alembic import command
    from sqlalchemy import inspect

    env = integration
    owner, _, wid, did, _, root = prepare(env, CONTENT)
    names = set(s.metadata.tables) - {
        "dataset_access_policies",
        "incidents",
        "incident_occurrences",
        "usage_prices",
        "usage_policies",
        "usage_attempts",
        "model_usage_events",
        "integration_keys",
        "integration_request_windows",
        "embed_grants",
        "webhook_subscriptions",
        "webhook_deliveries",
        "registered_sources",
        "source_imports",
        "consolidation_runs",
    }

    def snapshot():
        with env.engine.connect() as connection:
            return {
                name: sorted(
                    json.dumps(dict(row), sort_keys=True, default=str)
                    for row in connection.execute(select(s.metadata.tables[name])).mappings()
                )
                for name in names
            }

    before = snapshot()
    with env.engine.begin() as connection:
        env.config.attributes["connection"] = connection
        command.downgrade(env.config, "0018")
    assert "dataset_access_policies" not in inspect(env.engine).get_table_names()
    assert snapshot() == before
    with env.engine.begin() as connection:
        env.config.attributes["connection"] = connection
        command.upgrade(env.config, "head")
    assert snapshot() == before
    with env.engine.connect() as connection:
        for name in set(s.metadata.tables) - names:
            assert connection.execute(select(s.metadata.tables[name])).first() is None
    path = f"/workspaces/{wid}/datasets/{did}/access-policy"
    saved = env.client.put(
        path, headers=owner, json={"expected_version": 0, "enabled": True, "grants": []}
    )
    assert saved.status_code == 200
    assert query(env, owner, root).status_code == 404
    with (
        pytest.raises(RuntimeError, match="Preserve all dataset access policies"),
        env.engine.begin() as connection,
    ):
        env.config.attributes["connection"] = connection
        command.downgrade(env.config, "0018")
    assert env.client.get(path, headers=owner).json()["version"] == 1


def test_policy_change_during_model_planning_discards_the_old_scope(integration):
    from test_conversational_explorer import ScriptedModel

    env = integration
    _, owner_actor, member, _, wid, did, _, root, _, raw = fixture(env)

    class ChangingModel(ScriptedModel):
        async def complete(self, request):
            response = await super().complete(request)
            env.runtime.access_policies.save(
                owner_actor, UUID(wid), UUID(did), 1, True, raw["grants"]
            )
            return response

    env.runtime.intent_router.model = ChangingModel(
        {"kind": "numerical", "plan": {"metric": "amount", "aggregation": "sum"}}
    )
    thread = env.client.post(root + "/threads", headers=member).json()
    response = env.client.post(
        f"/workspaces/{wid}/threads/{thread['id']}/ask",
        headers=member,
        json={"question": "Total amount?"},
    )
    assert response.status_code == 404, response.text
    assert "0.30" not in response.text
    with env.engine.connect() as connection:
        assert connection.execute(select(s.query_executions.c.id)).all() == []
        assert connection.execute(select(s.thread_turns.c.status)).scalar_one() == "failed"


def test_tighten_then_restore_during_pdf_render_still_denies_old_epoch(integration, monkeypatch):
    from test_conversational_explorer import ScriptedModel

    env = integration
    _, owner_actor, member, _, wid, did, _, root, _, raw = fixture(env)
    env.runtime.intent_router.model = ScriptedModel(
        {"kind": "numerical", "plan": {"metric": "amount", "aggregation": "sum"}}
    )
    thread = env.client.post(root + "/threads", headers=member).json()
    path = f"/workspaces/{wid}/threads/{thread['id']}"
    answer = env.client.post(
        path + "/ask", headers=member, json={"question": "Total amount?"}
    ).json()
    original = env.runtime.pdf_exports.renderer.render

    def render(document):
        result = original(document)
        env.runtime.access_policies.save(
            owner_actor, UUID(wid), UUID(did), 1, True, raw["grants"][:1]
        )
        env.runtime.access_policies.save(owner_actor, UUID(wid), UUID(did), 2, True, raw["grants"])
        return result

    monkeypatch.setattr(env.runtime.pdf_exports.renderer, "render", render)
    response = env.client.get(path + f"/turns/{answer['turn']['id']}/export.pdf", headers=member)
    assert response.status_code == 404, response.text
    with env.engine.connect() as connection:
        assert (
            connection.execute(
                select(s.audit_events.c.id).where(s.audit_events.c.action == "pdf.exported")
            ).all()
            == []
        )
        assert len(connection.execute(select(s.query_executions.c.id)).all()) == 1


def test_shared_and_private_document_ids_and_search_are_not_exposed_to_restricted_grant(
    integration,
):
    env = integration
    owner, _, member, _, wid, did, _, _, _, _ = fixture(env)
    base = f"/workspaces/{wid}/datasets/{did}"
    for shared in (False, True):
        document = env.client.post(
            base + "/documents",
            headers=owner,
            params={"name": "Secret payroll.txt", "shared": shared},
            content=b"Confidential payroll is excluded from the regional grant.",
        )
        assert document.status_code == 201, document.text
        docid = document.json()["id"]
        with env.engine.connect() as connection:
            chunkid = connection.execute(
                select(s.document_chunks.c.id).where(s.document_chunks.c.document_id == UUID(docid))
            ).scalar_one()
        response = env.client.get(
            f"/workspaces/{wid}/documents/{docid}/chunks/{chunkid}", headers=member
        )
        assert response.status_code == 404, response.text
        assert "payroll" not in response.text
    assert env.client.get(base + "/documents", headers=member).json() == []
    assert (
        env.client.post(
            base + "/knowledge/search", headers=member, json={"query": "payroll"}
        ).status_code
        == 403
    )
    assert "payroll" not in env.client.get(f"/workspaces/{wid}/catalog", headers=member).text


def test_join_catalog_never_exposes_hidden_counterpart_columns(integration):
    from test_workspace_integration import dataset, upload

    env = integration
    owner, _, member, _, wid, did, _, root, _, _ = fixture(env)
    other = dataset(env, owner, wid)
    other_uid = upload(env, owner, wid, other, b"city,secret_category\nKarachi,Payroll\n").json()[
        "id"
    ]
    joined = env.client.post(
        f"/workspaces/{wid}/join-paths",
        headers=owner,
        json={
            "left_dataset_id": did,
            "right_dataset_id": other,
            "left_column": "city",
            "right_column": "city",
        },
    )
    assert joined.status_code == 201, joined.text
    assert env.client.get(f"/workspaces/{wid}/join-paths", headers=member).json() == []
    assert (
        env.client.get(root + "/understanding", headers=member).json()["relationship_options"] == []
    )
    response = env.client.post(
        f"/workspaces/{wid}/join-paths/{joined.json()['id']}/query",
        headers=member,
        json={
            "left_upload_id": root.split("/")[-1],
            "right_upload_id": other_uid,
            "metric": "amount",
            "aggregation": "sum",
        },
    )
    assert response.status_code == 403, response.text


def test_owner_management_member_name_is_usable_without_a_display_name(integration):
    env = integration
    owner, _, _, user, _, _, _, _, path, _ = fixture(env)
    person = next(
        item
        for item in env.client.get(path, headers=owner).json()["members"]
        if item["user_id"] == str(user.id)
    )
    assert person["display_name"] == user.display_name or person["display_name"] == user.email
    assert person["display_name"]
