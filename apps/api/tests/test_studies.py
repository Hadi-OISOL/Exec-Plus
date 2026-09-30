"""Use case: Verifies adaptive studies and dashboards using real retained snapshots.

What it does: Covers exact evidence, survey order, revocation, races and department isolation.
"""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from execplus.domain.errors import UnsupportedQuestionError
from execplus.domain.ingestion import IngestionError
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import dataset_view
from execplus.domain.studies import recommendations, validated_method
from execplus.domain.understanding import apply_definition, infer_definition
from execplus.infrastructure.persistence import schema as s
from test_understanding import confirm, context
from test_workspace_integration import accept, dataset, identity, invite, upload, workspace


def prepare(
    env, content=b"city,amount,cost\nKarachi,0.10,0.05\nLahore,0.20,0.15\n", domain="sales"
):
    headers, actor = identity(env, f"study-{uuid4().hex}@example.test")
    wid = workspace(env, headers)
    did = dataset(env, headers, wid)
    uid = upload(env, headers, wid, did, content).json()["id"]
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{uid}"
    current = context(env, headers, root)
    current["definition"]["domain"] = domain
    for column in current["definition"]["columns"]:
        if column["role"] == "metric":
            column["unit"] = "PKR"
    confirmed = confirm(env, headers, root, current)
    assert confirmed.status_code == 201, confirmed.text
    return headers, actor, wid, did, uid, root


def run(env, headers, root, method=None):
    current = env.client.get(root + "/adaptive-views", headers=headers).json()
    return env.client.post(
        root + "/studies",
        headers=headers,
        json=dict(
            name="A reproducible study",
            question="How does amount vary?",
            revision_id=current["revision_id"],
            understanding_id=current["understanding_id"],
            method=method or dict(kind="metric", column="amount", aggregation="sum"),
        ),
    )


def add_member(env, owner, wid, role="member"):
    member, actor = identity(env, f"teammate-{uuid4().hex}@example.test")
    iid = invite(env, owner, wid, actor.email, role).json()["id"]
    assert accept(env, member, wid, iid).status_code == 200
    return member, actor


@pytest.mark.parametrize("domain", ["sales", "finance", "inventory", "operations", "research"])
def test_recommendations_require_units_respect_domain_and_goal(domain):
    table = TableData(("city", "amount", "cost"), (("Karachi", "10", "2"),))
    source = profile(table)
    definition = infer_definition(source)
    definition["domain"] = domain
    for column in definition["columns"]:
        if column["role"] == "metric":
            column["unit"] = "PKR"
    view = apply_definition(dataset_view(source), definition)
    choices = recommendations(view, "cost")
    assert choices[0]["method"]["column"] == "cost"
    assert domain in choices[0]["reason"]
    assert "private goal" in choices[0]["reason"]
    assert {item["component"] for item in choices} <= {
        "table",
        "bar",
        "card",
        "line",
        "distribution",
    }
    definition["columns"][2]["role"] = "identifier"
    changed = recommendations(apply_definition(dataset_view(source), definition), "cost")
    assert all(item["method"]["column"] != "cost" for item in changed)
    definition["columns"][1]["unit"] = ""
    changed = recommendations(apply_definition(dataset_view(source), definition), "amount")
    assert all(item["method"]["kind"] != "metric" for item in changed)


@pytest.mark.parametrize(
    "bad",
    [
        dict(kind=[]),
        dict(aggregation=[]),
        dict(filters=[dict(column="amount", operator=[], value=1)]),
        dict(order=[[]]),
    ],
)
def test_invalid_methods_fail_cleanly(bad):
    source = profile(TableData(("amount",), (("1",),)))
    view = apply_definition(dataset_view(source), infer_definition(source))
    with pytest.raises((IngestionError, UnsupportedQuestionError)):
        validated_method(
            dict(
                kind="metric",
                column="amount",
                aggregation="sum",
                **{key: value for key, value in bad.items() if key not in {"kind", "aggregation"}},
            )
            | bad,
            view,
        )


