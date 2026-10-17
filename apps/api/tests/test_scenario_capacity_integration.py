"""Exercise bounded scenario/capacity extensions on real synthetic source receipts.

Checks exact exports, immutable old versions, private scopes, admission at every
computation and saved reopening with exhausted or expired local allowances.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update

from execplus.domain.ingestion import IngestionError
from execplus.domain.large_allocation import SENSITIVITY_METHOD
from execplus.domain.scenario_constraints import METHOD
from execplus.infrastructure.persistence import schema as s
from test_analysis_access_policies import revise
from test_calendar_analysis_integration import create as calendar_create
from test_calendar_analysis_integration import fixture as calendar_fixture
from test_large_allocation_integration import create as allocation_create
from test_large_allocation_integration import fixture as allocation_fixture
from test_large_allocation_integration import restricted as allocation_restricted
from test_local_plans import assign
from test_result_exports import download_text
from test_source_scenarios_integration import create as scenario_create
from test_source_scenarios_integration import endpoint
from test_source_scenarios_integration import fixture as scenario_fixture
from test_source_scenarios_integration import restricted_fixture as scenario_restricted
from test_studies import add_member
from test_understanding import confirm, context


def scenario(env, headers, root, **changes):
    return scenario_create(
        env,
        headers,
        root,
        **{
            "model": METHOD,
            "constraints": [dict(field="remaining", operator="minimum", value="35", unit="USD")],
            **changes,
        },
    )


def allocation(env, headers, root, **changes):
    return allocation_create(
        env,
        headers,
        root,
        **{
            "model": SENSITIVITY_METHOD,
            "resources": [dict(column="hours", capacity="0.5")],
            "capacity_sensitivity": dict(
                column="cost", unit="USD", capacities=["0.03", "0.08", "0.11", "0.13", "0.16"]
            ),
            **changes,
        },
    )


def admissions(env):
    with env.engine.connect() as connection:
        return connection.execute(select(func.count()).select_from(s.plan_admissions)).scalar_one()


class NoSearch:
    async def solve(self, problem):
        raise AssertionError("A saved outcome must never run the solver again")


def test_constrained_successor_preserves_v1_and_exact_margin_checks(integration):
    env = integration
    owner, _, _, _, _, root = scenario_fixture(env)
    old = scenario_create(env, owner, root).json()
    response = scenario(env, owner, root, parent_run_id=old["run"]["id"])
    assert response.status_code == 201, response.text
    body = response.json()
    result = body["run"]["result"]
    assert result["method_version"] == METHOD
    assert [v["constraints"][0]["status"] for v in result["sensitivity"]["points"]] == [
        "violated",
        "passed",
        "passed",
    ]
    assert result["baseline_constraints"][0]["exact_actual"] == {
        "numerator": "37",
        "denominator": "1",
    }
    assert env.client.get(endpoint(root, old), headers=owner).json()["run"] == old["run"]
    assert env.client.get(endpoint(root, body), headers=owner).json()["run"] == body["run"]
    assert scenario_create(env, owner, root, parent_run_id=body["run"]["id"]).status_code == 422
    invalid = scenario(
        env,
        owner,
        root,
        constraints=[dict(field="remaining", operator="minimum", value="35", unit="EUR")],
    )
    assert (
        invalid.status_code == 422 and invalid.json()["error"]["code"] == "scenario_constraint_unit"
    )


@pytest.mark.parametrize("kind", ["scenario", "allocation"])
@pytest.mark.parametrize("fmt", ["pdf", "xlsx", "csv", "png"])
def test_extensions_export_exact_scoped_results_and_revoke(integration, kind, fmt):
    env = integration
    if kind == "scenario":
        owner, member, _, root, policy, rules = scenario_restricted(env)
        response = scenario(env, member, root)
    else:
        owner, member, root, policy, rules = allocation_restricted(env)
        response = allocation(env, member, root)
    assert response.status_code == 201, response.text
    body = response.json()
    path = root.split("/uploads/")[0] + f"/analyses/{body['run']['id']}/export.{fmt}?kind={kind}"
    text = download_text(env.client.get(path, headers=member), fmt)
    for marker in (
        ["remaining", "violated", "35"]
        if kind == "scenario"
        else ["0.03", "0.08", "0.13", "0.16", "optimal"]
    ):
        assert marker in text
    assert (
        "secret" not in text
        and "Hidden" not in text
        and "Confidential whole-source context" not in text
    )
    assert env.client.get(path, headers=owner).status_code == 404
    rules["grants"][1]["conditions"][0]["value"] = "South"
    revise(env, owner, policy, rules)
    assert env.client.get(path, headers=member).status_code == 404
    assert env.client.get(endpoint(root, body), headers=member).status_code == 404


def test_capacity_six_solves_retained_outcomes_and_original_only_approval(integration, monkeypatch):
    env = integration
    owner, _, wid, _, _, root = allocation_fixture(env)
    original = env.runtime.decision_analysis.allocation_solver
    calls = []

    class Counted:
        async def solve(self, problem):
            calls.append(problem)
            return await original.solve(problem)

    monkeypatch.setattr(env.runtime.decision_analysis, "allocation_solver", Counted())
    response = allocation(env, owner, root)
    assert response.status_code == 201, response.text
    assert len(calls) == 6
    body = response.json()
    result = body["run"]["result"]
    assert Fraction(result["benefit"]) == Fraction("0.25")
    assert [
        Fraction(v["result"]["benefit"]) for v in result["capacity_sensitivity"]["variants"]
    ] == list(map(Fraction, ["0.07", "0.18", "0.25", "0.29", "0.29"]))
    assert result["capacity_sensitivity"]["approval_scope"] == "original_baseline_only"
    monkeypatch.setattr(env.runtime.decision_analysis, "allocation_solver", NoSearch())
    assert env.client.get(endpoint(root, body), headers=owner).json()["run"] == body["run"]
    member, _ = add_member(env, owner, wid, "admin")
    assert env.client.get(endpoint(root, body), headers=member).status_code == 404
    reviewed = env.client.post(
        endpoint(root, body) + "/reviews",
        headers=owner,
        json=dict(
            target="decision",
            status="approved",
            note="Only original capacity 0.11 USD",
            expected_version=0,
        ),
    )
    assert reviewed.status_code == 201, reviewed.text
    assert env.client.get(endpoint(root, body), headers=owner).json()["approval_effective"] is True
    current = context(env, owner, root)
    current["definition"]["description"] = "Changed declared assumptions"
    assert confirm(env, owner, root, current).status_code == 201
    reopened = env.client.get(endpoint(root, body), headers=owner).json()
    assert reopened["run"] == body["run"] and reopened["approval_effective"] is False


def test_capacity_infeasibility_has_exact_shortfall_and_survives_reopen(integration, monkeypatch):
    env = integration
    owner, _, _, _, _, root = allocation_fixture(env)
    response = allocation(
        env,
        owner,
        root,
        budget="0.01",
        bounds=[dict(candidate="B", minimum=1, maximum=2)],
        prerequisites=[dict(candidate="B", requires="A")],
        capacity_sensitivity=dict(column="cost", unit="USD", capacities=["0.03", "0.08"]),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    result = body["run"]["result"]
    assert result["solver_status"] == "infeasible" and result["benefit"] is None
    proof = result["infeasibility"][0]
    assert proof["proof_kind"] == "exact_constraint" and Fraction(proof["shortfall"]) == Fraction(
        "0.07"
    )
    assert proof["forced_quantities"] == {"A": 1, "B": 1}
    assert [v["result"]["solver_status"] for v in result["capacity_sensitivity"]["variants"]] == [
        "infeasible",
        "optimal",
    ]
    monkeypatch.setattr(env.runtime.decision_analysis, "allocation_solver", NoSearch())
    assert env.client.get(endpoint(root, body), headers=owner).json()["run"] == body["run"]


def test_all_infeasible_capacities_export_tables_without_inventing_zero_chart(integration):
    env = integration
    owner, _, _, _, _, root = allocation_fixture(env)
    response = allocation(
        env,
        owner,
        root,
        budget="0.01",
        bounds=[dict(candidate="B", minimum=1, maximum=2)],
        prerequisites=[dict(candidate="B", requires="A")],
        capacity_sensitivity=dict(column="cost", unit="USD", capacities=["0.02", "0.03"]),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    prefix = root.split("/uploads/")[0] + f"/analyses/{body['run']['id']}/export"
    text = download_text(env.client.get(prefix + ".xlsx?kind=allocation", headers=owner), "xlsx")
    assert "mandatory_resource_exceeds_capacity" in text and "0.02" in text and "0.03" in text
    image = env.client.get(prefix + ".png?kind=allocation", headers=owner)
    assert image.status_code == 422, image.text
    assert all(
        v["result"]["benefit"] is None
        for v in body["run"]["result"]["capacity_sensitivity"]["variants"]
    )


@pytest.mark.parametrize("kind", ["scenario", "allocation", "calendar"])
@pytest.mark.parametrize("blocked", ["zero", "expired"])
def test_original_saved_model_reopens_at_zero_or_expired_processing_plan(
    integration, monkeypatch, kind, blocked
):
    env = integration
    fixture, create = {
        "scenario": (scenario_fixture, scenario),
        "allocation": (allocation_fixture, allocation),
        "calendar": (calendar_fixture, calendar_create),
    }[kind]
    owner, actor, wid, _, _, root = fixture(env)
    response = create(env, owner, root)
    assert response.status_code == 201, response.text
    body = response.json()
    assignment = assign(env, actor, wid, processing=0)
    if blocked == "expired":
        end = datetime.now(timezone.utc) - timedelta(seconds=1)
        env.runtime.plans.assign(
            actor,
            UUID(wid),
            assignment["plan_key"],
            assignment["version"],
            end - timedelta(days=1),
            end,
        )
    before = admissions(env)
    monkeypatch.setattr(env.runtime.decision_analysis, "allocation_solver", NoSearch())
    replay = env.client.get(endpoint(root, body), headers=owner)
    assert replay.status_code == 200, replay.text
    assert replay.json()["run"] == body["run"] and admissions(env) == before
    assert create(env, owner, root).status_code == 429


@pytest.mark.parametrize("kind,expected", [("scenario", 2), ("allocation", 4)])
def test_full_model_inputs_admit_once_per_retry_and_changed_inputs_count_again(
    integration, kind, expected
):
    env = integration
    fixture, create = (
        (scenario_fixture, scenario) if kind == "scenario" else (allocation_fixture, allocation)
    )
    owner, actor, wid, _, _, root = fixture(env)
    assign(env, actor, wid, processing=20)
    headers = {**owner, "Idempotency-Key": str(uuid4())}
    options = (
        {}
        if kind == "scenario"
        else {"capacity_sensitivity": dict(column="cost", unit="USD", capacities=["0.03", "0.08"])}
    )
    first = create(env, headers, root, **options)
    assert first.status_code == 201, first.text
    assert admissions(env) == expected  # One source query plus one/three new computations.
    retry = create(env, headers, root, **options)
    assert retry.status_code == 201, retry.text
    assert admissions(env) == expected
    change = (
        {"constraints": [dict(field="remaining", operator="minimum", value="36", unit="USD")]}
        if kind == "scenario"
        else {"budget": "0.12"}
    )
    changed = create(env, headers, root, **options, **change)
    assert changed.status_code == 201, changed.text
    assert admissions(env) == 2 * expected - 1  # The unchanged projection alone deduplicates.


def test_every_capacity_admission_blocks_before_next_solver_when_budget_exhausted(
    integration, monkeypatch
):
    env = integration
    owner, actor, wid, _, _, root = allocation_fixture(env)
    assign(env, actor, wid, processing=2)
    original = env.runtime.decision_analysis.allocation_solver
    calls = []

    class Counted:
        async def solve(self, problem):
            calls.append(problem)
            return await original.solve(problem)

    monkeypatch.setattr(env.runtime.decision_analysis, "allocation_solver", Counted())
    response = allocation(env, owner, root)
    assert response.status_code == 429, response.text
    assert len(calls) == 1 and admissions(env) == 2
    with env.engine.connect() as connection:
        assert connection.execute(select(s.analysis_runs.c.id)).all() == []


def test_policy_revocation_after_first_solve_stops_remaining_work_and_publication(
    integration, monkeypatch
):
    env = integration
    owner, member, root, policy, rules = allocation_restricted(env)
    original = env.runtime.decision_analysis.allocation_solver
    calls = []

    class Revoking:
        async def solve(self, problem):
            calls.append(problem)
            result = await original.solve(problem)
            rules["grants"][1]["conditions"][0]["value"] = "South"
            revise(env, owner, policy, rules)
            return result

    monkeypatch.setattr(env.runtime.decision_analysis, "allocation_solver", Revoking())
    response = allocation(env, member, root)
    assert response.status_code in {404, 422}, response.text
    assert len(calls) == 1
    with env.engine.connect() as connection:
        assert connection.execute(select(s.analysis_runs.c.id)).all() == []


def test_model_admission_is_atomic_under_concurrent_attempts(integration):
    env = integration
    owner, actor, wid, did, uid, root = scenario_fixture(env)
    saved = scenario(env, owner, root).json()["run"]
    assign(env, actor, wid, processing=1)

    def attempt(_):
        try:
            env.runtime.decision_analysis._admit_model(
                actor,
                UUID(wid),
                UUID(did),
                UUID(uid),
                saved["request"],
                saved["evidence"]["sources"],
            )
            return "admitted"
        except IngestionError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(attempt, range(4)))
    assert results.count("admitted") == 1 and results.count("plan_limit") == 3
    assert admissions(env) == 1


def test_source_change_between_capacity_solves_stops_before_next_computation(
    integration, monkeypatch
):
    env = integration
    owner, _, _, _, _, root = allocation_fixture(env)
    original = env.runtime.decision_analysis.allocation_solver
    current = context(env, owner, root)
    current["definition"]["description"] = "Changed while comparing capacities"
    calls = []

    class Changing:
        async def solve(self, problem):
            calls.append(problem)
            result = await original.solve(problem)
            changed = await asyncio.to_thread(confirm, env, owner, root, current)
            assert changed.status_code == 201
            return result

    monkeypatch.setattr(env.runtime.decision_analysis, "allocation_solver", Changing())
    response = allocation(env, owner, root)
    assert response.status_code in {409, 422}, response.text
    assert len(calls) == 1
    with env.engine.connect() as connection:
        assert connection.execute(select(s.analysis_runs.c.id)).all() == []


@pytest.mark.parametrize("kind", ["scenario", "allocation"])
def test_forged_extension_result_or_exact_checks_cannot_reopen_or_export(integration, kind):
    env = integration
    fixture, create = (
        (scenario_fixture, scenario) if kind == "scenario" else (allocation_fixture, allocation)
    )
    owner, _, _, _, _, root = fixture(env)
    response = create(env, owner, root)
    assert response.status_code == 201, response.text
    body = response.json()
    result = deepcopy(body["run"]["result"])
    if kind == "scenario":
        result["baseline_constraints"][0]["status"] = "violated"
    else:
        result["capacity_sensitivity"]["variants"][0]["result"]["benefit"] = "999"
    with env.engine.begin() as connection:
        connection.execute(
            update(s.analysis_runs)
            .where(s.analysis_runs.c.id == UUID(body["run"]["id"]))
            .values(result=result)
        )
    assert env.client.get(endpoint(root, body), headers=owner).status_code == 409
    path = root.split("/uploads/")[0] + f"/analyses/{body['run']['id']}/export.xlsx?kind={kind}"
    assert env.client.get(path, headers=owner).status_code == 409
