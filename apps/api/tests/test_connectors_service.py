"""Use case: Proves connecting a platform and importing a source through the real API.

What it does: Drives the routes with stand-in connectors and checks secrets, isolation and errors.
"""

import json
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text

from execplus.application.connector_ports import (
    ConnectorApiError,
    ConnectorField,
    ConnectorSession,
    ProviderTokens,
)
from execplus.application.services.connectors import ConnectorService
from execplus.domain.connectors import Source
from execplus.infrastructure.persistence.connector_connections import SqlConnectorConnections
from execplus.infrastructure.persistence.repository import SQLUnitOfWork
from execplus.infrastructure.token_vault import FernetTokenVault
from test_workspace_integration import dataset, identity, workspace

WEB = "http://web.test"
ROWS = [
    {"Id": "1", "Total": 10.5, "Customer": {"name": "Ali"}, "Lines": [{"q": 1}]},
    {"Id": "2", "Total": 20, "Customer": {"name": "Sara"}, "Lines": []},
]


class StandInOAuth:
    id = "quickbooks"
    label = "QuickBooks Online"
    kind = "oauth"
    uses_pkce = True
    description = "Stand-in"
    fields: tuple[ConnectorField, ...] = ()

    def __init__(self):
        self.revoked, self.refreshed, self.fetched = [], [], []
        self.exchange_error = self.refresh_error = self.fetch_error = None
        self.rotate = False
        self.rows = ROWS
        self.verifier = ""

    def authorization_url(self, *, redirect_uri, state, challenge):
        return (
            f"https://platform.example/auth?redirect_uri={redirect_uri}&state={state}&c={challenge}"
        )

    def exchange_code(self, code, redirect_uri, verifier, callback):
        if self.exchange_error:
            raise self.exchange_error
        self.verifier = verifier
        refresh = None if code == "no-refresh" else "refresh-1"
        return ProviderTokens("access-1", refresh, 3600, {"realm_id": callback.get("realmId", "9")})

    def refresh(self, refresh_token, context):
        if self.refresh_error:
            raise self.refresh_error
        self.refreshed.append(refresh_token)
        return ProviderTokens("access-2", "refresh-2" if self.rotate else None, 3600, context)

    def revoke(self, refresh_token):
        self.revoked.append(refresh_token)

    def account_name(self, context):
        return f"Company {context['realm_id']}"

    def sources(self, session, parent):
        return [Source("Invoice", "Invoices")] if parent is None else []

    def fetch(self, session, source_id, max_rows):
        if self.fetch_error:
            raise self.fetch_error
        self.fetched.append((session.access_token, source_id, max_rows))
        return self.rows


class StandInCredentials:
    id = "odoo"
    label = "Odoo"
    kind = "credentials"
    description = "Stand-in"
    fields = (
        ConnectorField("url", "Address"),
        ConnectorField("api_key", "API key", secret=True),
    )

    def __init__(self):
        self.validated, self.sessions = [], []
        self.error = None

    def validate(self, credentials):
        if self.error:
            raise self.error
        self.validated.append(credentials)
        return "odoo.example / prod"

    def sources(self, session, parent):
        self.sessions.append(session)
        return [Source("invoices", "Customer invoices")]

    def fetch(self, session, source_id, max_rows):
        self.sessions.append(session)
        return ROWS


def enable(env, **extra):
    oauth, credentials = StandInOAuth(), StandInCredentials()
    vault = FernetTokenVault(Fernet.generate_key().decode())
    env.runtime.connectors = ConnectorService(
        {"quickbooks": oauth, "odoo": credentials},
        vault,
        SqlConnectorConnections(env.engine),
        env.runtime.service,
        SQLUnitOfWork(env.engine),
        public_api_url="http://api.test",
        web_origin=WEB,
        max_rows=extra.get("max_rows", 1000),
    )
    return oauth, credentials, vault


def connect_oauth(env, headers, **callback):
    started = env.client.post("/connectors/quickbooks/connect", headers=headers)
    assert started.status_code == 200, started.text
    state = parse_qs(urlparse(started.json()["url"]).query)["state"][0]
    params = dict(code="code-1", state=state, **callback)
    return env.client.get("/connectors/quickbooks/callback", params=params, follow_redirects=False)


