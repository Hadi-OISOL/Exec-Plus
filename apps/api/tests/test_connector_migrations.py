"""Use case: Preserves existing data and encrypted connections during connector migrations.

What it does: Checks additive upgrades and refuses downgrades that would discard connections.
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import inspect, select

from execplus.infrastructure.persistence import schema as s
from test_workspace_integration import dataset, identity, upload, workspace


def test_connector_upgrade_preserves_existing_rows(integration):
    env = integration
    headers, _ = identity(env, "connector-migration@example.test")
    wid = workspace(env, headers)
    did = dataset(env, headers, wid)
    assert upload(env, headers, wid, did).status_code == 201
    original = set(s.metadata.tables) - {
        "google_connections",
        "connector_connections",
        "account_reset_codes",
        "oauth_attempts",
        "external_identities",
    }

    def snapshot():
        with env.engine.connect() as connection:
            return {
                name: sorted(
                    json.dumps(dict(row), sort_keys=True, default=str)
                    for row in connection.execute(select(s.metadata.tables[name])).mappings()
                )
                for name in original
            }

    before = snapshot()
    with env.engine.begin() as connection:
        env.config.attributes["connection"] = connection
        command.downgrade(env.config, "0027")
    assert set(inspect(env.engine).get_table_names()) == original | {"alembic_version"}
    assert snapshot() == before
    with env.engine.begin() as connection:
        env.config.attributes["connection"] = connection
        command.upgrade(env.config, "head")
    assert snapshot() == before
    assert env.client.get("/health/ready").status_code == 200


@pytest.mark.parametrize("table_name", ["google_connections", "connector_connections"])
def test_connector_downgrade_refuses_retained_credentials(integration, table_name):
    env = integration
    _, actor = identity(env, "retained-connection@example.test")
    now = datetime.now(timezone.utc)
    values = dict(user_id=actor.id, created_at=now, updated_at=now, version=uuid4())
    if table_name == "google_connections":
        values.update(google_email=actor.email, scope="test", refresh_token_encrypted="sealed-test")
    else:
        values.update(provider="odoo", display_name="Test", sealed_credentials="sealed-test")
    table = s.metadata.tables[table_name]
    with env.engine.begin() as connection:
        connection.execute(table.insert().values(**values))
    with pytest.raises(RuntimeError, match="Disconnect"), env.engine.begin() as connection:
        env.config.attributes["connection"] = connection
        command.downgrade(env.config, "0027")
    with env.engine.connect() as connection:
        assert connection.execute(select(table)).mappings().one()["user_id"] == actor.id
    assert env.client.get("/health/ready").status_code == 200
