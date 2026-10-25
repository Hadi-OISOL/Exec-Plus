"""Use case: Proves resumable chunked uploads and per-user quotas on real PostgreSQL and MinIO.

What it does: Covers ordering, idempotency, hashes, resume, expiry, cancel, quotas and parity
with single-request ingestion for a multi-chunk file.
"""

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import update

from execplus.domain.google_oauth import import_filename
from execplus.domain.upload_sessions import safe_label
from execplus.infrastructure.persistence import schema as s
from test_workspace_integration import dataset, identity, upload, workspace

MIB = 1024 * 1024


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def start(env, headers, wid, content, name="sales.csv", **extra):
    return env.client.post(
        f"/workspaces/{wid}/upload-sessions",
        headers=headers,
        json={
            "filename": name,
            "size_bytes": len(content),
            "content_type": "text/csv",
            "sha256": sha(content),
            "purpose": "upload",
            **extra,
        },
    )


def put(env, headers, wid, sid, index, chunk, digest=None):
    return env.client.put(
        f"/workspaces/{wid}/upload-sessions/{sid}/chunks/{index}",
        headers={**headers, "X-Chunk-SHA256": digest or sha(chunk)},
        content=chunk,
    )


def chunks(content, size):
    return [content[offset : offset + size] for offset in range(0, len(content), size)]


def small_chunks(env, size=64 * 1024):
    env.runtime.upload_chunk_bytes = size
    env.runtime.__dict__.pop("upload_sessions", None)


def csv_bytes(rows, width=1):
    lines = ["item,amount,note"]
    lines += [f"item-{index},{index}.25,{'n' * width}" for index in range(rows)]
    return ("\n".join(lines) + "\n").encode()


def test_ordering_idempotency_hash_resume_and_completion(integration):
    env = integration
    small_chunks(env)
    owner, _ = identity(env, "chunk-owner@example.test")
    other, _ = identity(env, "chunk-other@example.test")
    wid = workspace(env, owner)
    did = dataset(env, owner, wid)
    content = csv_bytes(4000, 40)
    parts = chunks(content, 64 * 1024)
    assert len(parts) >= 3
    created = start(env, owner, wid, content, dataset_id=did)
    assert created.status_code == 201, created.text
    body = created.json()
    sid = body["id"]
    assert body["status"] == "open" and body["next_chunk"] == 0 and body["received_bytes"] == 0
    assert body["chunk_size"] == 64 * 1024 and body["total_chunks"] == len(parts)
    assert put(env, owner, wid, sid, 1, parts[1]).json()["error"]["code"] == "chunk_out_of_order"
    bad = put(env, owner, wid, sid, 0, parts[0], digest="0" * 64)
    assert bad.status_code == 409 and bad.json()["error"]["code"] == "hash_mismatch"
    first = put(env, owner, wid, sid, 0, parts[0])
    assert first.status_code == 200 and first.json()["next_chunk"] == 1
    assert put(env, owner, wid, sid, 0, parts[0]).status_code == 200
    replaced = put(env, owner, wid, sid, 0, parts[1][: len(parts[0])])
    assert replaced.status_code == 409 and replaced.json()["error"]["code"] == "hash_mismatch"
    foreign = put(env, other, wid, sid, 1, parts[1])
    assert foreign.status_code == 404 and foreign.json()["error"]["code"]
    missing = env.client.get(f"/workspaces/{wid}/upload-sessions/{uuid4()}", headers=owner)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "upload_session_not_found"
    preflight = env.client.options(
        f"/workspaces/{wid}/upload-sessions/{sid}/chunks/1",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "x-chunk-sha256",
        },
    )
    assert preflight.status_code == 200
    early = env.client.post(f"/workspaces/{wid}/upload-sessions/{sid}/complete", headers=owner)
    assert early.json()["error"]["code"] == "upload_incomplete"
    resumed = env.client.get(
        f"/workspaces/{wid}/upload-sessions", params={"status": "open"}, headers=owner
    ).json()
    assert [item["id"] for item in resumed] == [sid] and resumed[0]["next_chunk"] == 1
    for index in range(1, len(parts)):
        assert put(env, owner, wid, sid, index, parts[index]).status_code == 200
    state = env.client.get(f"/workspaces/{wid}/upload-sessions/{sid}", headers=owner).json()
    assert state["received_bytes"] == len(content) and state["next_chunk"] == len(parts)
    done = env.client.post(f"/workspaces/{wid}/upload-sessions/{sid}/complete", headers=owner)
    assert done.status_code == 201, done.text
    result = done.json()
    assert result["status"] == "completed" and result["upload"]["checksum"] == sha(content)
    assert result["upload"]["row_count"] == 4000 and "storage_key" not in result["upload"]
    assert put(env, owner, wid, sid, 0, parts[0]).json()["error"]["code"] == "session_closed"
    leftover = env.runtime.service.storage.client.list_objects_v2(
        Bucket=env.bucket, Prefix=f"workspaces/{wid}/upload-sessions/"
    )
    assert leftover.get("KeyCount", 0) == 0
    audit = [
        e["action"] for e in env.client.get(f"/workspaces/{wid}/audit-events", headers=owner).json()
    ]
    assert "upload_session.completed" in audit


