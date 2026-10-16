"""Use case: Protects retained work when integration access metadata is migrated.

What it does: Compares all prior tables through an additive 0022 round trip and
refuses downgrade once a private credential or embed record exists.
"""

import pytest
from sqlalchemy import inspect, select

from execplus.infrastructure.persistence import schema as s
from test_integration_access_integration import grant, issue, shared
from test_studies import prepare
from test_usage_migration import migrate, snapshots

NEW = {
    "integration_keys",
    "integration_request_windows",
    "embed_grants",
    "webhook_subscriptions",
    "webhook_deliveries",
}


def test_integration_migration_preserves_all_prior_tables(integration):
    env = integration
    prepare(env)
    migrate(env, "downgrade", "0021")
    names = set(inspect(env.engine).get_table_names()) - {"alembic_version"}
    before = snapshots(env, names)
    migrate(env, "upgrade", "0022")
    assert snapshots(env, names) == before
    with env.engine.connect() as connection:
        assert all(
            connection.execute(select(s.metadata.tables[name])).first() is None for name in NEW
        )
    migrate(env, "downgrade", "0021")
    assert snapshots(env, names) == before
    migrate(env, "upgrade", "head")
    assert snapshots(env, names) == before


@pytest.mark.parametrize("record", ["key", "embed"])
def test_integration_downgrade_preserves_credentials_and_views(integration, record):
    env = integration
    owner, _, wid, did, _, _, board = shared(env)
    if record == "key":
        issue(env, owner, wid, did)
    else:
        grant(env, owner, wid, board["id"])
    names = set(inspect(env.engine).get_table_names()) - {"alembic_version"}
    before = snapshots(env, names)
    with pytest.raises(RuntimeError, match="Preserve"):
        migrate(env, "downgrade", "0021")
    assert snapshots(env, names) == before
