"""Use case: Verifies new anomaly methods through governed API and export paths.

What it does: Replays exact results, protects private findings and original records,
tests denied columns/cohorts and refuses stale publication after permissions change.
"""

from copy import deepcopy
from uuid import UUID

import pytest
from sqlalchemy import select, update

from execplus.application.services import calendar_analysis, decision_analysis
from execplus.domain.multivariate_anomalies import METHOD as MULTI
from execplus.domain.rolling_anomalies import METHOD as ROLLING
from execplus.infrastructure.persistence import schema as s
from test_analysis_access_policies import grant, revise
from test_calendar_analysis_integration import fixture as calendar_fixture
from test_result_exports import download_text
from test_studies import add_member, prepare
from test_understanding import confirm, context


def setup(env, method):
    if method == ROLLING:
        return calendar_fixture(
            env,
            mutate=lambda rows: [
                ",".join([*row.split(",")[:2], "1000" if i == 28 else "10", "999"])
                for i, row in enumerate(rows)
            ],
        )
    rows = [
        f"r{i},{'reference' if i < 60 else 'comparison'},{(i * 3 + i * i) % 41},"
        f"{(i * 11 + i * i * 2) % 41 if i < 65 else 10000},private"
        for i in range(70)
    ]
    owner, actor, wid, did, uid, root = prepare(
        env, ("id,cohort,a,b,secret\n" + "\n".join(rows) + "\n").encode()
    )
    current = context(env, owner, root)
    for column in current["definition"]["columns"]:
        if column["name"] == "id":
            column.update(role="identifier")
        elif column["name"] == "cohort":
            column.update(role="dimension")
        elif column["name"] in {"a", "b"}:
            column.update(role="metric", unit="units", currency="")
    response = confirm(env, owner, root, current)
    assert response.status_code == 201, response.text
    return owner, actor, wid, did, uid, root


def body(env, headers, root, method):
    options = env.client.get(root + "/decision-analysis/options", headers=headers).json()
    common = dict(
        name="Advanced private review",
        model=method,
        revision_id=options["revision_id"],
        understanding_id=options["understanding_id"],
        filters=[],
    )
    if method == ROLLING:
        return {
            **common,
            "metric": "amount",
            "time_column": "day",
            "aggregation": "sum",
            "frequency": "daily",
            "coverage_confirmed": True,
            "coverage_start": "2020-01-01",
            "coverage_end": "2020-02-18",
            "evaluation_start": "2020-01-21",
            "reference_window": 20,
            "season_length": 1,
            "threshold": "3.5",
            "materiality": "0",
        }
    return {
        **common,
        "identifier_column": "id",
        "cohort_column": "cohort",
        "metrics": ["a", "b"],
        "reference_label": "reference",
        "comparison_label": "comparison",
        "threshold": "9",
    }


def create(env, headers, root, method, changes=None):
    suffix = "rolling-anomalies" if method == ROLLING else "multivariate-anomalies"
    return env.client.post(
        root + "/decision-analysis/" + suffix,
        headers=headers,
        json={**body(env, headers, root, method), **(changes or {})},
    )


@pytest.mark.parametrize("method", [ROLLING, MULTI])
def test_exact_replay_private_findings_feedback_and_exports(integration, method):
    env = integration
    owner, _, wid, _, _, root = setup(env, method)
    before = context(env, owner, root)
    response = create(env, owner, root, method)
    assert response.status_code == 201, response.text
    saved = response.json()
    run = saved["run"]
    base = root.split("/uploads/")[0]
    url = base + "/decision-analysis/" + run["id"]
    assert run["result"]["findings"]
    opened = env.client.get(url, headers=owner)
    assert opened.status_code == 200, opened.text
    assert opened.json()["run"] == run
    member, _ = add_member(env, owner, wid, "admin")
    assert env.client.get(url, headers=member).status_code == 404
    assert env.client.get(base + "/decision-analysis", headers=member).json() == []
    ids = [
        i
        for group in run["evidence"].get("calendar_query_ids", [[run["evidence"]["query_id"]]])
        for i in group
    ]
    for qid in ids:
        assert env.client.get(f"/workspaces/{wid}/queries/{qid}", headers=member).status_code == 404
        assert (
            env.client.post(f"/workspaces/{wid}/queries/{qid}/replay", headers=owner).status_code
            == 200
        )
    for format in ["xlsx", "pdf", "csv"]:
        export = base + f"/analyses/{run['id']}/export.{format}?kind=anomaly"
        value = env.client.get(export, headers=owner)
        text = download_text(value, format)
        assert ("2020-01-29" if method == ROLLING else "r65") in text
        assert env.client.get(export, headers=member).status_code == 404
    review = env.client.post(
        url + "/reviews",
        headers=owner,
        json=dict(
            target=run["result"]["findings"][0]["id"],
            status="investigate",
            note="Review source records",
            expected_version=0,
        ),
    )
    assert review.status_code == 201, review.text
    assert review.json()["run"] == run
    assert context(env, owner, root) == before


