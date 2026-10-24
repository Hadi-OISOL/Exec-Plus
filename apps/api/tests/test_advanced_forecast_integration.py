"""Use case: Exercises advanced forecasts through real governed services and APIs.

What it does: Verifies old/new replay, calendar evidence, later actuals, explicit
inputs, private access and tamper detection with isolated database/storage fixtures.
"""

import copy
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update

from execplus.application.services import forecasts as forecast_service
from execplus.infrastructure.persistence import schema as s
from test_forecast_integration import create, daily, request
from test_result_exports import download_text
from test_studies import add_member, prepare
from test_understanding import confirm, context
from test_workspace_integration import dataset, identity, upload, workspace


def test_old_and_advanced_forecasts_reopen_exactly_and_preserve_legacy_requests(integration):
    env = integration
    owner, _, wid, did, _, root = prepare(env, daily())
    legacy = create(env, owner, root).json()
    response = create(env, owner, root, engine="advanced-v2", method_family="auto", season_length=7)
    assert response.status_code == 201, response.text
    advanced = response.json()
    assert "engine" not in legacy["request"] and "method_family" not in legacy["request"]
    assert legacy["result"]["version"] == "forecast-v1"
    assert advanced["result"]["version"] == "forecast-v2"
    assert advanced["request"]["engine"] == "advanced-v2"
    assert advanced["result"]["method"]["id"] == "holt"
    assert Decimal(advanced["result"]["predictions"][0]["estimate"]) == Decimal("4.1")
    assert advanced["result"]["history"] == legacy["result"]["history"]
    assert len(advanced["result"]["selection"]["folds"]) == 3
    assert len(advanced["evidence"]["query_ids"]) == 3
    for value in (legacy, advanced):
        reopened = env.client.get(
            f"/workspaces/{wid}/datasets/{did}/forecasts/{value['id']}", headers=owner
        )
        assert reopened.status_code == 200, reopened.text
        assert reopened.json() == value
    assert "empirical validation-error" in " ".join(advanced["result"]["commentary"])


def test_advanced_later_actual_comparison_reopens_and_preserves_pending_period(integration):
    env = integration
    owner, _, wid, did, uid, root = prepare(env, daily())
    initial = create(env, owner, root, engine="advanced-v2").json()
    next_uid = upload(env, owner, wid, did, daily(42)).json()["id"]
    next_root = root.replace(uid, next_uid)
    assert (
        confirm(
            env, owner, next_root, context(env, owner, next_root), initial["evidence"]["definition"]
        ).status_code
        == 201
    )
    raw = request(env, owner, next_root)
    path = f"/workspaces/{wid}/datasets/{did}/forecasts/{initial['id']}"
    response = env.client.post(
        path + "/compare",
        headers=owner,
        json={
            "upload_id": next_uid,
            "revision_id": raw["revision_id"],
            "understanding_id": raw["understanding_id"],
            "coverage_start": "2024-02-10",
            "coverage_end": "2024-02-11",
            "coverage_confirmed": True,
        },
    )
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["result"]["observed_count"] == 2 and result["result"]["pending_count"] == 1
    assert Decimal(result["result"]["metrics"]["mae"]) == 0
    assert result["result"]["rows"][-1]["actual"] is None
    assert env.client.get(path + "/comparisons/" + result["id"], headers=owner).json() == result
    assert env.client.get(path, headers=owner).json() == initial


def test_advanced_private_owner_workspace_and_revoked_membership(integration):
    env = integration
    owner, _, wid, did, _, root = prepare(env, daily())
    member, actor = add_member(env, owner, wid)
    response = create(env, member, root, engine="advanced-v2")
    assert response.status_code == 201, response.text
    run = response.json()
    path = f"/workspaces/{wid}/datasets/{did}/forecasts/{run['id']}"
    assert env.client.get(path, headers=owner).status_code == 404
    assert env.client.get(path, headers=member).status_code == 200
    outsider, _ = identity(env, f"advanced-outsider-{uuid4().hex}@example.test")
    other_wid = workspace(env, outsider)
    other_did = dataset(env, outsider, other_wid)
    assert env.client.get(path, headers=outsider).status_code == 404
    assert (
        env.client.get(
            path.replace(wid, other_wid).replace(did, other_did), headers=outsider
        ).status_code
        == 404
    )
    assert (
        env.client.delete(f"/workspaces/{wid}/members/{actor.id}", headers=owner).status_code == 204
    )
    assert env.client.get(path, headers=member).status_code == 404


