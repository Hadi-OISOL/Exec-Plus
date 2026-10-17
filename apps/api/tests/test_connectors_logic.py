"""Use case: Proves the shared connector rules and every platform adapter offline.

What it does: Drives each adapter through a mock transport shaped like its documented API.
"""

import base64
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import parse_qs
from uuid import UUID

import httpx
import pytest

from execplus.application.connector_ports import ConnectorApiError, ConnectorSession
from execplus.domain.connectors import (
    connector_filename,
    flatten,
    records_to_csv,
    scalar,
    valid_provider,
)
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.connectors.base import HostPolicy, json_body
from execplus.infrastructure.connectors.bigquery import BigQueryConnector
from execplus.infrastructure.connectors.odoo import OdooConnector
from execplus.infrastructure.connectors.quickbooks import QuickBooksConnector
from execplus.infrastructure.connectors.xero import XeroConnector
from execplus.infrastructure.connectors.zoho import ZohoBooksConnector


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_provider_json_amounts_keep_their_decimal_digits_in_imports():
    response = httpx.Response(200, content=b'{"amount":9007199254740993.123456789012}')
    content = records_to_csv([json_body(response)])
    assert content == b"amount\n9007199254740993.123456789012\n"


@pytest.mark.parametrize(
    "records",
    [
        [{"customer_name": "first", "customer": {"name": "second"}}],
        [{"customer": {"name": "first"}, "customer_name": "second"}],
        [{"customer_name": "first"}, {"customer": {"name": "second"}}],
        [{"lines_count": 7, "lines": [{"value": 1}]}],
        [{"lines": [{"value": 1}]}, {"lines_count": 7}],
    ],
)
def test_ambiguous_flattened_and_generated_columns_are_refused(records):
    with pytest.raises(IngestionError) as caught:
        records_to_csv(records)
    assert caught.value.code == "ambiguous_source_columns"


def query_of(request):
    return {key: value[0] for key, value in parse_qs(request.url.query.decode()).items()}


def form_of(request):
    return {key: value[0] for key, value in parse_qs(request.content.decode()).items()}


def test_values_are_flattened_with_clear_names_and_no_lost_totals():
    record = {
        "Id": 7,
        "Total": Decimal("12.50"),
        "Paid": True,
        "Gone": None,
        "Customer": {"Ref": {"value": "9", "name": "Ali"}},
        "Tags": ["a", "b"],
        "Lines": [{"x": 1}, {"x": 2}],
        "When": datetime(2026, 1, 3, 4, 5, tzinfo=timezone.utc),
        "Key": UUID("12345678-1234-5678-1234-567812345678"),
        "Deep": {"a": {"b": {"c": {"d": 1}}}},
    }
    flat = flatten(record)
    assert flat["Customer_Ref_name"] == "Ali" and flat["Tags"] == "a; b"
    assert flat["Lines_count"] == "2" and "Lines" not in flat
    assert flat["Total"] == "12.50" and flat["Paid"] == "true" and flat["Gone"] == ""
    assert flat["When"] == "2026-01-03T04:05:00+00:00"
    assert flat["Key"] == "12345678-1234-5678-1234-567812345678"
    assert json.loads(flat["Deep_a_b_c"]) == {"d": 1}


def test_xero_dates_become_iso_dates_or_timestamps():
    midnight = int(datetime(2026, 1, 3, tzinfo=timezone.utc).timestamp() * 1000)
    afternoon = midnight + 15 * 3600 * 1000
    assert scalar(f"/Date({midnight}+0000)/") == "2026-01-03"
    assert scalar(f"/Date({afternoon})/") == "2026-01-03T15:00:00+00:00"
    assert scalar("/Date(not-a-date)/") == "/Date(not-a-date)/"


def test_records_become_csv_with_all_columns_and_refuse_empty_or_huge_sets():
    rows = [{"a": 1, "b": {"c": 2}}, {"a": 3, "d": "x"}]
    assert records_to_csv(rows).decode().splitlines() == ["a,b_c,d", "1,2,", "3,,x"]
    with pytest.raises(IngestionError) as empty:
        records_to_csv([])
    assert empty.value.code == "empty_source"
    with pytest.raises(IngestionError) as wide:
        records_to_csv([{str(index): "1" for index in range(501)}])
    assert wide.value.code == "source_too_large"


