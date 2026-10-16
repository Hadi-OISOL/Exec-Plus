"""Use case: Retains the exact answers supplied during a missing-details review.

What it does: Reproduces a confirmed four-field file, then checks unit saves, reopening and history.
"""

import copy

from test_conversational_explorer import ScriptedModel, prepare
from test_understanding import confirm, context

SOURCE = b"date,category,revenue,cost\n2026-01-01,Home,150,80\n2026-01-02,Office,200,90\n"


def reviewed_three_times(env):
    owner, wid, root = prepare(env, ScriptedModel(), content=SOURCE)
    for version in range(3):
        current = context(env, owner, root)
        definition = copy.deepcopy(current["definition"])
        definition["grain"] = "record"
        definition["description"] = f"Daily category sales and costs, review {version + 1}."
        for column in definition["columns"]:
            column["meaning"] = {
                "date": "The sales date",
                "category": "The product category",
                "revenue": "Money received from sales before costs",
                "cost": "Cost of sold products",
            }[column["name"]]
        assert confirm(env, owner, root, current, definition).status_code == 201
    return owner, wid, root


def test_confirmed_version_three_keeps_saved_meanings_and_saves_each_missing_unit(integration):
    env = integration
    owner, _, root = reviewed_three_times(env)
    before = context(env, owner, root)
    assert before["state"] == "confirmed" and before["version"] == 3
    assert before["questions"] == [
        "What unit does revenue measure?",
        "What unit does cost measure?",
    ]
    reading = env.client.post(root + "/data-brief?review_missing=true", headers=owner)
    assert reading.status_code == 200, reading.text
    brief = reading.json()
    assert brief["review_mode"] == "missing"
    assert {column["name"] for column in brief["columns"]} == {"revenue", "cost"}
    assert brief["next_question"]["kind"] == "unit"
    saved_definition = copy.deepcopy(before["definition"])
    revenue = next(c for c in saved_definition["columns"] if c["name"] == "revenue")
    revenue["unit"] = "USD"
    first = confirm(env, owner, root, before, saved_definition)
    assert first.status_code == 201, first.text
    reopened = context(env, owner, root)
    assert reopened["definition"] == saved_definition
    assert reopened["version"] == 4
    assert reopened["questions"] == ["What unit does cost measure?"]
    remaining = env.client.post(root + "/data-brief?review_missing=true", headers=owner).json()
    assert [column["name"] for column in remaining["columns"]] == ["cost"]
    assert remaining["definition"] == saved_definition
    cost = next(c for c in saved_definition["columns"] if c["name"] == "cost")
    cost["currency"] = "USD"
    second = confirm(env, owner, root, reopened, saved_definition)
    assert second.status_code == 201, second.text
    final = context(env, owner, root)
    assert final["definition"] == saved_definition and final["version"] == 5
    assert final["questions"] == []
    complete = env.client.post(root + "/data-brief?review_missing=true", headers=owner).json()
    assert complete["already_confirmed"] and complete["next_question"] is None
    for column in final["definition"]["columns"]:
        previous = next(c for c in before["definition"]["columns"] if c["name"] == column["name"])
        assert column["meaning"] == previous["meaning"]
        assert column["role"] == previous["role"]
    historic_id = next(item["id"] for item in final["history"] if item["version"] == 3)
    dataset_root = root.split("/uploads/")[0]
    historic = env.client.get(dataset_root + "/understandings/" + historic_id, headers=owner)
    assert historic.status_code == 200
    assert historic.json()["definition"] == before["definition"]


def test_saved_unitless_measure_does_not_reappear_as_missing_after_reopen(integration):
    env = integration
    owner, _, root = reviewed_three_times(env)
    current = context(env, owner, root)
    definition = copy.deepcopy(current["definition"])
    for column in definition["columns"]:
        if column["role"] == "metric":
            column["unit"] = "unitless"
    assert confirm(env, owner, root, current, definition).status_code == 201
    reopened = context(env, owner, root)
    assert reopened["questions"] == []
    assert reopened["definition"] == definition
    assert env.client.post(root + "/data-brief?review_missing=true", headers=owner).json()[
        "already_confirmed"
    ]
