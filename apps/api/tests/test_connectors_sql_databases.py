"""Use case: Proves the MySQL, MariaDB and SQL Server connectors against real database servers.

What it does: Builds a throwaway database with a read-only login and checks listing, previews,
exact copies, custom SELECT rules, read-only sessions, host rules and bounded large imports.
"""

import csv
import io
import os
import tempfile
import tracemalloc
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from execplus.application.connector_ports import ConnectorApiError, ConnectorSession
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.connectors.base import HostPolicy
from execplus.infrastructure.connectors.database import MySqlConnector, SqlServerConnector

ENGINES = {
    "mysql": ("EXECPLUS_TEST_MYSQL_URL", MySqlConnector),
    "mariadb": ("EXECPLUS_TEST_MARIADB_URL", MySqlConnector),
    "sqlserver": ("EXECPLUS_TEST_MSSQL_URL", SqlServerConnector),
}
BIG_ROWS = 300_000


def _mysql(admin, name, user, secret):
    statements = [
        f"CREATE DATABASE `{name}`",
        f"""CREATE TABLE `{name}`.orders (
            id INT PRIMARY KEY, customer VARCHAR(60), amount DECIMAL(18,4), paid BOOLEAN,
            placed DATETIME, meta JSON, doc VARBINARY(10))""",
        f"""INSERT INTO `{name}`.orders VALUES
            (1, 'Customer 1', 12345678901234.5678, 0, '2026-01-04 04:05:00',
             '{{"tier": "gold", "visits": 1}}', X'0102'),
            (2, 'Customer 2', 0.0001, 1, '2026-01-05 04:05:00',
             '{{"tier": "gold", "visits": 2}}', X'0102'),
            (3, 'Customer 3', -7.5000, 1, NULL, NULL, NULL)""",
        f"CREATE VIEW `{name}`.paid_orders AS SELECT id, amount FROM `{name}`.orders WHERE paid",
        f"""CREATE TABLE `{name}`.big (id INT PRIMARY KEY, amount DECIMAL(12,2),
            label VARCHAR(20))""",
        "SET SESSION cte_max_recursion_depth = 1000000",
        f"""INSERT INTO `{name}`.big
            WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < {BIG_ROWS})
            SELECT i, i * 0.01, CONCAT('row ', i) FROM n""",
        f"ANALYZE TABLE `{name}`.orders, `{name}`.big",
        f"CREATE USER '{user}'@'%%' IDENTIFIED BY '{secret}'",
        f"GRANT SELECT, SHOW VIEW ON `{name}`.* TO '{user}'@'%%'",
    ]
    with admin.connect() as connection:
        if connection.dialect.server_version_info and "MariaDB" in str(
            connection.exec_driver_sql("SELECT VERSION()").scalar_one()
        ):
            statements[5] = "SET SESSION max_recursive_iterations = 1000000"
        for statement in statements:
            connection.exec_driver_sql(statement)
        connection.commit()

    def drop():
        with admin.connect() as connection:
            connection.exec_driver_sql(f"DROP DATABASE `{name}`")
            connection.exec_driver_sql(f"DROP USER '{user}'@'%%'")
            connection.commit()

    return name, drop