def test_provider_ids_and_filenames_are_safe():
    assert valid_provider("zoho_books") == "zoho_books"
    for bad in ("", "Zoho", "../x", "a b", "1abc"):
        with pytest.raises(IngestionError):
            valid_provider(bad)
    name = connector_filename("Odoo", "db/one\\two", "Sales\x00 orders")
    assert name.endswith(".csv") and not re.search(r"[\\/\x00]", name)
    assert len(connector_filename("x" * 300, "y" * 300, "z" * 300)) <= 100
    assert connector_filename("", "", "") == "Imported data.csv"


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.1.2.3", "192.168.0.5", "172.16.0.9", "169.254.169.254", "::1", "0.0.0.0"],
)
def test_private_network_hosts_are_blocked_unless_explicitly_allowed(address):
    with pytest.raises(IngestionError) as blocked:
        HostPolicy(False).check_host(address)
    assert blocked.value.code == "connector_host_blocked"
    HostPolicy(True).check_host(address)


def test_public_hosts_pass_and_urls_are_checked_for_scheme_and_credentials():
    HostPolicy(False).check_host("8.8.8.8")
    policy = HostPolicy(False)
    assert policy.check_url("https://8.8.8.8/odoo/") == "https://8.8.8.8/odoo"
    for bad in ("ftp://8.8.8.8", "http://8.8.8.8", "https://user:pw@8.8.8.8", "not a url", ""):
        with pytest.raises(IngestionError):
            policy.check_url(bad)
    assert HostPolicy(True).check_url("http://127.0.0.1:8069")


def intuit_handler(rows, seen):
    def handler(request):
        seen.append(request)
        path = request.url.path
        if path.endswith("/tokens/bearer"):
            return httpx.Response(
                200, json=dict(access_token="at", refresh_token="rt", expires_in=3600)
            )
        if "/companyinfo/" in path:
            return httpx.Response(200, json={"CompanyInfo": {"CompanyName": "Acme Ltd"}})
        match = re.search(r"STARTPOSITION (\d+) MAXRESULTS (\d+)", query_of(request)["query"])
        start, size = int(match.group(1)), int(match.group(2))
        return httpx.Response(
            200, json={"QueryResponse": {"Invoice": rows[start - 1 : start - 1 + size]}}
        )

    return handler


def test_quickbooks_exchange_requires_the_company_and_reads_its_name():
    seen = []
    qb = QuickBooksConnector("cid", "sec", client=client(intuit_handler([], seen)))
    url = qb.authorization_url(redirect_uri="http://api/cb", state="s", challenge="")
    assert url.startswith("https://appcenter.intuit.com/connect/oauth2?")
    assert "com.intuit.quickbooks.accounting" in url and "state=s" in url
    tokens = qb.exchange_code("code", "http://api/cb", "", {"realmId": "123145"})
    assert tokens.refresh_token == "rt"
    assert tokens.context == {"realm_id": "123145", "company_name": "Acme Ltd"}
    assert qb.account_name(tokens.context) == "Acme Ltd"
    basic = "Basic " + base64.b64encode(b"cid:sec").decode()
    assert seen[0].headers["authorization"] == basic
    with pytest.raises(ConnectorApiError) as missing:
        qb.exchange_code("code", "http://api/cb", "", {})
    assert missing.value.code == "missing_company"


def test_quickbooks_pages_through_results_and_rejects_unknown_entities():
    seen = []
    rows = [{"Id": str(index)} for index in range(2500)]
    qb = QuickBooksConnector("cid", "sec", "sandbox", client(intuit_handler(rows, seen)))
    session = ConnectorSession("tok", {"realm_id": "999"})
    records = qb.fetch(session, "Invoice", 100_000)
    assert len(records) == 2500
    queries = [query_of(item)["query"] for item in seen]
    assert queries[0].endswith("STARTPOSITION 1 MAXRESULTS 1000")
    assert queries[1].endswith("STARTPOSITION 1001 MAXRESULTS 1000")
    assert seen[0].url.host == "sandbox-quickbooks.api.intuit.com"
    assert seen[0].headers["authorization"] == "Bearer tok"
    assert len(qb.fetch(session, "Invoice", 30)) == 30
    with pytest.raises(ConnectorApiError):
        qb.fetch(session, "Invoice; drop table", 10)
    assert "Invoice" in [item.id for item in qb.sources(session, None)]