def test_suggestions_dismissals_are_private_and_definition_scoped(integration):
    env = integration
    owner, _, wid, _did, _uid, root = prepare(env)
    member, _ = add_member(env, owner, wid)
    choices = env.client.get(root + "/adaptive-views", headers=owner).json()
    first = choices["recommendations"][0]["id"]
    assert (
        env.client.post(
            root + "/adaptive-views/dismissals",
            headers=owner,
            json=dict(understanding_id=choices["understanding_id"], dismissed=[first]),
        ).status_code
        == 204
    )
    assert first not in {
        item["id"]
        for item in env.client.get(root + "/adaptive-views", headers=owner).json()[
            "recommendations"
        ]
    }
    assert first in {
        item["id"]
        for item in env.client.get(root + "/adaptive-views", headers=member).json()[
            "recommendations"
        ]
    }
    changed = context(env, owner, root)
    changed["definition"]["domain"] = "finance"
    assert confirm(env, owner, root, changed).status_code == 201
    assert env.client.get(root + "/adaptive-views", headers=owner).json()["dismissed"] == []


def test_study_exact_receipts_missingness_replay_and_rerun(integration):
    env = integration
    owner, _, wid, did, uid, root = prepare(
        env, b"city,amount\nKarachi,0.10\nKarachi,0.20\nLahore,\n"
    )
    response = run(env, owner, root)
    assert response.status_code == 201, response.text
    first = response.json()
    assert first["display"]["rows"] == [["0.300000000000"]]
    assert first["display"]["coverage"]["rows"] == [[3, 2, 1]]
    assert first["sample_count"] == 3
    assert first["version"]["evidence"]["preparation_version"] == "profile-v1"
    assert all(
        item["lineage"]["receipt"]["sources"][0]["understanding_id"] for item in first["results"]
    )
    path = f"/workspaces/{wid}/study-versions/{first['version']['id']}"
    assert env.client.get(path, headers=owner).json()["display"] == first["display"]
    new_uid = upload(env, owner, wid, did, b"city,amount\nKarachi,0.50\n").json()["id"]
    new_root = root.replace(uid, new_uid)
    assert (
        env.client.get(new_root + "/adaptive-views", headers=owner).json()["state"]
        == "needs_review"
    )
    meaning = context(env, owner, new_root)
    assert confirm(env, owner, new_root, meaning).status_code == 201
    suggested = env.client.get(new_root + "/adaptive-views", headers=owner).json()
    rerun = env.client.post(
        f"/workspaces/{wid}/studies/{first['study']['id']}/rerun",
        headers=owner,
        json=dict(
            upload_id=new_uid,
            parent_id=first["version"]["id"],
            revision_id=suggested["revision_id"],
            understanding_id=suggested["understanding_id"],
        ),
    )
    assert rerun.status_code == 201, rerun.text
    second = rerun.json()
    assert second["version"]["number"] == 2
    assert second["display"]["rows"] == [["0.500000000000"]]
    assert env.client.get(path, headers=owner).json()["display"] == first["display"]
    comparison = env.client.get(
        f"/workspaces/{wid}/study-comparison",
        headers=owner,
        params=dict(before=first["version"]["id"], after=second["version"]["id"]),
    ).json()
    assert comparison["comparable"]
    assert comparison["differences"][0]["delta"] == "0.200000000000"


def test_ordered_survey_counts_missing_groups_and_limits(integration):
    env = integration
    owner, _, wid, _, _, root = prepare(
        env, b"team,rating\nSales,Agree\nSales,Disagree\nSales,Agree\nSupport,\n", "research"
    )
    method = dict(
        kind="distribution", column="rating", group_by=["team"], order=["Disagree", "Agree"]
    )
    missing_order = run(env, owner, root, {**method, "order": []})
    assert missing_order.status_code == 422
    response = run(env, owner, root, method)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["display"]["rows"] == [
        ["Sales", "Disagree", 1],
        ["Sales", "Agree", 2],
        ["Support", None, 1],
    ]
    assert body["sample_count"] == 4
    assert any("fewer than five" in text for text in body["limitations"])
    assert run(env, owner, root, {**method, "order": ["Agree"]}).status_code == 422
    missing = run(env, owner, root, dict(kind="missingness", column="rating", group_by=["team"]))
    assert missing.status_code == 201, missing.text
    assert missing.json()["display"]["rows"] == [["Sales", 3, 3, 0], ["Support", 1, 0, 1]]
    assert (
        env.client.get(
            f"/workspaces/{wid}/study-versions/{body['version']['id']}", headers=owner
        ).json()["display"]
        == body["display"]
    )


