"""Use case: Proves large staged-refresh files arrive through resumable chunked upload sessions.

What it does: Stages multi-chunk files into validated candidates, keeps failures from touching the
active source, enforces session ownership, dataset and completeness, quota reservations and
recovery of interrupted staging on real PostgreSQL and MinIO.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, update

from execplus.infrastructure.persistence import schema as s
from test_refresh import activate, setup
from test_upload_sessions import chunks, put, sha, small_chunks, start
from test_workspace_integration import identity


def rows(count, amount="0.30"):
    lines = ["city,amount"] + [f"City {index},{amount}" for index in range(count)]
    return ("\n".join(lines) + "\n").encode()


def options(env, headers, path):
    feed = env.client.get(path + "/refresh", headers=headers).json()["feed"]
    return dict(
        request_id=str(uuid4()),
        expected_version=feed["version"],
        mode="replace",
        keys=[],
        duplicates="keep_all",
        as_of=datetime.now(timezone.utc).isoformat(),
    )


def upload(env, headers, wid, did, content, name="refresh.csv"):
    response = start(env, headers, wid, content, name=name, dataset_id=str(did))
    assert response.status_code == 201, response.text
    sid = response.json()["id"]
    for index, chunk in enumerate(chunks(content, env.runtime.upload_chunk_bytes)):
        assert put(env, headers, wid, sid, index, chunk).status_code == 200
    return sid


def stage(env, headers, path, sid, owner=None):
    return env.client.post(
        path + "/refresh/candidates/from-upload-session",
        headers=headers,
        json=options(env, owner or headers, path) | {"session_id": sid},
    )


def session_state(env, headers, wid, sid):
    return env.client.get(f"/workspaces/{wid}/upload-sessions/{sid}", headers=headers).json()


def test_a_multi_chunk_file_becomes_a_validated_candidate_and_activates(integration):
    env = integration
    small_chunks(env)
    h, _, wid, did, uid, path, _ = setup(env)
    content = rows(20_000)
    assert len(content) > 4 * env.runtime.upload_chunk_bytes
    sid = upload(env, h, wid, did, content)
    storage = env.client.get("/me/storage", headers=h).json()
    assert storage["open_upload_bytes"] == len(content)
    response = stage(env, h, path, sid)
    assert response.status_code == 201, response.text
    candidate = response.json()
    assert candidate["status"] == "queued", candidate
    assert env.client.get(path + "/refresh", headers=h).json()["feed"]["source"]["upload_id"] == uid
    assert session_state(env, h, wid, sid)["status"] == "completed"
    assert env.client.get("/me/storage", headers=h).json()["open_upload_bytes"] == 0
    assert activate(env, h, wid, candidate).json()["status"] == "activated"
    with env.engine.begin() as connection:
        staged = connection.execute(
            select(s.uploads.c.checksum, s.uploads.c.size).where(
                s.uploads.c.id == UUID(candidate["details"]["input_upload_id"])
            )
        ).one()
    assert staged == (sha(content), len(content))
    again = stage(env, h, path, sid)
    assert (again.status_code, again.json()["error"]["code"]) == (409, "session_closed")


def test_an_invalid_chunked_file_fails_without_changing_the_active_source(integration):
    env = integration
    small_chunks(env)
    h, _, wid, did, uid, path, _ = setup(env)
    sid = upload(env, h, wid, did, rows(10_000) + b"Last,wrong\n")
    response = stage(env, h, path, sid)
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "failed"
    assert env.client.get(path + "/refresh", headers=h).json()["feed"]["source"]["upload_id"] == uid
    assert session_state(env, h, wid, sid)["status"] == "completed"


def test_sessions_must_be_complete_owned_and_for_the_same_dataset(integration):
    env = integration
    small_chunks(env)
    h, _, wid, did, _, path, _ = setup(env)
    content = rows(10_000)
    partial = start(env, h, wid, content, dataset_id=str(did)).json()["id"]
    assert put(env, h, wid, partial, 0, chunks(content, env.runtime.upload_chunk_bytes)[0])
    refused = stage(env, h, path, partial)
    assert (refused.status_code, refused.json()["error"]["code"]) == (409, "upload_incomplete")
    unbound = start(env, h, wid, content).json()["id"]
    for index, chunk in enumerate(chunks(content, env.runtime.upload_chunk_bytes)):
        put(env, h, wid, unbound, index, chunk)
    mismatch = stage(env, h, path, unbound)
    assert (mismatch.status_code, mismatch.json()["error"]["code"]) == (409, "session_mismatch")
    assert session_state(env, h, wid, unbound)["status"] == "open"
    stranger, _ = identity(env, "refresh-stranger@example.test")
    foreign = stage(env, stranger, path, upload(env, h, wid, did, content), owner=h)
    assert foreign.status_code in {403, 404}
    assert stage(env, h, path, str(uuid4())).status_code == 404


def test_interrupted_staging_is_failed_by_the_sweep_instead_of_ingested(integration):
    env = integration
    small_chunks(env)
    h, _, wid, did, _, path, _ = setup(env)
    sid = upload(env, h, wid, did, rows(10_000))
    uploads_before = len(env.client.get(path + "/uploads", headers=h).json())
    with env.engine.begin() as connection:
        connection.execute(
            update(s.upload_sessions)
            .where(s.upload_sessions.c.id == UUID(sid))
            .values(
                status="processing",
                error_code="consumed_elsewhere",
                lease_until=datetime.now(timezone.utc),
            )
        )
    assert env.runtime.upload_sessions.sweep() == {"expired": 0, "recovered": 1}
    state = session_state(env, h, wid, sid)
    assert state["status"] == "failed" and state["error"]["code"] == "interrupted"
    assert len(env.client.get(path + "/uploads", headers=h).json()) == uploads_before