def test_quickbooks_refresh_keeps_the_company_and_surfaces_a_rotated_token():
    def handler(request):
        assert form_of(request)["grant_type"] == "refresh_token"
        return httpx.Response(200, json=dict(access_token="new", refresh_token="rt-2"))

    tokens = QuickBooksConnector("c", "s", client=client(handler)).refresh(
        "rt-1", {"realm_id": "5"}
    )
    assert (tokens.access_token, tokens.refresh_token, tokens.context) == (
        "new",
        "rt-2",
        {"realm_id": "5"},
    )


def xero_handler(pages, seen):
    def handler(request):
        seen.append(request)
        path = request.url.path
        if path == "/connect/token":
            return httpx.Response(
                200, json=dict(access_token="at", refresh_token="rt", expires_in=1800)
            )
        if path == "/connections":
            return httpx.Response(
                200, json=[{"tenantId": "t-1", "tenantName": "Demo Co"}, {"tenantId": "t-2"}]
            )
        name = path.rsplit("/", 1)[1]
        number = int(query_of(request).get("page", 1))
        return httpx.Response(200, json={name: pages.get(number, [])})

    return handler


def test_xero_uses_pkce_finds_the_organisation_and_pages_with_its_tenant_header():
    seen = []
    midnight = int(datetime(2026, 1, 3, tzinfo=timezone.utc).timestamp() * 1000)
    page_one = [
        {"InvoiceID": str(index), "Date": f"/Date({midnight}+0000)/"} for index in range(100)
    ]
    xero = XeroConnector(
        "cid",
        "sec",
        "offline_access accounting.transactions.read",
        client(xero_handler({1: page_one, 2: [{"InvoiceID": "last"}]}, seen)),
    )
    url = xero.authorization_url(redirect_uri="http://api/cb", state="s", challenge="chal")
    assert "code_challenge=chal" in url and "code_challenge_method=S256" in url and xero.uses_pkce
    tokens = xero.exchange_code("code", "http://api/cb", "verifier", {})
    assert tokens.context == {"tenant_id": "t-1", "tenant_name": "Demo Co"}
    assert form_of(seen[0])["code_verifier"] == "verifier"
    session = ConnectorSession("tok", tokens.context)
    records = xero.fetch(session, "Invoices", 1000)
    assert len(records) == 101
    fetches = [item for item in seen if item.url.path.endswith("/Invoices")]
    assert [query_of(item)["page"] for item in fetches] == ["1", "2"]
    assert fetches[0].headers["xero-tenant-id"] == "t-1"
    assert records_to_csv(records[:1]).decode().splitlines()[1].endswith("2026-01-03")


def test_xero_lists_without_paging_are_requested_once_and_denied_access_is_reported():
    seen = []
    xero = XeroConnector("c", "s", "x", client(xero_handler({1: [{"AccountID": "1"}]}, seen)))
    session = ConnectorSession("tok", {"tenant_id": "t"})
    assert len(xero.fetch(session, "Accounts", 1000)) == 1
    assert len([item for item in seen if item.url.path.endswith("/Accounts")]) == 1
    assert "page" not in query_of(seen[-1])

    def nobody(request):
        if request.url.path == "/connect/token":
            return httpx.Response(200, json=dict(access_token="at", refresh_token="rt"))
        return httpx.Response(200, json=[])

    with pytest.raises(ConnectorApiError) as none:
        XeroConnector("c", "s", "x", client(nobody)).exchange_code("code", "u", "v", {})
    assert none.value.code == "no_organisation"


def zoho_handler(seen):
    def handler(request):
        seen.append(request)
        path = request.url.path
        if path == "/oauth/v2/token":
            form = form_of(request)
            if form.get("code") == "bad":
                return httpx.Response(200, json={"error": "invalid_code"})
            return httpx.Response(
                200,
                json=dict(
                    access_token="at",
                    refresh_token="rt",
                    api_domain="https://www.zohoapis.eu",
                    expires_in=3600,
                ),
            )
        if path == "/books/v3/organizations":
            return httpx.Response(
                200,
                json={"code": 0, "organizations": [{"organization_id": "77", "name": "Zed Ltd"}]},
            )
        page = int(query_of(request)["page"])
        return httpx.Response(
            200,
            json={
                "code": 0,
                "invoices": [{"invoice_id": f"{page}-{n}"} for n in range(2)],
                "page_context": {"has_more_page": page < 3},
            },
        )

    return handler