@pytest.mark.parametrize("role", ["member", "admin"])
def test_private_studies_boards_explicit_sharing_and_revocation(integration, role):
    env = integration
    owner, _, wid, did, _, root = prepare(env)
    member, member_user = add_member(env, owner, wid, role)
    body = run(env, owner, root).json()
    sid, vid = body["study"]["id"], body["version"]["id"]
    path = f"/workspaces/{wid}"
    assert env.client.get(path + f"/study-versions/{vid}", headers=member).status_code == 404
    assert env.client.get(path + f"/datasets/{did}/studies", headers=member).json() == []
    assert (
        env.client.post(
            path + "/study-boards",
            headers=owner,
            json=dict(name="Team board", shared=True, pins=[vid]),
        ).status_code
        == 422
    )
    assert (
        env.client.patch(
            path + f"/studies/{sid}", headers=owner, json=dict(shared=True)
        ).status_code
        == 204
    )
    board = env.client.post(
        path + "/study-boards", headers=owner, json=dict(name="Team board", shared=True, pins=[vid])
    ).json()
    assert env.client.get(path + f"/study-boards/{board['id']}", headers=member).status_code == 200
    assert (
        env.client.patch(
            path + f"/study-boards/{board['id']}",
            headers=member,
            json=dict(name="Stolen", pins=[], expected_version=1),
        ).status_code
        == 403
    )
    assert (
        env.client.patch(
            path + f"/studies/{sid}", headers=member, json=dict(shared=False)
        ).status_code
        == 403
    )
    env.client.patch(path + f"/studies/{sid}", headers=owner, json=dict(shared=False))
    assert env.client.get(path + f"/study-boards/{board['id']}", headers=member).status_code == 404
    env.client.patch(path + f"/studies/{sid}", headers=owner, json=dict(shared=True))
    env.client.delete(path + f"/members/{member_user.id}", headers=owner)
    assert env.client.get(path + f"/study-boards/{board['id']}", headers=member).status_code == 404


def test_board_six_pin_bound_optimistic_concurrency_and_tenant_isolation(integration):
    env = integration
    owner, actor, wid, _, _, root = prepare(env)
    other = workspace(env, owner, "Other department")
    body = run(env, owner, root).json()
    version = body["version"]["id"]
    values = [str(uuid4()) for _ in range(7)]
    with pytest.raises(IngestionError, match="six"):
        env.runtime.studies.save_board(actor, UUID(wid), "Too many", False, values)
    assert (
        env.client.post(
            f"/workspaces/{other}/study-boards",
            headers=owner,
            json=dict(name="Cross tenant", pins=[version]),
        ).status_code
        == 404
    )
    assert (
        env.client.get(f"/workspaces/{other}/study-versions/{version}", headers=owner).status_code
        == 404
    )
    board = env.runtime.studies.save_board(actor, UUID(wid), "Pins", False, [version])

    def update_board():
        try:
            env.runtime.studies.save_board(actor, UUID(wid), "Pins", False, [], board.id, 1)
            return "saved"
        except IngestionError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: update_board(), range(2))) == ["board_conflict", "saved"]


def test_organization_membership_does_not_grant_department_access(integration):
    env = integration
    owner, _, wid, _, _, _root = prepare(env)
    member, _ = add_member(env, owner, wid)
    other = workspace(env, owner, "Finance")
    org = env.client.post("/organizations", headers=owner, json=dict(name="Demo company")).json()
    for workspace_id, name in ((wid, "Sales"), (other, "Finance")):
        attached = env.client.post(
            f"/workspaces/{workspace_id}/department",
            headers=owner,
            json=dict(organization_id=org["id"], name=name),
        )
        assert attached.status_code == 200, attached.text
    listing = env.client.get("/organizations", headers=member).json()
    assert listing[0]["departments"] == [
        dict(workspace_id=wid, organization_id=org["id"], name="Sales")
    ]
    assert env.client.get(f"/workspaces/{other}/study-boards", headers=member).status_code == 404
    assert (
        env.client.post(
            f"/workspaces/{wid}/department",
            headers=member,
            json=dict(organization_id=org["id"], name="Hijacked"),
        ).status_code
        == 403
    )
    outsider, _ = identity(env, "outside@example.test")
    assert env.client.get("/organizations", headers=outsider).json() == []