@pytest.mark.parametrize("field", ["result", "request", "method_version", "unknown_engine"])
def test_advanced_saved_parameters_or_result_tampering_is_refused(integration, field):
    env = integration
    owner, _, wid, did, _, root = prepare(env, daily())
    run = create(env, owner, root, engine="advanced-v2").json()
    target = "request" if field == "unknown_engine" else field
    altered = copy.deepcopy(run[target])
    if field == "result":
        altered["predictions"][0]["estimate"] = "9999"
    elif field == "request":
        altered["engine"] = "basic-v1"
    elif field == "unknown_engine":
        altered["engine"] = "no-such-engine"
    else:
        altered = "forecast-v1"
    with env.engine.begin() as connection:
        connection.execute(
            update(s.forecast_runs)
            .where(s.forecast_runs.c.id == UUID(run["id"]))
            .values(**{target: altered})
        )
    response = env.client.get(
        f"/workspaces/{wid}/datasets/{did}/forecasts/{run['id']}", headers=owner
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "lineage_mismatch"


@pytest.mark.parametrize(
    "changes",
    [
        {"engine": "unregistered"},
        {"engine": "basic-v1", "method_family": "holt"},
        {"engine": "advanced-v2", "method_family": "arbitrary_code"},
        {"engine": "advanced-v2", "method_family": "holt_winters_additive"},
        {"engine": "advanced-v2", "horizon": 30},
    ],
)
def test_unavailable_or_ineligible_advanced_method_never_silently_substitutes(integration, changes):
    env = integration
    owner, _, _, _, _, root = prepare(env, daily())
    response = create(env, owner, root, **changes)
    assert response.status_code == 422, response.text
    with env.engine.connect() as connection:
        assert connection.execute(select(s.forecast_runs.c.id)).all() == []


@pytest.mark.parametrize(
    "content,code", [(daily(missing=5), "missing_periods"), (daily(blank=5), "missing_measure")]
)
def test_advanced_source_never_imputes_missing_periods_or_values(integration, content, code):
    env = integration
    owner, _, _, _, _, root = prepare(env, content)
    response = create(env, owner, root, engine="advanced-v2")
    assert response.status_code == 422 and response.json()["error"]["code"] == code


def test_advanced_governed_filters_and_definition_freshness_remain_required(integration):
    env = integration
    owner, _, _, _, _, root = prepare(env, daily(extra=True))
    current = context(env, owner, root)
    current["definition"]["metrics"] = [
        {
            "name": "Karachi revenue",
            "column": "amount",
            "aggregation": "sum",
            "filters": [{"column": "city", "operator": "eq", "value": "Karachi"}],
        }
    ]
    assert confirm(env, owner, root, current).status_code == 201
    raw = request(env, owner, root, engine="advanced-v2")
    response = env.client.post(root + "/forecasts", headers=owner, json=raw)
    assert response.status_code == 201, response.text
    assert Decimal(response.json()["result"]["history"][-1]["actual"]) == Decimal("4")
    current = context(env, owner, root)
    assert confirm(env, owner, root, current).status_code == 201
    assert env.client.post(root + "/forecasts", headers=owner, json=raw).status_code == 422


@pytest.mark.parametrize("format", ["pdf", "xlsx", "csv", "png"])
def test_advanced_forecast_and_later_comparison_export_exact_saved_results(integration, format):
    env = integration
    owner, _, wid, did, _, root = prepare(env, daily())
    run = create(env, owner, root, engine="advanced-v2").json()
    base = f"/workspaces/{wid}/datasets/{did}/forecasts/{run['id']}"
    response = env.client.get(base + f"/export.{format}", headers=owner)
    exported = download_text(response, format)
    assert run["result"]["predictions"][0]["estimate"] in exported
    assert "validation" in exported.lower()
    assert run["evidence"]["query_ids"][0] in exported
    assert env.client.get(base, headers=owner).json() == run
    raw = request(env, owner, root)
    compared = env.client.post(
        base + "/compare",
        headers=owner,
        json={
            "upload_id": run["upload_id"],
            "revision_id": raw["revision_id"],
            "understanding_id": raw["understanding_id"],
            "coverage_start": "2024-01-01",
            "coverage_end": "2024-02-09",
            "coverage_confirmed": True,
        },
    )
    assert compared.status_code == 201, compared.text
    comparison = compared.json()
    response = env.client.get(
        base + f"/comparisons/{comparison['id']}/export.{format}", headers=owner
    )
    exported = download_text(response, format)
    assert run["result"]["predictions"][0]["estimate"] in exported
    assert "pending" in exported.lower()
    member, _ = add_member(env, owner, wid)
    assert env.client.get(base + f"/export.{format}", headers=member).status_code == 404
    assert (
        env.client.get(
            base + f"/comparisons/{comparison['id']}/export.{format}", headers=member
        ).status_code
        == 404
    )


def restricted_forecast_fixture(env):
    owner, owner_actor, wid, did, _, root = prepare(env, daily(extra=True))
    member, actor = add_member(env, owner, wid)
    policy_path = f"/workspaces/{wid}/datasets/{did}/access-policy"
    body = {
        "expected_version": 0,
        "enabled": True,
        "grants": [
            {"user_id": str(owner_actor.id), "columns": None, "conditions": []},
            {
                "user_id": str(actor.id),
                "columns": ["day", "amount"],
                "conditions": [{"column": "city", "operator": "eq", "value": "Karachi"}],
            },
        ],
    }
    saved = env.client.put(policy_path, headers=owner, json=body)
    assert saved.status_code == 200, saved.text
    return owner, member, actor, wid, did, root, policy_path, body


def test_advanced_forecast_only_sees_allowed_rows_fields_and_hides_old_policy_results(integration):
    env = integration
    owner, member, actor, wid, did, root, policy_path, body = restricted_forecast_fixture(env)
    response = create(env, member, root, engine="advanced-v2")
    assert response.status_code == 201, response.text
    run = response.json()
    assert Decimal(run["result"]["history"][-1]["actual"]) == 4
    assert Decimal(run["result"]["predictions"][0]["estimate"]) == Decimal("4.1")
    assert {item["name"] for item in run["evidence"]["definition"]["columns"]} == {"day", "amount"}
    assert run["evidence"]["sources"][0]["access_actor_id"] == str(actor.id)
    base = f"/workspaces/{wid}/datasets/{did}/forecasts"
    assert env.client.get(base + "/" + run["id"], headers=member).json() == run
    assert env.client.get(base + "/" + run["id"], headers=owner).status_code == 404
    body["expected_version"] = 1
    body["grants"][1]["conditions"][0]["value"] = "Lahore"
    assert env.client.put(policy_path, headers=owner, json=body).status_code == 200
    assert env.client.get(base, headers=member).json() == []
    assert env.client.get(base + "/" + run["id"], headers=member).status_code == 404
    assert (
        env.client.get(base + "/" + run["id"] + "/export.xlsx", headers=member).status_code == 404
    )


def test_policy_change_during_advanced_fit_prevents_publication(integration, monkeypatch):
    env = integration
    owner, member, _, _, _, root, policy_path, body = restricted_forecast_fixture(env)
    real = forecast_service.calculate_forecast

    def change_access(points, raw, *events):
        result = real(points, raw, *events)
        body["expected_version"] = 1
        body["grants"][1]["conditions"][0]["value"] = "Lahore"
        changed = env.client.put(policy_path, headers=owner, json=body)
        assert changed.status_code == 200, changed.text
        return result

    monkeypatch.setattr(forecast_service, "calculate_forecast", change_access)
    response = create(env, member, root, engine="advanced-v2")
    assert response.status_code == 404, response.text
    with env.engine.connect() as connection:
        assert connection.execute(select(s.forecast_runs.c.id)).all() == []
