"""Use case: Proves additive model accounting preserves retained control-plane data.

What it does: Compares every existing 0020 table across migration and refuses any
lossy downgrade after explicit price, allowance or attempt evidence is retained.
"""

import json

import pytest
from alembic import command
from sqlalchemy import inspect, select

from execplus.infrastructure.persistence import schema as s
from test_studies import prepare
from test_usage_metering_integration import configured, reserve

NEW = {"usage_prices", "usage_policies", "usage_attempts", "model_usage_events"}


def migrate(env, direction, revision):
    with env.engine.begin() as connection:
        env.config.attributes["connection"] = connection
        getattr(command, direction)(env.config, revision)


def snapshots(env, names):
    with env.engine.connect() as connection:
        return {
            name: sorted(
                json.dumps(dict(row), sort_keys=True, default=str)
                for row in connection.execute(select(s.metadata.tables[name])).mappings()
            )
            for name in names
        }


def test_usage_migration_round_trip_preserves_every_0020_table(integration):
    env = integration
    prepare(env)
    migrate(env, "downgrade", "0020")
    names = set(inspect(env.engine).get_table_names()) - {"alembic_version"}
    before = snapshots(env, names)
    migrate(env, "upgrade", "0021")
    assert snapshots(env, names) == before
    with env.engine.connect() as connection:
        assert all(
            connection.execute(select(s.metadata.tables[name])).first() is None for name in NEW
        )
    migrate(env, "downgrade", "0020")
    assert snapshots(env, names) == before
    migrate(env, "upgrade", "head")
    assert snapshots(env, names) == before


def test_usage_downgrade_refuses_configuration_and_retains_attempt_history(
    integration, monkeypatch
):
    env = integration
    service, _, _, _, _, _, _, scope, _ = configured(env, monkeypatch)
    attempted = reserve(service, scope)
    service.start(scope, attempted.id)
    names = set(inspect(env.engine).get_table_names()) - {"alembic_version"}
    before = snapshots(env, names)
    with pytest.raises(RuntimeError, match="Preserve all model usage"):
        migrate(env, "downgrade", "0020")
    assert snapshots(env, names) == before
