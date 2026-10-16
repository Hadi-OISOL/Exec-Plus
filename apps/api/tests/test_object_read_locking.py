"""Use case: Keeps source reads responsive while permission changes remain atomic.

What it does: Exercises concurrent workspace-lock acquisition during real object reads
and rejects publication when permissions or source metadata changed during that I/O.
"""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select, text, update

from execplus.infrastructure.persistence import schema as s
from test_dataset_access import fixture
from test_understanding import context

READS = ("metadata", "list", "profile", "revisions", "understanding")
WRITES = ("download", "preview", "apply", "restore", "save_meaning")


def request(env, headers, root, route, profile, meaning):
    if route == "list":
        return env.client.get(root.rsplit("/", 1)[0], headers=headers)
    if route in READS:
        return env.client.get(root + ("" if route == "metadata" else "/" + route), headers=headers)
    if route == "download":
        return env.client.get(root + "/content", headers=headers)
    if route == "save_meaning":
        return env.client.post(
            root + "/understanding",
            headers=headers,
            json={
                "revision_id": meaning["revision_id"],
                "expected_version": meaning["version"],
                "state": "confirmed",
                "definition": meaning["definition"],
            },
        )
    body = {"expected_revision_id": profile["id"]}
    suffix = "/cleaning/" + route
    if route == "restore":
        suffix = "/restore"
        body["revision_id"] = profile["id"]
    else:
        body["trim"] = True
    return env.client.post(root + suffix, headers=headers, json=body)


def counts(env):
    with env.engine.connect() as connection:
        return tuple(
            connection.execute(select(func.count()).select_from(table)).scalar_one()
            for table in (s.revisions, s.understandings, s.audit_events)
        )


@pytest.mark.parametrize("route", READS + WRITES)
@pytest.mark.parametrize("mutation", ["policy_epoch", "membership"])
def test_object_read_releases_workspace_lock_and_rechecks_before_returning(
    integration, monkeypatch, route, mutation
):
    env = integration
    owner, actor, member, user, wid, did, _, root, _, _ = fixture(env)
    headers, target = (member, user) if route in READS else (owner, actor)
    profile = env.client.get(root + "/profile", headers=owner).json()
    meaning = context(env, owner, root)
    before = counts(env)
    original = env.runtime.service.storage.read
    calls = 0

    def changing_read(*args, **kwargs):
        nonlocal calls
        content = original(*args, **kwargs)
        calls += 1
        with env.engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout = '750ms'"))
            connection.execute(
                select(s.workspaces).where(s.workspaces.c.id == UUID(wid)).with_for_update()
            )
            if mutation == "membership":
                connection.execute(
                    delete(s.memberships).where(
                        s.memberships.c.workspace_id == UUID(wid),
                        s.memberships.c.user_id == target.id,
                    )
                )
            else:
                policy = dict(
                    connection.execute(
                        select(s.dataset_access_policies)
                        .where(s.dataset_access_policies.c.dataset_id == UUID(did))
                        .order_by(s.dataset_access_policies.c.version.desc())
                    )
                    .mappings()
                    .first()
                )
                policy.update(id=uuid4(), version=policy["version"] + 1)
                connection.execute(s.dataset_access_policies.insert().values(**policy))
        return content

    monkeypatch.setattr(env.runtime.service.storage, "read", changing_read)
    response = request(env, headers, root, route, profile, meaning)
    assert calls == 1
    assert response.status_code == 404, response.text
    assert "Lahore" not in response.text and "9999" not in response.text
    assert counts(env) == before


