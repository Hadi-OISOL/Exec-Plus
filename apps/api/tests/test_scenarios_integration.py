"""Use case: Verifies private scenario comparisons with real source and database evidence.

What it does: Exercises exact replay, succession, ownership, missingness and input guards.
"""

from copy import deepcopy
from decimal import Decimal
from uuid import UUID

import pytest
from alembic import command
from sqlalchemy import select, update

from execplus.infrastructure.persistence import schema as s
from test_decision_analysis_integration import create as create_analysis
from test_studies import add_member, prepare
from test_understanding import confirm, context


def create(env, headers, root, **extra):
    options = env.client.get(root + "/decision-analysis/options", headers=headers).json()
    body = dict(
        name="Conditional alternatives",
        metric="amount",
        aggregation="sum",
        revision_id=options["revision_id"],
        understanding_id=options["understanding_id"],
        assumptions_confirmed=True,
        alternatives=[
            dict(name="Increase", operation="percent_change", value="10"),
            dict(name="Replace", operation="replace", value="-0.20"),
        ],
    )
    return env.client.post(
        root + "/decision-analysis/scenarios", headers=headers, json={**body, **extra}
    )


def test_scenario_exact_replay_successor_and_private_receipts(integration):
    env = integration
    headers, _, wid, _, _, root = prepare(env)
    response = create(env, headers, root)
    assert response.status_code == 201, response.text
    body = response.json()
    result = body["run"]["result"]
    assert Decimal(result["baseline"]) == Decimal("0.30")
    assert Decimal(result["alternatives"][0]["result"]) == Decimal("0.33")
    url = root.split("/uploads/")[0] + "/decision-analysis/" + body["run"]["id"]
    assert env.client.get(url, headers=headers).json()["run"] == body["run"]
    successor = create(env, headers, root, parent_run_id=body["run"]["id"])
    assert successor.status_code == 201, successor.text
    assert successor.json()["run"]["result"]["parent_run_id"] == body["run"]["id"]
    assert env.client.get(url, headers=headers).json()["run"] == body["run"]
    member, _ = add_member(env, headers, wid, "admin")
    assert env.client.get(url, headers=member).status_code == 404
    assert create(env, member, root, parent_run_id=body["run"]["id"]).status_code == 404
    receipt = f"/workspaces/{wid}/queries/{body['run']['evidence']['query_id']}"
    assert env.client.get(receipt, headers=member).status_code == 404
    assert env.client.post(receipt + "/replay", headers=member).status_code == 404
    assert env.client.post(receipt + "/replay", headers=headers).status_code == 200
    assert (
        env.client.post(
            url + "/reviews",
            headers=headers,
            json=dict(target="decision", status="approved", note="Approve", expected_version=0),
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "extra",
    [
        dict(assumptions_confirmed=False),
        dict(assumptions_confirmed=1),
        dict(aggregation="count"),
        dict(alternatives=[]),
        dict(alternatives=[dict(name="x", operation="python", value="1")]),
        dict(alternatives=[dict(name="x", operation="replace", value=1)]),
    ],
)
def test_scenario_http_contract_refuses_unsupported_input(integration, extra):
    env = integration
    headers, _, _, _, _, root = prepare(env)
    assert create(env, headers, root, **extra).status_code == 422
    assert (
        env.client.get(root.split("/uploads/")[0] + "/decision-analysis", headers=headers).json()
        == []
    )


@pytest.mark.parametrize(
    "content", [b"city,amount,cost\nKarachi,1,1\nLahore,,2\n", b"city,amount,cost\nKarachi,1,1\n"]
)
def test_scenario_missing_or_empty_population_refuses(integration, content):
    env = integration
    headers, _, _, _, _, root = prepare(env, content)
    extra = (
        {}
        if b",," in content
        else dict(filters=[dict(column="city", operator="eq", value="No records")])
    )
    response = create(env, headers, root, **extra)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("field", ["request", "result", "evidence"])
def test_scenario_tamper_refuses(integration, field):
    env = integration
    headers, _, _, _, _, root = prepare(env)
    body = create(env, headers, root).json()
    changed = deepcopy(body["run"][field])
    if field == "evidence":
        changed["coverage_query_ids"] = [changed["query_id"], changed["query_id"]]
    else:
        changed["tampered"] = True
    with env.engine.begin() as conn:
        conn.execute(
            update(s.analysis_runs)
            .where(s.analysis_runs.c.id == UUID(body["run"]["id"]))
            .values(**{field: changed})
        )
    url = root.split("/uploads/")[0] + "/decision-analysis/" + body["run"]["id"]
    response = env.client.get(url, headers=headers)
    assert response.status_code == 409, response.text


def test_scenario_incompatible_successor_refuses(integration):
    env = integration
    headers, _, _, _, _, root = prepare(env)
    parent = create(env, headers, root).json()["run"]["id"]
    response = create(env, headers, root, parent_run_id=parent, metric="cost")
    assert response.status_code == 422, response.text


def test_scenario_historical_replay_preserves_meaning_and_refuses_changed_successor(integration):
    env = integration
    headers, _, _, _, _, root = prepare(env)
    body = create(env, headers, root).json()
    current = context(env, headers, root)
    current["definition"]["columns"][1]["meaning"] = "A different business measure"
    assert confirm(env, headers, root, current).status_code == 201
    url = root.split("/uploads/")[0] + "/decision-analysis/" + body["run"]["id"]
    old = env.client.get(url, headers=headers)
    assert old.status_code == 200, old.text
    assert old.json()["current"] is False
    assert old.json()["run"] == body["run"]
    assert create(env, headers, root, parent_run_id=body["run"]["id"]).status_code == 422


def test_scenario_required_filters_and_three_receipts_match(integration):
    env = integration
    headers, _, _, _, _, root = prepare(env)
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
    assert Decimal(body["run"]["result"]["baseline"]) == Decimal("0.10")
    assert body["run"]["result"]["sample_count"] == 1
    assert (
        len(
            set(
                [
                    body["run"]["evidence"]["query_id"],
                    *body["run"]["evidence"]["coverage_query_ids"],
                ]
            )
        )
        == 3
    )


def test_0017_preserves_existing_analysis_and_blocks_lossy_downgrade(integration):
    env = integration
    headers, _, _, _, _, root = prepare(env)
    original = create_analysis(env, headers, root, "allocations")
    assert original.status_code == 201, original.text

    def retained():
        with env.engine.connect() as c:
            return {
                name: sorted(str(dict(r)) for r in c.execute(select(table)).mappings())
                for name, table in s.metadata.tables.items()
            }

    before = retained()
    with env.engine.begin() as c:
        env.config.attributes["connection"] = c
        command.downgrade(env.config, "0016")
    with env.engine.begin() as c:
        env.config.attributes["connection"] = c
        command.upgrade(env.config, "head")
    assert retained() == before
    response = create(env, headers, root)
    assert response.status_code == 201, response.text
    with pytest.raises(RuntimeError), env.engine.begin() as c:
        env.config.attributes["connection"] = c
        command.downgrade(env.config, "0016")
    assert env.client.get("/health/ready").status_code == 200


def test_changed_governed_population_cannot_be_linked_as_a_successor(integration):
    env = integration
    headers, _, _, _, _, root = prepare(env)
    original = create(env, headers, root).json()
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
    response = create(env, headers, root, parent_run_id=original["run"]["id"])
    assert response.status_code == 422, response.text
