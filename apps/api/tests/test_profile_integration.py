"""Use case: Verifies Phase 1 profiles, lineage, samples and usage on real services.

What it does: Proves authorization, atomic persistence, reconstruction and upgrade compatibility.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from uuid import UUID, uuid4

import pytest
from alembic import command
from sqlalchemy import delete, select

from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.persistence.repository import SQLWorkspaceRepository
from test_workspace_integration import dataset, identity, upload, workspace


def setup(env, email="owner@example.test", content=b"item,amount\n A ,10\nA,10\nB,\n"):
    headers, _ = identity(env, email)
    wid = workspace(env, headers)
    did = dataset(env, headers, wid)
    stored = upload(env, headers, wid, did, content=content)
    assert stored.status_code == 201, stored.text
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{stored.json()['id']}"
    profile = env.client.get(root + "/profile", headers=headers)
    assert profile.status_code == 200
    return headers, wid, did, root, profile.json()


def test_preview_apply_restart_reconstruct_restore_and_usage(integration):
    env = integration
    headers, wid, _, root, original = setup(env)
    body = {
        "expected_revision_id": original["id"],
        "trim": True,
        "drop_duplicates": True,
        "drop_missing": True,
        "mapping": {"amount": "sales"},
    }
    history = env.client.get(root + "/revisions", headers=headers).json()
    events_before = env.client.get(f"/workspaces/{wid}/usage", headers=headers).json()["events"]
    preview = env.client.post(root + "/cleaning/preview", headers=headers, json=body)
    assert preview.status_code == 200 and preview.headers["cache-control"] == "no-store"
    assert preview.json()["rows"] == [["A", "10"]]
    assert preview.json()["headers"] == ["item", "sales"]
    assert preview.json()["removed_rows"] == 2
    assert env.client.get(root + "/revisions", headers=headers).json() == history
    assert (
        env.client.get(f"/workspaces/{wid}/usage", headers=headers).json()["events"]
        == events_before
    )
    applied = env.client.post(root + "/cleaning/apply", headers=headers, json=body)
    assert applied.status_code == 201, applied.text
    active = applied.json()["revision"]
    assert active["output_checksum"] == preview.json()["revision"]["output_checksum"]
    assert active["source_checksum"] == original["source_checksum"]
    assert active["parent_id"] == original["id"] and len(active["recipe"]) == 1
    assert active["profile"]["quality_score"] == "100.00"
    assert (
        env.client.get(root + "/content", headers=headers).content
        == b"item,amount\n A ,10\nA,10\nB,\n"
    )
    env.engine.dispose()
    replay = env.client.post(
        root + "/cleaning/preview", headers=headers, json={"expected_revision_id": active["id"]}
    )
    assert replay.json()["rows"] == [["A", "10"]]
    assert replay.json()["revision"]["output_checksum"] == active["output_checksum"]
    restore = env.client.post(
        root + "/restore",
        headers=headers,
        json={"expected_revision_id": active["id"], "revision_id": original["id"]},
    )
    assert restore.status_code == 200 and restore.json()["id"] == original["id"]
    assert env.client.get(root + "/profile", headers=headers).json() == original
    assert len(env.client.get(root + "/revisions", headers=headers).json()) == 2
    usage = env.client.get(f"/workspaces/{wid}/usage", headers=headers)
    assert usage.json()["storage_bytes"] == len(b"item,amount\n A ,10\nA,10\nB,\n")
    assert usage.json()["uploads"] == 1 and usage.json()["active_seats"] == 1
    assert {event["kind"] for event in usage.json()["events"]} >= {
        "upload",
        "storage_bytes",
        "seat_added",
        "seat_limit",
        "profile",
        "cleaning",
        "restore",
    }
    assert "amount" not in usage.text and "sales" not in usage.text and "Bearer" not in usage.text
    audit = env.client.get(f"/workspaces/{wid}/audit-events", headers=headers).text
    assert "amount" not in audit and "sales" not in audit


def test_every_profile_route_rejects_cross_tenant_and_mixed_ids_before_storage(
    integration, monkeypatch
):
    env = integration
    first = setup(env, "first@example.test")
    second = setup(env, "second@example.test")

    def forbidden_read(*args):
        pytest.fail("Unauthorized request reached object storage")

    monkeypatch.setattr(env.runtime.service.storage, "read", forbidden_read)
    for own, other in ((first, second), (second, first)):
        headers, wid, did, _, revision = own
        _, foreign_wid, foreign_did, foreign_root, foreign_revision = other
        for root in (
            foreign_root,
            foreign_root.replace(foreign_wid, wid),
            foreign_root.replace(foreign_wid, wid).replace(foreign_did, did),
        ):
            for suffix in ("/profile", "/revisions"):
                assert env.client.get(root + suffix, headers=headers).status_code == 404
            for suffix in ("/cleaning/preview", "/cleaning/apply"):
                assert (
                    env.client.post(
                        root + suffix,
                        headers=headers,
                        json={"expected_revision_id": revision["id"]},
                    ).status_code
                    == 404
                )
            assert (
                env.client.post(
                    root + "/restore",
                    headers=headers,
                    json={
                        "expected_revision_id": revision["id"],
                        "revision_id": foreign_revision["id"],
                    },
                ).status_code
                == 404
            )
        assert (
            env.client.get(f"/workspaces/{foreign_wid}/usage", headers=headers).status_code == 404
        )
        assert (
            env.client.post(
                f"/workspaces/{foreign_wid}/samples/sales-v1", headers=headers
            ).status_code
            == 404
        )


def test_foreign_revision_and_revoked_membership_cannot_access_data(integration, monkeypatch):
    env = integration
    headers, wid, _, root, revision = setup(env)
    other = setup(env, "other@example.test")
    response = env.client.post(
        root + "/restore",
        headers=headers,
        json={"expected_revision_id": revision["id"], "revision_id": other[4]["id"]},
    )
    assert response.status_code == 404
    with env.engine.begin() as connection:
        connection.execute(delete(s.memberships).where(s.memberships.c.workspace_id == UUID(wid)))

    def forbidden_read(*args):
        pytest.fail("Revoked member reached storage")

    monkeypatch.setattr(env.runtime.service.storage, "read", forbidden_read)
    assert env.client.get(root + "/profile", headers=headers).status_code == 404
    assert (
        env.client.post(
            root + "/cleaning/apply", headers=headers, json={"expected_revision_id": revision["id"]}
        ).status_code
        == 404
    )


def test_concurrent_apply_and_stale_restore_are_conflicts(integration):
    headers, _, _, root, revision = setup(integration)
    body = {"expected_revision_id": revision["id"], "trim": True}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: (
                    integration.client.post(
                        root + "/cleaning/apply", headers=headers, json=body
                    ).status_code
                ),
                range(2),
            )
        )
    assert sorted(results) == [201, 409]
    assert len(integration.client.get(root + "/revisions", headers=headers).json()) == 2
    assert (
        integration.client.post(
            root + "/restore", headers=headers, json={**body, "revision_id": revision["id"]}
        ).status_code
        == 422
    )
    assert (
        integration.client.post(
            root + "/restore",
            headers=headers,
            json={"expected_revision_id": revision["id"], "revision_id": revision["id"]},
        ).status_code
        == 409
    )


def test_cleaning_audit_failure_rolls_back_revision_head_and_usage(integration, monkeypatch):
    env = integration
    headers, wid, _, root, revision = setup(env)
    before = env.client.get(f"/workspaces/{wid}/usage", headers=headers).json()

    def fail(*args):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(env.runtime.service, "_audit", fail)
    with pytest.raises(RuntimeError, match="simulated failure"):
        env.client.post(
            root + "/cleaning/apply",
            headers=headers,
            json={"expected_revision_id": revision["id"], "trim": True},
        )
    assert env.client.get(root + "/profile", headers=headers).json() == revision
    assert len(env.client.get(root + "/revisions", headers=headers).json()) == 1
    assert env.client.get(f"/workspaces/{wid}/usage", headers=headers).json() == before


@pytest.mark.parametrize("sample_id", ["finance-v1", "sales-v1", "inventory-v1"])
def test_sample_import_has_version_private_original_and_profile(integration, sample_id):
    env = integration
    headers, _ = identity(env, "sample@example.test")
    wid = workspace(env, headers)
    catalog = env.client.get("/samples", headers=headers)
    assert catalog.status_code == 200 and len(catalog.json()) == 3
    sample = env.client.post(f"/workspaces/{wid}/samples/{sample_id}", headers=headers)
    assert sample.status_code == 201, sample.text
    assert sample.json()["sample_id"] == sample_id and "storage_key" not in sample.json()
    root = f"/workspaces/{wid}/datasets/{sample.json()['dataset_id']}/uploads/{sample.json()['id']}"
    profile = env.client.get(root + "/profile", headers=headers)
    assert profile.status_code == 200 and profile.json()["profile"]["row_count"] >= 3
    assert env.client.get(root + "/content", headers=headers).status_code == 200
    assert env.client.get("/samples").status_code == 401


def test_sample_storage_failure_is_atomic(integration, monkeypatch):
    env = integration
    headers, _ = identity(env, "sample@example.test")
    wid = workspace(env, headers)
    put = env.runtime.service.storage.put

    def fail_after_write(*args):
        put(*args)
        raise RuntimeError("storage interrupted")

    monkeypatch.setattr(env.runtime.service.storage, "put", fail_after_write)
    with pytest.raises(RuntimeError, match="storage interrupted"):
        env.client.post(f"/workspaces/{wid}/samples/sales-v1", headers=headers)
    assert env.client.get(f"/workspaces/{wid}/datasets", headers=headers).json() == []
    assert env.runtime.service.storage.client.list_objects_v2(Bucket=env.bucket)["KeyCount"] == 0
    assert env.client.get(f"/workspaces/{wid}/usage", headers=headers).json()["uploads"] == 0


def test_existing_upload_survives_migration_and_gets_lazy_profile_once(integration):
    env = integration
    headers, _, _, root, original = setup(env)
    content = env.client.get(root + "/content", headers=headers).content
    with env.engine.begin() as connection:
        env.config.attributes["connection"] = connection
        command.downgrade(env.config, "0001")
    with env.engine.begin() as connection:
        env.config.attributes["connection"] = connection
        command.upgrade(env.config, "head")
    profile = env.client.get(root + "/profile", headers=headers)
    assert profile.status_code == 200 and profile.json()["profile"] == original["profile"]
    assert env.client.get(root + "/content", headers=headers).content == content
    assert env.client.get(root + "/profile", headers=headers).json() == profile.json()
    assert len(env.client.get(root + "/revisions", headers=headers).json()) == 1


def test_tampered_object_cannot_produce_a_cleaned_revision(integration):
    env = integration
    headers, wid, did, root, revision = setup(env)
    with env.engine.begin() as connection:
        stored = SQLWorkspaceRepository(connection).upload(
            UUID(wid), UUID(did), UUID(root.rsplit("/", 1)[1])
        )
    env.runtime.service.storage.client.put_object(
        Bucket=env.bucket, Key=stored.storage_key, Body=b"tampered"
    )
    response = env.client.post(
        root + "/cleaning/apply",
        headers=headers,
        json={"expected_revision_id": revision["id"], "trim": True},
    )
    assert response.status_code == 503
    assert len(env.client.get(root + "/revisions", headers=headers).json()) == 1


def test_database_rejects_cross_tenant_revision_reference(integration):
    from sqlalchemy.exc import IntegrityError

    env = integration
    _, wid, did, root, _ = setup(env)
    _, foreign_wid, _, _, _ = setup(env, "other@example.test")
    with env.engine.begin() as connection:
        revision = SQLWorkspaceRepository(connection).active_revision(
            UUID(wid), UUID(did), UUID(root.rsplit("/", 1)[1])
        )
    values = {**asdict(revision), "id": uuid4(), "workspace_id": UUID(foreign_wid)}
    with pytest.raises(IntegrityError), env.engine.begin() as connection:
        connection.execute(s.revisions.insert().values(**values))
    with env.engine.connect() as connection:
        assert len(connection.execute(select(s.revisions)).all()) == 2


def test_members_can_prepare_data_but_usage_is_manager_only(integration):
    from test_workspace_integration import accept, invite

    env = integration
    owner, wid, _, root, revision = setup(env)
    member, _ = identity(env, "member@example.test")
    invitation = invite(env, owner, wid, "member@example.test").json()
    reserved = env.client.get(f"/workspaces/{wid}/usage", headers=owner).json()
    assert reserved["reserved_seats"] == 1 and reserved["active_seats"] == 1
    assert accept(env, member, wid, invitation["id"]).status_code == 200
    assert env.client.get(f"/workspaces/{wid}/usage", headers=member).status_code == 403
    assert env.client.get(root + "/profile", headers=member).status_code == 200
    assert (
        env.client.post(
            root + "/cleaning/apply",
            headers=member,
            json={"expected_revision_id": revision["id"], "trim": True},
        ).status_code
        == 201
    )
    current = env.client.get(f"/workspaces/{wid}/usage", headers=owner).json()
    assert current["reserved_seats"] == 0 and current["active_seats"] == 2


def test_recipe_depth_bound_preview_limit_and_invalid_inputs(integration):
    content = b"item,amount\n" + b"A,1\n" * 15
    headers, _, _, root, revision = setup(integration, content=content)
    client = integration.client
    preview = client.post(
        root + "/cleaning/preview", headers=headers, json={"expected_revision_id": revision["id"]}
    )
    assert len(preview.json()["rows"]) == 10
    assert preview.json()["revision"]["profile"]["row_count"] == 15
    for invalid in ({"trim": "true"}, {"unexpected": True}, {"mapping": {"amount": "item"}}):
        assert (
            client.post(
                root + "/cleaning/apply",
                headers=headers,
                json={"expected_revision_id": revision["id"], **invalid},
            ).status_code
            == 422
        )
    assert len(client.get(root + "/revisions", headers=headers).json()) == 1
    original = revision
    for _ in range(20):
        response = client.post(
            root + "/cleaning/apply",
            headers=headers,
            json={"expected_revision_id": revision["id"], "trim": True},
        )
        assert response.status_code == 201, response.text
        revision = response.json()["revision"]
    assert (
        client.post(
            root + "/cleaning/apply",
            headers=headers,
            json={"expected_revision_id": revision["id"], "trim": True},
        ).status_code
        == 422
    )
    assert len(client.get(root + "/revisions", headers=headers).json()) == 21
    assert (
        client.post(
            root + "/restore",
            headers=headers,
            json={"expected_revision_id": revision["id"], "revision_id": original["id"]},
        ).status_code
        == 200
    )