def test_whole_file_checksum_mismatch_fails_without_upload(integration):
    env = integration
    small_chunks(env)
    owner, _ = identity(env, "checksum@example.test")
    wid = workspace(env, owner)
    did = dataset(env, owner, wid)
    content = csv_bytes(10)
    sid = start(env, owner, wid, content, dataset_id=did, sha256="a" * 64).json()["id"]
    assert put(env, owner, wid, sid, 0, content).status_code == 200
    done = env.client.post(f"/workspaces/{wid}/upload-sessions/{sid}/complete", headers=owner)
    assert done.status_code == 409 and done.json()["error"]["code"] == "checksum_mismatch"
    state = env.client.get(f"/workspaces/{wid}/upload-sessions/{sid}", headers=owner).json()
    assert state["status"] == "failed" and state["error"]["code"] == "checksum_mismatch"
    assert env.client.get(f"/workspaces/{wid}/datasets/{did}/uploads", headers=owner).json() == []


def test_cancel_and_expiry_remove_parts(integration):
    env = integration
    small_chunks(env)
    owner, _ = identity(env, "cancel@example.test")
    wid = workspace(env, owner)
    content = csv_bytes(4000, 40)
    parts = chunks(content, 64 * 1024)
    storage = env.runtime.service.storage.client
    prefix = f"workspaces/{wid}/upload-sessions/"
    cancelled = start(env, owner, wid, content).json()["id"]
    put(env, owner, wid, cancelled, 0, parts[0])
    assert storage.list_objects_v2(Bucket=env.bucket, Prefix=prefix)["KeyCount"] == 1
    gone = env.client.delete(f"/workspaces/{wid}/upload-sessions/{cancelled}", headers=owner)
    assert gone.status_code == 204
    assert storage.list_objects_v2(Bucket=env.bucket, Prefix=prefix)["KeyCount"] == 0
    assert put(env, owner, wid, cancelled, 1, parts[1]).json()["error"]["code"] == "session_closed"
    stale = start(env, owner, wid, content).json()["id"]
    put(env, owner, wid, stale, 0, parts[0])
    with env.engine.begin() as connection:
        connection.execute(
            update(s.upload_sessions)
            .where(s.upload_sessions.c.id == UUID(stale))
            .values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
        )
    view = env.client.get(f"/workspaces/{wid}/upload-sessions/{stale}", headers=owner).json()
    assert view["status"] == "expired"
    assert put(env, owner, wid, stale, 1, parts[1]).json()["error"]["code"] == "session_closed"
    assert env.runtime.upload_sessions.sweep() == {"expired": 1, "recovered": 0}
    assert storage.list_objects_v2(Bucket=env.bucket, Prefix=prefix)["KeyCount"] == 0
    storage_view = env.client.get("/me/storage", headers=owner).json()
    assert storage_view["open_upload_bytes"] == 0
    actions = [
        e["action"] for e in env.client.get(f"/workspaces/{wid}/audit-events", headers=owner).json()
    ]
    assert "upload_session.cancelled" in actions


def test_quota_at_start_mid_upload_and_staff_override(integration):
    env = integration
    small_chunks(env)
    owner, user = identity(env, "quota@example.test")
    staff, staff_user = identity(env, "quota-staff@example.test")
    wid = workspace(env, owner)
    did = dataset(env, owner, wid)
    content = csv_bytes(4000, 40)
    parts = chunks(content, 64 * 1024)
    assert upload(env, owner, wid, did).status_code == 201
    stored = env.client.get("/me/storage", headers=owner).json()
    assert stored["quota_bytes"] == 5 * 1024**3 and stored["used_bytes"] > 0
    denied = env.client.put(
        f"/admin/users/{user.id}/storage-quota", headers=owner, json={"quota_bytes": 10}
    )
    assert denied.status_code == 403
    env.runtime.operations.change_staff("quota-staff@example.test", "admin")
    tight = env.client.put(
        f"/admin/users/{user.id}/storage-quota",
        headers=staff,
        json={"quota_bytes": stored["used_bytes"] + 100},
    )
    assert tight.status_code == 200, tight.text
    refused = start(env, owner, wid, content, dataset_id=did)
    assert refused.status_code == 409
    error = refused.json()["error"]
    assert error["code"] == "quota_exceeded"
    assert error["used_bytes"] == stored["used_bytes"]
    assert error["quota_bytes"] == stored["used_bytes"] + 100
    assert error["requested_bytes"] == len(content)
    single = upload(env, owner, wid, did, content=content)
    assert single.status_code == 409 and single.json()["error"]["code"] == "quota_exceeded"
    env.runtime.operations.set_storage_quota(None, user.id, None)
    sid = start(env, owner, wid, content, dataset_id=did).json()["id"]
    assert env.client.get("/me/storage", headers=owner).json()["open_upload_bytes"] == len(content)
    assert put(env, owner, wid, sid, 0, parts[0]).status_code == 200
    env.runtime.operations.set_storage_quota(None, user.id, stored["used_bytes"] + 100)
    mid = put(env, owner, wid, sid, 1, parts[1])
    assert mid.status_code == 409 and mid.json()["error"]["code"] == "quota_exceeded"
    assert staff_user.id != user.id


