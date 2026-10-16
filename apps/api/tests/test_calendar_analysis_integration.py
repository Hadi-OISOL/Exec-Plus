"""Use case: Verifies chronological analyses through real governed query receipts.

What it does: Checks exact retained results, privacy, policy races and immutable
compatibility while refusing incomplete windows and invented source meanings.
"""

from copy import deepcopy
from datetime import date, timedelta
from fractions import Fraction
from uuid import UUID

import pytest
from sqlalchemy import select, update

from execplus.application.services import calendar_analysis as calendar_module
from execplus.infrastructure.persistence import schema as s
from test_analysis_access_policies import grant, revise
from test_result_exports import download_text
from test_studies import add_member, prepare
from test_understanding import confirm, context

SEASONAL = "seasonal-residual-mad-iqr-v1"
DRIFT = "empirical-window-distance-v1"


def fixture(env, method=SEASONAL, both_regions=False, mutate=None):
    values = [10 + (index % 7) * 20 + (100 if index == 28 else 0) for index in range(49)]
    if method == DRIFT:
        values = [0] * 4 + [2] * 4 + [1] * 4 + [3] * 4
    rows = [
        f"{date(2020, 1, 1) + timedelta(days=index)},North,{value},999"
        for index, value in enumerate(values)
    ]
    if both_regions:
        rows += [
            f"{date(2020, 1, 1) + timedelta(days=index)},South,1000,777"
            for index in range(len(values))
        ]
    if mutate:
        rows = mutate(rows)
    content = ("day,region,amount,secret\n" + "\n".join(rows) + "\n").encode()
    owner, actor, wid, did, uid, root = prepare(env, content)
    current = context(env, owner, root)
    current["definition"].update(grain="record", description="Private whole-source description")
    next(
        column for column in current["definition"]["columns"] if column["name"] == "amount"
    ).update(unit="", currency="USD")
    response = confirm(env, owner, root, current)
    assert response.status_code == 201, response.text
    return owner, actor, wid, did, uid, root


def create(env, headers, root, method=SEASONAL, **changes):
    options = env.client.get(root + "/decision-analysis/options", headers=headers)
    assert options.status_code == 200, options.text
    current = options.json()
    body = dict(
        name="Private calendar check",
        model=method,
        revision_id=current["revision_id"],
        understanding_id=current["understanding_id"],
        metric="amount",
        aggregation="sum",
        time_column="day",
        frequency="daily",
        coverage_confirmed=True,
        materiality="0",
        filters=[],
    )
    if method == SEASONAL:
        body.update(
            coverage_start="2020-01-01",
            coverage_end="2020-02-18",
            training_end="2020-01-28",
            season_length=7,
            threshold="3.5",
        )
        path = "/seasonal-anomalies"
    else:
        body.update(
            reference_start="2020-01-01",
            reference_end="2020-01-08",
            comparison_start="2020-01-09",
            comparison_end="2020-01-16",
            minimum_cdf_separation="0.2",
        )
        path = "/distribution-drift"
    return env.client.post(
        root + "/decision-analysis" + path, headers=headers, json={**body, **changes}
    )


def endpoint(root, body):
    return root.split("/uploads/")[0] + "/decision-analysis/" + body["run"]["id"]


@pytest.mark.parametrize("method", [SEASONAL, DRIFT])
def test_calendar_methods_keep_exact_private_receipts_and_immutable_replay(integration, method):
    env = integration
    owner, _, wid, _, _, root = fixture(env, method)
    response = create(env, owner, root, method)
    assert response.status_code == 201, response.text
    body = response.json()
    result = body["run"]["result"]
    assert body["run"]["method_version"] == method
    if method == SEASONAL:
        assert [item["period"] for item in result["findings"]] == ["2020-01-29", "2020-02-05"]
        assert result["reference"]["baseline"] == "0"
        assert result["history"][28]["actual"] == "110"
        assert result["history"][28]["expected"] == "10"
    else:
        distance = result["wasserstein_distance"]
        assert Fraction(int(distance["numerator"]), int(distance["denominator"])) == 1
        assert result["maximum_cdf_separation"]["display"] == "0.5"
    assert env.client.get(endpoint(root, body), headers=owner).json()["run"] == body["run"]
    ids = [value for values in body["run"]["evidence"]["calendar_query_ids"] for value in values]
    assert len(set(ids)) == (3 if method == SEASONAL else 6)
    for identifier in ids:
        path = f"/workspaces/{wid}/queries/{identifier}"
        receipt = env.client.get(path, headers=owner)
        assert receipt.status_code == 200, receipt.text
        assert receipt.json()["model_route"] == "deterministic:" + method
        assert receipt.json()["aggregation"] == "analysis"
        replay = env.client.post(path + "/replay", headers=owner)
        assert replay.status_code == 200, replay.text
    target = result["findings"][0]["id"]
    review = env.client.post(
        endpoint(root, body) + "/reviews",
        headers=owner,
        json=dict(
            target=target,
            status="investigate",
            note="Check the observed change",
            expected_version=0,
        ),
    )
    assert review.status_code == 201, review.text
    assert env.client.get(endpoint(root, body), headers=owner).json()["run"] == body["run"]