def test_zoho_follows_the_data_centre_the_user_signed_in_on_and_pages_until_done():
    seen = []
    zoho = ZohoBooksConnector("cid", "sec", "com", client(zoho_handler(seen)))
    url = zoho.authorization_url(redirect_uri="http://api/cb", state="s", challenge="")
    assert (
        url.startswith("https://accounts.zoho.com/oauth/v2/auth?") and "access_type=offline" in url
    )
    assert "ZohoBooks.invoices.READ" in url
    tokens = zoho.exchange_code(
        "code", "http://api/cb", "", {"accounts-server": "https://accounts.zoho.eu"}
    )
    assert seen[0].url.host == "accounts.zoho.eu"
    assert tokens.context["api_domain"] == "https://www.zohoapis.eu"
    assert (
        tokens.context["organization_id"] == "77" and zoho.account_name(tokens.context) == "Zed Ltd"
    )
    records = zoho.fetch(ConnectorSession("tok", tokens.context), "invoices", 1000)
    assert len(records) == 6
    pages = [query_of(item) for item in seen if item.url.path == "/books/v3/invoices"]
    assert [item["page"] for item in pages] == ["1", "2", "3"] and pages[0][
        "organization_id"
    ] == "77"
    last = next(item for item in seen if item.url.path == "/books/v3/invoices")
    assert last.headers["authorization"] == "Zoho-oauthtoken tok"


def test_zoho_ignores_untrusted_hosts_and_reports_errors_returned_with_a_200():
    seen = []
    zoho = ZohoBooksConnector("c", "s", "com", client(zoho_handler(seen)))
    zoho.exchange_code("code", "u", "", {"accounts-server": "https://evil.example"})
    assert seen[0].url.host == "accounts.zoho.com"
    with pytest.raises(ConnectorApiError) as rejected:
        zoho.exchange_code("bad", "u", "", {})
    assert rejected.value.code == "invalid_code"
    with pytest.raises(ConnectorApiError):
        zoho.fetch(
            ConnectorSession("t", {"api_domain": "https://evil.example", "organization_id": "1"}),
            "invoices",
            5,
        )
    with pytest.raises(ConnectorApiError):
        zoho.fetch(
            ConnectorSession("t", {"api_domain": "https://www.zohoapis.com"}), "../secrets", 5
        )


class OdooServer:
    def __init__(self, uid=7, models=None):
        self.uid, self.calls = uid, []
        self.models = (
            models
            if models is not None
            else {
                "account.move": {
                    "fields": {
                        "name": "char",
                        "partner_id": "many2one",
                        "amount_total": "float",
                        "ref": "char",
                        "invoice_date": "date",
                    },
                    "rows": [
                        {
                            "id": index,
                            "name": f"INV/{index}",
                            "partner_id": [index, f"Client {index}"] if index % 2 else False,
                            "amount_total": 10.5,
                            "ref": False,
                            "invoice_date": "2026-01-03",
                        }
                        for index in range(1, 1201)
                    ],
                }
            }
        )

    def handler(self, request):
        body = json.loads(request.content)
        params = body["params"]
        self.calls.append((params["service"], params["method"]))
        if params["service"] == "common":
            return httpx.Response(200, json={"result": self.uid})
        _, _, _, model, method, _, kwargs = params["args"]
        if model not in self.models:
            return httpx.Response(200, json={"error": {"data": {"name": "builtins.KeyError"}}})
        if method == "fields_get":
            return httpx.Response(
                200,
                json={
                    "result": {
                        name: {"type": kind} for name, kind in self.models[model]["fields"].items()
                    }
                },
            )
        assert set(kwargs["fields"]) <= set(self.models[model]["fields"])
        rows = self.models[model]["rows"][kwargs["offset"] : kwargs["offset"] + kwargs["limit"]]
        return httpx.Response(
            200,
            json={
                "result": [
                    {
                        key: value
                        for key, value in row.items()
                        if key in kwargs["fields"] or key == "id"
                    }
                    for row in rows
                ]
            },
        )


