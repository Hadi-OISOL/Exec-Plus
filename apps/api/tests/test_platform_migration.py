"""Use case: Preserves the existing private data partner when durable work is introduced.

What it does: Upgrades real legacy evidence and verifies tenant and turn linkage in PostgreSQL.
"""

import json
from uuid import UUID, uuid4

import pytest
from alembic import command
from sqlalchemy import inspect, select, update
from sqlalchemy.exc import IntegrityError

from execplus.infrastructure.persistence import schema as s
from test_refresh import monitor, process, setup, stage
from test_studies import run
from test_workspace_integration import dataset, identity, upload, workspace


def legacy_rows(engine):
    result = {}
    with engine.connect() as connection:
        for name, table in s.metadata.tables.items():
            if name in {"jobs", "job_attempts", "job_events"}:
                continue
            rows = [dict(row) for row in connection.execute(select(table)).mappings()]
            result[name] = sorted(json.dumps(row, sort_keys=True, default=str) for row in rows)
    return result


def test_upgrade_0012_preserves_old_receipts_meaning_refresh_studies_and_turns(integration):
    env = integration
    headers, _, wid, _did, uid, path, _feed = setup(env)
    root = path + f"/uploads/{uid}"
    study = run(env, headers, root)
    assert study.status_code == 201, study.text
    monitor(env, headers, path)
    assert process(env, headers, path)["complete"] == 1
    candidate = stage(env, headers, path)
    assert candidate.status_code == 201, candidate.text
    tid = env.client.post(root + "/threads", headers=headers).json()["id"]
    thread_path = f"/workspaces/{wid}/threads/{tid}"
    answer = env.client.post(
        thread_path + "/ask",
        headers=headers,
        json={"question": "Help me understand my data", "request_id": str(uuid4())},
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["turn"].get("job_id") is None
    before = legacy_rows(env.engine)
    with env.engine.begin() as connection:
        env.config.attributes["connection"] = connection
        command.downgrade(env.config, "0012")
    assert "jobs" not in inspect(env.engine).get_table_names()
    assert "job_id" not in {
        column["name"] for column in inspect(env.engine).get_columns("thread_turns")
    }
    with env.engine.begin() as connection:
        env.config.attributes["connection"] = connection
        command.upgrade(env.config, "head")
    assert legacy_rows(env.engine) == before
    turn = answer.json()["turn"]
    reopened = env.client.get(thread_path + f"/turns/{turn['id']}/answer", headers=headers)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json() == answer.json()["answer"]
    queued = env.client.post(
        thread_path + "/jobs",
        headers=headers,
        json={"question": "Help me understand my data", "request_id": str(uuid4())},
    )
    assert queued.status_code == 202, queued.text
    assert queued.json()["status"] == "queued"


def test_database_rejects_cross_workspace_job_and_wrong_turn_backlinks(integration):
    env = integration
    headers, _ = identity(env, "job-constraints@example.test")
    wid = workspace(env, headers)
    did = dataset(env, headers, wid)
    uid = upload(env, headers, wid, did).json()["id"]
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{uid}"
    assert env.client.get(root + "/profile", headers=headers).status_code == 200
    tid = env.client.post(root + "/threads", headers=headers).json()["id"]
    path = f"/workspaces/{wid}/threads/{tid}"
    first = env.client.post(
        path + "/jobs",
        headers=headers,
        json={"question": "Help me understand my data", "request_id": str(uuid4())},
    ).json()
    assert "id" in first, first
    assert (
        env.client.post(f"/workspaces/{wid}/jobs/{first['id']}/cancel", headers=headers).status_code
        == 200
    )
    second = env.client.post(
        path + "/jobs",
        headers=headers,
        json={"question": "Help me understand my data", "request_id": str(uuid4())},
    ).json()
    with pytest.raises(IntegrityError), env.engine.begin() as connection:
        connection.execute(
            update(s.thread_turns)
            .where(s.thread_turns.c.id == UUID(first["turn_id"]))
            .values(job_id=UUID(second["id"]))
        )
    other = workspace(env, headers, name="Unrelated workspace")
    with pytest.raises(IntegrityError), env.engine.begin() as connection:
        connection.execute(
            update(s.jobs).where(s.jobs.c.id == UUID(second["id"])).values(workspace_id=UUID(other))
        )
    assert (
        env.client.get(f"/workspaces/{wid}/jobs/{second['id']}", headers=headers).status_code == 200
    )
