"""Use case: Preserves retained work across additive source-import metadata.

What it does: Checks every previous table and refuses downgrade when approved
connection versions or immutable import records would otherwise be discarded.
"""

from uuid import uuid4

import pytest
from sqlalchemy import inspect, select

from execplus.infrastructure.persistence import schema as s
from test_source_import_lifecycle import setup
from test_studies import prepare
from test_usage_migration import migrate, snapshots

NEW = {"registered_sources", "source_imports"}


def test_source_migration_preserves_every_prior_table(integration):
    env = integration
    prepare(env)
    migrate(env, "downgrade", "0022")
    names = set(inspect(env.engine).get_table_names()) - {"alembic_version"}
    before = snapshots(env, names)
    migrate(env, "upgrade", "0023")
    assert snapshots(env, names) == before
    with env.engine.connect() as connection:
        assert all(
            connection.execute(select(s.metadata.tables[name])).first() is None for name in NEW
        )
    migrate(env, "downgrade", "0022")
    assert snapshots(env, names) == before
    migrate(env, "upgrade", "head")
    assert snapshots(env, names) == before


@pytest.mark.parametrize("imported", [False, True])
def test_source_downgrade_refuses_to_discard_config_or_saved_import(integration, imported):
    env = integration
    fixture = setup(env)
    if imported:
        fixture.service.start(fixture.actor, fixture.wid, uuid4(), fixture.selection)
    names = set(inspect(env.engine).get_table_names()) - {"alembic_version"}
    before = snapshots(env, names)
    with pytest.raises(RuntimeError, match="Preserve all source"):
        migrate(env, "downgrade", "0022")
    assert snapshots(env, names) == before
