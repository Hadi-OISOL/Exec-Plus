"""Use case: Prevents product reporting from holding revocation locks over aggregation.

What it does: Uses independent NOWAIT transactions to prove progress and rejects
reports when source access, membership or staff authority changes during computation.
"""

from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy import select, update

from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.persistence.reporting import SQLReportingRepository
from test_studies import prepare


@pytest.mark.parametrize("staff", [False, True])
@pytest.mark.parametrize("change", ["none", "policy", "policy_cycle", "authority"])
def test_usage_aggregate_releases_revocation_locks_and_rechecks_exact_epochs(
    integration, monkeypatch, staff, change
):
    env = integration
    owner, actor, wid, did, _, _ = prepare(env)
    if staff:
        env.runtime.operations.change_staff(actor.email, "admin")
    original = SQLReportingRepository.product_usage_facts
    checked = False

    def aggregate(repo, *args):
        nonlocal checked
        with env.engine.begin() as connection:
            connection.execute(
                select(s.workspaces.c.id)
                .where(s.workspaces.c.id == UUID(wid))
                .with_for_update(nowait=True)
            ).scalar_one()
            if staff:
                connection.execute(
                    select(s.staff_grants.c.user_id)
                    .where(s.staff_grants.c.user_id == actor.id)
                    .with_for_update(nowait=True)
                ).scalar_one()
        checked = True
        result = original(repo, *args)
        if change in {"policy", "policy_cycle"}:
            env.runtime.access_policies.save(
                actor,
                UUID(wid),
                UUID(did),
                0,
                True,
                [
                    {
                        "user_id": str(actor.id),
                        "columns": None,
                        "conditions": [],
                    }
                ],
            )
            if change == "policy_cycle":
                env.runtime.access_policies.save(actor, UUID(wid), UUID(did), 1, False, [])
        elif change == "authority":
            if staff:
                env.runtime.operations.change_staff(actor.email, None)
            else:
                with env.engine.begin() as connection:
                    connection.execute(
                        update(s.memberships)
                        .where(
                            s.memberships.c.workspace_id == UUID(wid),
                            s.memberships.c.user_id == actor.id,
                        )
                        .values(created_at=s.memberships.c.created_at + timedelta(seconds=1))
                    )
        return result

    monkeypatch.setattr(SQLReportingRepository, "product_usage_facts", aggregate)
    prefix = "/admin" if staff else ""
    response = env.client.get(f"{prefix}/workspaces/{wid}/product-usage", headers=owner)
    assert checked
    assert response.status_code == (
        200 if change == "none" else 403 if staff and change == "authority" else 404
    ), response.text
    if staff:
        with env.engine.connect() as connection:
            outcomes = (
                connection.execute(
                    select(s.staff_audit.c.outcome).where(
                        s.staff_audit.c.actor_id == actor.id,
                        s.staff_audit.c.action == "admin.product_usage",
                    )
                )
                .scalars()
                .all()
            )
        assert outcomes == ["success" if change == "none" else "denied"]


def test_staff_report_rejects_membership_recreation_under_an_unchanged_full_policy(
    integration, monkeypatch
):
    from test_workspace_integration import accept, identity, invite

    env = integration
    owner, owner_actor, wid, did, _, _ = prepare(env)
    headers, actor = identity(env, "reporting-staff-cycle@example.test")
    invitation = invite(env, owner, wid, actor.email, "admin").json()["id"]
    assert accept(env, headers, wid, invitation).status_code == 200
    env.runtime.operations.change_staff(actor.email, "admin")
    env.runtime.access_policies.save(
        owner_actor,
        UUID(wid),
        UUID(did),
        0,
        True,
        [
            {"user_id": str(user.id), "columns": None, "conditions": []}
            for user in (actor, owner_actor)
        ],
    )
    original = SQLReportingRepository.product_usage_facts

    def cycle(repo, *args):
        result = original(repo, *args)
        env.runtime.service.remove_member(owner_actor, UUID(wid), actor.id)
        replacement = invite(env, owner, wid, actor.email, "admin").json()["id"]
        assert accept(env, headers, wid, replacement).status_code == 200
        return result

    monkeypatch.setattr(SQLReportingRepository, "product_usage_facts", cycle)
    response = env.client.get(f"/admin/workspaces/{wid}/product-usage", headers=headers)
    assert response.status_code == 404, response.text
    with env.engine.connect() as connection:
        outcomes = (
            connection.execute(
                select(s.staff_audit.c.outcome).where(
                    s.staff_audit.c.actor_id == actor.id,
                    s.staff_audit.c.action == "admin.product_usage",
                )
            )
            .scalars()
            .all()
        )
    assert outcomes == ["denied"]
