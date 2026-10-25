"""Use case: Verifies the hypotheses-v1 checks, model-spec grammar and private feedback ordering.

What it does: Uploads fictional leads and sales files, recomputes every tested candidate with
pandas independently, and checks endpoint scoping, feedback toggling and per-member privacy.
"""

import io
import json
import random
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pandas as pd
import pytest

from execplus.domain.hypotheses import (
    Fields,
    Spec,
    candidates,
    evaluate,
    ordered,
    parse_model_specs,
    updated_feedback,
)
from test_workspace_integration import identity, invite, upload, workspace


def leads_csv() -> bytes:
    rng = random.Random(7)
    lines = ["lead_name,source,location,intent_score,fit_score,total_score,posted_at"]
    sources = ["LinkedIn", "Upwork", "Reddit", "Facebook"]
    start = date(2026, 8, 1)
    for index in range(48):
        source = sources[index % 4] if index % 3 else "LinkedIn"
        intent = rng.randint(6, 10) if source == "LinkedIn" else rng.randint(2, 8)
        fit = rng.randint(6, 10) if source == "LinkedIn" else rng.randint(1, 8)
        total = fit * 5 + intent * 4 + rng.randint(0, 9)
        location = ["Lahore", "Karachi", "Remote"][rng.randint(0, 2)]
        posted = start + timedelta(days=index * 2)
        lines.append(
            f"Lead {index},{source},{location},{intent},{fit},{total},{posted.isoformat()}"
        )
    return ("\n".join(lines) + "\n").encode()


def sales_csv() -> bytes:
    rng = random.Random(11)
    lines = ["region,product,revenue,units,order_date"]
    start = date(2026, 1, 1)
    for index in range(60):
        region = ["North", "North", "North", "South", "East"][index % 5]
        units = rng.randint(1, 20)
        price = Decimal(rng.randint(500, 2500)) / 100
        revenue = price * units * (3 if region == "North" else 1)
        product = ["Tea", "Rice", "Oil"][rng.randint(0, 2)]
        day = start + timedelta(days=index * 3)
        lines.append(f"{region},{product},{revenue},{units},{day.isoformat()}")
    return ("\n".join(lines) + "\n").encode()


