"""Use case: Verifies bounded proactive discovery and meaningful low-input choices.

What it does: Covers reordered farm fields, safe pH suggestions and real governed execution.
"""

from dataclasses import replace

import pytest

from execplus.domain.discovery import discovery_steps
from execplus.domain.exploration_selection import anomaly_default
from execplus.domain.guidance import suggested_exploration
from execplus.domain.patterns import pattern_request
from test_discovery import setup
from test_patterns import prepared
from test_understanding import confirm, context
from test_workspace_integration import identity


def test_outcomes_and_useful_groups_survive_wide_source_order():
    headers = [
        *[f"sensor_{i}" for i in range(10)],
        "Yield",
        *[f"label_{i}" for i in range(5)],
        "Region",
        "Irrigation",
        "Growth_Stage",
    ]
    rows = [
        (
            [i + j for j in range(10)]
            + [i * 3]
            + ["A" if i % 2 else "B"] * 5
            + [
                "North" if i % 2 else "South",
                "Drip" if i % 2 else "Flood",
                "Harvest" if i % 2 else "Growing",
            ]
        )
        for i in range(40)
    ]
    ctx, table = prepared(headers, rows)
    request = pattern_request(ctx, table)
    assert request["metrics"][0] == "Yield"
    assert {"Region", "Irrigation", "Growth_Stage"} <= set(request["categories"])
    assert len(request["metrics"]) == 8 and len(request["categories"]) == 4
    assert request["focus"] == ["Yield"]
    assert discovery_steps(ctx)[0].metric == "Yield"
    focused = pattern_request(ctx, table, ("sensor_9",))
    assert focused["metrics"][0] == "sensor_9"


def test_ph_suggestion_is_average_and_never_invents_percentage_unit():
    ctx, _ = prepared(
        ["Soil_pH", "Region"], [(6 + i / 100, "A" if i % 2 else "B") for i in range(20)]
    )
    prompts = suggested_exploration(ctx)
    assert any("average of Soil_pH" in prompt for prompt in prompts)
    assert not any("total" in prompt or "%" in prompt for prompt in prompts)
    assert anomaly_default(ctx)["unit"] == "units"


@pytest.mark.parametrize(
    "condition", ["unconfirmed", "missing_unit", "variable_unit", "few_rows", "identifier"]
)
def test_anomaly_default_excludes_ineligible_measures(condition):
    ctx, _ = prepared(["amount"], [(i,) for i in range(20)])
    if condition == "unconfirmed":
        ctx = replace(ctx, state="needs_review")
    elif condition == "few_rows":
        ctx, _ = prepared(["amount"], [(i,) for i in range(7)])
    elif condition == "identifier":
        ctx = replace(ctx, view=replace(ctx.view, metrics={}))
    else:
        column = ctx.view.definition["columns"][0]
        if condition == "missing_unit":
            column["unit"] = None
        else:
            column["unit_column"] = "unit"
    assert anomaly_default(ctx) is None


def test_confirmed_discovery_runs_one_scoped_pattern_scan_and_replays(integration):
    env = integration
    content = b"Region,revenue,cost\n" + b"".join(
        f"{'North' if i % 2 else 'South'},{i},{i * 2}\n".encode() for i in range(1, 41)
    )
    owner, wid, root, model = setup(env, content)
    current = context(env, owner, root)
    for column in current["definition"]["columns"]:
        if column["role"] == "metric":
            column["unit"] = "USD"
    assert confirm(env, owner, root, current, current["definition"]).status_code == 201
    response = env.client.get(root + "/discovery", headers=owner)
    assert response.status_code == 200, response.text
    brief = response.json()
    evidence = brief["patterns_evidence"]
    assert evidence["sources"] == brief["sources"]
    assert evidence["result"]["findings"]
    replay = env.client.post(
        f"/workspaces/{wid}/queries/{evidence['query_id']}/replay", headers=owner
    )
    assert replay.status_code == 200, replay.text
    assert len(replay.json()["rows"]) == 40
    options = env.client.get(root + "/decision-analysis/options", headers=owner).json()
    default = options["anomaly_default"]
    assert default["metric"] == "revenue" and default["unit"] == "USD"
    result = env.client.post(
        root + "/decision-analysis/anomalies",
        headers=owner,
        json=dict(
            name="Suggested check",
            revision_id=options["revision_id"],
            understanding_id=options["understanding_id"],
            metric=default["metric"],
            threshold=default["threshold"],
            materiality=default["materiality"],
            minimum_segment_size=default["minimum_segment_size"],
            segment_column=None,
            filters=[],
        ),
    )
    assert result.status_code == 201, result.text
    assert result.json()["run"]["result"]["sample_count"] == 40
    outsider, _ = identity(env, "proactive-outsider@example.test")
    assert env.client.get(root + "/discovery", headers=outsider).status_code == 404
    assert env.client.get(root + "/decision-analysis/options", headers=outsider).status_code == 404
    assert not model.requests