@pytest.mark.parametrize("method", [ROLLING, MULTI])
def test_current_policy_blocks_saved_results_receipts_and_exports(integration, method):
    env = integration
    owner, actor, wid, did, _, root = setup(env, method)
    member, reader = add_member(env, owner, wid)
    columns = ["day", "region", "amount"] if method == ROLLING else ["id", "cohort", "a", "b"]
    condition = (
        {"column": "region", "operator": "eq", "value": "North"}
        if method == ROLLING
        else {"column": "id", "operator": "ne", "value": "unseen"}
    )
    policy, state = grant(env, owner, actor, wid, did, reader, columns, condition)
    response = create(env, member, root, method)
    assert response.status_code == 201, response.text
    run = response.json()["run"]
    base = root.split("/uploads/")[0]
    assert "secret" not in str(run["evidence"]["definition"])
    state = deepcopy(state)
    state["grants"] = state["grants"][:1]
    revise(env, owner, policy, state)
    assert (
        env.client.get(base + "/decision-analysis/" + run["id"], headers=member).status_code == 404
    )
    assert (
        env.client.get(
            base + f"/analyses/{run['id']}/export.xlsx?kind=anomaly", headers=member
        ).status_code
        == 404
    )
    assert (
        env.client.post(
            f"/workspaces/{wid}/queries/{run['evidence']['query_id']}/replay", headers=member
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"metrics": ["a", "secret"]},
        {"metrics": ["a", "a"]},
        {"identifier_column": "cohort"},
        {"cohort_column": "id"},
        {"reference_label": "comparison"},
        {"threshold": "0"},
        {"reference_label": "reference' OR 1=1 --"},
    ],
)
def test_invalid_multivariate_columns_thresholds_and_injection_refuse(integration, changes):
    env = integration
    owner, *_, root = setup(env, MULTI)
    response = create(env, owner, root, MULTI, changes)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    "changes",
    [
        {"coverage_confirmed": False},
        {"reference_window": 19},
        {"season_length": 2},
        {"evaluation_start": "2020-01-19"},
        {"coverage_end": "2020-03-01"},
    ],
)
def test_rolling_refuses_incomplete_or_unsupported_windows(integration, changes):
    env = integration
    owner, *_, root = setup(env, ROLLING)
    response = create(env, owner, root, ROLLING, changes)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("method", [ROLLING, MULTI])
def test_permission_change_during_math_prevents_publication(integration, monkeypatch, method):
    env = integration
    owner, actor, wid, did, _, root = setup(env, method)
    member, reader = add_member(env, owner, wid)
    condition = (
        dict(column="region", operator="eq", value="North")
        if method == ROLLING
        else dict(column="id", operator="ne", value="unseen")
    )
    policy, state = grant(env, owner, actor, wid, did, reader, None, condition)
    module = calendar_analysis if method == ROLLING else decision_analysis
    name = "calculate_calendar" if method == ROLLING else "calculate"
    original = getattr(module, name)

    def changed(raw, values):
        result = original(raw, values)
        revise(env, owner, policy, state)
        return result

    monkeypatch.setattr(module, name, changed)
    response = create(env, member, root, method)
    assert response.status_code in {404, 422}, response.text
    with env.engine.connect() as connection:
        assert connection.execute(select(s.analysis_runs.c.id)).all() == []


@pytest.mark.parametrize("method", [ROLLING, MULTI])
def test_immutable_results_survive_later_meaning_but_reject_tampering(integration, method):
    env = integration
    owner, _, _, _, _, root = setup(env, method)
    response = create(env, owner, root, method)
    assert response.status_code == 201, response.text
    saved = response.json()["run"]
    path = root.split("/uploads/")[0] + "/decision-analysis/" + saved["id"]
    meaning = context(env, owner, root)
    meaning["definition"]["description"] = "New meaning version for future work"
    assert confirm(env, owner, root, meaning).status_code == 201
    opened = env.client.get(path, headers=owner)
    assert opened.status_code == 200, opened.text
    assert opened.json()["run"] == saved and opened.json()["current"] is False
    altered = deepcopy(saved["result"])
    altered["findings"] = []
    with env.engine.begin() as connection:
        connection.execute(
            update(s.analysis_runs)
            .where(s.analysis_runs.c.id == UUID(saved["id"]))
            .values(result=altered)
        )
    assert env.client.get(path, headers=owner).status_code == 409
    assert (
        env.client.get(
            root.split("/uploads/")[0] + f"/analyses/{saved['id']}/export.xlsx?kind=anomaly",
            headers=owner,
        ).status_code
        == 409
    )
