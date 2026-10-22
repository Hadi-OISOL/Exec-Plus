"""Use case: Proves the PostgreSQL connector against a real database and its read-only guarantee.

What it does: Builds a throwaway schema and checks listing, copying, caps, safety and credentials.
"""

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from execplus.application.connector_ports import ConnectorApiError, ConnectorSession
from execplus.domain.connectors import records_to_csv
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.connectors.base import HostPolicy
from execplus.infrastructure.connectors.database import PostgresConnector


@pytest.fixture
def database():
    raw = os.environ.get("EXECPLUS_TEST_DATABASE_URL")
    if not raw:
        pytest.skip("Set EXECPLUS_TEST_DATABASE_URL to run the real PostgreSQL connector tests")
    url = make_url(raw)
    schema = "conn_" + uuid4().hex[:12]
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(
            text(
                f"""CREATE TABLE "{schema}".orders (
                    id serial PRIMARY KEY, customer text, amount numeric(12,2), paid boolean,
                    placed timestamptz, meta jsonb, doc bytea)"""
            )
        )
        connection.execute(
            text(
                f"""INSERT INTO "{schema}".orders (customer, amount, paid, placed, meta, doc)
                    SELECT 'Customer ' || n, n * 12.5, n % 2 = 0,
                           timestamptz '2026-01-03 04:05+00' + n * interval '1 day',
                           jsonb_build_object('tier', 'gold', 'visits', n), '\\x0102'::bytea
                    FROM generate_series(1, 5) AS n"""
            )
        )
        connection.execute(
            text(
                f'CREATE VIEW "{schema}".paid_orders AS '
                f'SELECT id, amount FROM "{schema}".orders WHERE paid'
            )
        )
    credentials = dict(
        host=url.host or "localhost",
        port=str(url.port or 5432),
        database=url.database or "",
        user=url.username or "",
        password=url.password or "",
    )
    yield schema, credentials, engine
    with engine.connect() as connection:
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    engine.dispose()


def connector():
    return PostgresConnector(HostPolicy(True))


def test_credentials_are_checked_and_the_display_name_names_the_database(database):
    _, credentials, _ = database
    name = connector().validate(credentials)
    assert name == f"{credentials['database']}@{credentials['host']}"


def test_wrong_passwords_and_missing_fields_are_rejected_without_leaking_details(database):
    _, credentials, _ = database
    with pytest.raises(ConnectorApiError) as wrong:
        connector().validate({**credentials, "password": "definitely-wrong"})
    assert wrong.value.status == 401 and "definitely-wrong" not in str(wrong.value)
    for field in ("database", "user"):
        with pytest.raises(ConnectorApiError):
            connector().validate({**credentials, field: ""})
    for bad_port in ("0", "70000", "abc"):
        with pytest.raises(ConnectorApiError):
            connector().validate({**credentials, "port": bad_port})
    for bad_host in ("", "user@host", "a/b", "has space"):
        with pytest.raises(ConnectorApiError):
            connector().validate({**credentials, "host": bad_host})


def test_private_hosts_are_refused_when_the_policy_forbids_them(database):
    _, credentials, _ = database
    with pytest.raises(IngestionError) as blocked:
        PostgresConnector(HostPolicy(False)).validate({**credentials, "host": "127.0.0.1"})
    assert blocked.value.code == "connector_host_blocked"


def test_schemas_tables_and_views_are_browsable(database):
    schema, credentials, _ = database
    session = ConnectorSession("", credentials)
    schemas = connector().sources(session, None)
    ours = next(item for item in schemas if item.label == schema)
    assert ours.container and not any(item.label.startswith("pg_") for item in schemas)
    assert "information_schema" not in [item.label for item in schemas]
    tables = connector().sources(session, ours.id)
    assert [item.label for item in tables] == ["orders", "paid_orders"]
    assert not any(item.container for item in tables)


def test_a_table_is_copied_with_exact_numbers_and_without_binary_columns(database):
    schema, credentials, _ = database
    session = ConnectorSession("", credentials)
    table = next(
        item for item in connector().sources(session, f"schema/{schema}") if item.label == "orders"
    )
    records = connector().fetch(session, table.id, 1000)
    assert len(records) == 5 and "doc" not in records[0]
    lines = records_to_csv(records).decode().splitlines()
    assert lines[0] == "id,customer,amount,paid,placed,meta_tier,meta_visits"
    assert lines[1] == "1,Customer 1,12.50,false,2026-01-04T04:05:00+00:00,gold,1"
    assert lines[2].split(",")[3] == "true"


def test_the_row_cap_is_enforced_and_views_can_be_copied(database):
    schema, credentials, _ = database
    session = ConnectorSession("", credentials)
    ids = {item.label: item.id for item in connector().sources(session, f"schema/{schema}")}
    assert len(connector().fetch(session, ids["orders"], 2)) == 2
    assert len(connector().fetch(session, ids["paid_orders"], 100)) == 2


def test_unknown_or_hostile_sources_are_refused_and_nothing_is_changed(database):
    schema, credentials, engine = database
    session = ConnectorSession("", credentials)
    for bad in (
        f"table/{schema}/orders; DROP TABLE {schema}.orders",
        f"table/{schema}/missing",
        f"table/{schema}",
        f"view/{schema}/orders",
        "orders",
    ):
        with pytest.raises(ConnectorApiError) as refused:
            connector().fetch(session, bad, 10)
        assert refused.value.status == 404
    with engine.connect() as connection:
        count = connection.execute(text(f'SELECT count(*) FROM "{schema}".orders')).scalar_one()
    assert count == 5


def test_the_session_is_read_only_so_writes_are_impossible(database):
    schema, credentials, _ = database
    guarded = connector()._engine(credentials)
    try:
        with guarded.connect() as connection:
            assert connection.execute(text("SHOW transaction_read_only")).scalar_one() == "on"
            for statement in (
                f"INSERT INTO \"{schema}\".orders (customer) VALUES ('x')",
                f'DELETE FROM "{schema}".orders',
                f'CREATE TABLE "{schema}".evil (id int)',
                f'DROP TABLE "{schema}".orders',
            ):
                with pytest.raises(DBAPIError):
                    connection.execute(text(statement))
                connection.rollback()
    finally:
        guarded.dispose()


def test_the_control_plane_database_is_never_an_eligible_source(database):
    _, credentials, _ = database
    own = (credentials["host"], int(credentials["port"]), credentials["database"])
    guarded = PostgresConnector(HostPolicy(True), own)
    with pytest.raises(ConnectorApiError) as refused:
        guarded.validate(credentials)
    assert refused.value.code == "control_plane_database"
    with pytest.raises(ConnectorApiError):
        guarded.validate(
            {
                **credentials,
                "host": "127.0.0.1" if credentials["host"] == "localhost" else "localhost",
            }
        )
    other = PostgresConnector(HostPolicy(True), (own[0], own[1], "some_other_database"))
    assert other.validate(credentials)
