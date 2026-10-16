"""Use case: Exercises optional CP-SAT allocations through governed saved evidence.

What it does: Verifies exact results, retained replay, private access and publication races.
"""

from decimal import Decimal

import pytest
from sqlalchemy import select

from execplus.domain.large_allocation import SolverOutcome
from execplus.infrastructure.persistence import schema as s
from test_analysis_access_policies import grant, revise
from test_result_exports import download_text
from test_studies import add_member, prepare
from test_understanding import confirm, context


def fixture(env, content=None):
    value = prepare(
        env,
        content
        or (
            b"action,cost,benefit,hours,water,space,region,secret\n"
            b"A,0.03,0.07,0.2,2,1,North,999\nB,0.05,0.11,0.1,1,2,North,777\n"
        ),
    )
    headers, _, _, _, _, root = value
    current = context(env, headers, root)
    current["definition"].update(grain="record", description="Confidential whole-source context")
    for column in current["definition"]["columns"]:
        if column["name"] in {"cost", "benefit"}:
            column.update(unit="", currency="USD")
        if column["name"] == "hours":
            column.update(unit="hours", currency="")
    assert confirm(env, headers, root, current).status_code == 201
    return value


def create(env, headers, root, **changes):
    options = env.client.get(root + "/decision-analysis/options", headers=headers)
    assert options.status_code == 200, options.text
    value = options.json()
    body = dict(
        name="Larger private allocation",
        revision_id=value["revision_id"],
        understanding_id=value["understanding_id"],
        entity_column="action",
        cost_column="cost",
        benefit_column="benefit",
        budget="0.11",
        maximum_quantity=2,
        resources=[
            dict(column="hours", capacity="0.5"),
            dict(column="water", capacity="5"),
            dict(column="space", capacity="4"),
        ],
        bounds=[],
        prerequisites=[],
        exclusions=[],
        assumptions_confirmed=True,
    )
    return env.client.post(
        root + "/decision-analysis/large-allocations", headers=headers, json={**body, **changes}
    )


def endpoint(root, body):
    return root.split("/uploads/")[0] + "/decision-analysis/" + body["run"]["id"]


def test_real_large_allocation_exact_replay_review_and_legacy_compatibility(
    integration, monkeypatch
):
    env = integration
    owner, _, wid, _, _, root = fixture(env)
    response = create(env, owner, root)
    assert response.status_code == 201, response.text
    body = response.json()
    result = body["run"]["result"]
    assert result["solver_status"] == "optimal"
    assert [row["quantity"] for row in result["allocations"]] == [2, 1]
    assert Decimal(result["benefit"]) == Decimal("0.25")
    assert Decimal(result["cost"]) == Decimal("0.11")
    assert [Decimal(r["used"]) for r in result["resources"]] == list(
        map(Decimal, ["0.11", "0.5", "5", "4"])
    )

    class NoSearch:
        async def solve(self, problem):
            raise AssertionError("Reopening must not rerun bounded search")

    monkeypatch.setattr(env.runtime.decision_analysis, "allocation_solver", NoSearch())
    assert env.client.get(endpoint(root, body), headers=owner).json()["run"] == body["run"]
    qpath = f"/workspaces/{wid}/queries/{body['run']['evidence']['query_id']}"
    assert env.client.get(qpath, headers=owner).json()["aggregation"] == "analysis"
    assert env.client.post(qpath + "/replay", headers=owner).status_code == 200
    reviewed = env.client.post(
        endpoint(root, body) + "/reviews",
        headers=owner,
        json=dict(
            target="decision",
            status="approved",
            note="Approve only the declared hypothetical model",
            expected_version=0,
        ),
    )
    assert reviewed.status_code == 201, reviewed.text
    legacy = env.client.post(
        root + "/decision-analysis/allocations",
        headers=owner,
        json=dict(
            name="Original solver remains unchanged",
            revision_id=body["run"]["revision_id"],
            understanding_id=body["run"]["understanding_id"],
            entity_column="action",
            cost_column="cost",
            benefit_column="benefit",
            budget="0.11",
            quantum="0.01",
            maximum_quantity=2,
            assumptions_confirmed=True,
        ),
    )
    assert legacy.status_code == 201, legacy.text
    old = legacy.json()
    assert old["run"]["method_version"] == "integer-budget-v1"
    assert Decimal(old["run"]["result"]["benefit"]) == Decimal("0.25")
    current = context(env, owner, root)
    current["definition"]["description"] = "Changed meaning"
    assert confirm(env, owner, root, current).status_code == 201
    reopened = env.client.get(endpoint(root, body), headers=owner)
    assert reopened.status_code == 200 and reopened.json()["run"] == body["run"]
    assert reopened.json()["current"] is False and reopened.json()["approval_effective"] is False
    assert env.client.get(endpoint(root, old), headers=owner).json()["run"] == old["run"]