def _mssql(admin, name, user, secret):
    with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql(f"CREATE DATABASE [{name}]")
        connection.exec_driver_sql(f"CREATE LOGIN [{user}] WITH PASSWORD = '{secret}'")
    statements = [
        f"CREATE USER [{user}] FOR LOGIN [{user}]",
        f"ALTER ROLE db_datareader ADD MEMBER [{user}]",
        "CREATE SCHEMA sales",
        """CREATE TABLE sales.orders (
            id INT PRIMARY KEY, customer NVARCHAR(60), amount DECIMAL(18,4), paid BIT,
            placed DATETIME2, meta NVARCHAR(200), doc VARBINARY(10))""",
        """INSERT INTO sales.orders VALUES
            (1, N'Customer 1', 12345678901234.5678, 0, '2026-01-04 04:05:00',
             N'{"tier": "gold"}', 0x0102),
            (2, N'Customer 2', 0.0001, 1, '2026-01-05 04:05:00', N'x', 0x0102),
            (3, N'Customer 3', -7.5000, 1, NULL, NULL, NULL)""",
        "CREATE VIEW sales.paid_orders AS SELECT id, amount FROM sales.orders WHERE paid = 1",
        "CREATE TABLE sales.big (id INT PRIMARY KEY, amount DECIMAL(12,2), label VARCHAR(20))",
        f"""WITH n AS (SELECT TOP ({BIG_ROWS}) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i
            FROM sys.all_objects a CROSS JOIN sys.all_objects b CROSS JOIN sys.all_objects c)
            INSERT INTO sales.big SELECT i, i * 0.01, CONCAT('row ', i) FROM n""",
    ]
    scoped = create_engine(admin.url.set(database=name))
    with scoped.connect() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)
        connection.commit()
    scoped.dispose()

    def drop():
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.exec_driver_sql(
                f"ALTER DATABASE [{name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE"
            )
            connection.exec_driver_sql(f"DROP DATABASE [{name}]")
            connection.exec_driver_sql(f"DROP LOGIN [{user}]")

    return "sales", drop


@pytest.fixture(scope="module", params=list(ENGINES))
def server(request):
    variable, kind = ENGINES[request.param]
    raw = os.environ.get(variable)
    if not raw:
        pytest.skip(f"Set {variable} to run the real {request.param} connector tests")
    url = make_url(raw)
    name = "conn_" + uuid4().hex[:10]
    user, secret = "reader_" + uuid4().hex[:8], "Rd!" + uuid4().hex
    admin = create_engine(url)
    build = _mssql if kind is SqlServerConnector else _mysql
    schema, drop = build(admin, name, user, secret)
    base = dict(host=url.host or "localhost", port=str(url.port), database=name)
    reader = {**base, "user": user, "password": secret}
    owner = {**base, "user": url.username or "", "password": url.password or ""}
    yield request.param, kind, schema, reader, owner, admin
    drop()
    admin.dispose()


def session(credentials):
    return ConnectorSession("", credentials)


def export(connector, credentials, source_id, max_rows=1000, max_bytes=20 * 1024 * 1024):
    with tempfile.TemporaryFile() as target:
        count = connector.export(
            session(credentials), source_id, target, max_rows=max_rows, max_bytes=max_bytes
        )
        target.seek(0)
        return count, target.read().decode()


def test_the_read_only_login_connects_and_wrong_passwords_are_refused(server):
    _, kind, _, reader, _, _ = server
    connector = kind(HostPolicy(True))
    assert connector.validate(reader) == f"{reader['database']}@{reader['host']}"
    with pytest.raises(ConnectorApiError) as wrong:
        connector.validate({**reader, "password": "definitely-wrong"})
    assert wrong.value.status == 401 and "definitely-wrong" not in str(wrong.value)
    for field in ("database", "user"):
        with pytest.raises(ConnectorApiError):
            connector.validate({**reader, field: ""})
    for bad in ({"port": "0"}, {"port": "abc"}, {"host": "a@b"}, {"tls": "maybe"}):
        with pytest.raises(ConnectorApiError):
            connector.validate({**reader, **bad})


def test_private_hosts_and_unencrypted_sessions_are_refused_outside_trusted_deployments(server):
    _, kind, _, reader, _, _ = server
    strict = kind(HostPolicy(False))
    with pytest.raises(IngestionError) as blocked:
        strict.validate(reader)
    assert blocked.value.code == "connector_host_blocked"
    assert "off" not in next(item for item in strict.fields if item.name == "tls").options
    with pytest.raises(ConnectorApiError) as plain:
        strict._tls({"tls": "off"})
    assert plain.value.code == "invalid_tls"


