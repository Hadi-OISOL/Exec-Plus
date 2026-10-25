"""Use case: Verifies "Build a prediction model" through the governed API.

What it does: Checks sign-in, owner-only results and receipts, stale-source refusal,
exact reopening and refusal of tampered or reviewed prediction runs.
"""

import random

from sqlalchemy import update

from execplus.infrastructure.persistence import schema as s
from test_studies import add_member, prepare
from test_understanding import confirm, context


def content(size=300):
    rng = random.Random(11)
    lines = ["outcome,visits,channel,lead_id,spend"]
    for index in range(size):
        visits = rng.randint(0, 20)
        channel = rng.choice(["web", "phone", "partner"])
        score = (visits - 10) / 4 + (0.8 if channel == "partner" else 0) + rng.gauss(0, 1)
        lines.append(
            f"{'yes' if score > 1 else 'no'},{visits},{channel},L{index:05d},"
            f"{round(rng.gauss(100, 15), 2)}"
        )
    return ("\n".join(lines) + "\n").encode()


def create(env, headers, root, **changes):
    options = env.client.get(root + "/decision-analysis/options", headers=headers)
    assert options.status_code == 200, options.text
    value = options.json()
    body = dict(
        name="Who will convert?",
        revision_id=value["revision_id"],
        understanding_id=value["understanding_id"],
        target_column="outcome",
    )
    body.update(changes)
    return env.client.post(
        root + "/decision-analysis/prediction-models", headers=headers, json=body
    )


def test_owner_private_result_reopens_exactly(integration):
    env = integration
    owner, _, wid, _, _, root = prepare(env, content())
    options = env.client.get(root + "/decision-analysis/options", headers=owner).json()
    assert {"name": "outcome", "task": "classification"} in options["prediction_models"]["targets"]
    assert options["prediction_models"]["state"] == "ready"
    response = create(env, owner, root)
    assert response.status_code == 201, response.text
    run = response.json()["run"]
    result = run["result"]
    assert run["method_version"] == "prediction-model-v1"
    assert result["verdict"]["status"] == "beats_guess"
    assert result["coverage"]["holdout_rows"] == 60
    assert "lead_id" in {item["column"] for item in result["exclusions"]}
    base = root.split("/uploads/")[0]
    url = base + "/decision-analysis/" + run["id"]
    opened = env.client.get(url, headers=owner)
    assert opened.status_code == 200, opened.text
    assert opened.json()["run"] == run
    assert [
        item["id"] for item in env.client.get(base + "/decision-analysis", headers=owner).json()
    ] == [run["id"]]
    member, _ = add_member(env, owner, wid, "admin")
    assert env.client.get(url, headers=member).status_code == 404
    assert env.client.get(base + "/decision-analysis", headers=member).json() == []
    query = f"/workspaces/{wid}/queries/{run['evidence']['query_id']}"
    assert env.client.get(query, headers=member).status_code == 404
    review = env.client.post(
        url + "/reviews",
        headers=owner,
        json=dict(target="decision", status="approved", note="ok", expected_version=0),
    )
    assert review.status_code == 422
    with env.engine.begin() as connection:
        changed = {**result, "metrics": {**result["metrics"], "auc": "0.9999"}}
        connection.execute(
            update(s.analysis_runs).where(s.analysis_runs.c.id == run["id"]).values(result=changed)
        )
    assert env.client.get(url, headers=owner).status_code == 409


def test_sign_in_stale_source_and_leaking_inputs_are_refused(integration):
    env = integration
    owner, _, _, _, _, root = prepare(env, content())
    stale = env.client.get(root + "/decision-analysis/options", headers=owner).json()
    assert (
        env.client.post(
            root + "/decision-analysis/prediction-models",
            json=dict(
                name="x",
                revision_id=stale["revision_id"],
                understanding_id=stale["understanding_id"],
                target_column="outcome",
            ),
        ).status_code
        == 401
    )
    current = context(env, owner, root)
    assert confirm(env, owner, root, current).status_code == 201
    refused = env.client.post(
        root + "/decision-analysis/prediction-models",
        headers=owner,
        json=dict(
            name="Old options",
            revision_id=stale["revision_id"],
            understanding_id=stale["understanding_id"],
            target_column="outcome",
        ),
    )
    assert refused.status_code == 422 and "current source" in refused.text
    leaking = create(env, owner, root, input_columns=["lead_id", "visits"])
    assert leaking.status_code == 422 and "lead_id" in leaking.text
    regression = create(env, owner, root, target_column="spend", input_columns=["visits"])
    assert regression.status_code == 201, regression.text
    assert regression.json()["run"]["result"]["task"] == "regression"
