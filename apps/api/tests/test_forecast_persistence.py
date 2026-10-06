"""Use case: Preserves immutable private forecast evidence in real PostgreSQL.

What it does: Checks scoped lookup, complete source constraints and additive 0014 migration.
"""

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from alembic import command
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from execplus.domain.forecast_records import ForecastComparison, ForecastRun
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.persistence import schema as s
from test_studies import add_member, prepare, run
from test_workspace_integration import workspace


def retained_forecast(env):
    headers, actor, wid, did, uid, path = prepare(env)
    with env.runtime.service.uow() as repo:
        definition = repo.latest_understanding(UUID(wid), UUID(did))
        record = ForecastRun(
            uuid4(),
            UUID(wid),
            UUID(did),
            actor.id,
            "Private forecast",
            UUID(uid),
            definition.revision_id,
            definition.id,
            "last_value",
            "forecast-v1",
            {"horizon": 2},
            {"query_ids": [], "source_checksum": "fixture-only"},
            {"predictions": ["0.10000000000000000001", "0.20"]},
            datetime.now(timezone.utc),
        )
        repo.add(record)
    return headers, actor, path, record


def comparison(record):
    return ForecastComparison(
        uuid4(),
        record.workspace_id,
        record.dataset_id,
        record.owner_id,
        record.id,
        record.upload_id,
        record.revision_id,
        record.understanding_id,
        {"query_ids": [], "definition_id": str(record.understanding_id)},
        {"actual": "0.10000000000000000002", "error": "0.00000000000000000001"},
        datetime.now(timezone.utc),
    )


def test_forecast_records_roundtrip_exact_strings_and_owner_scoped_lists(integration):
    env = integration
    headers, actor, _, original = retained_forecast(env)
    _, member = add_member(env, headers, str(original.workspace_id))
    other_workspace = UUID(workspace(env, headers, name="Another workspace"))
    later = replace(original, id=uuid4(), created_at=original.created_at + timedelta(seconds=1))
    evaluated = comparison(original)
    with env.runtime.service.uow() as repo:
        repo.add(later)
        repo.add(evaluated)
    with env.runtime.service.uow() as repo:
        assert repo.forecast_run(original.workspace_id, original.id, actor.id) == original
        assert repo.forecast_runs(original.workspace_id, original.dataset_id, actor.id) == (
            later,
            original,
        )
        assert repo.forecast_comparison(original.workspace_id, evaluated.id, actor.id) == evaluated
        assert repo.forecast_comparisons(original.workspace_id, original.id, actor.id) == (
            evaluated,
        )
        assert repo.forecast_runs(original.workspace_id, original.dataset_id, member.id) == ()
        assert repo.forecast_comparisons(original.workspace_id, original.id, member.id) == ()
        for wid, owner in ((other_workspace, actor.id), (original.workspace_id, member.id)):
            with pytest.raises(IngestionError) as error:
                repo.forecast_run(wid, original.id, owner)
            assert error.value.status == 404
            with pytest.raises(IngestionError) as error:
                repo.forecast_comparison(wid, evaluated.id, owner)
            assert error.value.status == 404
    with pytest.raises(IntegrityError), env.runtime.service.uow() as repo:
        repo.add(replace(original, result={"predictions": ["999"]}))


@pytest.mark.parametrize(
    "field", ["workspace_id", "dataset_id", "upload_id", "revision_id", "understanding_id"]
)
def test_database_refuses_forecast_source_identity_mismatch(integration, field):
    env = integration
    _, _, _, original = retained_forecast(env)
    _, _, _, unrelated = retained_forecast(env)
    with pytest.raises(IntegrityError), env.runtime.service.uow() as repo:
        repo.add(replace(original, id=uuid4(), **{field: getattr(unrelated, field)}))
    with pytest.raises(IntegrityError), env.runtime.service.uow() as repo:
        repo.add(replace(comparison(original), **{field: getattr(unrelated, field)}))


def test_comparison_cannot_link_another_forecast_owner(integration):
    env = integration
    headers, _, _, original = retained_forecast(env)
    _, other = add_member(env, headers, str(original.workspace_id))
    with pytest.raises(IntegrityError), env.runtime.service.uow() as repo:
        repo.add(replace(comparison(original), owner_id=other.id))


def test_0014_preserves_all_0013_tables_and_existing_receipts_and_jobs(integration):
    env = integration
    headers, _, wid, _, _, path = prepare(env)
    study = run(env, headers, path)
    assert study.status_code == 201, study.text
    tid = env.client.post(path + "/threads", headers=headers).json()["id"]
    thread = f"/workspaces/{wid}/threads/{tid}"
    job = env.client.post(
        thread + "/jobs",
        headers=headers,
        json={"question": "Help me understand my data", "request_id": str(uuid4())},
    )
    assert job.status_code == 202, job.text

    def legacy():
        with env.engine.connect() as connection:
            return {
                name: sorted(
                    json.dumps(dict(row), sort_keys=True, default=str)
                    for row in connection.execute(select(table)).mappings()
                )
                for name, table in s.metadata.tables.items()
                if name not in {"forecast_runs", "forecast_comparisons"}
            }

    before = legacy()
    with env.engine.begin() as connection:
        env.config.attributes["connection"] = connection
        command.downgrade(env.config, "0013")
    assert "forecast_runs" not in inspect(env.engine).get_table_names()
    assert "jobs" in inspect(env.engine).get_table_names()
    with env.engine.begin() as connection:
        env.config.attributes["connection"] = connection
        command.upgrade(env.config, "head")
    assert legacy() == before
    version_id = study.json()["version"]["id"]
    reopened = env.client.get(f"/workspaces/{wid}/study-versions/{version_id}", headers=headers)
    assert reopened.status_code == 200, reopened.text
    assert (
        env.client.get(f"/workspaces/{wid}/jobs/{job.json()['id']}", headers=headers).json()[
            "status"
        ]
        == "queued"
    )