def test_encrypted_sessions_work_and_unverifiable_certificates_are_refused(server):
    name, kind, _, reader, _, _ = server
    connector = kind(HostPolicy(True))
    assert connector.validate({**reader, "tls": "require"})
    if name != "sqlserver":
        with pytest.raises(ConnectorApiError) as unverified:
            connector.validate({**reader, "tls": "verify"})
        assert (unverified.value.status, unverified.value.code) == (422, "tls_unverified")


def _fresh_mysql_login(admin, database):
    user, secret = "plain_" + uuid4().hex[:8], "Pl!" + uuid4().hex
    with admin.connect() as connection:
        connection.exec_driver_sql(f"CREATE USER '{user}'@'%%' IDENTIFIED BY '{secret}'")
        connection.exec_driver_sql(f"GRANT SELECT ON `{database}`.* TO '{user}'@'%%'")
        connection.commit()
    return user, secret


def test_a_first_unencrypted_sign_in_with_tls_off_connects_without_encryption(server):
    name, kind, _, reader, _, admin = server
    if name == "sqlserver":
        connector = kind(HostPolicy(True))
        assert connector.validate({**reader, "tls": "off"})
        return
    user, secret = _fresh_mysql_login(admin, reader["database"])
    plain = {**reader, "user": user, "password": secret, "tls": "off"}
    connector = kind(HostPolicy(True))
    assert connector.validate(plain)
    with connector._connection(plain) as connection:
        cipher = connection.exec_driver_sql("SHOW SESSION STATUS LIKE 'Ssl_cipher'").one()[1]
    assert not cipher


def test_servers_without_tls_connect_when_allowed_and_refuse_clearly_when_tls_is_required():
    raw = os.environ.get("EXECPLUS_TEST_MYSQL_PLAIN_URL")
    if not raw:
        pytest.skip("Set EXECPLUS_TEST_MYSQL_PLAIN_URL to a MySQL server started without TLS")
    url = make_url(raw)
    admin = create_engine(url)
    database = "plain_" + uuid4().hex[:8]
    with admin.connect() as connection:
        connection.exec_driver_sql(f"CREATE DATABASE `{database}`")
        connection.commit()
    user, secret = _fresh_mysql_login(admin, database)
    base = dict(
        host=url.host or "localhost",
        port=str(url.port),
        database=database,
        user=user,
        password=secret,
    )
    try:
        trusted = MySqlConnector(HostPolicy(True))
        assert trusted.validate({**base, "tls": "off"})
        assert trusted.validate(base)
        for mode in ("require", "verify"):
            with pytest.raises(ConnectorApiError) as refused:
                trusted.validate({**base, "tls": mode})
            assert (refused.value.status, refused.value.code) == (422, "tls_unavailable")
            with pytest.raises(ConnectorApiError) as listing:
                trusted.sources(session({**base, "tls": mode}), None)
            assert listing.value.code == "tls_unavailable"
    finally:
        with admin.connect() as connection:
            connection.exec_driver_sql(f"DROP DATABASE `{database}`")
            connection.exec_driver_sql(f"DROP USER '{user}'@'%%'")
            connection.commit()
        admin.dispose()


def test_schemas_tables_and_views_are_listed_with_approximate_row_counts(server):
    name, kind, schema, reader, _, _ = server
    connector = kind(HostPolicy(True))
    schemas = connector.sources(session(reader), None)
    labels = [item.label.lower() for item in schemas]
    assert schema in [item.label for item in schemas]
    assert not {"mysql", "sys", "information_schema", "performance_schema"} & set(labels)
    assert not any(label.startswith("db_") for label in labels)
    ours = next(item for item in schemas if item.label == schema)
    tables = {item.label: item for item in connector.sources(session(reader), ours.id)}
    assert list(tables) == ["big", "orders", "paid_orders"]
    assert tables["paid_orders"].rows is None and not tables["orders"].container
    assert tables["orders"].rows is not None and tables["big"].rows is not None
    if name == "sqlserver":
        assert (tables["orders"].rows, tables["big"].rows) == (3, BIG_ROWS)
    else:
        assert 0 < tables["big"].rows <= BIG_ROWS * 2