def test_source_changes_during_execution_do_not_save_a_study(integration, monkeypatch):
    env = integration
    owner, actor, wid, did, uid, root = prepare(env)
    original = env.runtime.analytics.executor.execute
    changed = False

    async def changing(plan, scope, table, view):
        nonlocal changed
        result = await original(plan, scope, table, view)
        if not changed:
            changed = True
            current = env.runtime.understanding.overview(actor, UUID(wid), UUID(did), UUID(uid))
            env.runtime.understanding.save(
                actor,
                UUID(wid),
                UUID(did),
                UUID(uid),
                UUID(current["revision_id"]),
                current["version"],
                "confirmed",
                current["definition"],
            )
        return result

    monkeypatch.setattr(env.runtime.analytics.executor, "execute", changing)
    response = run(env, owner, root)
    assert response.status_code == 409, response.text
    assert env.client.get(f"/workspaces/{wid}/datasets/{did}/studies", headers=owner).json() == []


def test_original_deleted_bytes_block_study_and_board_replay(integration):
    env = integration
    owner, _, wid, did, uid, root = prepare(env)
    created = run(env, owner, root).json()
    with env.runtime.studies.uow() as repo:
        source = repo.upload(UUID(wid), UUID(did), UUID(uid))
    env.runtime.analytics.storage.delete(source)
    response = env.client.get(
        f"/workspaces/{wid}/study-versions/{created['version']['id']}", headers=owner
    )
    assert response.status_code >= 400
    assert "0.300000000000" not in response.text


def test_study_audit_contains_identifiers_not_questions_or_results(integration):
    env = integration
    owner, _, wid, _, _, root = prepare(env)
    created = run(env, owner, root)
    assert created.status_code == 201, created.text
    with env.engine.connect() as connection:
        events = (
            connection.execute(
                select(s.audit_events).where(s.audit_events.c.workspace_id == UUID(wid))
            )
            .mappings()
            .all()
        )
    text = str(events)
    assert "study.created" in text
    assert "How does amount" not in text
    assert "Karachi" not in text


def test_required_filters_apply_to_both_business_value_and_coverage(integration):
    env = integration
    owner, _, wid, did, _, root = prepare(env, b"city,amount\nKarachi,0.10\nLahore,0.20\n")
    current = context(env, owner, root)
    current["definition"]["metrics"] = [
        dict(
            name="Karachi amount",
            column="amount",
            aggregation="sum",
            filters=[dict(column="city", operator="eq", value="Karachi")],
        )
    ]
    assert confirm(env, owner, root, current).status_code == 201
    env.client.post(
        f"/workspaces/{wid}/datasets/{did}/preferences",
        headers=owner,
        json=dict(domain_hint="sales", goal="private acquisition target"),
    )
    value = run(env, owner, root).json()
    assert value["display"]["rows"] == [["0.100000000000"]]
    assert value["display"]["coverage"]["rows"] == [[1, 1, 0]]
    assert value["sample_count"] == 1
    env.client.patch(
        f"/workspaces/{wid}/studies/{value['study']['id']}", headers=owner, json=dict(shared=True)
    )
    member, _ = add_member(env, owner, wid)
    shared = env.client.get(
        f"/workspaces/{wid}/study-versions/{value['version']['id']}", headers=member
    )
    assert shared.status_code == 200
    assert "private acquisition target" not in shared.text
    assert (
        "private acquisition target"
        not in env.client.get(f"/workspaces/{wid}/datasets/{did}/studies", headers=member).text
    )


def test_six_real_pins_then_seventh_refused(integration):
    env = integration
    owner, actor, wid, _, _, root = prepare(env)
    pins = [run(env, owner, root).json()["version"]["id"] for _ in range(7)]
    board = env.runtime.studies.save_board(actor, UUID(wid), "Six results", False, pins[:6])
    opened = env.client.get(f"/workspaces/{wid}/study-boards/{board.id}", headers=owner)
    assert opened.status_code == 200, opened.text
    assert len(opened.json()["studies"]) == 6
    response = env.client.patch(
        f"/workspaces/{wid}/study-boards/{board.id}",
        headers=owner,
        json=dict(name="Too many", pins=pins, expected_version=1),
    )
    assert response.status_code == 422
    assert (
        len(
            env.client.get(f"/workspaces/{wid}/study-boards/{board.id}", headers=owner).json()[
                "studies"
            ]
        )
        == 6
    )


