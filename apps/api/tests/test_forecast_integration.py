"""Use case: Verifies forecasts over real retained PostgreSQL and MinIO snapshots.

What it does: Covers exact calendar evidence, private history, refreshed actuals and refusals.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update

from execplus.infrastructure.persistence import schema as s
from test_refresh import setup as refresh_setup
from test_refresh import stage
from test_studies import add_member, prepare
from test_understanding import confirm, context
from test_workspace_integration import dataset, identity, upload, workspace


def daily(count=40, missing=None, blank=None, extra=False):
    rows = ["day,amount,city"]
    for index in range(count):
        if index == missing:
            continue
        day = date(2024, 1, 1) + timedelta(days=index)
        amount = "" if index == blank else str(Decimal(index + 1) / 10)
        rows.append(f"{day},{amount},Karachi")
        if extra:
            rows.append(f"{day},100,Lahore")
    return ("\n".join(rows) + "\n").encode()


def request(env, headers, root, **changes):
    options = env.client.get(root + "/forecasts/options", headers=headers)
    assert options.status_code == 200, options.text
    choice = options.json()
    return (
        dict(
            name="Daily sales outlook",
            time_column="day",
            metric="amount",
            aggregation="sum",
            filters=[],
            frequency="daily",
            horizon=3,
            season_length=None,
            coverage_start="2024-01-01",
            coverage_end="2024-02-09",
            coverage_confirmed=True,
            revision_id=choice["revision_id"],
            understanding_id=choice["understanding_id"],
        )
        | changes
    )


def create(env, headers, root, **changes):
    return env.client.post(
        root + "/forecasts", headers=headers, json=request(env, headers, root, **changes)
    )


def test_forecast_retains_exact_calendar_receipts_and_reopens(integration):
    env = integration
    owner, _, wid, did, _uid, root = prepare(env, daily())
    options = env.client.get(root + "/forecasts/options", headers=owner).json()
    assert options["state"] == "ready"
    assert options["date_columns"] == ["day"]
    result = create(env, owner, root)
    assert result.status_code == 201, result.text
    value = result.json()
    assert value["result"]["history"][0]["actual"] == "0.100000000000"
    assert value["result"]["history"][-1]["actual"] == "4.000000000000"
    assert value["result"]["method"]["id"] == "linear_trend"
    assert Decimal(value["result"]["predictions"][0]["estimate"]) == Decimal("4.1")
    assert Decimal(value["result"]["accuracy"]["mae"]) == 0
    assert len(value["evidence"]["query_ids"]) == 3
    for query in value["evidence"]["query_ids"]:
        replay = env.client.post(f"/workspaces/{wid}/queries/{query}/replay", headers=owner)
        assert replay.status_code == 200, replay.text
    path = f"/workspaces/{wid}/datasets/{did}/forecasts"
    listed = env.client.get(path, headers=owner).json()
    assert listed[0]["id"] == value["id"] and "result" not in listed[0]
    reopened = env.client.get(path + "/" + value["id"], headers=owner)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["result"] == value["result"]
    assert "not a percentage guarantee" in " ".join(value["result"]["commentary"])
    changed = context(env, owner, root)
    changed["definition"]["columns"][1]["meaning"] = "Reviewed daily sales"
    assert confirm(env, owner, root, changed).status_code == 201
    assert (
        env.client.get(path + "/" + value["id"], headers=owner).json()["result"] == value["result"]
    )


def test_forecast_comparison_preserves_original_and_pending_periods(integration):
    env = integration
    owner, _, wid, did, uid, root = prepare(env, daily())
    original = create(env, owner, root).json()
    original_definition = original["evidence"]["definition"]
    next_uid = upload(env, owner, wid, did, daily(42)).json()["id"]
    next_root = root.replace(uid, next_uid)
    assert (
        confirm(
            env, owner, next_root, context(env, owner, next_root), original_definition
        ).status_code
        == 201
    )
    raw = request(env, owner, next_root)
    path = f"/workspaces/{wid}/datasets/{did}/forecasts/{original['id']}"
    comparison = env.client.post(
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
    assert comparison.status_code == 201, comparison.text
    value = comparison.json()
    assert value["result"]["observed_count"] == 2 and value["result"]["pending_count"] == 1
    assert value["result"]["rows"][0]["actual"] == "4.100000000000"
    assert value["result"]["rows"][-1]["actual"] is None
    assert Decimal(value["result"]["metrics"]["mae"]) == 0
    assert env.client.get(path, headers=owner).json()["result"] == original["result"]
    reopened = env.client.get(path + "/comparisons/" + value["id"], headers=owner)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["result"] == value["result"]
    assert len(env.client.get(path + "/comparisons", headers=owner).json()) == 1
    changed = context(env, owner, next_root)
    changed["definition"]["columns"][1]["unit"] = "USD"
    assert confirm(env, owner, next_root, changed).status_code == 201
    changed_raw = request(env, owner, next_root)
    failed = env.client.post(
        path + "/compare",
        headers=owner,
        json={
            "upload_id": next_uid,
            "revision_id": changed_raw["revision_id"],
            "understanding_id": changed_raw["understanding_id"],
            "coverage_start": "2024-02-10",
            "coverage_end": "2024-02-11",
            "coverage_confirmed": True,
        },
    )
    assert (
        failed.status_code == 409
        and failed.json()["error"]["code"] == "forecast_definition_changed"
    )


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"coverage_confirmed": False}, "invalid_request"),
        ({"frequency": "monthly"}, "incomplete_period"),
        ({"coverage_end": "2024-01-12"}, "forecast_insufficient_history"),
        ({"coverage_end": "2099-01-01"}, "invalid_coverage"),
        ({"horizon": 30}, "forecast_insufficient_history"),
        ({"time_column": "city"}, "date_required"),
        (
            {"filters": [{"column": "day", "operator": "eq", "value": "2024-01-01"}]},
            "invalid_forecast_filter",
        ),
        ({"season_length": 5}, "forecast_season"),
    ],
)
def test_forecast_invalid_scope_is_actionable(integration, changes, code):
    env = integration
    owner, _, _, _, _, root = prepare(env, daily())
    result = create(env, owner, root, **changes)
    assert result.status_code == 422, result.text
    assert result.json()["error"]["code"] == code


@pytest.mark.parametrize(
    "content,code", [(daily(missing=5), "missing_periods"), (daily(blank=5), "missing_measure")]
)
def test_forecast_never_silently_imputes_missing_data(integration, content, code):
    env = integration
    owner, _, _, _, _, root = prepare(env, content)
    result = create(env, owner, root)
    assert result.status_code == 422, result.text
    assert result.json()["error"]["code"] == code


def test_forecasts_honor_governed_filters_and_current_confirmation(integration):
    env = integration
    owner, _, wid, did, uid, root = prepare(env, daily(extra=True))
    current = context(env, owner, root)
    current["definition"]["metrics"] = [
        dict(
            name="Karachi revenue",
            column="amount",
            aggregation="sum",
            filters=[dict(column="city", operator="eq", value="Karachi")],
        )
    ]
    assert confirm(env, owner, root, current).status_code == 201
    result = create(env, owner, root)
    assert result.status_code == 201, result.text
    assert Decimal(result.json()["result"]["history"][-1]["actual"]) == 4
    assert create(env, owner, root, aggregation="avg").status_code == 422
    old = request(env, owner, root)
    current = context(env, owner, root)
    assert confirm(env, owner, root, current).status_code == 201
    assert env.client.post(root + "/forecasts", headers=owner, json=old).status_code == 422
    next_uid = upload(env, owner, wid, did, daily(41)).json()["id"]
    assert (
        env.client.get(root.replace(uid, next_uid) + "/forecasts/options", headers=owner).json()[
            "state"
        ]
        == "needs_review"
    )


def test_forecast_privacy_cross_workspace_and_revocation(integration):
    env = integration
    owner, _, wid, did, _, root = prepare(env, daily())
    member, actor = add_member(env, owner, wid)
    result = create(env, member, root)
    assert result.status_code == 201, result.text
    value = result.json()
    path = f"/workspaces/{wid}/datasets/{did}/forecasts"
    assert env.client.get(path, headers=owner).json() == []
    assert env.client.get(path + "/" + value["id"], headers=owner).status_code == 404
    outsider, _ = identity(env, f"forecast-outsider-{uuid4().hex}@example.test")
    other_wid = workspace(env, outsider)
    other_did = dataset(env, outsider, other_wid)
    assert (
        env.client.get(
            path.replace(wid, other_wid).replace(did, other_did) + "/" + value["id"],
            headers=outsider,
        ).status_code
        == 404
    )
    assert (
        env.client.delete(f"/workspaces/{wid}/members/{actor.id}", headers=owner).status_code == 204
    )
    assert env.client.get(path + "/" + value["id"], headers=member).status_code == 404


def test_forecast_rejects_tampered_stored_result(integration):
    env = integration
    owner, _, wid, did, _, root = prepare(env, daily())
    value = create(env, owner, root).json()
    altered = dict(value["result"])
    altered["predictions"][0]["estimate"] = "9999"
    with env.engine.begin() as connection:
        connection.execute(
            update(s.forecast_runs)
            .where(s.forecast_runs.c.id == UUID(value["id"]))
            .values(result=altered)
        )
    response = env.client.get(
        f"/workspaces/{wid}/datasets/{did}/forecasts/{value['id']}", headers=owner
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "lineage_mismatch"


def test_monthly_forecast_uses_weighted_raw_average_and_exact_sum(integration):
    env = integration
    rows = ["day,amount,city"]
    for index in range(24):
        year, month = 2022 + index // 12, index % 12 + 1
        rows += [
            f"{year}-{month:02}-01,0.10,Karachi",
            f"{year}-{month:02}-01,0.20,Karachi",
            f"{year}-{month:02}-20,0.60,Karachi",
        ]
    owner, _, _, _, _, root = prepare(env, ("\n".join(rows) + "\n").encode())
    result = create(
        env,
        owner,
        root,
        frequency="monthly",
        aggregation="avg",
        coverage_start="2022-01-01",
        coverage_end="2023-12-31",
    )
    assert result.status_code == 201, result.text
    assert all(
        Decimal(point["actual"]) == Decimal("0.3") for point in result.json()["result"]["history"]
    )
    summed = create(
        env,
        owner,
        root,
        frequency="monthly",
        aggregation="sum",
        coverage_start="2022-01-01",
        coverage_end="2023-12-31",
    )
    assert summed.status_code == 201, summed.text
    assert all(
        Decimal(point["actual"]) == Decimal("0.9") for point in summed.json()["result"]["history"]
    )
    with env.engine.connect() as connection:
        assert connection.execute(select(s.forecast_runs.c.id)).all()


def test_scheduled_refresh_supplies_later_actuals_without_rewriting_forecast(integration):
    env = integration
    owner, _, _wid, _did, uid, path, _ = refresh_setup(env, daily())
    root = path + f"/uploads/{uid}"
    original_response = create(env, owner, root)
    assert original_response.status_code == 201, original_response.text
    original = original_response.json()
    candidate = stage(env, owner, path, daily(43))
    assert candidate.status_code == 201, candidate.text
    assert candidate.json()["status"] == "queued"
    due = datetime.now(timezone.utc) + timedelta(hours=2)
    assert env.runtime.refresh.process_due(due)["activated"] == 1
    head = env.client.get(path + "/refresh", headers=owner).json()["feed"]["source"]
    comparison = env.client.post(
        path + f"/forecasts/{original['id']}/compare",
        headers=owner,
        json=dict(
            upload_id=head["upload_id"],
            revision_id=head["revision_id"],
            understanding_id=head["understanding_id"],
            coverage_start="2024-02-10",
            coverage_end="2024-02-12",
            coverage_confirmed=True,
        ),
    )
    assert comparison.status_code == 201, comparison.text
    result = comparison.json()["result"]
    assert result["observed_count"] == 3 and result["pending_count"] == 0
    assert Decimal(result["metrics"]["mae"]) == 0
    reopened = env.client.get(path + f"/forecasts/{original['id']}", headers=owner)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["result"] == original["result"]