def test_rejects_oversize_unsupported_and_unsafe_names(integration):
    env = integration
    owner, _ = identity(env, "limits@example.test")
    wid = workspace(env, owner)

    def begin(**body):
        payload = {"filename": "a.csv", "size_bytes": 10, "content_type": "text/csv", **body}
        return env.client.post(f"/workspaces/{wid}/upload-sessions", headers=owner, json=payload)

    too_big = begin(size_bytes=600 * MIB)
    assert too_big.status_code == 413 and too_big.json()["error"]["code"] == "file_too_large"
    assert begin(filename="a.pdf", content_type="application/pdf").status_code == 415
    assert begin(filename="../a.csv").json()["error"]["code"] == "unsafe_filename"
    assert begin(filename="a.csv").status_code == 201


def test_sixty_mib_multi_chunk_upload_matches_single_request(integration):
    env = integration
    env.runtime.service.max_upload_bytes = 500 * MIB
    env.runtime.service.parser.max_bytes = 500 * MIB
    owner, _ = identity(env, "large@example.test")
    wid = workspace(env, owner)
    content = csv_bytes(60_000, 1000)
    assert 55 * MIB < len(content) < 65 * MIB
    created = start(env, owner, wid, content, name="large sales.csv").json()
    sid = created["id"]
    assert created["chunk_size"] == 8 * MIB and created["total_chunks"] == 8
    for index, chunk in enumerate(chunks(content, 8 * MIB)):
        assert put(env, owner, wid, sid, index, chunk).status_code == 200
    done = env.client.post(f"/workspaces/{wid}/upload-sessions/{sid}/complete", headers=owner)
    assert done.status_code == 201, done.text
    assert done.json()["status"] == "processing" and done.json()["upload"] is None
    state = env.client.get(f"/workspaces/{wid}/upload-sessions/{sid}", headers=owner).json()
    assert state["status"] == "completed", state
    chunked = state["upload"]
    did = state["dataset_id"]
    names = [d["name"] for d in env.client.get(f"/workspaces/{wid}/datasets", headers=owner).json()]
    assert "large sales" in names
    other = dataset(env, owner, wid)
    direct = upload(env, owner, wid, other, content=content, name="large sales.csv")
    assert direct.status_code == 201, direct.text
    single = direct.json()
    fields = (
        "filename",
        "content_type",
        "size",
        "checksum",
        "status",
        "format",
        "row_count",
        "column_count",
    )
    assert {k: chunked[k] for k in fields} == {k: single[k] for k in fields}

    def profile(dataset_id, upload_id):
        value = env.client.get(
            f"/workspaces/{wid}/datasets/{dataset_id}/uploads/{upload_id}/profile", headers=owner
        ).json()
        return {
            k: v
            for k, v in value.items()
            if k not in {"id", "upload_id", "dataset_id", "created_at"}
        }

    assert profile(did, chunked["id"]) == profile(other, single["id"])


def test_generated_import_names_are_sanitized():
    name = import_filename("Sales / 2024: Q1 %", "")
    assert name == "Sales 2024 Q1.csv"
    assert import_filename("Report", "Tab: A/B") == "Report - Tab A B.csv"
    assert safe_label("..\x00hidden", 20, "x") == "hidden"
    assert safe_label("///", 20, "fallback") == "fallback"


def test_sweep_recovers_processing_session_after_lost_worker(integration):
    env = integration
    small_chunks(env)
    owner, _ = identity(env, "recover@example.test")
    wid = workspace(env, owner)
    content = csv_bytes(10)
    sid = start(env, owner, wid, content, name="recovered.csv").json()["id"]
    assert put(env, owner, wid, sid, 0, content).status_code == 200
    with env.engine.begin() as connection:
        connection.execute(
            update(s.upload_sessions)
            .where(s.upload_sessions.c.id == UUID(sid))
            .values(status="processing", lease_until=datetime.now(timezone.utc))
        )
    assert env.runtime.upload_sessions.sweep() == {"expired": 0, "recovered": 1}
    state = env.client.get(f"/workspaces/{wid}/upload-sessions/{sid}", headers=owner).json()
    assert state["status"] == "completed" and state["upload"]["checksum"] == sha(content)
    assert env.runtime.upload_sessions.sweep() == {"expired": 0, "recovered": 0}
