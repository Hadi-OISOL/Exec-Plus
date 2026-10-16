"""Use case: Protects prior saved work when adding company worksheet persistence.

What it does: Compares real table contents across0023/0024 and refuses nonempty downgrade.
"""

import pytest
from sqlalchemy import inspect, select

from execplus.infrastructure.persistence import schema as s
from test_company_consolidation_integration import create, fixture
from test_usage_migration import migrate, snapshots


def test_consolidation_migration_keeps_every_prior_table(integration):
    env = integration
    fixture(env)
    migrate(env, "downgrade", "0023")
    names = set(inspect(env.engine).get_table_names()) - {"alembic_version"}
    before = snapshots(env, names)
    migrate(env, "upgrade", "0024")
    assert snapshots(env, names) == before
    with env.engine.connect() as connection:
        assert connection.execute(select(s.consolidation_runs)).first() is None
    migrate(env, "downgrade", "0023")
    assert snapshots(env, names) == before
    migrate(env, "upgrade", "head")
    assert snapshots(env, names) == before


def test_nonempty_worksheet_downgrade_refuses_and_preserves_every_table(integration):
    env = integration
    owner, _, _, path, request, _, _ = fixture(env)
    create(env, owner, path, request)
    names = set(inspect(env.engine).get_table_names()) - {"alembic_version"}
    before = snapshots(env, names)
    with pytest.raises(RuntimeError, match="Keep saved company worksheets"):
        migrate(env, "downgrade", "0023")
    assert snapshots(env, names) == before
