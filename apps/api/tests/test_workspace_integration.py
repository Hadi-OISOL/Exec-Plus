"""Use case: Proves Week 1 against real PostgreSQL and S3-compatible storage.

What it does: Exercises API journeys, IDOR attacks, seat races, migrations, and rollback.
"""

import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from alembic import command
from sqlalchemy import inspect, select, text, update

from execplus.application.services.health import HealthService
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.identity import LocalSessionIdentity
from execplus.infrastructure.object_storage import storage_key
from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.readiness import DatabaseProbe, StorageProbe
from test_file_parser import XLSX, workbook_bytes


def identity(env, email):
    token = env.runtime.identity.provision(email)
    return {"Authorization": f"Bearer {token}"}, env.runtime.identity.authenticate(token)


def workspace(env, headers, name="Workspace", seats=3):
    response = env.client.post(
        "/workspaces", headers=headers, json={"name": name, "seat_limit": seats}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def dataset(env, headers, wid):
    response = env.client.post(
        f"/workspaces/{wid}/datasets", headers=headers, json={"name": "Sales"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def upload(
    env,
    headers,
    wid,
    did,
    content=b"item,amount\nprivate-row,12\n",
    name="sales.csv",
    mime="text/csv",
):
    return env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads",
        params={"filename": name},
        headers={**headers, "Content-Type": mime},
        content=content,
    )


def invite(env, headers, wid, email, role="member"):
    return env.client.post(
        f"/workspaces/{wid}/invitations", headers=headers, json={"email": email, "role": role}
    )


def accept(env, headers, wid, iid):
    return env.client.post(f"/workspaces/{wid}/invitations/{iid}/accept", headers=headers)


def test_complete_journey_persists_originals_and_safe_audit(integration):
    env = integration
    owner, user = identity(env, "owner@example.test")
    teammate, _ = identity(env, "member@example.test")
    assert env.client.get("/auth/me", headers=owner).json()["email"] == user.email
    wid = workspace(env, owner)
    invitation = invite(env, owner, wid, " MEMBER@example.test ").json()
    assert accept(env, teammate, wid, invitation["id"]).status_code == 200
    assert len(env.client.get(f"/workspaces/{wid}/members", headers=owner).json()) == 2
    did = dataset(env, teammate, wid)
    response = upload(env, teammate, wid, did)
    assert response.status_code == 201, response.text
    result = response.json()
    assert "storage_key" not in result
    assert (result["row_count"], result["column_count"], result["status"]) == (1, 2, "stored")
    assert result["checksum"] == hashlib.sha256(b"item,amount\nprivate-row,12\n").hexdigest()
    excel = upload(env, teammate, wid, did, workbook_bytes(), "sales.xlsx", XLSX)
    assert excel.status_code == 201, excel.text
    records = env.client.get(f"/workspaces/{wid}/datasets/{did}/uploads", headers=owner).json()
    assert len(records) == 2
    assert (
        env.client.get(
            f"/workspaces/{wid}/datasets/{did}/uploads/{result['id']}/content", headers=owner
        ).content
        == b"item,amount\nprivate-row,12\n"
    )
    stored = env.runtime.service.get_upload(user, UUID(wid), UUID(did), UUID(result["id"]))
    assert env.runtime.service.storage.metadata(stored).size == result["size"]
    assert env.runtime.service.storage.read(stored) == b"item,amount\nprivate-row,12\n"
    assert storage_key(stored).startswith(f"workspaces/{wid}/datasets/{did}/uploads/")
    audit = env.client.get(f"/workspaces/{wid}/audit-events", headers=owner)
    assert "private-row" not in audit.text
    assert "Bearer" not in audit.text and "sales.csv" not in audit.text
    assert {item["action"] for item in audit.json()} >= {
        "workspace.created",
        "membership.created",
        "invitation.created",
        "invitation.accepted",
        "dataset.created",
        "upload.stored",
        "upload.downloaded",
    }
    with env.engine.connect() as connection:
        assert connection.execute(select(s.uploads.c.id)).rowcount == 2
        assert connection.execute(select(s.audit_events.c.workspace_id)).first()[0] == UUID(wid)


def test_bidirectional_tenant_and_idor_isolation(integration):
    env = integration
    tenants = []
    for email in ["a@example.test", "b@example.test"]:
        headers, user = identity(env, email)
        wid = workspace(env, headers)
        did = dataset(env, headers, wid)
        uid = upload(env, headers, wid, did).json()["id"]
        tenants.append((headers, user, wid, did, uid))
    for current, other in [(tenants[0], tenants[1]), (tenants[1], tenants[0])]:
        headers, actor, own_wid, own_did, _ = current
        _, _, wid, did, uid = other
        base = f"/workspaces/{wid}"
        for path in [
            f"{base}/members",
            f"{base}/invitations",
            f"{base}/audit-events",
            f"{base}/datasets",
            f"{base}/datasets/{did}",
            f"{base}/datasets/{did}/uploads",
            f"{base}/datasets/{did}/uploads/{uid}",
            f"{base}/datasets/{did}/uploads/{uid}/content",
            f"/workspaces/{own_wid}/datasets/{did}",
            f"/workspaces/{own_wid}/datasets/{own_did}/uploads/{uid}/content",
        ]:
            assert env.client.get(path, headers=headers).status_code == 404, path
        assert (
            env.client.patch(
                f"{base}/datasets/{did}", headers=headers, json={"name": "attack"}
            ).status_code
            == 404
        )
        assert (
            env.client.patch(
                f"/workspaces/{own_wid}/datasets/{did}", headers=headers, json={"name": "attack"}
            ).status_code
            == 404
        )
        assert upload(env, headers, wid, did).status_code == 404
        assert upload(env, headers, own_wid, did).status_code == 404
        assert invite(env, headers, wid, "attack@example.test").status_code == 404
        assert env.client.delete(f"{base}/members/{actor.id}", headers=headers).status_code == 404
        with pytest.raises(IngestionError):
            env.runtime.service.download(actor, UUID(own_wid), UUID(did), UUID(uid))
        stored = env.runtime.service.get_upload(other[1], UUID(wid), UUID(did), UUID(uid))
        with pytest.raises(IngestionError, match="scope"):
            env.runtime.service.storage.read(replace(stored, workspace_id=UUID(own_wid)))
        assert [row["id"] for row in env.client.get("/workspaces", headers=headers).json()] == [
            own_wid
        ]


@pytest.mark.parametrize("seats,status", [(3, 201), (50, 201), (2, 422), (51, 422)])
def test_seat_limit_bounds(integration, seats, status):
    headers, _ = identity(integration, "owner@example.test")
    assert (
        integration.client.post(
            "/workspaces", headers=headers, json={"name": "Team", "seat_limit": seats}
        ).status_code
        == status
    )


def test_seat_reservations_expiry_removal_and_role_policy(integration):
    env = integration
    owner, owner_user = identity(env, "owner@example.test")
    member, member_user = identity(env, "member@example.test")
    stranger, _ = identity(env, "stranger@example.test")
    wid = workspace(env, owner)
    first = invite(env, owner, wid, "member@example.test").json()
    assert (
        invite(env, owner, wid, "member@example.test").json()["error"]["code"] == "already_invited"
    )
    second = invite(env, owner, wid, "pending@example.test").json()
    assert invite(env, owner, wid, "full@example.test").status_code == 409
    assert accept(env, stranger, wid, first["id"]).status_code == 404
    assert accept(env, member, wid, first["id"]).status_code == 200
    assert accept(env, member, wid, first["id"]).status_code == 409
    assert invite(env, member, wid, "x@example.test").status_code == 403
    assert env.client.get(f"/workspaces/{wid}/audit-events", headers=member).status_code == 403
    assert (
        env.client.patch(
            f"/workspaces/{wid}/seats", headers=member, json={"seat_limit": 50}
        ).status_code
        == 403
    )
    assert (
        env.client.delete(f"/workspaces/{wid}/members/{owner_user.id}", headers=owner).status_code
        == 403
    )
    assert (
        env.client.delete(f"/workspaces/{wid}/members/{member_user.id}", headers=owner).status_code
        == 204
    )
    assert env.client.get(f"/workspaces/{wid}/members", headers=member).status_code == 404
    third = invite(env, owner, wid, "replacement@example.test")
    assert third.status_code == 201
    assert (
        env.client.delete(
            f"/workspaces/{wid}/invitations/{second['id']}", headers=owner
        ).status_code
        == 204
    )
    expiring = invite(env, owner, wid, "stranger@example.test").json()
    with env.engine.begin() as connection:
        connection.execute(
            update(s.invitations)
            .where(s.invitations.c.id == UUID(expiring["id"]))
            .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )
    assert accept(env, stranger, wid, expiring["id"]).status_code == 409
    assert invite(env, owner, wid, "now-free@example.test").status_code == 201


def test_concurrent_invitations_cannot_exceed_seats(integration):
    env = integration
    headers, actor = identity(env, "owner@example.test")
    wid = workspace(env, headers)

    def invite_one(number):
        try:
            return env.runtime.service.invite(
                actor, UUID(wid), f"user{number}@example.test", "member"
            ).status
        except IngestionError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(invite_one, range(8)))
    assert outcomes.count("pending") == 2
    assert outcomes.count("seat_limit_reached") == 6
    assert len(env.runtime.service.list_invitations(actor, UUID(wid))) == 2


def test_unauthenticated_and_invalid_ids_do_not_leak(integration):
    env = integration
    assert env.client.get("/workspaces").status_code == 401
    assert (
        env.client.get("/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401
    )
    headers, _ = identity(env, "owner@example.test")
    assert env.client.get("/workspaces/not-a-uuid/datasets", headers=headers).status_code == 422
    assert env.client.get(f"/workspaces/{uuid4()}/datasets", headers=headers).status_code == 404
    wid = workspace(env, headers)
    assert (
        env.client.get(f"/workspaces/{wid}/datasets/{uuid4()}", headers=headers).status_code == 404
    )
    with env.engine.begin() as connection:
        connection.execute(
            update(s.sessions).values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )
    assert env.client.get("/auth/me", headers=headers).status_code == 401
    with pytest.raises(ValueError, match="local/test"):
        LocalSessionIdentity(env.engine, "production")


def test_invalid_files_never_persist(integration):
    env = integration
    headers, _ = identity(env, "owner@example.test")
    wid = workspace(env, headers)
    did = dataset(env, headers, wid)
    for data, name, mime, code in [
        (b"a,b\n1,2,3", "a.csv", "text/csv", "malformed_csv"),
        (b"bad", "bad.xlsx", XLSX, "malformed_excel"),
        (workbook_bytes(multiple=True), "bad.xlsx", XLSX, "multiple_sheets"),
        (workbook_bytes(merged=True), "bad.xlsx", XLSX, "merged_cells"),
        (b"a,b\n1,2", "../bad.csv", "text/csv", "unsafe_filename"),
        (b"bad", "bad.exe", "application/octet-stream", "unsupported_format"),
    ]:
        response = upload(env, headers, wid, did, data, name, mime)
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == code
    env.runtime.service.max_upload_bytes = 10
    assert upload(env, headers, wid, did).status_code == 413
    with env.engine.connect() as connection:
        assert connection.execute(select(s.uploads)).all() == []
    assert (
        env.runtime.service.storage.client.list_objects_v2(Bucket=env.bucket).get("KeyCount") == 0
    )


def test_failed_database_write_compensates_object(integration, monkeypatch):
    env = integration
    headers, actor = identity(env, "owner@example.test")
    wid = UUID(workspace(env, headers))
    did = UUID(dataset(env, headers, str(wid)))

    def fail(*args):
        raise RuntimeError("simulated audit failure")

    monkeypatch.setattr(env.runtime.service, "_audit", fail)
    with pytest.raises(RuntimeError, match="audit failure"):
        env.runtime.service.upload(actor, wid, did, "a.csv", "text/csv", BytesIO(b"a,b\n1,2"))
    assert env.runtime.service.list_uploads(actor, wid, did) == ()
    assert (
        env.runtime.service.storage.client.list_objects_v2(Bucket=env.bucket).get("KeyCount") == 0
    )


@pytest.mark.asyncio
async def test_real_readiness_and_migration_roundtrip(integration):
    env = integration
    service = HealthService((DatabaseProbe(env.engine), StorageProbe(env.runtime.service.storage)))
    ready, components = await service.readiness()
    assert ready and len(components) == 2
    with env.engine.begin() as connection:
        env.config.attributes["connection"] = connection
        command.downgrade(env.config, "base")
    assert "workspaces" not in inspect(env.engine).get_table_names()
    assert not (await service.readiness())[0]
    with env.engine.begin() as connection:
        env.config.attributes["connection"] = connection
        command.upgrade(env.config, "head")
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0002"
        )
    assert (await service.readiness())[0]


def test_logout_revokes_session(integration):
    headers, _ = identity(integration, "logout@example.test")
    assert integration.client.post("/auth/logout", headers=headers).status_code == 204
    assert integration.client.get("/auth/me", headers=headers).status_code == 401


def test_chunked_upload_enforces_actual_bytes_and_invalid_uuid(integration):
    env = integration
    headers, _ = identity(env, "owner@example.test")
    wid = workspace(env, headers)
    did = dataset(env, headers, wid)
    env.runtime.service.max_upload_bytes = 8
    response = env.client.post(
        f"/workspaces/{wid}/datasets/{did}/uploads?filename=large.csv",
        headers={**headers, "Content-Type": "text/csv"},
        content=iter([b"a,b\n", b"1,2\n", b"3,4\n"]),
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"
    assert env.runtime.service.storage.client.list_objects_v2(Bucket=env.bucket)["KeyCount"] == 0
    assert (
        env.client.get(
            f"/workspaces/{wid}/datasets/{did}/uploads/not-a-uuid", headers=headers
        ).status_code
        == 422
    )


def test_admin_permissions_and_seat_reduction(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    admin, admin_user = identity(env, "admin@example.test")
    wid = workspace(env, owner, seats=4)
    iid = invite(env, owner, wid, "admin@example.test", "admin").json()["id"]
    assert accept(env, admin, wid, iid).status_code == 200
    assert invite(env, admin, wid, "another@example.test", "admin").status_code == 403
    assert invite(env, admin, wid, "member@example.test").status_code == 201
    assert invite(env, admin, wid, "member2@example.test").status_code == 201
    assert (
        env.client.patch(
            f"/workspaces/{wid}/seats", headers=owner, json={"seat_limit": 3}
        ).status_code
        == 409
    )
    assert env.client.get(f"/workspaces/{wid}/audit-events", headers=admin).status_code == 200
    assert (
        env.client.delete(f"/workspaces/{wid}/members/{admin_user.id}", headers=owner).status_code
        == 204
    )
    assert invite(env, admin, wid, "revoked@example.test").status_code == 404


def test_storage_failure_rolls_back_metadata(integration, monkeypatch):
    env = integration
    headers, actor = identity(env, "owner@example.test")
    wid = UUID(workspace(env, headers))
    did = UUID(dataset(env, headers, str(wid)))

    def fail(*args):
        raise IngestionError("storage_unavailable", "Storage unavailable.", 503)

    monkeypatch.setattr(env.runtime.service.storage, "put", fail)
    assert upload(env, headers, str(wid), str(did)).status_code == 503
    assert env.runtime.service.list_uploads(actor, wid, did) == ()


def test_composite_foreign_key_prevents_cross_tenant_upload(integration):
    from sqlalchemy.exc import IntegrityError

    env = integration
    headers, actor = identity(env, "owner@example.test")
    wid = workspace(env, headers)
    other = workspace(env, headers, "Other")
    did = dataset(env, headers, wid)
    uid = upload(env, headers, wid, did).json()["id"]
    with pytest.raises(IntegrityError), env.engine.begin() as connection:
        connection.execute(
            update(s.uploads).where(s.uploads.c.id == UUID(uid)).values(workspace_id=UUID(other))
        )
    stored = env.runtime.service.get_upload(actor, UUID(wid), UUID(did), UUID(uid))
    assert stored.workspace_id == UUID(wid)


def test_concurrent_acceptance_is_single_use(integration):
    env = integration
    owner, _ = identity(env, "owner@example.test")
    _, member = identity(env, "member@example.test")
    wid = UUID(workspace(env, owner))
    iid = UUID(invite(env, owner, str(wid), member.email).json()["id"])

    def accept_one(_):
        try:
            env.runtime.service.accept_invitation(member, wid, iid)
            return "accepted"
        except IngestionError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(accept_one, range(4)))
    assert outcomes.count("accepted") == 1
    assert outcomes.count("invitation_unavailable") == 3


def test_migration_matches_repository_schema(integration):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    with integration.engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), s.metadata) == []


