"""Use case: Exercises private decision analysis against PostgreSQL and retained objects.

What it does: Verifies replay, review races, stale meaning, tampering and owner isolation.
"""

import asyncio
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
from uuid import UUID

import pytest
from alembic import command
from sqlalchemy import delete, inspect, select, update
from sqlalchemy.exc import IntegrityError

from execplus.application.services import decision_analysis as service_module
from execplus.domain.analysis_queries import analysis_plan
from execplus.domain.evidence import receipt
from execplus.infrastructure.persistence import schema as s
from test_studies import add_member, prepare
from test_understanding import confirm, context
from test_workspace_integration import dataset, upload, workspace


def create(env, headers, root, kind="anomalies", **extra):
    options = env.client.get(root + "/decision-analysis/options", headers=headers)
    assert options.status_code == 200, options.text
    value = options.json()
    assert value["state"] == "ready"
    body = dict(
        name="Private reproducible analysis",
        revision_id=value["revision_id"],
        understanding_id=value["understanding_id"],
    )
    if kind == "anomalies":
        body.update(metric="amount", threshold="3.5", materiality="0")
    else:
        body.update(
            entity_column="city",
            cost_column="cost",
            benefit_column="amount",
            budget="0.20",
            quantum="0.05",
            maximum_quantity=2,
            assumptions_confirmed=True,
        )
    return env.client.post(
        root + "/decision-analysis/" + kind, headers=headers, json={**body, **extra}
    )


def endpoint(root, body):
    return root.split("/uploads/")[0] + "/decision-analysis/" + body["run"]["id"]


def test_anomaly_exact_replay_feedback_and_private_owner(integration):
    env = integration
    data = b"city,amount,cost\n" + b"Karachi,10,1\n" * 8 + b"Lahore,100,2\n"
    headers, _, wid, _, _, root = prepare(env, data)
    response = create(env, headers, root)
    assert response.status_code == 201, response.text
    body = response.json()
    result = body["run"]["result"]
    assert result["sample_count"] == 9
    assert result["baseline"] == "10"
    assert result["findings"][0]["value"] == "100"
    url = endpoint(root, body)
    reopened = env.client.get(url, headers=headers)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["run"] == body["run"]
    reviewed = env.client.post(
        url + "/reviews",
        headers=headers,
        json=dict(
            target=result["findings"][0]["id"],
            status="investigate",
            note="Check the source with the data owner.",
            expected_version=0,
        ),
    )
    assert reviewed.status_code == 201, reviewed.text
    assert reviewed.json()["review_version"] == 1
    assert reviewed.json()["run"]["result"] == result
    member, _ = add_member(env, headers, wid, "admin")
    assert env.client.get(url, headers=member).status_code == 404
    assert (
        env.client.post(
            url + "/reviews",
            headers=member,
            json=dict(
                target=result["findings"][0]["id"],
                status="dismissed",
                note="No",
                expected_version=1,
            ),
        ).status_code
        == 404
    )
    assert env.client.get(url.rsplit("/", 1)[0], headers=member).json() == []
    receipt_url = f"/workspaces/{wid}/queries/{body['run']['evidence']['query_id']}"
    assert env.client.get(receipt_url, headers=member).status_code == 404
    assert env.client.post(receipt_url + "/replay", headers=member).status_code == 404
    assert env.client.post(receipt_url + "/replay", headers=headers).status_code == 200


def test_allocation_exact_review_race_and_stale_approval(integration):
    env = integration
    headers, actor, wid, did, _, root = prepare(env)
    response = create(env, headers, root, "allocations")
    assert response.status_code == 201, response.text
    body = response.json()
    assert Decimal(body["run"]["result"]["benefit"]) == Decimal("0.30")
    assert body["run"]["result"]["cost"] == "0.20"
    url = endpoint(root, body)
    _, scope, table, view = env.runtime.analytics.context_at(
        actor, UUID(wid), body["run"]["evidence"]["sources"][0]
    )
    plan, units = analysis_plan(scope, UUID(did), view, table, body["run"]["request"])
    plan = replace(plan, query_id=UUID(body["run"]["evidence"]["query_id"]))
    result = asyncio.run(env.runtime.analytics.executor.execute(plan, scope, table, view))
    with env.runtime.decision_analysis.uow() as repo:
        record = repo.query_execution(UUID(wid), plan.query_id)
    assert record.receipt == receipt(plan, view.sources, result)
    assert units == body["run"]["evidence"]["units"]
    assert view.definition == body["run"]["evidence"]["definition"]
    reopened = env.client.get(url, headers=headers)
    assert reopened.status_code == 200, reopened.text
    payload = dict(
        target="decision",
        status="approved",
        note="Reviewed the linear assumptions.",
        expected_version=0,
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: env.client.post(url + "/reviews", headers=headers, json=payload), range(2)
            )
        )
    assert sorted(r.status_code for r in responses) == [201, 409], [r.text for r in responses]
    approved = env.client.get(url, headers=headers).json()
    assert approved["approval_effective"] is True
    current = context(env, headers, root)
    current["definition"]["columns"][1]["meaning"] = "A revised definition"
    assert confirm(env, headers, root, current).status_code == 201
    stale = env.client.get(url, headers=headers)
    assert stale.status_code == 200, stale.text
    assert stale.json()["current"] is False
    assert stale.json()["approval_effective"] is False
    assert stale.json()["decision_status"] == "approved"
    payload.update(status="pending", expected_version=1, note="Reopen after a definition change.")
    assert env.client.post(url + "/reviews", headers=headers, json=payload).status_code == 201
    payload.update(status="approved", expected_version=2)
    assert env.client.post(url + "/reviews", headers=headers, json=payload).status_code == 409


