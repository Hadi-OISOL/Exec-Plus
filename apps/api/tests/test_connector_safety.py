"""Use case: Proves every platform adapter only reads, stays off unless set up and fails clearly.

What it does: Records each mock-platform request, checks scopes, settings gating and error mapping.
"""

import json

import httpx
import pytest
from cryptography.fernet import Fernet

from execplus.application.connector_ports import ConnectorApiError, ConnectorSession
from execplus.application.services.connectors import ConnectorService
from execplus.bootstrap import build_connectors
from execplus.config import Settings
from execplus.domain.connectors import KNOWN_PLATFORMS, RecordBuffer, unconfigured_platforms
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.connectors import zoho
from execplus.infrastructure.connectors.base import HostPolicy
from execplus.infrastructure.connectors.bigquery import SCOPES as BIGQUERY_SCOPES
from execplus.infrastructure.connectors.bigquery import BigQueryConnector
from execplus.infrastructure.connectors.database import MySqlConnector
from execplus.infrastructure.connectors.odoo import OdooConnector
from execplus.infrastructure.connectors.quickbooks import QuickBooksConnector
from execplus.infrastructure.connectors.xero import XeroConnector
from execplus.infrastructure.connectors.zoho import ZohoBooksConnector
from test_connectors_logic import (
    CREDENTIALS,
    OdooServer,
    bigquery_handler,
    client,
    intuit_handler,
    query_of,
    xero_handler,
    zoho_handler,
)

TOKEN_HOSTS = {"oauth.platform.intuit.com", "identity.xero.com", "oauth.example"}
KEY = Fernet.generate_key().decode()


def data_requests(seen):
    return [
        item
        for item in seen
        if item.url.host not in TOKEN_HOSTS and not item.url.host.startswith("accounts.zoho")
    ]


def test_quickbooks_only_runs_select_queries_with_get():
    seen = []
    rows = [{"Id": str(index)} for index in range(30)]
    qb = QuickBooksConnector("c", "s", client=client(intuit_handler(rows, seen)))
    tokens = qb.exchange_code("code", "http://api/cb", "", {"realmId": "1"})
    qb.fetch(ConnectorSession(tokens.access_token, tokens.context), "Invoice", 100)
    reads = data_requests(seen)
    assert reads and {item.method for item in reads} == {"GET"}
    queries = [query_of(item)["query"] for item in reads if item.url.path.endswith("/query")]
    assert queries and all(query.startswith("select * from Invoice ") for query in queries)


def test_xero_reads_with_get_and_its_default_scopes_are_read_only():
    seen = []
    xero = XeroConnector("c", "s", "x", client(xero_handler({1: [{"InvoiceID": "1"}]}, seen)))
    tokens = xero.exchange_code("code", "u", "v", {})
    xero.fetch(ConnectorSession("tok", tokens.context), "Invoices", 100)
    assert {item.method for item in data_requests(seen)} == {"GET"}
    scopes = Settings(_env_file=None).xero_scopes.split()
    assert all(scope == "offline_access" or scope.endswith(".read") for scope in scopes)


def test_zoho_reads_with_get_and_asks_only_for_read_scopes():
    seen = []
    books = ZohoBooksConnector("c", "s", "com", client(zoho_handler(seen)))
    tokens = books.exchange_code("code", "u", "", {})
    books.fetch(ConnectorSession("tok", tokens.context), "invoices", 100)
    assert {item.method for item in data_requests(seen)} == {"GET"}
    assert all(scope.endswith(".READ") for scope in zoho.SCOPES.split(","))


def test_bigquery_copies_through_table_reads_and_never_runs_a_query_job():
    seen = []
    bq = BigQueryConnector(
        "c",
        "s",
        "https://a",
        "https://oauth.example/token",
        "https://oauth.example/revoke",
        client(bigquery_handler(seen)),
    )
    bq.fetch(ConnectorSession("tok"), "t/acme-prod/sales/orders", 10)
    reads = data_requests(seen)
    assert reads and {item.method for item in reads} == {"GET"}
    assert not [item for item in reads if "/queries" in item.url.path or "/jobs" in item.url.path]
    assert [scope for scope in BIGQUERY_SCOPES if "bigquery" in scope] == [
        "https://www.googleapis.com/auth/bigquery.readonly"
    ]


def test_odoo_only_calls_login_field_listing_and_search_read():
    server = OdooServer()
    methods = []

    def handler(request):
        params = json.loads(request.content)["params"]
        if params["service"] == "object":
            methods.append(params["args"][4])
        return server.handler(request)

    odoo = OdooConnector(HostPolicy(True), client(handler))
    odoo.validate(CREDENTIALS)
    odoo.fetch(ConnectorSession("", CREDENTIALS), "invoices", 50)
    assert set(server.calls) == {("common", "authenticate"), ("object", "execute_kw")}
    assert set(methods) == {"fields_get", "search_read"}


def test_no_platform_is_built_without_its_settings():
    assert build_connectors(Settings(_env_file=None)) == {}
    assert Settings(_env_file=None).enabled_connectors == ()