def test_a_table_is_copied_with_exact_decimals_and_without_binary_columns(server):
    name, kind, schema, reader, _, _ = server
    connector = kind(HostPolicy(True))
    count, content = export(connector, reader, f"table/{schema}/orders")
    rows = list(csv.reader(io.StringIO(content)))
    assert count == 3 and "doc" not in rows[0]
    if name == "sqlserver":
        assert rows[0] == ["id", "customer", "amount", "paid", "placed", "meta"]
        assert rows[1] == [
            "1",
            "Customer 1",
            "12345678901234.5678",
            "false",
            "2026-01-04T04:05:00",
            '{"tier": "gold"}',
        ]
    elif name == "mysql":
        assert rows[0] == [
            "id",
            "customer",
            "amount",
            "paid",
            "placed",
            "meta_tier",
            "meta_visits",
            "meta",
        ]
        assert rows[1] == [
            "1",
            "Customer 1",
            "12345678901234.5678",
            "0",
            "2026-01-04T04:05:00",
            "gold",
            "1",
            "",
        ]
    else:
        assert rows[0] == ["id", "customer", "amount", "paid", "placed", "meta"]
        assert rows[1] == [
            "1",
            "Customer 1",
            "12345678901234.5678",
            "0",
            "2026-01-04T04:05:00",
            '{"tier": "gold", "visits": 1}',
        ]
    assert rows[2][2] == "0.0001" and rows[3][2] == "-7.5000"
    view_count, _ = export(connector, reader, f"table/{schema}/paid_orders")
    assert view_count == 2


def test_previews_show_the_first_rows_of_tables_and_queries(server):
    _, kind, schema, reader, _, _ = server
    connector = kind(HostPolicy(True))
    table = connector.preview(session(reader), f"table/{schema}/big")
    assert table["columns"] == ["id", "amount", "label"] and len(table["rows"]) == 20
    query = connector.preview(
        session(reader), f"query/SELECT id, amount FROM {schema}.orders WHERE id = 1"
    )
    assert query == {"columns": ["id", "amount"], "rows": [["1", "12345678901234.5678"]]}


def test_a_custom_select_is_imported_and_the_row_limit_refuses_partial_copies(server):
    _, kind, schema, reader, _, _ = server
    connector = kind(HostPolicy(True))
    query = f"query/SELECT customer, amount * 2 AS doubled FROM {schema}.orders WHERE id > 1;"
    count, content = export(connector, reader, query)
    assert count == 2
    assert content.splitlines()[0] == "customer,doubled"
    assert "Customer 3,-15.0000" in content
    with pytest.raises(IngestionError) as capped:
        export(connector, reader, f"query/SELECT id FROM {schema}.big", max_rows=10)
    assert capped.value.code == "source_too_large"
    with pytest.raises(IngestionError) as wide:
        export(connector, reader, f"table/{schema}/big", max_bytes=1000)
    assert wide.value.code == "source_too_large"


HOSTILE = {
    "mysql": [
        "DELETE FROM {s}.orders",
        "SELECT 1; DELETE FROM {s}.orders",
        "SELECT 1 /*!50000 ; DELETE FROM {s}.orders */",
        "SELECT 1 # comment",
        "SELECT SLEEP(5)",
        "SELECT * FROM {s}.orders FOR UPDATE",
        "SELECT LOAD_FILE('/etc/passwd')",
        "SELECT id INTO @x FROM {s}.orders",
        "UPDATE {s}.orders SET amount = 0",
        "SELECT 1 FROM {s}.orders; -- '",
    ],
    "sqlserver": [
        "DELETE FROM {s}.orders",
        "SELECT 1; DELETE FROM {s}.orders",
        "SELECT 1 -- ; DELETE",
        "SELECT * INTO {s}.copy FROM {s}.orders",
        "EXEC xp_cmdshell 'dir'",
        "WAITFOR DELAY '00:00:05'",
        "SELECT * FROM OPENROWSET('SQLNCLI', 'x', 'SELECT 1')",
        "UPDATE {s}.orders SET amount = 0",
        "SELECT 1 /* ; DROP TABLE {s}.orders */",
    ],
}