def test_private_bucket_and_api_metadata_hide_storage_paths(integration):
    import httpx

    env = integration
    headers, actor = identity(env, "owner@example.test")
    wid = workspace(env, headers)
    did = dataset(env, headers, wid)
    uid = upload(env, headers, wid, did).json()["id"]
    response = env.client.get(f"/workspaces/{wid}/datasets/{did}/uploads/{uid}", headers=headers)
    assert response.status_code == 200 and "storage_key" not in response.json()
    stored = env.runtime.service.get_upload(actor, UUID(wid), UUID(did), UUID(uid))
    endpoint = env.runtime.service.storage.client.meta.endpoint_url
    direct = httpx.get(f"{endpoint}/{env.bucket}/{stored.storage_key}")
    assert direct.status_code == 403
    assert "private-row" not in direct.text
    assert env.client.get("/health/ready").status_code == 200


def test_membership_revocation_during_validation_prevents_storage(integration, monkeypatch):
    env = integration
    owner_headers, owner = identity(env, "owner@example.test")
    member_headers, member = identity(env, "member@example.test")
    wid = workspace(env, owner_headers)
    iid = invite(env, owner_headers, wid, member.email).json()["id"]
    assert accept(env, member_headers, wid, iid).status_code == 200
    did = dataset(env, owner_headers, wid)
    parse = env.runtime.service.parser.parse

    def revoke_then_parse(*args):
        structure = parse(*args)
        env.runtime.service.remove_member(owner, UUID(wid), member.id)
        return structure

    monkeypatch.setattr(env.runtime.service.parser, "parse", revoke_then_parse)
    assert upload(env, member_headers, wid, did).status_code == 404
    assert env.runtime.service.storage.client.list_objects_v2(Bucket=env.bucket)["KeyCount"] == 0
    assert env.runtime.service.list_uploads(owner, UUID(wid), UUID(did)) == ()