@pytest.mark.parametrize("target", ["result", "receipt", "request", "units", "definition"])
def test_saved_analysis_tampering_refuses_reopening(integration, target):
    env = integration
    headers, _, _, _, _, root = prepare(env)
    response = create(env, headers, root, "allocations")
    assert response.status_code == 201, response.text
    body = response.json()
    run = body["run"]
    with env.engine.begin() as connection:
        if target == "receipt":
            row = (
                connection.execute(
                    s.query_executions.select().where(
                        s.query_executions.c.id == UUID(run["evidence"]["query_id"])
                    )
                )
                .mappings()
                .one()
            )
            value = copy.deepcopy(row["receipt"])
            value["answer"]["records_analyzed"] += 1
            connection.execute(
                update(s.query_executions)
                .where(s.query_executions.c.id == row["id"])
                .values(receipt=value)
            )
        else:
            key = target if target in {"result", "request"} else "evidence"
            value = copy.deepcopy(run[key])
            if target == "result":
                value["benefit"] = "999"
            elif target == "request":
                value["budget"] = "999"
            elif target == "units":
                value["units"]["cost"] = "USD"
            else:
                value["definition"]["domain"] = "finance"
            connection.execute(
                update(s.analysis_runs)
                .where(s.analysis_runs.c.id == UUID(run["id"]))
                .values(**{key: value})
            )
    assert env.client.get(endpoint(root, body), headers=headers).status_code == 409