@pytest.mark.parametrize("route", ["profile", "understanding", "apply", "save_meaning"])
def test_source_metadata_change_during_parse_never_publishes_old_snapshot(
    integration, monkeypatch, route
):
    env = integration
    owner, _, member, _, wid, _, uid, root, _, _ = fixture(env)
    headers = member if route in READS else owner
    profile = env.client.get(root + "/profile", headers=owner).json()
    meaning = context(env, owner, root)
    before = counts(env)
    original = env.runtime.service.parser.parse
    calls = 0

    def changing_parse(*args, **kwargs):
        nonlocal calls
        result = original(*args, **kwargs)
        calls += 1
        with env.engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout = '750ms'"))
            connection.execute(
                select(s.workspaces).where(s.workspaces.c.id == UUID(wid)).with_for_update()
            )
            connection.execute(
                update(s.uploads).where(s.uploads.c.id == UUID(uid)).values(checksum="a" * 64)
            )
        return result

    monkeypatch.setattr(env.runtime.service.parser, "parse", changing_parse)
    response = request(env, headers, root, route, profile, meaning)
    assert calls == 1
    assert response.status_code == 409, response.text
    assert counts(env) == before


def test_non_editor_definition_save_is_denied_before_source_io(integration, monkeypatch):
    from test_studies import add_member, prepare

    env = integration
    owner, _, wid, _, _, root = prepare(env)
    member, _ = add_member(env, owner, wid, "member")
    meaning = context(env, owner, root)

    def forbidden_read(*args, **kwargs):
        pytest.fail("A member without definition-edit permission reached storage")

    monkeypatch.setattr(env.runtime.service.storage, "read", forbidden_read)
    response = request(env, member, root, "save_meaning", {}, meaning)
    assert response.status_code == 403


@pytest.mark.parametrize("mutation", ["policy_epoch", "membership", "sample_membership"])
def test_upload_put_releases_workspace_lock_and_compensates_only_its_new_object(
    integration, monkeypatch, mutation
):
    from test_workspace_integration import upload

    env = integration
    owner, actor, _, _, wid, did, _, _, _, _ = fixture(env)
    before = counts(env)
    with env.engine.connect() as connection:
        dataset_count = connection.execute(
            select(func.count()).select_from(s.datasets)
        ).scalar_one()
        upload_count = connection.execute(select(func.count()).select_from(s.uploads)).scalar_one()
    storage = env.runtime.service.storage
    original = storage.put
    original_keys = {
        item["Key"]
        for item in storage.client.list_objects_v2(Bucket=env.bucket).get("Contents", [])
    }
    calls = 0

    def changing_put(*args, **kwargs):
        nonlocal calls
        original(*args, **kwargs)
        calls += 1
        with env.engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout = '750ms'"))
            connection.execute(
                select(s.workspaces).where(s.workspaces.c.id == UUID(wid)).with_for_update()
            )
            if mutation == "policy_epoch":
                policy = dict(
                    connection.execute(
                        select(s.dataset_access_policies)
                        .where(s.dataset_access_policies.c.dataset_id == UUID(did))
                        .order_by(s.dataset_access_policies.c.version.desc())
                    )
                    .mappings()
                    .first()
                )
                policy.update(id=uuid4(), version=policy["version"] + 1)
                connection.execute(s.dataset_access_policies.insert().values(**policy))
            else:
                connection.execute(
                    delete(s.memberships).where(
                        s.memberships.c.workspace_id == UUID(wid),
                        s.memberships.c.user_id == actor.id,
                    )
                )

    monkeypatch.setattr(storage, "put", changing_put)
    response = (
        env.client.post(f"/workspaces/{wid}/samples/finance-v1", headers=owner)
        if mutation == "sample_membership"
        else upload(env, owner, wid, did)
    )
    assert calls == 1
    assert response.status_code == 404, response.text
    assert counts(env) == before
    retained_keys = {
        item["Key"]
        for item in storage.client.list_objects_v2(Bucket=env.bucket).get("Contents", [])
    }
    assert retained_keys == original_keys
    with env.engine.connect() as connection:
        assert (
            connection.execute(select(func.count()).select_from(s.datasets)).scalar_one()
            == dataset_count
        )
        assert (
            connection.execute(select(func.count()).select_from(s.uploads)).scalar_one()
            == upload_count
        )