def test_large_run_receipt_and_exports_are_private_even_from_workspace_admin(integration):
    env = integration
    owner, _, wid, _, _, root = fixture(env)
    created = create(env, owner, root)
    assert created.status_code == 201, created.text
    body = created.json()
    member, _ = add_member(env, owner, wid, "admin")
    assert env.client.get(endpoint(root, body), headers=member).status_code == 404
    assert (
        env.client.get(root.split("/uploads/")[0] + "/decision-analysis", headers=member).json()
        == []
    )
    assert (
        env.client.get(
            f"/workspaces/{wid}/queries/{body['run']['evidence']['query_id']}", headers=member
        ).status_code
        == 404
    )
    for fmt in ("pdf", "xlsx", "csv", "png"):
        path = (
            root.split("/uploads/")[0]
            + f"/analyses/{body['run']['id']}/export.{fmt}?kind=allocation"
        )
        assert env.client.get(path, headers=member).status_code == 404


def restricted(env):
    owner, actor, wid, did, _, root = fixture(
        env,
        b"action,cost,benefit,hours,water,space,region,secret\nA,0.03,0.07,0.2,2,1,North,999\nB,0.05,0.11,0.1,1,2,North,777\nHidden,1,999,1,1,1,South,888\n",
    )
    member, member_actor = add_member(env, owner, wid, "admin")
    path, rules = grant(
        env,
        owner,
        actor,
        wid,
        did,
        member_actor,
        ["action", "cost", "benefit", "hours", "water", "space"],
        dict(column="region", operator="eq", value="North"),
    )
    return owner, member, root, path, rules


@pytest.mark.parametrize("fmt", ["pdf", "xlsx", "csv", "png"])
def test_restricted_large_allocations_export_all_exact_resources_and_revoke(integration, fmt):
    env = integration
    owner, member, root, policy, rules = restricted(env)
    response = create(env, member, root)
    assert response.status_code == 201, response.text
    body = response.json()
    path = (
        root.split("/uploads/")[0] + f"/analyses/{body['run']['id']}/export.{fmt}?kind=allocation"
    )
    exported = download_text(env.client.get(path, headers=member), fmt)
    assert "0.25" in exported and "0.11" in exported
    assert all(name in exported for name in ("hours", "water", "space"))
    assert "withheld_for_restricted_access" in exported
    assert (
        "Confidential whole-source context" not in exported
        and "secret" not in exported
        and "Hidden" not in exported
    )
    assert env.client.get(endpoint(root, body), headers=member).json()["run"] == body["run"]
    revise(env, owner, policy, rules)
    assert env.client.get(path, headers=member).status_code == 404
    assert (
        env.client.get(root.split("/uploads/")[0] + "/decision-analysis", headers=member).json()
        == []
    )


@pytest.mark.parametrize(
    "status,quantities,objective",
    [("FEASIBLE", (0, 1), 11), ("UNKNOWN", None, None), ("INFEASIBLE", None, None)],
)
def test_search_status_is_honest_and_only_checked_solutions_can_be_approved(
    integration, monkeypatch, status, quantities, objective
):
    env = integration
    owner, _, _, _, _, root = fixture(env)

    class Outcome:
        async def solve(self, problem):
            return SolverOutcome(status, quantities, objective)

    monkeypatch.setattr(env.runtime.decision_analysis, "allocation_solver", Outcome())
    response = create(env, owner, root)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["run"]["result"]["solver_status"] == status.lower()
    reviewed = env.client.post(
        endpoint(root, body) + "/reviews",
        headers=owner,
        json=dict(
            target="decision",
            status="approved",
            note="Acknowledge solver outcome",
            expected_version=0,
        ),
    )
    assert reviewed.status_code == (201 if status == "FEASIBLE" else 409)
    assert env.client.get(endpoint(root, body), headers=owner).json()["run"] == body["run"]