def test_changed_units_disable_cross_version_deltas(integration):
    env = integration
    owner, _, wid, _, uid, root = prepare(env)
    first = run(env, owner, root).json()
    current = context(env, owner, root)
    current["definition"]["columns"][1]["unit"] = "USD"
    assert confirm(env, owner, root, current).status_code == 201
    suggestion = env.client.get(root + "/adaptive-views", headers=owner).json()
    second = env.client.post(
        f"/workspaces/{wid}/studies/{first['study']['id']}/rerun",
        headers=owner,
        json=dict(
            upload_id=uid,
            parent_id=first["version"]["id"],
            revision_id=suggestion["revision_id"],
            understanding_id=suggestion["understanding_id"],
        ),
    ).json()
    comparison = env.client.get(
        f"/workspaces/{wid}/study-comparison",
        headers=owner,
        params=dict(before=first["version"]["id"], after=second["version"]["id"]),
    ).json()
    assert not comparison["comparable"]
    assert comparison["differences"] == []
    assert comparison["before"]["unit"] == "PKR"
    assert comparison["after"]["unit"] == "USD"


def test_inventory_periods_and_no_matching_records_are_explicit(integration):
    env = integration
    owner, _, _, _, _, root = prepare(
        env, b"date,stock\n2026-01-01,10\n2026-01-02,12\n", "inventory"
    )
    current = context(env, owner, root)
    definition = current["definition"]
    definition["grain"] = "inventory_snapshot"
    response = env.client.post(
        root + "/understanding",
        headers=owner,
        json=dict(
            revision_id=current["revision_id"],
            expected_version=current["version"],
            state="confirmed",
            definition=definition,
        ),
    )
    assert response.status_code == 201, response.text
    assert (
        run(env, owner, root, dict(kind="metric", column="stock", aggregation="sum")).status_code
        == 422
    )
    trend = run(
        env, owner, root, dict(kind="metric", column="stock", aggregation="sum", group_by=["date"])
    )
    assert trend.status_code == 201, trend.text
    empty = run(
        env,
        owner,
        root,
        dict(
            kind="metric",
            column="stock",
            aggregation="sum",
            filters=[dict(column="date", operator="eq", value="2027-01-01")],
        ),
    )
    assert empty.status_code == 201, empty.text
    assert empty.json()["sample_count"] == 0
    assert any("insufficient data" in text for text in empty.json()["limitations"])


def test_domain_correction_changes_priority_and_ordinal_is_never_summed():
    source = profile(TableData(("revenue", "stock", "rating"), (("10", "20", "5"),)))
    definition = infer_definition(source)
    for column in definition["columns"]:
        column["unit"] = "units"
    definition["domain"] = "sales"
    sales = recommendations(apply_definition(dataset_view(source), definition), "")
    definition["domain"] = "inventory"
    inventory = recommendations(apply_definition(dataset_view(source), definition), "")
    assert sales[0]["method"]["column"] == "revenue"
    assert inventory[0]["method"]["column"] == "stock"
    view = apply_definition(dataset_view(source), definition)
    with pytest.raises(UnsupportedQuestionError):
        validated_method(dict(kind="metric", column="rating", aggregation="sum"), view)


def test_private_permission_is_rechecked_after_replay(integration, monkeypatch):
    env = integration
    owner, actor, wid, _, _, root = prepare(env)
    member, _ = add_member(env, owner, wid)
    first = run(env, owner, root).json()
    sid, vid = first["study"]["id"], first["version"]["id"]
    env.runtime.studies.share(actor, UUID(wid), UUID(sid), True)
    original = env.runtime.analytics.replay

    async def revoke_after_replay(*args, **kwargs):
        result = await original(*args, **kwargs)
        env.runtime.studies.share(actor, UUID(wid), UUID(sid), False)
        return result

    monkeypatch.setattr(env.runtime.analytics, "replay", revoke_after_replay)
    result = env.client.get(f"/workspaces/{wid}/study-versions/{vid}", headers=member)
    assert result.status_code == 404
    assert "0.300000000000" not in result.text