def stored(env, user_id, provider):
    with env.engine.connect() as connection:
        return connection.execute(
            text(
                "SELECT sealed_credentials FROM connector_connections "
                "WHERE user_id=:u AND provider=:p"
            ),
            dict(u=user_id, p=provider),
        ).scalar_one_or_none()


def test_no_connectors_means_an_empty_catalog_and_clear_errors(integration):
    owner, _ = identity(integration, "none@example.test")
    assert integration.client.get("/connectors", headers=owner).json() == []
    missing = integration.client.post("/connectors/quickbooks/connect", headers=owner)
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "unknown_connector"
    assert integration.client.get("/connectors").status_code == 401


def test_the_catalog_lists_each_platform_with_its_form_and_the_callers_connections(integration):
    enable(integration)
    owner, _ = identity(integration, "catalog@example.test")
    catalog = {
        item["id"]: item for item in integration.client.get("/connectors", headers=owner).json()
    }
    assert set(catalog) == {"quickbooks", "odoo"}
    assert catalog["odoo"]["kind"] == "credentials" and catalog["quickbooks"]["kind"] == "oauth"
    assert [item["name"] for item in catalog["odoo"]["fields"]] == ["url", "api_key"]
    assert catalog["odoo"]["fields"][1]["secret"] is True
    assert catalog["quickbooks"]["connected"] is False and catalog["quickbooks"]["account"] == ""


def test_unknown_or_malformed_platform_names_are_refused(integration):
    enable(integration)
    owner, _ = identity(integration, "unknown@example.test")
    for name in ("nonsense", "QuickBooks", "a-b", "1x"):
        response = integration.client.post(f"/connectors/{name}/connect", headers=owner)
        assert response.status_code == 404
    wrong_kind = integration.client.post("/connectors/odoo/connect", headers=owner)
    assert wrong_kind.status_code == 404
    also_wrong = integration.client.post(
        "/connectors/quickbooks/credentials", headers=owner, json={"values": {"a": "b"}}
    )
    assert also_wrong.status_code == 404


def test_oauth_connect_redirects_stores_sealed_secrets_and_never_in_plaintext(integration):
    oauth, _, vault = enable(integration)
    owner, user = identity(integration, "oauth@example.test")
    started = integration.client.post("/connectors/quickbooks/connect", headers=owner).json()["url"]
    query = parse_qs(urlparse(started).query)
    assert query["redirect_uri"] == ["http://api.test/connectors/quickbooks/callback"]
    assert query["c"][0]
    callback = connect_oauth(integration, owner, realmId="4620816365")
    assert callback.headers["location"] == f"{WEB}/workspace?connector_connected=quickbooks"
    sealed = stored(integration, user.id, "quickbooks")
    assert "refresh-1" not in sealed and "4620816365" not in sealed
    assert json.loads(vault.unseal(sealed)) == dict(
        refresh_token="refresh-1", context={"realm_id": "4620816365"}
    )
    assert oauth.verifier
    status = integration.client.get("/connectors/quickbooks/status", headers=owner).json()
    assert status == dict(connected=True, account="Company 4620816365")
    catalog = integration.client.get("/connectors", headers=owner).json()
    assert next(item for item in catalog if item["id"] == "quickbooks")["connected"] is True


def test_callbacks_need_a_valid_unexpired_state_for_the_same_platform(integration):
    enable(integration)
    owner, _ = identity(integration, "state@example.test")
    forged = integration.client.get(
        "/connectors/quickbooks/callback",
        params=dict(code="c", state="forged"),
        follow_redirects=False,
    )
    assert forged.headers["location"].endswith(
        "connector_error=connector_state_invalid&connector=quickbooks"
    )
    started = integration.client.post("/connectors/quickbooks/connect", headers=owner).json()["url"]
    state = parse_qs(urlparse(started).query)["state"][0]
    other_vault = integration.runtime.connectors.vault
    assert other_vault.unseal(state)
    denied = integration.client.get(
        "/connectors/quickbooks/callback",
        params=dict(error="access_denied", state=state),
        follow_redirects=False,
    )
    assert denied.headers["location"].endswith(
        "connector_error=connector_denied&connector=quickbooks"
    )
    missing = integration.client.get("/connectors/quickbooks/callback", follow_redirects=False)
    assert "connector_denied" in missing.headers["location"]