def test_policy_change_during_solver_blocks_publication(integration, monkeypatch):
    env = integration
    owner, member, root, policy, rules = restricted(env)
    original = env.runtime.decision_analysis.allocation_solver

    class Revoking:
        async def solve(self, problem):
            result = await original.solve(problem)
            revise(env, owner, policy, rules)
            return result

    monkeypatch.setattr(env.runtime.decision_analysis, "allocation_solver", Revoking())
    response = create(env, member, root)
    assert response.status_code in {404, 422}, response.text
    with env.engine.connect() as connection:
        assert connection.execute(select(s.analysis_runs.c.id)).all() == []


@pytest.mark.parametrize(
    "change",
    [
        {"maximum_quantity": 101},
        {"resources": [dict(column="hours", capacity="1")] * 4},
        {"assumptions_confirmed": False},
        {"resources": [dict(column="cost", capacity="1")]},
        {"budget": "0.00000000000000000000000000000000000001"},
    ],
)
def test_route_limits_duplicate_columns_and_unsafe_scaling_are_refused(integration, change):
    env = integration
    owner, _, _, _, _, root = fixture(env)
    response = create(env, owner, root, **change)
    assert response.status_code == 422, response.text


def test_fifty_one_rows_are_refused_instead_of_truncated(integration):
    env = integration
    content = (
        "action,cost,benefit,hours,water,space\n"
        + "\n".join(f"A{i},1,2,1,1,1" for i in range(51))
        + "\n"
    ).encode()
    owner, _, _, _, _, root = fixture(env, content)
    response = create(env, owner, root)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "invalid_candidates"


def test_large_allocation_requires_one_shared_governed_population(integration):
    env = integration
    owner, _, _, _, _, root = fixture(env)
    current = context(env, owner, root)
    current["definition"]["metrics"] = [
        dict(
            name="North benefit",
            column="benefit",
            aggregation="sum",
            filters=[dict(column="region", operator="eq", value="North")],
        )
    ]
    assert confirm(env, owner, root, current).status_code == 201
    response = create(env, owner, root)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "allocation_population_mismatch"
    response = create(
        env, owner, root, filters=[dict(column="region", operator="eq", value="North")]
    )
    assert response.status_code == 201, response.text
    assert Decimal(response.json()["run"]["result"]["benefit"]) == Decimal("0.25")


def test_corrupted_retained_quantities_fail_replay(integration):
    from copy import deepcopy
    from uuid import UUID

    from sqlalchemy import update

    env = integration
    owner, _, _, _, _, root = fixture(env)
    response = create(env, owner, root)
    assert response.status_code == 201, response.text
    body = response.json()
    corrupted = deepcopy(body["run"]["result"])
    corrupted["allocations"][0]["quantity"] = 0
    with env.engine.begin() as connection:
        connection.execute(
            update(s.analysis_runs)
            .where(s.analysis_runs.c.id == UUID(body["run"]["id"]))
            .values(result=corrupted)
        )
    reopened = env.client.get(endpoint(root, body), headers=owner)
    assert reopened.status_code == 409, reopened.text


@pytest.mark.parametrize(
    "content",
    [
        b"action,cost,benefit,hours,water,space\nA,0.03,0.07,,2,1\nB,0.05,0.11,0.1,1,2\n",
        b"action,cost,benefit,hours,water,space\nA,0.03,0.07,0.2,2,1\nA,0.05,0.11,0.1,1,2\n",
    ],
)
def test_missing_values_and_duplicate_action_rows_are_refused(integration, content):
    env = integration
    owner, _, _, _, _, root = fixture(env, content)
    response = create(env, owner, root)
    assert response.status_code == 422, response.text
    with env.engine.connect() as connection:
        assert connection.execute(select(s.analysis_runs.c.id)).all() == []