CREDENTIALS = {
    "url": "http://localhost:8069",
    "database": "prod",
    "login": "a@b.test",
    "api_key": "k",
}


def test_odoo_validates_logins_and_blocks_private_servers_when_not_allowed():
    server = OdooServer()
    odoo = OdooConnector(HostPolicy(True), client(server.handler))
    assert odoo.validate(CREDENTIALS) == "localhost / prod"
    with pytest.raises(ConnectorApiError) as rejected:
        OdooConnector(HostPolicy(True), client(OdooServer(uid=False).handler)).validate(CREDENTIALS)
    assert rejected.value.status == 401
    with pytest.raises(IngestionError) as blocked:
        OdooConnector(HostPolicy(False), client(server.handler)).validate(CREDENTIALS)
    assert blocked.value.code in {"connector_host_blocked", "connector_host_invalid"}
    with pytest.raises(ConnectorApiError):
        odoo.validate({**CREDENTIALS, "api_key": ""})


def test_odoo_pages_and_turns_relations_into_ids_and_names_without_false_values():
    server = OdooServer()
    odoo = OdooConnector(HostPolicy(True), client(server.handler))
    records = odoo.fetch(ConnectorSession("", CREDENTIALS), "invoices", 5000)
    assert len(records) == 1200
    first, second = records[0], records[1]
    assert (first["partner_id_id"], first["partner_id_name"]) == (1, "Client 1")
    assert second["partner_id_id"] is None and second["ref"] is None
    assert first["invoice_date"] == "2026-01-03" and "move_type" not in first
    assert [call for call in server.calls if call == ("object", "execute_kw")]
    assert len(odoo.fetch(ConnectorSession("", CREDENTIALS), "invoices", 20)) == 20


def test_odoo_reports_apps_that_are_not_installed_and_unknown_sources():
    odoo = OdooConnector(HostPolicy(True), client(OdooServer(models={}).handler))
    with pytest.raises(ConnectorApiError) as missing:
        odoo.fetch(ConnectorSession("", CREDENTIALS), "sales_orders", 10)
    assert missing.value.status == 404
    with pytest.raises(ConnectorApiError):
        odoo.fetch(ConnectorSession("", CREDENTIALS), "res.users", 10)
    assert "invoices" in [item.id for item in odoo.sources(ConnectorSession(), None)]


def bigquery_handler(seen):
    def handler(request):
        seen.append(request)
        path = request.url.path
        if request.url.host == "oauth.example":
            return httpx.Response(
                200,
                json=dict(
                    access_token="at",
                    refresh_token="rt",
                    expires_in=3600,
                    scope="openid email https://www.googleapis.com/auth/bigquery.readonly",
                    id_token="h."
                    + base64.urlsafe_b64encode(json.dumps({"email": "me@example.test"}).encode())
                    .decode()
                    .rstrip("=")
                    + ".s",
                ),
            )
        if path == "/bigquery/v2/projects":
            return httpx.Response(
                200, json={"projects": [{"id": "acme-prod", "friendlyName": "Acme"}]}
            )
        if path.endswith("/datasets"):
            return httpx.Response(
                200, json={"datasets": [{"datasetReference": {"datasetId": "sales"}}]}
            )
        if path.endswith("/tables"):
            return httpx.Response(
                200,
                json={
                    "tables": [
                        {"tableReference": {"tableId": "orders"}, "type": "TABLE"},
                        {"tableReference": {"tableId": "v_orders"}, "type": "VIEW"},
                    ]
                },
            )
        if path.endswith("/data"):
            token = query_of(request).get("pageToken")
            row = {
                "f": [
                    {"v": "1"},
                    {"v": "1.7672256E9"},
                    {"v": {"f": [{"v": "Karachi"}]}},
                    {"v": [{"v": "x"}, {"v": "y"}]},
                    {"v": "AAEC"},
                ]
            }
            return httpx.Response(
                200, json={"rows": [row], **({} if token else {"pageToken": "next"})}
            )
        return httpx.Response(
            200,
            json={
                "schema": {
                    "fields": [
                        {"name": "id", "type": "INTEGER"},
                        {"name": "placed", "type": "TIMESTAMP"},
                        {
                            "name": "address",
                            "type": "RECORD",
                            "fields": [{"name": "city", "type": "STRING"}],
                        },
                        {"name": "tags", "type": "STRING", "mode": "REPEATED"},
                        {"name": "blob", "type": "BYTES"},
                    ]
                }
            },
        )

    return handler