def test_a_platform_that_returns_no_lasting_token_or_rejects_the_code_stores_nothing(integration):
    oauth, _, _ = enable(integration)
    owner, user = identity(integration, "refused@example.test")
    started = integration.client.post("/connectors/quickbooks/connect", headers=owner).json()["url"]
    state = parse_qs(urlparse(started).query)["state"][0]
    no_refresh = integration.client.get(
        "/connectors/quickbooks/callback",
        params=dict(code="no-refresh", state=state),
        follow_redirects=False,
    )
    assert no_refresh.headers["location"].endswith(
        "connector_error=connector_no_refresh&connector=quickbooks"
    )
    oauth.exchange_error = ConnectorApiError(400, "invalid_grant")
    rejected = integration.client.get(
        "/connectors/quickbooks/callback",
        params=dict(code="c", state=state),
        follow_redirects=False,
    )
    assert "connector_credentials_rejected" in rejected.headers["location"]
    assert stored(integration, user.id, "quickbooks") is None


def test_each_user_only_ever_uses_their_own_connection(integration):
    enable(integration)
    first, first_user = identity(integration, "first@example.test")
    second, _ = identity(integration, "second@example.test")
    connect_oauth(integration, first, realmId="111")
    assert (
        integration.client.get("/connectors/quickbooks/status", headers=second).json()["connected"]
        is False
    )
    blocked = integration.client.get("/connectors/quickbooks/sources", headers=second)
    assert (
        blocked.status_code == 409 and blocked.json()["error"]["code"] == "connector_not_connected"
    )
    other_state = integration.client.post("/connectors/quickbooks/connect", headers=second).json()[
        "url"
    ]
    token = parse_qs(urlparse(other_state).query)["state"][0]
    integration.client.get(
        "/connectors/quickbooks/callback", params=dict(code="c", state=token, realmId="222")
    )
    assert (
        integration.client.get("/connectors/quickbooks/status", headers=first).json()["account"]
        == "Company 111"
    )
    assert (
        integration.client.get("/connectors/quickbooks/status", headers=second).json()["account"]
        == "Company 222"
    )
    assert first_user.id


def test_rotated_refresh_tokens_are_saved_and_revoked_grants_ask_to_reconnect(integration):
    oauth, _, vault = enable(integration)
    owner, user = identity(integration, "rotate@example.test")
    connect_oauth(integration, owner, realmId="5")
    oauth.rotate = True
    assert (
        integration.client.get("/connectors/quickbooks/sources", headers=owner).status_code == 200
    )
    assert oauth.refreshed == ["refresh-1"]
    assert (
        json.loads(vault.unseal(stored(integration, user.id, "quickbooks")))["refresh_token"]
        == "refresh-2"
    )
    integration.client.get("/connectors/quickbooks/sources", headers=owner)
    assert oauth.refreshed[-1] == "refresh-2"
    oauth.refresh_error = ConnectorApiError(400, "invalid_grant")
    revoked = integration.client.get("/connectors/quickbooks/sources", headers=owner)
    assert revoked.status_code == 409 and revoked.json()["error"]["code"] == "connector_reconnect"
    assert stored(integration, user.id, "quickbooks") is None


