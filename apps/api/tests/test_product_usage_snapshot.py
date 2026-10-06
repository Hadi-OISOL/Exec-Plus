"""Use case: Verifies a product report observes one PostgreSQL statement snapshot.

What it does: Exercises concurrent commits, aggregate query count and exact metering values.
"""

from datetime import date, timedelta
from uuid import UUID, uuid4

from sqlalchemy import event, insert

from execplus.application.services import product_usage
from execplus.domain.product_usage import UsageFacts, report_start
from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.persistence.reporting import SQLReportingRepository
from test_product_usage_integration import NOW, FixedClock, activity, report
from test_workspace_integration import identity, workspace


def test_mid_report_commit_is_visible_only_in_the_next_complete_report(integration, monkeypatch):
    env = integration
    headers, actor = identity(env, "usage-snapshot@example.test")
    wid = workspace(env, headers)
    statements = []
    committed = False

    def commit_after_first_aggregate(_conn, _cursor, statement, _params, _context, _many):
        nonlocal committed
        if "audit_events" not in statement or not statement.lstrip().upper().startswith(
            ("WITH", "SELECT")
        ):
            return
        statements.append(statement)
        if committed:
            return
        committed = True
        activity(env, wid, actor, "job.submitted", NOW - timedelta(days=8))
        activity(env, wid, actor, "query.executed", NOW - timedelta(days=8))
        with env.engine.begin() as connection:
            connection.execute(
                insert(s.usage_events).values(
                    id=uuid4(),
                    workspace_id=UUID(wid),
                    actor_id=actor.id,
                    kind="upload",
                    quantity=1,
                    resource_id=uuid4(),
                    created_at=NOW - timedelta(days=8),
                )
            )

    event.listen(env.engine, "after_cursor_execute", commit_after_first_aggregate)
    try:
        first = report(env, headers, wid, monkeypatch)
    finally:
        event.remove(env.engine, "after_cursor_execute", commit_after_first_aggregate)
    assert committed and len(statements) == 1
    assert first["summary"]["active_users"] == first["summary"]["active_members"] == 0
    assert first["summary"]["never_active_members"] == 1
    assert first["cohorts"] == first["features"] == []
    assert all(item["actions"] == item["active_users"] == 0 for item in first["weekly"])
    assert first["usage"]["uploads"] == first["usage"]["queries_completed"] == 0

    second = report(env, headers, wid, monkeypatch)
    assert second["summary"]["active_users"] == second["summary"]["active_members"] == 1
    assert second["summary"]["never_active_members"] == 0
    assert second["features"] == [dict(feature="conversation", users=1, actions=1)]
    assert sum(item["actions"] for item in second["weekly"]) == 1
    assert second["cohorts"][0]["users"] == 1
    assert second["cohorts"][0]["cells"][0]["rate_percent"] == "100.00"
    assert second["usage"]["uploads"] == second["usage"]["queries_completed"] == 1


def test_json_aggregate_keeps_large_integer_metering_and_empty_observations_exact(integration):
    env = integration
    headers, actor = identity(env, "usage-exact-snapshot@example.test")
    wid = workspace(env, headers)
    quantity = 2**31 - 1
    with env.engine.begin() as connection:
        for _ in range(2):
            connection.execute(
                insert(s.usage_events).values(
                    id=uuid4(),
                    workspace_id=UUID(wid),
                    actor_id=actor.id,
                    kind="storage_bytes",
                    quantity=quantity,
                    resource_id=uuid4(),
                    created_at=NOW - timedelta(days=1),
                )
            )
    with env.engine.connect() as connection:
        repo = SQLReportingRepository()
        repo.connection = connection
        facts = repo.product_usage_facts(UUID(wid), report_start(NOW, 8), NOW)
    assert facts.weekly == facts.features == facts.cohorts == facts.retained == ()
    assert facts.usage["storage_bytes"] == quantity * 2
    assert type(facts.usage["storage_bytes"]) is int


def test_owner_and_staff_http_reports_preserve_unsafe_integers_and_boolean_maturity(
    integration, monkeypatch
):
    env = integration
    owner, _ = identity(env, "usage-wire-owner@example.test")
    wid = workspace(env, owner)
    staff, staff_actor = identity(env, "usage-wire-staff@example.test")
    env.runtime.operations.change_staff(staff_actor.email, "admin")
    boundary = 2**53 - 1
    large = boundary + 2
    cohort = date(2026, 9, 28)
    facts = UsageFacts(
        summary=dict(active_users=large, current_members=boundary),
        weekly=((cohort, 1, large),),
        features=(("conversation", 1, large),),
        cohorts=((cohort, 3),),
        retained=((cohort, cohort, 1),),
        usage=dict(uploads=1, storage_bytes=large, queries_completed=boundary),
    )
    monkeypatch.setattr(
        SQLReportingRepository, "product_usage_facts", lambda _repo, _wid, _start, _now: facts
    )
    monkeypatch.setattr(product_usage, "datetime", FixedClock)
    results = []
    for prefix, headers in (("", owner), ("/admin", staff)):
        response = env.client.get(
            f"{prefix}/workspaces/{wid}/product-usage?weeks=2", headers=headers
        )
        assert response.status_code == 200
        value = response.json()
        assert value["usage"]["storage_bytes"] == str(large)
        assert value["summary"]["active_users"] == str(large)
        assert value["weekly"][0]["actions"] == str(large)
        assert value["features"][0]["actions"] == str(large)
        assert value["usage"]["queries_completed"] == boundary
        assert type(value["usage"]["queries_completed"]) is int
        assert value["weekly"][0]["complete"] is True
        assert value["weekly"][1]["complete"] is False
        assert value["cohorts"][0]["cells"][0]["eligible"] is True
        assert value["cohorts"][0]["cells"][1]["eligible"] is False
        assert value["cohorts"][0]["cells"][0]["rate_percent"] == "33.33"
        assert value["cohorts"][0]["cells"][1]["retained"] is None
        results.append(value)
    assert results[0] == results[1]
    assert facts.usage["storage_bytes"] == large and type(facts.usage["storage_bytes"]) is int