def test_each_platform_is_built_only_from_its_own_settings():
    google = dict(google_client_id="g", google_client_secret="gs")
    cases = {
        "quickbooks": dict(quickbooks_client_id="q", quickbooks_client_secret="qs"),
        "xero": dict(xero_client_id="x", xero_client_secret="xs"),
        "zoho_books": dict(zoho_client_id="z", zoho_client_secret="zs"),
        "odoo": dict(odoo_enabled=True),
        "postgresql": dict(database_connector_enabled=True),
        "mysql": dict(mysql_connector_enabled=True),
        "sqlserver": dict(mssql_connector_enabled=True),
        "bigquery": dict(bigquery_enabled=True, **google),
    }
    for platform, values in cases.items():
        settings = Settings(_env_file=None, token_encryption_key=KEY, **values)
        assert list(build_connectors(settings)) == [platform]
        assert settings.enabled_connectors == (platform,)


@pytest.mark.parametrize(
    "values",
    [
        dict(quickbooks_client_id="q"),
        dict(xero_client_secret="xs"),
        dict(zoho_client_id="z"),
        dict(bigquery_enabled=True),
        dict(odoo_enabled=True, token_encryption_key=""),
        dict(database_connector_enabled=True, token_encryption_key="not-a-fernet-key"),
        dict(mysql_connector_enabled=True, token_encryption_key=""),
        dict(mssql_connector_enabled=True, token_encryption_key="not-a-fernet-key"),
    ],
)
def test_half_configured_platforms_refuse_to_start(values):
    with pytest.raises(ValueError):
        Settings(_env_file=None, **{"token_encryption_key": KEY, **values})


def test_unconfigured_platforms_are_listed_without_any_connect_form():
    listed = unconfigured_platforms(["xero", "odoo"])
    assert [item["id"] for item in listed] == [
        platform for platform, _ in KNOWN_PLATFORMS if platform not in {"xero", "odoo"}
    ]
    assert all(
        item["configured"] is False and item["fields"] == [] and item["kind"] == "unavailable"
        for item in listed
    )
    assert unconfigured_platforms(platform for platform, _ in KNOWN_PLATFORMS) == []


@pytest.mark.parametrize(
    ("status", "code", "expected", "http"),
    [
        (401, "", "connector_credentials_rejected", 422),
        (400, "invalid_grant", "connector_credentials_rejected", 422),
        (400, "other", "connector_invalid_request", 422),
        (403, "", "connector_forbidden", 403),
        (404, "", "connector_source_unavailable", 404),
        (422, "", "connector_invalid_request", 422),
        (429, "", "connector_rate_limited", 429),
        (502, "", "connector_unexpected_response", 502),
        (500, "", "connector_unavailable", 503),
        (503, "", "connector_unavailable", 503),
        (422, "control_plane_database", "connector_host_blocked", 422),
        (403, "not_read_only", "connector_not_read_only", 403),
        (422, "tls_unavailable", "connector_tls_unavailable", 422),
        (422, "tls_unverified", "connector_tls_unverified", 422),
    ],
)
def test_platform_failures_map_to_stable_user_errors(status, code, expected, http):
    failure = ConnectorService._failure(ConnectorApiError(status, code))
    assert (failure.code, failure.status) == (expected, http)


def test_malformed_platform_rows_are_refused_as_unexpected_replies():
    with pytest.raises(IngestionError) as refused:
        RecordBuffer().extend(["not a record"])  # type: ignore[list-item]
    assert (refused.value.code, refused.value.status) == ("connector_unexpected_response", 502)
    shapeless = QuickBooksConnector(
        "c",
        "s",
        client=client(lambda request: httpx.Response(200, json={"QueryResponse": []})),
    )
    service = object.__new__(ConnectorService)
    with pytest.raises(IngestionError) as wrapped:
        service._call(
            lambda: shapeless.fetch(ConnectorSession("t", {"realm_id": "1"}), "Invoice", 5)
        )
    assert wrapped.value.code == "connector_unexpected_response"


def test_mysql_tls_choices_never_downgrade_a_required_encryption():
    trusted, strict = MySqlConnector(HostPolicy(True)), MySqlConnector(HostPolicy(False))
    assert trusted._connect_args("off")["ssl_disabled"] is True
    preferred = trusted._connect_args("")
    assert "ssl" not in preferred and "ssl_disabled" not in preferred
    for connector, mode in ((trusted, "require"), (trusted, "verify"), (strict, "")):
        assert "ssl" in connector._connect_args(mode)
    assert trusted._connect_args("verify")["ssl"].check_hostname is True
    assert "caching_sha2_password" in trusted._connect_args("off")["auth_plugin_map"]


def test_mysql_driver_tls_failures_become_clear_connector_errors():
    import pymysql
    from sqlalchemy.exc import OperationalError

    def wrapped(reason):
        return OperationalError("connect", {}, reason)

    connector = MySqlConnector(HostPolicy(True))
    missing = wrapped(pymysql.err.OperationalError(2026, "SSL is required"))
    assert connector._refusal(missing).code == "tls_unavailable"
    unverified = wrapped(pymysql.err.OperationalError(2003, "[SSL: CERTIFICATE_VERIFY_FAILED]"))
    assert connector._refusal(unverified).code == "tls_unverified"
    assert connector._refusal(wrapped(pymysql.err.OperationalError(1045, "denied"))) is None