def test_infeasible_mandatory_quantities_cannot_be_approved(integration):
    env = integration
    headers, _, _, _, _, root = prepare(env)
    response = create(
        env,
        headers,
        root,
        "allocations",
        budget="0",
        bounds=[dict(candidate="Karachi", minimum=1, maximum=1)],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["run"]["result"]["status"] == "infeasible"
    reviewed = env.client.post(
        endpoint(root, body) + "/reviews",
        headers=headers,
        json=dict(
            target="decision",
            status="approved",
            note="Approve",
            expected_version=0,
        ),
    )
    assert reviewed.status_code == 409


def test_filtered_small_population_is_not_silently_expanded(integration):
    env = integration
    data = b"city,amount,cost\n" + b"Karachi,10,1\n" * 8 + b"Lahore,100,2\n"
    headers, _, _, _, _, root = prepare(env, data)
    response = create(
        env, headers, root, filters=[dict(column="city", operator="eq", value="Lahore")]
    )
    assert response.status_code == 422, response.text


def test_revocation_denies_saved_result_and_approval(integration):
    env = integration
    owner, _, wid, _, _, root = prepare(env)
    member, actor = add_member(env, owner, wid)
    response = create(env, member, root, "allocations")
    assert response.status_code == 201, response.text
    url = endpoint(root, response.json())
    assert (
        env.client.delete(f"/workspaces/{wid}/members/{actor.id}", headers=owner).status_code == 204
    )
    assert env.client.get(url, headers=member).status_code == 404
    assert (
        env.client.post(
            url + "/reviews",
            headers=member,
            json=dict(
                target="decision",
                status="approved",
                note="Approve",
                expected_version=0,
            ),
        ).status_code
        == 404
    )


def test_required_filters_are_preserved_in_source_receipt(integration):
    env = integration
    data = b"city,amount,cost\n" + b"Karachi,10,1\n" * 8 + b"Lahore,100,2\n"
    headers, _, _, _, _, root = prepare(env, data)
    current = context(env, headers, root)
    current["definition"]["metrics"] = [
        dict(
            name="Karachi amount",
            column="amount",
            aggregation="sum",
            filters=[dict(column="city", operator="eq", value="Karachi")],
        )
    ]
    assert confirm(env, headers, root, current).status_code == 201
    response = create(env, headers, root)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["run"]["result"]["sample_count"] == 8
    assert body["run"]["result"]["findings"] == []
    assert env.client.get(endpoint(root, body), headers=headers).status_code == 200


@pytest.mark.parametrize(
    "change",
    [
        dict(assumptions_confirmed=False),
        dict(entity_column="amount"),
        dict(cost_column="city"),
        dict(maximum_quantity=True),
        dict(budget="NaN"),
        dict(bounds=[dict(candidate="unknown", minimum=1, maximum=1)]),
    ],
)
def test_invalid_decision_inputs_do_not_create_saved_runs(integration, change):
    env = integration
    headers, _, _, _, _, root = prepare(env)
    response = create(env, headers, root, "allocations", **change)
    assert response.status_code in {422, 400}, response.text
    assert (
        env.client.get(root.split("/uploads/")[0] + "/decision-analysis", headers=headers).json()
        == []
    )


def test_analysis_database_constraints_and_0016_preserve_prior_tables(integration):
    env = integration
    headers, actor, wid, _, _, root = prepare(env)
    response = create(env, headers, root, "allocations")
    assert response.status_code == 201, response.text
    with env.runtime.decision_analysis.uow() as repo:
        original = repo.analysis_run(UUID(wid), UUID(response.json()["run"]["id"]), actor.id)
    another = UUID(workspace(env, headers, name="Other tenant"))
    with pytest.raises(IntegrityError), env.runtime.decision_analysis.uow() as repo:
        repo.add(
            replace(original, id=UUID("11111111-1111-1111-1111-111111111111"), workspace_id=another)
        )
    with env.engine.begin() as connection:
        connection.execute(delete(s.analysis_runs))

    def retained():
        with env.engine.connect() as connection:
            return {
                name: sorted(
                    json.dumps(dict(row), sort_keys=True, default=str)
                    for row in connection.execute(select(table)).mappings()
                )
                for name, table in s.metadata.tables.items()
                if name not in {"analysis_runs", "analysis_reviews"}
            }

    before = retained()
    with env.engine.begin() as connection:
        env.config.attributes["connection"] = connection
        command.downgrade(env.config, "0015")
    assert "analysis_runs" not in inspect(env.engine).get_table_names()
    with env.engine.begin() as connection:
        env.config.attributes["connection"] = connection
        command.upgrade(env.config, "head")
    assert retained() == before
    assert env.client.get("/health/ready").status_code == 200


def test_unconfirmed_source_cannot_execute_analysis(integration):
    env = integration
    headers, _, _, _, _, _ = prepare(env)
    wid = workspace(env, headers, name="Unreviewed source")
    did = dataset(env, headers, wid)
    uid = upload(env, headers, wid, did, b"city,amount,cost\nA,1,1\n").json()["id"]
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{uid}"
    options = env.client.get(root + "/decision-analysis/options", headers=headers).json()
    assert options["state"] == "needs_review"
    response = env.client.post(
        root + "/decision-analysis/anomalies",
        headers=headers,
        json=dict(
            name="Unconfirmed",
            revision_id=options["revision_id"],
            understanding_id=options["understanding_id"],
            metric="amount",
        ),
    )
    assert response.status_code in {422, 409}, response.text


def test_membership_revoked_during_compute_prevents_publication(integration, monkeypatch):
    env = integration
    owner, _, wid, _, _, root = prepare(env)
    member, actor = add_member(env, owner, wid)
    original = service_module.calculate

    def revoke_after_calculation(raw, result):
        calculated = original(raw, result)
        with env.engine.begin() as connection:
            connection.execute(
                delete(s.memberships).where(
                    s.memberships.c.workspace_id == UUID(wid),
                    s.memberships.c.user_id == actor.id,
                )
            )
        return calculated

    monkeypatch.setattr(service_module, "calculate", revoke_after_calculation)
    response = create(env, member, root, "allocations")
    assert response.status_code == 404, response.text
    with env.engine.connect() as connection:
        assert connection.execute(select(s.analysis_runs)).all() == []


def test_changed_source_bytes_prevent_reopening(integration):
    env = integration
    headers, _, wid, did, uid, root = prepare(env)
    response = create(env, headers, root, "allocations")
    assert response.status_code == 201, response.text
    with env.runtime.service.uow() as repo:
        stored = repo.upload(UUID(wid), UUID(did), UUID(uid))
    env.runtime.service.storage.client.put_object(
        Bucket=env.bucket,
        Key=stored.storage_key,
        Body=b"city,amount,cost\nKarachi,999,1\nLahore,1000,1\n",
    )
    reopened = env.client.get(endpoint(root, response.json()), headers=headers)
    assert reopened.status_code == 503, reopened.text
    assert reopened.json()["error"]["code"] == "storage_integrity"


def test_anomaly_does_not_drop_missing_values(integration):
    env = integration
    content = b"city,amount,cost\n" + b"Karachi,10,1\n" * 8 + b"Lahore,,2\n"
    headers, _, _, _, _, root = prepare(env, content)
    response = create(env, headers, root)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("kind,count", [("anomalies", 1001), ("allocations", 21)])
def test_result_caps_refuse_truncation(integration, kind, count):
    env = integration
    content = ("city,amount,cost\n" + "".join(f"A{i},{i + 1},1\n" for i in range(count))).encode()
    headers, _, _, _, _, root = prepare(env, content)
    response = create(env, headers, root, kind)
    assert response.status_code == 422, response.text