def test_bigquery_browses_projects_datasets_and_tables_and_skips_views():
    seen = []
    bq = BigQueryConnector(
        "cid",
        "sec",
        "https://accounts.example/auth",
        "https://oauth.example/token",
        "https://oauth.example/revoke",
        client(bigquery_handler(seen)),
    )
    session = ConnectorSession("tok")
    project = bq.sources(session, None)[0]
    assert project.container and project.label == "Acme"
    dataset = bq.sources(session, project.id)[0]
    assert dataset.container and dataset.label == "sales"
    tables = bq.sources(session, dataset.id)
    assert [item.label for item in tables] == ["orders"] and not tables[0].container
    assert seen[0].headers["authorization"] == "Bearer tok"
    with pytest.raises(ConnectorApiError):
        bq.sources(session, "x/unknown")


def test_bigquery_copies_a_table_converting_timestamps_records_lists_and_binary():
    seen = []
    bq = BigQueryConnector(
        "c",
        "s",
        "https://a",
        "https://oauth.example/token",
        "https://oauth.example/revoke",
        client(bigquery_handler(seen)),
    )
    records = bq.fetch(ConnectorSession("tok"), "t/acme-prod/sales/orders", 10)
    assert len(records) == 2
    first = records[0]
    assert first["placed"] == "2026-01-01T00:00:00+00:00"
    assert (
        first["address"] == {"city": "Karachi"}
        and first["tags"] == ["x", "y"]
        and first["blob"] == "(binary)"
    )
    csv_text = records_to_csv(records).decode().splitlines()
    assert csv_text[0] == "id,placed,address_city,tags,blob" and csv_text[1].endswith(
        "x; y,(binary)"
    )
    pages = [query_of(item) for item in seen if item.url.path.endswith("/data")]
    assert "pageToken" not in pages[0] and pages[1]["pageToken"] == "next"
    assert len(bq.fetch(ConnectorSession("tok"), "t/acme-prod/sales/orders", 1)) == 1
    with pytest.raises(ConnectorApiError):
        bq.fetch(ConnectorSession("tok"), "p/acme-prod", 10)


def test_bigquery_exchange_needs_the_bigquery_permission_and_reads_the_account_email():
    seen = []
    bq = BigQueryConnector(
        "c",
        "s",
        "https://accounts.example/auth",
        "https://oauth.example/token",
        "https://oauth.example/revoke",
        client(bigquery_handler(seen)),
    )
    url = bq.authorization_url(redirect_uri="http://api/cb", state="s", challenge="chal")
    assert (
        "bigquery.readonly" in url and "code_challenge=chal" in url and "access_type=offline" in url
    )
    tokens = bq.exchange_code("code", "http://api/cb", "verifier", {})
    assert (
        tokens.context == {"account": "me@example.test"}
        and bq.account_name(tokens.context) == "me@example.test"
    )
    narrow = BigQueryConnector(
        "c",
        "s",
        "https://a",
        "https://oauth.example/token",
        "https://r",
        client(
            lambda request: httpx.Response(
                200, json=dict(access_token="a", refresh_token="r", scope="openid email")
            )
        ),
    )
    with pytest.raises(ConnectorApiError) as missing:
        narrow.exchange_code("code", "u", "v", {})
    assert missing.value.code == "scope_missing"


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500])
def test_platform_errors_keep_their_status(status):
    failing = client(lambda request: httpx.Response(status, json={"error": "x"}))
    with pytest.raises(ConnectorApiError) as error:
        QuickBooksConnector("c", "s", client=failing).fetch(
            ConnectorSession("t", {"realm_id": "1"}), "Invoice", 5
        )
    assert error.value.status == status


def test_network_failures_become_service_unavailable():
    def handler(request):
        raise httpx.ConnectError("down")

    with pytest.raises(ConnectorApiError) as error:
        XeroConnector("c", "s", "x", client(handler)).refresh("rt", {})
    assert error.value.status == 503