def test_writes_extra_statements_comments_and_risky_functions_are_refused(server):
    name, kind, schema, reader, _, admin = server
    connector = kind(HostPolicy(True))
    for query in HOSTILE["sqlserver" if name == "sqlserver" else "mysql"]:
        with pytest.raises(IngestionError) as refused:
            connector.preview(session(reader), "query/" + query.format(s=schema))
        assert refused.value.code == "connector_query_refused", query
    if name != "sqlserver":
        quoted = connector.preview(
            session(reader), f"query/SELECT 'a\\' ; DELETE FROM {schema}.orders; -- ' AS v"
        )
        assert quoted["rows"] == [[f"a' ; DELETE FROM {schema}.orders; -- "]]
    for blank in ("query/", "query/  ;  "):
        with pytest.raises(IngestionError):
            connector.preview(session(reader), blank)
    for bad in (f"table/{schema}/orders; DROP TABLE x", f"table/{schema}/missing", "orders"):
        with pytest.raises(ConnectorApiError) as unknown:
            connector.preview(session(reader), bad)
        assert unknown.value.status == 404
    with admin.connect() as connection:
        counted = connection.exec_driver_sql(
            f"SELECT COUNT(*) FROM {reader['database']}.{schema}.orders"
            if name == "sqlserver"
            else f"SELECT COUNT(*) FROM `{reader['database']}`.orders"
        ).scalar_one()
    assert counted == 3


def test_sessions_are_read_only_even_for_accounts_that_could_write(server):
    name, kind, schema, reader, owner, admin = server
    connector = kind(HostPolicy(True))
    table = f"{schema}.orders"
    if name == "sqlserver":
        with pytest.raises(ConnectorApiError) as refused:
            connector.validate(owner)
        assert refused.value.code == "not_read_only"
        with connector._connection(owner) as connection:
            connection.exec_driver_sql(f"DELETE FROM {table}")
            assert connection.exec_driver_sql(f"SELECT COUNT(*) FROM {table}").scalar() == 0
        with connector._connection(reader) as connection, pytest.raises(DBAPIError):
            connection.exec_driver_sql(f"DELETE FROM {table}")
    else:
        assert connector.validate(owner)
        guarded = connector._engine(owner)
        try:
            with guarded.connect() as connection:
                for statement in (
                    f"INSERT INTO {table} (id) VALUES (99)",
                    f"DELETE FROM {table}",
                    f"CREATE TABLE {schema}.evil (id INT)",
                    f"DROP TABLE {table}",
                ):
                    with pytest.raises(DBAPIError):
                        connection.exec_driver_sql(statement)
                    connection.rollback()
        finally:
            guarded.dispose()
    with admin.connect() as connection:
        counted = connection.exec_driver_sql(
            f"SELECT COUNT(*) FROM {reader['database']}.{schema}.orders"
            if name == "sqlserver"
            else f"SELECT COUNT(*) FROM `{reader['database']}`.orders"
        ).scalar_one()
    assert counted == 3


def test_a_300k_row_table_streams_to_a_file_in_batches_with_bounded_memory(server):
    _, kind, schema, reader, _, _ = server
    connector = kind(HostPolicy(True))
    with tempfile.TemporaryFile() as target:
        tracemalloc.start()
        try:
            count = connector.export(
                session(reader),
                f"table/{schema}/big",
                target,
                max_rows=1_000_000,
                max_bytes=200 * 1024 * 1024,
            )
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        size = target.tell()
        target.seek(0)
        reader_rows = csv.reader(io.TextIOWrapper(target, encoding="utf-8"))
        assert next(reader_rows) == ["id", "amount", "label"]
        total, lines = Decimal(0), 0
        for row in reader_rows:
            total += Decimal(row[1])
            lines += 1
    assert count == lines == BIG_ROWS
    assert total == sum(Decimal(i) / 100 for i in range(1, BIG_ROWS + 1))
    assert peak < 32 * 1024 * 1024 and size > 5 * 1024 * 1024