def test_old_source_order_pattern_evidence_reopens_unchanged(integration, monkeypatch):
    from execplus.application.services import patterns as module
    from test_patterns_integration import discover, reopen, sample
    from test_studies import prepare

    env = integration
    _, actor, wid, did, uid, _ = prepare(env, sample())
    current = module.pattern_request

    def legacy(context, table, selected=()):
        return current(context, table, selected, selection_version=None)

    monkeypatch.setattr(module, "pattern_request", legacy)
    evidence = discover(env, actor, wid, did, uid)
    assert "selection_version" not in evidence["request"]
    monkeypatch.setattr(module, "pattern_request", current)
    assert reopen(env, actor, wid, evidence) == evidence


def test_confirmed_automatic_pattern_scan_cannot_publish_after_meaning_change(
    integration, monkeypatch
):
    import asyncio

    env = integration
    content = b"amount,reading\n" + b"".join(f"{i},{i * 2}\n".encode() for i in range(40))
    owner, _, root, _ = setup(env, content)
    current = context(env, owner, root)
    for column in current["definition"]["columns"]:
        column["unit"] = "units"
    assert confirm(env, owner, root, current, current["definition"]).status_code == 201
    original = env.runtime.intent_router.patterns.discover

    async def changed(*args, **kwargs):
        result = await original(*args, **kwargs)
        latest = await asyncio.to_thread(context, env, owner, root)
        latest["definition"]["description"] = "Changed while the briefing was computing"
        saved = await asyncio.to_thread(confirm, env, owner, root, latest)
        assert saved.status_code == 201
        return result

    monkeypatch.setattr(env.runtime.intent_router.patterns, "discover", changed)
    response = env.client.get(root + "/discovery", headers=owner)
    assert response.status_code == 422, response.text
    assert "meaning changed" in response.text


def test_automatic_patterns_and_anomaly_choices_use_only_authorized_projection(integration):
    from test_studies import add_member, prepare

    env = integration
    content = b"city,amount,reading,secret_cost\n" + b"".join(
        f"{'Visible' if i < 20 else 'Hidden'},{i + 1},{i * 2},987654\n".encode() for i in range(40)
    )
    owner, actor, wid, did, _, root = prepare(env, content)
    member, user = add_member(env, owner, wid)
    policy = env.client.put(
        f"/workspaces/{wid}/datasets/{did}/access-policy",
        headers=owner,
        json=dict(
            expected_version=0,
            enabled=True,
            grants=[
                dict(user_id=str(actor.id), columns=None, conditions=[]),
                dict(
                    user_id=str(user.id),
                    columns=["city", "amount", "reading"],
                    conditions=[dict(column="city", operator="eq", value="Visible")],
                ),
            ],
        ),
    )
    assert policy.status_code == 200, policy.text
    response = env.client.get(root + "/discovery", headers=member)
    assert response.status_code == 200, response.text
    evidence = response.json()["patterns_evidence"]
    assert evidence["result"]["coverage"]["filtered_rows"] == 20
    assert evidence["sources"][0]["access_actor_id"] == str(user.id)
    assert "secret_cost" not in response.text and "Hidden" not in response.text
    options = env.client.get(root + "/decision-analysis/options", headers=member)
    assert options.status_code == 200, options.text
    assert options.json()["anomaly_default"]["metric"] == "amount"
    assert "secret_cost" not in options.text