def test_credentials_are_validated_then_sealed_and_unknown_fields_are_dropped(integration):
    _, credentials, vault = enable(integration)
    owner, user = identity(integration, "creds@example.test")
    saved = integration.client.post(
        "/connectors/odoo/credentials",
        headers=owner,
        json={"values": {"url": " https://odoo.example ", "api_key": "secret-key", "extra": "x"}},
    )
    assert saved.status_code == 200 and saved.json() == dict(
        connected=True, account="odoo.example / prod"
    )
    assert credentials.validated == [{"url": "https://odoo.example", "api_key": "secret-key"}]
    sealed = stored(integration, user.id, "odoo")
    assert (
        "secret-key" not in sealed
        and json.loads(vault.unseal(sealed))["context"]["api_key"] == "secret-key"
    )
    listing = integration.client.get("/connectors/odoo/sources", headers=owner).json()
    assert listing == [dict(id="invoices", label="Customer invoices", container=False)]
    assert credentials.sessions[-1] == ConnectorSession(
        "", {"url": "https://odoo.example", "api_key": "secret-key"}
    )


def test_bad_credentials_are_rejected_and_incomplete_forms_are_refused(integration):
    _, credentials, _ = enable(integration)
    owner, user = identity(integration, "badcreds@example.test")
    credentials.error = ConnectorApiError(401, "invalid_login")
    rejected = integration.client.post(
        "/connectors/odoo/credentials",
        headers=owner,
        json={"values": {"url": "https://o", "api_key": "k"}},
    )
    assert (
        rejected.status_code == 422
        and rejected.json()["error"]["code"] == "connector_credentials_rejected"
    )
    assert "k" not in rejected.text.replace("key", "")
    credentials.error = None
    incomplete = integration.client.post(
        "/connectors/odoo/credentials", headers=owner, json={"values": {"url": "https://o"}}
    )
    assert incomplete.status_code == 422
    assert (
        integration.client.post(
            "/connectors/odoo/credentials", headers=owner, json={"values": {}, "extra": 1}
        ).status_code
        == 422
    )
    too_long = integration.client.post(
        "/connectors/odoo/credentials",
        headers=owner,
        json={"values": {"url": "x" * 501, "api_key": "k"}},
    )
    assert too_long.status_code == 422
    assert stored(integration, user.id, "odoo") is None


def setup_import(env, email="import@example.test"):
    oauth, credentials, _ = enable(env)
    owner, user = identity(env, email)
    connect_oauth(env, owner, realmId="9")
    wid = workspace(env, owner)
    did = dataset(env, owner, wid)
    return oauth, credentials, owner, user, f"/workspaces/{wid}/datasets/{did}"


