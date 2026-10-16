"""Use case: Verifies source snapshots against a separate real PostgreSQL database.

What it does: Uses a disposable SELECT-only account, exact scalar fixtures and
concurrent commits to prove bounded read-only extraction without customer access.
"""

import csv
import hashlib
import json
import os
from dataclasses import replace
from io import StringIO
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from sqlalchemy.engine import make_url

from execplus.domain.ingestion import IngestionError
from execplus.domain.source_imports import MAX_CELL_BYTES, PostgresSource, SourceTable
from execplus.infrastructure.sources.postgres import PostgresSecrets, PostgresSnapshotExtractor


@pytest.fixture
def source_db(tmp_path):
    raw = os.environ.get("EXECPLUS_TEST_DATABASE_URL")
    if not raw:
        pytest.skip("A local PostgreSQL server is required for the separate source DB fixture")
    url = make_url(raw)
    assert url.host in {"127.0.0.1", "localhost"}, "Source fixture is local-only"
    name, role, password = "source_" + uuid4().hex, "reader_" + uuid4().hex, uuid4().hex
    params = dict(
        host="127.0.0.1",
        port=url.port or 5432,
        dbname=url.database,
        user=url.username,
        password=url.password,
    )
    with psycopg.connect(**params, autocommit=True) as control:
        control.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        control.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOINHERIT NOREPLICATION NOBYPASSRLS"
            ).format(sql.Identifier(role), sql.Literal(password))
        )
        try:
            with psycopg.connect(**{**params, "dbname": name}, autocommit=True) as admin:
                admin.execute(
                    "CREATE TABLE samples (id bigint, day date, region text, "
                    "revenue numeric(38,12), ready boolean, moment timestamptz, note text)"
                )
                admin.execute(
                    "INSERT INTO samples VALUES "
                    "(1,'2026-10-01','Karachi',0.1,true,'2026-10-01 12:00+05',NULL),"
                    "(2,'2026-10-02','Lahore',0.2,false,'2026-10-02 13:00+05','precise')"
                )
                admin.execute(sql.SQL("GRANT SELECT ON samples TO {}").format(sql.Identifier(role)))
                secret = tmp_path / "fixture.json"
                secret.write_text(json.dumps(dict(username=role, password=password)))
                secret.chmod(0o600)
                selection = SourceTable(
                    "public",
                    "samples",
                    ("id", "day", "region", "revenue", "ready", "moment", "note"),
                )
                source = PostgresSource(
                    uuid4(),
                    uuid4(),
                    1,
                    "Fictional source",
                    "localhost",
                    "127.0.0.1",
                    url.port or 5432,
                    name,
                    "fixture",
                    (selection,),
                )
                adapter = PostgresSnapshotExtractor(
                    PostgresSecrets(tmp_path),
                    frozenset({("127.0.0.1", url.port or 5432, url.database)}),
                    local_test=True,
                )
                yield SimpleNamespace(
                    admin=admin,
                    source=source,
                    selection=selection,
                    adapter=adapter,
                    secret=secret,
                    role=role,
                    password=password,
                    connect={**params, "dbname": name},
                )
        finally:
            control.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
            control.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def test_source_snapshot_is_complete_exact_and_does_not_modify_customer_table(source_db):
    f = source_db
    before = f.admin.execute("SELECT * FROM samples ORDER BY id").fetchall()
    snapshot = f.adapter.read(f.source, f.selection)
    rows = list(csv.reader(StringIO(snapshot.content.decode())))
    assert snapshot.row_count == 2 and rows[0] == list(f.selection.columns)
    assert rows[1][3:6] == ["0.100000000000", "true", "2026-10-01T07:00:00+00:00"]
    assert rows[2][3] == "0.200000000000" and rows[1][-1] == ""
    assert snapshot.checksum == hashlib.sha256(snapshot.content).hexdigest()
    assert f.admin.execute("SELECT * FROM samples ORDER BY id").fetchall() == before
    assert f.password not in repr(snapshot) and f.password not in repr(f.source)
    with (
        psycopg.connect(**{**f.connect, "user": f.role, "password": f.password}) as reader,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        reader.execute("DELETE FROM samples")


def test_repeatable_read_keeps_one_complete_snapshot_when_source_commits_mid_read(
    source_db, monkeypatch
):
    f = source_db
    original = psycopg.Connection.execute
    changed = False

    def execute(connection, query, *args, **kwargs):
        nonlocal changed
        result = original(connection, query, *args, **kwargs)
        statement = query.as_string(connection) if isinstance(query, sql.Composable) else query
        if not changed and connection.info.user == f.role and "SELECT COUNT(*)" in statement:
            changed = True
            f.admin.execute(
                "INSERT INTO samples (id,day,region,revenue) VALUES (3,'2026-10-03','New',0.3)"
            )
        return result

    monkeypatch.setattr(psycopg.Connection, "execute", execute)
    snapshot = f.adapter.read(f.source, f.selection)
    assert changed and snapshot.row_count == 2
    assert f.admin.execute("SELECT COUNT(*) FROM samples").fetchone()[0] == 3
    assert "New" not in snapshot.content.decode()


@pytest.mark.parametrize(
    "limit,expected", [("rows", "source_rows"), ("bytes", "source_size"), ("cell", "source_value")]
)
def test_import_limits_reject_whole_snapshot_instead_of_truncating(source_db, limit, expected):
    f = source_db
    source = f.source
    if limit == "rows":
        source = replace(source, max_rows=1)
    elif limit == "bytes":
        source = replace(source, max_bytes=10)
    else:
        f.admin.execute("UPDATE samples SET note=%s WHERE id=1", ("x" * (MAX_CELL_BYTES + 1),))
    with pytest.raises(IngestionError) as caught:
        f.adapter.read(source, f.selection)
    assert caught.value.code == expected


@pytest.mark.parametrize(
    "change,expected",
    [
        ("write_role", "source_role"),
        ("renamed", "source_schema"),
        ("unsupported", "source_schema"),
        ("view", "source_table"),
    ],
)
def test_changed_schema_unsafe_roles_and_views_are_refused(source_db, change, expected):
    f = source_db
    if change == "write_role":
        f.admin.execute(sql.SQL("GRANT INSERT ON samples TO {}").format(sql.Identifier(f.role)))
    elif change == "renamed":
        f.admin.execute("ALTER TABLE samples RENAME COLUMN revenue TO hidden_revenue")
    elif change == "unsupported":
        f.admin.execute("ALTER TABLE samples ALTER COLUMN note TYPE jsonb USING to_jsonb(note)")
    else:
        f.admin.execute("ALTER TABLE samples RENAME TO original_samples")
        f.admin.execute("CREATE VIEW samples AS SELECT * FROM original_samples")
        f.admin.execute(sql.SQL("GRANT SELECT ON samples TO {}").format(sql.Identifier(f.role)))
    with pytest.raises(IngestionError) as caught:
        f.adapter.read(f.source, f.selection)
    assert caught.value.code == expected


def test_quoted_source_names_cannot_execute_injected_sql(source_db):
    f = source_db
    name, column = "sales; DROP TABLE samples", 'amount"; DELETE FROM samples; --'
    f.admin.execute(
        sql.SQL("CREATE TABLE {} ({} numeric)").format(sql.Identifier(name), sql.Identifier(column))
    )
    f.admin.execute(sql.SQL("INSERT INTO {} VALUES (0.125)").format(sql.Identifier(name)))
    f.admin.execute(
        sql.SQL("GRANT SELECT ON {} TO {}").format(sql.Identifier(name), sql.Identifier(f.role))
    )
    selection = SourceTable("public", name, (column,))
    snapshot = f.adapter.read(replace(f.source, tables=(selection,)), selection)
    assert list(csv.reader(StringIO(snapshot.content.decode())))[1] == ["0.125"]
    assert f.admin.execute("SELECT COUNT(*) FROM samples").fetchone()[0] == 2


@pytest.mark.parametrize(
    "mode",
    ["public_secret", "symlink", "fifo", "bad_password", "blocked_control", "production_loopback"],
)
def test_secret_and_endpoint_failures_do_not_expose_credentials(source_db, mode, caplog):
    f = source_db
    source, adapter = f.source, f.adapter
    if mode == "public_secret":
        f.secret.chmod(0o644)
    elif mode == "symlink":
        target = f.secret.with_name("original.json")
        f.secret.rename(target)
        f.secret.symlink_to(target)
    elif mode == "fifo":
        f.secret.unlink()
        os.mkfifo(f.secret, 0o600)
    elif mode == "bad_password":
        f.secret.write_text(json.dumps(dict(username=f.role, password="unusable-fixture-password")))
    elif mode == "blocked_control":
        adapter = PostgresSnapshotExtractor(
            adapter.secrets,
            frozenset({(source.address, source.port, source.database)}),
            local_test=True,
        )
    else:
        adapter = PostgresSnapshotExtractor(adapter.secrets, frozenset())
    with pytest.raises(IngestionError) as caught:
        adapter.read(source, f.selection)
    assert f.password not in str(caught.value) and f.password not in caplog.text
    assert "unusable-fixture-password" not in str(caught.value)


def test_unapproved_fields_are_denied_before_any_database_connection(source_db, monkeypatch):
    f = source_db

    def connect(*args, **kwargs):
        raise AssertionError("An unapproved selection must never open a connection")

    monkeypatch.setattr(psycopg, "connect", connect)
    with pytest.raises(IngestionError) as caught:
        f.adapter.read(f.source, SourceTable("public", "samples", ("not_approved",)))
    assert caught.value.status == 404


def test_source_lock_wait_has_a_bounded_safe_failure(source_db):
    f = source_db
    with psycopg.connect(**f.connect) as holder:
        holder.execute("LOCK TABLE samples IN ACCESS EXCLUSIVE MODE")
        with pytest.raises(IngestionError) as caught:
            f.adapter.read(replace(f.source, timeout_seconds=1), f.selection)
    assert caught.value.code == "source_timeout"


@pytest.mark.parametrize("value", ["", "   "])
def test_empty_text_is_not_silently_converted_to_missing_data(source_db, value):
    f = source_db
    f.admin.execute("UPDATE samples SET note=%s WHERE id=1", (value,))
    with pytest.raises(IngestionError) as caught:
        f.adapter.read(f.source, f.selection)
    assert caught.value.code == "source_value"


def test_binary_float_source_requires_an_explicit_normalization_before_import(source_db):
    f = source_db
    f.admin.execute("ALTER TABLE samples ALTER COLUMN revenue TYPE double precision")
    with pytest.raises(IngestionError) as caught:
        f.adapter.read(f.source, f.selection)
    assert caught.value.code == "source_schema"


@pytest.mark.parametrize("environment", ["local", "staging", "production"])
def test_loopback_source_fixture_setting_is_refused_outside_test(environment):
    from pydantic import ValidationError

    from execplus.config import Settings

    with pytest.raises(ValidationError, match="restricted to the test"):
        Settings(environment=environment, source_allow_test_loopback=True, _env_file=None)


def test_loopback_test_setting_does_not_remove_control_database_denial(tmp_path):
    from execplus.config import Settings
    from execplus.infrastructure.sources.postgres import controlled_extractor

    settings = Settings(environment="test", source_allow_test_loopback=True, _env_file=None)
    adapter = controlled_extractor(
        tmp_path, "127.0.0.1", 5432, "control", local_test=settings.source_allow_test_loopback
    )
    table = SourceTable("public", "private", ("value",))
    source = PostgresSource(
        uuid4(), uuid4(), 1, "Not allowed", "localhost", "127.0.0.1", 5432,
        "control", "never-read", (table,),
    )
    with pytest.raises(IngestionError) as caught:
        adapter.read(source, table)
    assert caught.value.code == "source_endpoint"


def test_shared_deadline_stops_before_count_after_slow_metadata(source_db, monkeypatch):
    import execplus.infrastructure.sources.postgres as module

    fixture = source_db
    elapsed = [0.0]
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: elapsed[0]))
    execute = psycopg.Connection.execute
    count_attempted = False

    def observed(connection, query, *args, **kwargs):
        nonlocal count_attempted
        statement = query.as_string(connection) if isinstance(query, sql.Composable) else query
        if "SELECT COUNT(*)" in statement:
            count_attempted = True
        result = execute(connection, query, *args, **kwargs)
        if "SELECT a.attname" in statement:
            elapsed[0] = 2.1
        return result

    monkeypatch.setattr(psycopg.Connection, "execute", observed)
    with pytest.raises(IngestionError) as caught:
        fixture.adapter.read(replace(fixture.source, timeout_seconds=2), fixture.selection)
    assert caught.value.code == "source_timeout"
    assert not count_attempted


def test_deadline_cannot_publish_after_last_cell_processing(source_db, monkeypatch):
    import execplus.infrastructure.sources.postgres as module

    elapsed = [0.0]
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: elapsed[0]))
    original = module.cell
    calls = 0

    def slow(value):
        nonlocal calls
        calls += 1
        if calls == 14:
            elapsed[0] = 2.1
        return original(value)

    monkeypatch.setattr(module, "cell", slow)
    with pytest.raises(IngestionError) as caught:
        source_db.adapter.read(replace(source_db.source, timeout_seconds=2), source_db.selection)
    assert caught.value.code == "source_timeout" and calls == 14
