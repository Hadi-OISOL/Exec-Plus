"""Use case: Preserves native account protections when Google sign-in is available.

What it does: Rejects implicit password-account linking and disabled sessions in the shared issuer.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select, update

from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.identity import DatabaseSessionIdentity
from execplus.infrastructure.persistence import schema as s
from test_google_access import WEB, enable, exchange, sign_in
from test_local_accounts_integration import native


@pytest.mark.parametrize("disabled", [False, True])
def test_google_sign_in_cannot_bypass_native_account_protection(integration, disabled):
    env = integration
    _, actor, _, token = native(env, "google-native@example.test")
    issuer = DatabaseSessionIdentity(env.engine)
    assert issuer.authenticate(token).id == actor.id
    if disabled:
        with env.engine.begin() as connection:
            connection.execute(
                update(s.local_accounts)
                .where(s.local_accounts.c.user_id == actor.id)
                .values(disabled_at=datetime.now(timezone.utc))
            )
        with pytest.raises(IngestionError) as refused:
            issuer.authenticate(token)
        assert refused.value.status == 401
    with env.engine.connect() as connection:
        before = connection.execute(select(func.count()).select_from(s.sessions)).scalar_one()
    google, _ = enable(env)
    env.runtime.google_access.issuer = issuer
    _, callback = sign_in(env, google, actor.email)
    assert callback.headers["location"] == (f"{WEB}/workspace?oauth=complete")
    assert exchange(env) == {"error": "google_identity_conflict"}
    with env.engine.connect() as connection:
        assert (
            connection.execute(select(func.count()).select_from(s.sessions)).scalar_one() == before
        )


def test_connector_import_respects_workspace_plan_limits(integration):
    from test_connectors_service import connect_oauth
    from test_connectors_service import enable as enable_connectors
    from test_local_plans import assign
    from test_workspace_integration import dataset

    env = integration
    headers, actor, wid, _ = native(env, "connector-plan@example.test")
    did = dataset(env, headers, wid)
    enable_connectors(env)
    connect_oauth(env, headers, realmId="1")
    assign(env, actor, wid, file_bytes=1)
    base = f"/workspaces/{wid}/datasets/{did}"
    response = env.client.post(
        base + "/connectors/quickbooks/import", headers=headers, json={"source_id": "Invoice"}
    )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "plan_limit"
    assert env.client.get(base + "/uploads", headers=headers).json() == []