@pytest.mark.parametrize("method", [SEASONAL, DRIFT])
def test_calendar_results_and_all_receipts_are_hidden_from_another_workspace_admin(
    integration, method
):
    env = integration
    owner, _, wid, _, _, root = fixture(env, method)
    response = create(env, owner, root, method)
    assert response.status_code == 201, response.text
    body = response.json()
    member, _ = add_member(env, owner, wid, "admin")
    assert env.client.get(endpoint(root, body), headers=member).status_code == 404
    assert (
        env.client.get(root.split("/uploads/")[0] + "/decision-analysis", headers=member).json()
        == []
    )
    for identifier in [
        value for values in body["run"]["evidence"]["calendar_query_ids"] for value in values
    ]:
        path = f"/workspaces/{wid}/queries/{identifier}"
        assert env.client.get(path, headers=member).status_code == 404
        assert env.client.post(path + "/replay", headers=member).status_code == 404


@pytest.mark.parametrize(
    "changes",
    [
        dict(coverage_confirmed=False),
        dict(coverage_confirmed=1),
        dict(training_end="2020-01-27"),
        dict(training_end="2020-02-17"),
        dict(season_length=12),
        dict(coverage_end="2099-01-01"),
        dict(time_column="region"),
        dict(metric="secret", aggregation="median"),
    ],
)
def test_calendar_coverage_and_method_inputs_never_silently_change(integration, changes):
    env = integration
    owner, _, _, _, _, root = fixture(env)
    response = create(env, owner, root, **changes)
    assert response.status_code == 422, response.text
    with env.engine.connect() as connection:
        assert connection.execute(select(s.analysis_runs.c.id)).all() == []


@pytest.mark.parametrize("problem", ["missing_period", "missing_measure", "missing_date"])
def test_missing_coverage_is_not_imputed(integration, problem):
    def mutate(rows):
        if problem == "missing_period":
            return rows[:12] + rows[13:]
        rows[12] = rows[12].replace(
            "2020-01-13" if problem == "missing_date" else ",110,",
            "" if problem == "missing_date" else ",,",
        )
        return rows

    env = integration
    owner, _, _, _, _, root = fixture(env, mutate=mutate)
    response = create(env, owner, root)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("field", ["request", "result", "units", "queries", "coverage", "records"])
def test_saved_calendar_evidence_tampering_is_refused(integration, field):
    env = integration
    owner, _, _, _, _, root = fixture(env)
    body = create(env, owner, root).json()
    column = field if field in {"request", "result"} else "evidence"
    value = deepcopy(body["run"][column])
    if field in {"request", "result"}:
        value["tampered"] = True
    elif field == "units":
        value["units"]["amount"] = "EUR"
    elif field == "queries":
        value["calendar_query_ids"][0][1] = value["calendar_query_ids"][0][0]
    elif field == "coverage":
        value["coverage_declaration"] = "Automatically guaranteed complete"
    else:
        value["matching_records"] += 1
    with env.engine.begin() as connection:
        connection.execute(
            update(s.analysis_runs)
            .where(s.analysis_runs.c.id == UUID(body["run"]["id"]))
            .values(**{column: value})
        )
    assert env.client.get(endpoint(root, body), headers=owner).status_code == 409