def test_import_turns_a_source_into_a_normal_profiled_upload_and_is_audited(integration):
    oauth, _, owner, _, base = setup_import(integration)
    response = integration.client.post(
        f"{base}/connectors/quickbooks/import", headers=owner, json={"source_id": "Invoice"}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert (
        body["filename"] == "QuickBooks Online - Company 9 - Invoices.csv"
        and body["format"] == "csv"
    )
    content = integration.client.get(
        f"{base}/uploads/{body['id']}/content", headers=owner
    ).content.decode()
    assert content.splitlines() == [
        "Id,Total,Customer_name,Lines_count",
        "1,10.5,Ali,1",
        "2,20,Sara,0",
    ]
    profile = integration.client.get(f"{base}/uploads/{body['id']}/profile", headers=owner)
    assert profile.status_code == 200 and profile.json()["profile"]["row_count"] == 2
    assert oauth.fetched == [("access-2", "Invoice", 1000)]
    with integration.engine.connect() as connection:
        count = connection.execute(
            text("SELECT count(*) FROM audit_events WHERE action='connector.imported'")
        ).scalar_one()
    assert count == 1


def test_credential_platforms_import_the_same_way(integration):
    _, _, owner, _, base = setup_import(integration)
    integration.client.post(
        "/connectors/odoo/credentials",
        headers=owner,
        json={"values": {"url": "https://o", "api_key": "k"}},
    )
    response = integration.client.post(
        f"{base}/connectors/odoo/import", headers=owner, json={"source_id": "invoices"}
    )
    assert response.status_code == 201
    assert response.json()["filename"] == "Odoo - odoo.example prod - Customer invoices.csv"


def test_the_configured_row_cap_is_passed_to_the_platform(integration):
    oauth, _, vault = enable(integration, max_rows=7)
    owner, _ = identity(integration, "cap@example.test")
    connect_oauth(integration, owner, realmId="1")
    wid = workspace(integration, owner)
    did = dataset(integration, owner, wid)
    integration.client.post(
        f"/workspaces/{wid}/datasets/{did}/connectors/quickbooks/import",
        headers=owner,
        json={"source_id": "Invoice"},
    )
    assert oauth.fetched[-1][2] == 7 and vault


def test_import_needs_membership_a_connection_and_a_valid_request(integration):
    oauth, _, owner, _, base = setup_import(integration)
    stranger, _ = identity(integration, "stranger@example.test")
    refused = integration.client.post(
        f"{base}/connectors/quickbooks/import", headers=stranger, json={"source_id": "Invoice"}
    )
    assert refused.status_code in {403, 404} and oauth.fetched == []
    assert (
        integration.client.post(
            f"{base}/connectors/quickbooks/import", json={"source_id": "x"}
        ).status_code
        == 401
    )
    for body in ({}, {"source_id": ""}, {"source_id": "x" * 601}, {"source_id": "a", "extra": 1}):
        assert (
            integration.client.post(
                f"{base}/connectors/quickbooks/import", headers=owner, json=body
            ).status_code
            == 422
        )
    integration.client.delete("/connectors/quickbooks", headers=owner)
    gone = integration.client.post(
        f"{base}/connectors/quickbooks/import", headers=owner, json={"source_id": "Invoice"}
    )
    assert gone.status_code == 409 and gone.json()["error"]["code"] == "connector_not_connected"


@pytest.mark.parametrize(
    "error, status, code",
    [
        (ConnectorApiError(403), 403, "connector_forbidden"),
        (ConnectorApiError(404), 404, "connector_source_unavailable"),
        (ConnectorApiError(422), 422, "connector_invalid_request"),
        (ConnectorApiError(429), 429, "connector_rate_limited"),
        (ConnectorApiError(502), 502, "connector_unexpected_response"),
        (ConnectorApiError(500), 503, "connector_unavailable"),
        (ConnectorApiError(503), 503, "connector_unavailable"),
    ],
)
def test_platform_failures_during_import_become_clear_errors(integration, error, status, code):
    oauth, _, owner, _, base = setup_import(integration)
    oauth.fetch_error = error
    response = integration.client.post(
        f"{base}/connectors/quickbooks/import", headers=owner, json={"source_id": "Invoice"}
    )
    assert response.status_code == status and response.json()["error"]["code"] == code
    assert integration.client.get(f"{base}/uploads", headers=owner).json() == []


def test_empty_and_oversized_sources_create_no_upload(integration):
    oauth, _, owner, _, base = setup_import(integration)
    oauth.rows = []
    empty = integration.client.post(
        f"{base}/connectors/quickbooks/import", headers=owner, json={"source_id": "Invoice"}
    )
    assert empty.status_code == 422 and empty.json()["error"]["code"] == "empty_source"
    oauth.rows = [{str(index): "1" for index in range(501)}]
    wide = integration.client.post(
        f"{base}/connectors/quickbooks/import", headers=owner, json={"source_id": "Invoice"}
    )
    assert wide.status_code == 413
    assert integration.client.get(f"{base}/uploads", headers=owner).json() == []


def test_disconnect_revokes_oauth_tokens_deletes_credentials_and_is_repeatable(integration):
    oauth, _, owner, user, _ = setup_import(integration)
    integration.client.post(
        "/connectors/odoo/credentials",
        headers=owner,
        json={"values": {"url": "https://o", "api_key": "k"}},
    )
    assert integration.client.delete("/connectors/quickbooks", headers=owner).status_code == 204
    assert oauth.revoked == ["refresh-1"] and stored(integration, user.id, "quickbooks") is None
    assert integration.client.delete("/connectors/odoo", headers=owner).status_code == 204
    assert stored(integration, user.id, "odoo") is None
    assert integration.client.delete("/connectors/odoo", headers=owner).status_code == 204
    assert oauth.revoked == ["refresh-1"]