def pandas_status(frame: pd.DataFrame, kind: str, measure: str, column: str, direction: str):
    """An independent recomputation of the published rule for one candidate."""
    if kind == "group_gap":
        kept = frame[[column, measure]].dropna()
        counts = kept[column].astype(str).value_counts()
        top = sorted(counts.index, key=lambda label: (-counts[label], label))[0]
        inside = kept[kept[column].astype(str) == top][measure].astype(float)
        outside = kept[kept[column].astype(str) != top][measure].astype(float)
        if len(inside) < 5 or len(outside) < 5:
            return "not_enough_data", {}
        pooled = (
            ((len(inside) - 1) * inside.var() + (len(outside) - 1) * outside.var())
            / (len(inside) + len(outside) - 2)
        ) ** 0.5
        gap = inside.mean() - outside.mean()
        signed = gap if direction == "higher" else -gap
        holds = signed / pooled >= 0.2 if pooled else signed > 0
        figures = {"group_average": inside.mean(), "other_average": outside.mean()}
        return ("supported" if holds else "not_supported"), figures
    if kind == "relationship":
        kept = frame[[measure, column]].dropna().astype(float)
        if len(kept) < 20:
            return "not_enough_data", {}
        rho = kept[measure].corr(kept[column], method="spearman")
        holds = rho >= 0.3 if direction == "rises" else rho <= -0.3
        return ("supported" if holds else "not_supported"), {"spearman": rho}
    if kind == "concentration":
        grouped = frame.groupby(column)
        totals = grouped[measure].sum() if measure else grouped.size()
        share = totals.max() * 100 / totals.sum()
        return ("supported" if share > 50 else "not_supported"), {"share_percent": share}
    kept = frame[[column, measure]].dropna().sort_values(column, kind="stable")
    dates = sorted(kept[column])
    cutoff = dates[len(dates) // 2]
    older = kept[kept[column] < cutoff][measure].astype(float)
    recent = kept[kept[column] >= cutoff][measure].astype(float)
    if len(older) < 5 or len(recent) < 5:
        return "not_enough_data", {}
    pooled = (
        ((len(older) - 1) * older.var() + (len(recent) - 1) * recent.var())
        / (len(older) + len(recent) - 2)
    ) ** 0.5
    gap = recent.mean() - older.mean()
    signed = gap if direction == "higher" else -gap
    return ("supported" if signed / pooled >= 0.2 else "not_supported"), {
        "recent_average": recent.mean(),
        "older_average": older.mean(),
    }


def post_file(env, content, name, email):
    headers, _ = identity(env, email)
    wid = workspace(env, headers)
    did = env.client.post(
        f"/workspaces/{wid}/datasets", headers=headers, json={"name": name}
    ).json()["id"]
    response = upload(env, headers, wid, did, content, name, "text/csv")
    assert response.status_code == 201, response.text
    return headers, wid, response.json()["id"]


@pytest.mark.parametrize(
    ("content", "name", "date_column"),
    [(leads_csv(), "Fictional leads.csv", "posted_at"), (sales_csv(), "Sales.csv", "order_date")],
)
def test_statuses_match_an_independent_pandas_recomputation(
    integration, content, name, date_column
):
    headers, wid, uid = post_file(integration, content, name, f"{uuid4().hex[:8]}@example.test")
    response = integration.client.get(
        f"/workspaces/{wid}/uploads/{uid}/hypotheses", headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version"] == "hypotheses-v1"
    items = body["items"]
    assert 4 <= len(items) <= 8
    assert {item["kind"] for item in items} == {
        "group_gap",
        "relationship",
        "concentration",
        "recent_change",
    }
    frame = pd.read_csv(io.BytesIO(content), parse_dates=[date_column])
    for item in items:
        kind, measure, column, direction = item["id"].split(":")
        status, figures = pandas_status(frame, kind, measure, column, direction)
        assert item["status"] == status, item
        for key, value in figures.items():
            tolerance = {"share_percent": 0.05, "spearman": 0.0006}.get(key, 1e-9)
            assert abs(float(item["evidence"][key]) - float(value)) <= tolerance, (key, item)
        assert item["evidence"]["query_id"]
        assert set(item) == {
            "id",
            "kind",
            "origin",
            "statement",
            "status",
            "finding",
            "evidence",
            "question",
            "feedback",
        }
        assert all(isinstance(value, str) for value in item["evidence"].values())
        assert "cause" not in item["statement"].casefold()
    relationship = next(item for item in items if item["kind"] == "relationship")
    assert "not proof of a cause" in relationship["finding"]
    assert any(item["status"] == "supported" for item in items)


def test_leads_find_the_linkedin_gap_and_sales_find_one_dominant_region(integration):
    headers, wid, uid = post_file(integration, leads_csv(), "Leads.csv", "lead-h@example.test")
    items = integration.client.get(
        f"/workspaces/{wid}/uploads/{uid}/hypotheses", headers=headers
    ).json()["items"]
    gap = next(
        item for item in items if item["id"].startswith("group_gap:") and ":source:" in item["id"]
    )
    measure = gap["id"].split(":")[1]
    assert gap["statement"] == (
        f"Leads where source is LinkedIn have a higher average {measure} than other leads."
    )
    assert gap["status"] == "supported"
    assert gap["question"] == f"What is the average of {measure} by source?"
    headers, wid, uid = post_file(integration, sales_csv(), "Sales.csv", "sales-h@example.test")
    items = integration.client.get(
        f"/workspaces/{wid}/uploads/{uid}/hypotheses", headers=headers
    ).json()["items"]
    share = next(item for item in items if item["kind"] == "concentration")
    assert share["statement"] == "One region accounts for most of the total revenue."
    assert share["status"] == "supported" and share["evidence"]["top_group"] == "North"


def test_endpoint_scoping_404_and_auth(integration):
    headers, wid, uid = post_file(integration, leads_csv(), "Leads.csv", "scope-h@example.test")
    path = f"/workspaces/{wid}/uploads/{uid}/hypotheses"
    assert integration.client.get(path, headers=headers).status_code == 200
    missing = f"/workspaces/{wid}/uploads/{uuid4()}/hypotheses"
    assert integration.client.get(missing, headers=headers).status_code == 404
    outsider, _ = identity(integration, "outsider-h@example.test")
    assert integration.client.get(path, headers=outsider).status_code in {403, 404}
    assert integration.client.get(path).status_code == 401
    feedback = f"/workspaces/{wid}/hypothesis-feedback"
    assert integration.client.put(
        feedback, headers=outsider, json={"kind": "relationship", "vote": "like"}
    ).status_code in {403, 404}


def test_feedback_reorders_types_for_that_member_only_and_toggles_off(integration):
    env = integration
    headers, wid, uid = post_file(env, leads_csv(), "Leads.csv", "owner-h@example.test")
    member, _ = identity(env, "member-h@example.test")
    invitation = invite(env, headers, wid, "member-h@example.test").json()["id"]
    assert (
        env.client.post(
            f"/workspaces/{wid}/invitations/{invitation}/accept", headers=member
        ).status_code
        == 200
    )
    path = f"/workspaces/{wid}/uploads/{uid}/hypotheses"
    before = [item["kind"] for item in env.client.get(path, headers=headers).json()["items"]]
    assert before[0] == "group_gap"
    feedback = f"/workspaces/{wid}/hypothesis-feedback"
    saved = env.client.put(feedback, headers=headers, json={"kind": "group_gap", "vote": "dislike"})
    assert saved.status_code == 200, saved.text
    assert saved.json() == {"feedback": {"group_gap": {"vote": "dislike"}}}
    saved = env.client.put(
        feedback,
        headers=headers,
        json={"kind": "group_gap", "vote": "dislike", "reason": "too_obvious"},
    )
    assert saved.json()["feedback"]["group_gap"] == {"vote": "dislike", "reason": "too_obvious"}
    mine = env.client.get(path, headers=headers).json()["items"]
    kinds = [item["kind"] for item in mine]
    assert kinds[-before.count("group_gap") :] == ["group_gap"] * before.count("group_gap")
    assert all(
        item["feedback"] == ("dislike" if item["kind"] == "group_gap" else None) for item in mine
    )
    theirs = env.client.get(path, headers=member).json()["items"]
    assert [item["kind"] for item in theirs] == before
    assert all(item["feedback"] is None for item in theirs)
    cleared = env.client.put(
        feedback, headers=headers, json={"kind": "group_gap", "vote": "dislike"}
    )
    assert cleared.json() == {"feedback": {}}
    assert [item["kind"] for item in env.client.get(path, headers=headers).json()["items"]] == (
        before
    )
    bad = env.client.put(feedback, headers=headers, json={"kind": "group_gap", "vote": "meh"})
    assert bad.status_code == 422


FIELDS = Fields(
    ("intent_score", "fit_score"), ("intent_score", "fit_score"), (), ("source",), "posted_at"
)


def test_model_specs_must_stay_inside_the_grammar():
    reply = {
        "specs": [
            {
                "kind": "relationship",
                "measure": "fit_score",
                "column": "intent_score",
                "direction": "falls",
            }
        ]
    }
    specs = parse_model_specs(json.dumps(reply), FIELDS)
    assert specs == [Spec("relationship", "fit_score", "intent_score", "falls", "model")]
    for bad in (
        {"specs": [{**reply["specs"][0], "measure": "salary"}]},
        {"specs": [{**reply["specs"][0], "direction": "causes"}]},
        {"specs": [{**reply["specs"][0], "value": "42"}]},
        {"specs": reply["specs"] * 4},
        {"specs": [], "note": "x"},
    ):
        with pytest.raises(ValueError):
            parse_model_specs(json.dumps(bad), FIELDS)


def test_candidates_are_varied_bounded_and_feedback_only_moves_disliked_kinds():
    specs = candidates(FIELDS)
    assert len(specs) <= 8
    assert [spec.kind for spec in specs[:4]] == [
        "group_gap",
        "relationship",
        "concentration",
        "recent_change",
    ]
    moved = ordered(specs, {"group_gap": {"vote": "dislike"}})
    assert [spec.kind for spec in moved][-2:] == ["group_gap", "group_gap"]
    assert ordered(specs, {}) == specs
    assert updated_feedback({"relationship": {"vote": "like"}}, "relationship", "like", None) == {}
    with pytest.raises(ValueError):
        updated_feedback({}, "relationship", "like", "too_obvious")


def test_small_groups_report_not_enough_data():
    rows = tuple((label, Decimal(value)) for label, value in [("A", 1), ("A", 2), ("B", 3)])
    outcome = evaluate(
        Spec("group_gap", "score", "team", "higher"), "teams", ("team", "score"), rows
    )
    assert outcome.status == "not_enough_data"
    assert outcome.evidence["group_rows"] == "2"