def restricted_fixture(env, method=SEASONAL):
    owner, owner_actor, wid, did, _, root = fixture(env, method, both_regions=True)
    member, actor = add_member(env, owner, wid)
    path, rules = grant(
        env,
        owner,
        owner_actor,
        wid,
        did,
        actor,
        ["day", "amount"],
        dict(column="region", operator="eq", value="North"),
    )
    return owner, member, root, path, rules


@pytest.mark.parametrize("method", [SEASONAL, DRIFT])
@pytest.mark.parametrize("format", ["pdf", "xlsx", "csv", "png"])
def test_calendar_exports_retain_every_period_and_private_exact_evidence(
    integration, method, format
):
    env = integration
    owner, member, root, policy, rules = restricted_fixture(env, method)
    response = create(env, member, root, method)
    assert response.status_code == 201, response.text
    body = response.json()
    path = (
        root.split("/uploads/")[0] + f"/analyses/{body['run']['id']}/export.{format}?kind=anomaly"
    )
    exported = download_text(env.client.get(path, headers=member), format)
    result = body["run"]["result"]
    rows = result["history"] if method == SEASONAL else result["observations"]
    for row in rows:
        assert row["period"] in exported
        assert row["actual" if method == SEASONAL else "value"] in exported
    assert "withheld_for_restricted_access" in exported
    assert "Private whole-source description" not in exported
    assert "secret" not in exported
    assert "calibrated" in exported
    for ids in body["run"]["evidence"]["calendar_query_ids"]:
        for identifier in ids:
            assert identifier in exported
    assert env.client.get(path, headers=owner).status_code == 404
    assert env.client.get(endpoint(root, body), headers=member).json()["run"] == body["run"]
    revise(env, owner, policy, rules)
    assert env.client.get(path, headers=member).status_code == 404


def test_restricted_calendar_evidence_stays_projected_and_policy_revisions_hide_saved_work(
    integration,
):
    env = integration
    owner, member, root, policy, rules = restricted_fixture(env)
    response = create(env, member, root)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["run"]["evidence"]["matching_records"] == 49
    assert {column["name"] for column in body["run"]["evidence"]["definition"]["columns"]} == {
        "day",
        "amount",
    }
    assert "Private whole-source description" not in response.text
    assert body["run"]["evidence"]["sources"][0]["fingerprints"] == "withheld_for_restricted_access"
    assert body["run"]["result"]["history"][28]["actual"] == "110"
    assert env.client.get(endpoint(root, body), headers=owner).status_code == 404
    assert env.client.get(endpoint(root, body), headers=member).json()["run"] == body["run"]
    revise(env, owner, policy, rules)
    assert env.client.get(endpoint(root, body), headers=member).status_code == 404
    assert (
        env.client.get(root.split("/uploads/")[0] + "/decision-analysis", headers=member).json()
        == []
    )


def test_policy_change_during_calendar_math_blocks_publication(integration, monkeypatch):
    env = integration
    owner, member, root, policy, rules = restricted_fixture(env)
    original = calendar_module.calculate_calendar

    def changed(raw, values):
        result = original(raw, values)
        revise(env, owner, policy, rules)
        return result

    monkeypatch.setattr(calendar_module, "calculate_calendar", changed)
    response = create(env, member, root)
    assert response.status_code in {404, 422}, response.text
    with env.engine.connect() as connection:
        assert connection.execute(select(s.analysis_runs.c.id)).all() == []


def test_old_snapshot_and_new_calendar_results_reopen_after_new_meaning(integration):
    env = integration
    owner, _, _, _, _, root = fixture(env)
    calendar = create(env, owner, root).json()
    current = env.client.get(root + "/decision-analysis/options", headers=owner).json()
    snapshot_response = env.client.post(
        root + "/decision-analysis/anomalies",
        headers=owner,
        json=dict(
            name="Original snapshot",
            metric="amount",
            revision_id=current["revision_id"],
            understanding_id=current["understanding_id"],
        ),
    )
    assert snapshot_response.status_code == 201, snapshot_response.text
    snapshot = snapshot_response.json()
    meaning = context(env, owner, root)
    meaning["definition"]["description"] = "New description for future analyses"
    assert confirm(env, owner, root, meaning).status_code == 201
    for saved in (snapshot, calendar):
        reopened = env.client.get(endpoint(root, saved), headers=owner)
        assert reopened.status_code == 200, reopened.text
        assert reopened.json()["run"] == saved["run"]
        assert reopened.json()["current"] is False
