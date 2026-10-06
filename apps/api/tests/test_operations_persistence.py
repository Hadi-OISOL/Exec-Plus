"""Use case: Protects staff CLI privacy and additive operations migration.

What it does: Verifies staff grants, tenant constraints and retained forecast/job data.
"""

import json
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from alembic import command
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from execplus import manage
from execplus.domain.operations import SupportEvent, SupportTicket
from execplus.infrastructure.persistence import schema as s
from test_forecast_integration import create as create_forecast
from test_forecast_integration import daily
from test_operations import setup
from test_studies import prepare
from test_workspace_integration import identity, workspace


def test_0015_preserves_all_0014_tables_forecasts_receipts_and_jobs(integration):
    env = integration
    headers, _, wid, did, _, root = prepare(env, daily())
    forecast = create_forecast(env, headers, root)
    assert forecast.status_code == 201
    tid = env.client.post(root + "/threads", headers=headers).json()["id"]
    job = env.client.post(
        f"/workspaces/{wid}/threads/{tid}/jobs",
        headers=headers,
        json={"question": "Help me understand my data", "request_id": str(uuid4())},
    )
    assert job.status_code == 202
    added = {"staff_grants", "staff_audit", "support_tickets", "support_events"}

    def snapshot():
        with env.engine.connect() as connection:
            return {
                name: sorted(
                    json.dumps(dict(row), sort_keys=True, default=str)
                    for row in connection.execute(select(table)).mappings()
                )
                for name, table in s.metadata.tables.items()
                if name not in added
            }

    before = snapshot()
    with env.engine.begin() as connection:
        env.config.attributes["connection"] = connection
        command.downgrade(env.config, "0014")
    assert added.isdisjoint(inspect(env.engine).get_table_names())
    assert snapshot() == before
    with env.engine.begin() as connection:
        env.config.attributes["connection"] = connection
        command.upgrade(env.config, "head")
    assert snapshot() == before
    assert added <= set(inspect(env.engine).get_table_names())
    response = env.client.get(
        f"/workspaces/{wid}/datasets/{did}/forecasts/{forecast.json()['id']}", headers=headers
    )
    assert response.status_code == 200 and response.json()["result"] == forecast.json()["result"]
    assert (
        env.client.get(f"/workspaces/{wid}/jobs/{job.json()['id']}", headers=headers).json()[
            "status"
        ]
        == "queued"
    )


def test_support_database_rejects_cross_tenant_events_and_foreign_feedback_owner(integration):
    env = integration
    owner, actor, wid, _, _, _, _ = setup(env)
    second = workspace(env, owner, name="Second tenant")
    other, other_actor = identity(env, "feedback-constraint@example.test")
    other_wid = workspace(env, other)
    feedback = env.client.post(
        f"/workspaces/{other_wid}/feedback",
        headers=other,
        json={"feature": "profile", "rating": 1, "category": "incorrect"},
    ).json()
    moment = datetime.now(timezone.utc)
    value = SupportTicket(
        uuid4(),
        UUID(wid),
        actor.id,
        "Case",
        "Shared text",
        "other",
        "other",
        "open",
        "normal",
        1,
        moment,
        moment,
    )
    with env.runtime.service.uow() as repo:
        repo.add_support_ticket(value)
    wrong = SupportEvent(
        uuid4(),
        UUID(second),
        value.id,
        1,
        actor.id,
        "requester",
        "created",
        "",
        "open",
        "normal",
        None,
        moment,
    )
    with pytest.raises(IntegrityError), env.runtime.service.uow() as repo:
        repo.add_support_event(wrong)
    for record in (
        replace(value, id=uuid4(), feedback_id=UUID(feedback["id"])),
        replace(value, id=uuid4(), workspace_id=UUID(other_wid), feedback_id=UUID(feedback["id"])),
    ):
        with pytest.raises(IntegrityError), env.runtime.service.uow() as repo:
            repo.add_support_ticket(record)
    with env.runtime.service.uow() as repo:
        repo.add_support_ticket(
            replace(
                value,
                id=uuid4(),
                workspace_id=UUID(other_wid),
                requester_id=other_actor.id,
                feedback_id=UUID(feedback["id"]),
            )
        )


def test_staff_cli_persists_grants_revokes_and_prints_no_session_token(
    integration, monkeypatch, capsys
):
    env = integration
    headers, actor = identity(env, "real-cli-staff@example.test")
    monkeypatch.setattr(manage, "build_runtime", lambda settings: env.runtime)
    for action, expected in (("grant-staff", "admin"), ("revoke-staff", None)):
        monkeypatch.setattr(
            sys, "argv", ["execplus.manage", action, "--email", actor.email, "--role", "admin"]
        )
        manage.main()
        captured = capsys.readouterr()
        assert captured.err == ""
        value = json.loads(captured.out)
        assert value == {"user_id": str(actor.id), "role": expected, "revoked": expected is None}
        assert "token" not in captured.out and actor.email not in captured.out
        assert env.client.get("/admin/access", headers=headers).json() == {"role": expected}


@pytest.mark.parametrize("stage", ["build", "change", "dispose"])
def test_staff_cli_failure_boundary_hides_dependency_parameters(stage):
    script = """
import sys
from types import SimpleNamespace
from sqlalchemy.exc import StatementError
from execplus import manage
stage = sys.argv[1]
def fail(*args, **kwargs):
    raise StatementError(
        "dependency failed", "SQL statement", {"secret": "PRIVATE_PARAMETER_SENTINEL"},
        RuntimeError("PRIVATE_PARAMETER_SENTINEL"),
    )
def change(*args, **kwargs):
    if stage == "change":
        fail()
    return {"role": "admin"}
def build(settings):
    if stage == "build":
        fail()
    return SimpleNamespace(
        operations=SimpleNamespace(change_staff=change),
        engine=SimpleNamespace(dispose=fail if stage == "dispose" else lambda: None),
    )
manage.Settings = lambda: object()
manage.build_runtime = build
sys.argv = ["execplus.manage", "grant-staff", "--email", "private@example.test", "--role", "admin"]
manage.main()
"""
    result = subprocess.run(
        [sys.executable, "-c", script, stage],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 1 and result.stdout == ""
    assert (
        result.stderr == "operator action=staff-access outcome=failed code=staff_access_failure\n"
    )
    assert "PRIVATE_PARAMETER_SENTINEL" not in result.stderr and "Traceback" not in result.stderr
