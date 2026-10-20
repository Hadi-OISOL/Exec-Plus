"""Use case: Proves additive native-account schema behavior in disposable PostgreSQL.

What it does: Preserves legacy records and refuses downgrade after retained account or guide state.
"""

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, create_engine, inspect, select, text

from execplus.infrastructure.persistence import schema as s


@pytest.fixture
def account_migration():
    url = os.environ.get("EXECPLUS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set the dedicated PostgreSQL integration URL")
    name = "test_accounts_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{name}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={name}"})
    config = Config("alembic.ini")
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "0024")
        now, user_id, workspace_id = datetime.now(timezone.utc), uuid4(), uuid4()
        with engine.begin() as connection:
            connection.execute(
                s.users.insert().values(
                    id=user_id, email="legacy@example.test", display_name="Legacy", created_at=now
                )
            )
            connection.execute(
                s.sessions.insert().values(
                    token_hash="a" * 64, user_id=user_id, expires_at=now + timedelta(hours=8)
                )
            )
            connection.execute(
                s.workspaces.insert().values(
                    id=workspace_id,
                    name="Legacy workspace",
                    seat_limit=3,
                    created_at=now,
                    updated_at=now,
                )
            )
            connection.execute(
                s.memberships.insert().values(
                    workspace_id=workspace_id, user_id=user_id, role="owner", created_at=now
                )
            )
        yield engine, config, user_id, workspace_id, now
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{name}" CASCADE'))
        admin.dispose()


def migrate(engine, config, version, *, down=False):
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        (command.downgrade if down else command.upgrade)(config, version)


def test_0025_upgrade_and_empty_downgrade_preserve_all_legacy_tables(account_migration):
    engine, config, *_ = account_migration
    tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
    historical = MetaData()
    historical.reflect(bind=engine, only=sorted(tables))

    def snapshot():
        with engine.connect() as connection:
            return {
                name: list(connection.execute(select(historical.tables[name])).mappings())
                for name in sorted(tables)
            }

    before = snapshot()
    migrate(engine, config, "0025")
    assert snapshot() == before
    assert set(inspect(engine).get_table_names()) - tables == {
        "alembic_version",
        "local_accounts",
        "account_events",
        "account_rate_windows",
        "invitation_identity_approvals",
        "onboarding_progress",
    }
    migrate(engine, config, "0024", down=True)
    assert snapshot() == before
    assert set(inspect(engine).get_table_names()) == tables | {"alembic_version"}


@pytest.mark.parametrize("retained", ["account", "history", "guide"])
def test_0025_downgrade_refuses_retained_identity_and_private_history(account_migration, retained):
    engine, config, user_id, workspace_id, now = account_migration
    migrate(engine, config, "0025")
    with engine.begin() as connection:
        if retained == "account":
            connection.execute(
                s.local_accounts.insert().values(
                    user_id=user_id,
                    password_hash="synthetic-non-authenticating-hash",
                    password_changed_at=now,
                )
            )
        elif retained == "history":
            connection.execute(
                s.account_events.insert().values(
                    id=uuid4(), user_id=user_id, action="synthetic.event", reason="", created_at=now
                )
            )
        else:
            connection.execute(
                s.onboarding_progress.insert().values(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    version=1,
                    active_step="data",
                    skipped_steps=[],
                    paused=True,
                    finished=False,
                    updated_at=now,
                )
            )
    with pytest.raises(RuntimeError, match="Keep local accounts"):
        migrate(engine, config, "0024", down=True)
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0025"
        )
        assert connection.execute(select(s.users.c.id)).scalar_one() == user_id
