"""Use case: Proves Google sign-in, the Google connection and sheet import through the real API.

What it does: Drives the routes with a stand-in Google; checks sessions, sealed tokens and errors.
"""

import base64
import json
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text

from execplus.application.google_ports import (
    GoogleApiError,
    SheetTab,
    SpreadsheetInfo,
    TokenSet,
)
from execplus.application.services.google_access import GoogleAccessService
from execplus.infrastructure.google import HttpGoogleGateway
from execplus.infrastructure.persistence.google_connections import SqlGoogleConnections
from execplus.infrastructure.persistence.repository import SQLUnitOfWork
from execplus.infrastructure.token_vault import FernetTokenVault
from test_workspace_integration import dataset, identity, workspace

CLIENT = "client-id.apps.googleusercontent.com"
SHEET = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
DRIVE = "https://www.googleapis.com/auth/drive.file"
WEB = "http://web.test"
VALUES = [["order", "amt", "st"], [1, 1250.5, "P"], [2, 980, "R"]]


def jwt(claims):
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"e30.{body}.signature"


class StandInGoogle(HttpGoogleGateway):
    def __init__(self):
        super().__init__(
            CLIENT, "secret", "https://accounts.example/auth", "https://t", "https://r", "https://s"
        )
        self.codes, self.used, self.revoked, self.last = {}, set(), [], {}
        self.refresh_error = None
        self.sheet_error = None
        self.sheets = {
            SHEET: (
                SpreadsheetInfo("Orders", (SheetTab(0, "Jan", 3, 3), SheetTab(7, "Feb", 3, 3))),
                {"Jan": VALUES, "Feb": VALUES},
            )
        }

    def authorization_url(self, **kwargs):
        self.last = dict(nonce=kwargs["nonce"], state=kwargs["state"], scopes=kwargs["scopes"])
        return super().authorization_url(**kwargs)

    def grant(self, code, email, scope, refresh="rt-1", **changes):
        claims = dict(
            iss="https://accounts.google.com",
            aud=CLIENT,
            exp=4_000_000_000,
            nonce=self.last["nonce"],
            email=email,
            email_verified=True,
            sub="subject-" + email.lower(),
            name="Person",
        )
        claims.update(changes)
        self.codes[code] = TokenSet("access", 3600, refresh, jwt(claims), scope)

    def exchange_code(self, code, verifier, redirect_uri):
        if code in self.used or code not in self.codes:
            raise GoogleApiError(400, "invalid_grant")
        self.used.add(code)
        self.last.update(verifier=verifier, redirect_uri=redirect_uri)
        return self.codes[code]

    def refresh(self, refresh_token):
        if self.refresh_error:
            raise self.refresh_error
        return TokenSet("access-for-" + refresh_token, 3600)

    def revoke(self, token):
        self.revoked.append(token)

    def spreadsheet(self, access_token, spreadsheet_id):
        if self.sheet_error:
            raise self.sheet_error
        return self.sheets[spreadsheet_id][0]

    def sheet_values(self, access_token, spreadsheet_id, tab_title, max_bytes):
        if self.sheet_error:
            raise self.sheet_error
        return self.sheets[spreadsheet_id][1][tab_title]


def enable(env, picker=True):
    google = StandInGoogle()
    vault = FernetTokenVault(Fernet.generate_key().decode())
    env.runtime.google_access = GoogleAccessService(
        google,
        vault,
        SqlGoogleConnections(env.engine),
        env.runtime.identity,
        env.runtime.service,
        SQLUnitOfWork(env.engine),
        client_id=CLIENT,
        oauth=env.runtime.oauth_state,
        public_api_url="http://api.test",
        web_origin=WEB,
        picker_api_key="picker-key" if picker else "",
        app_id="12345" if picker else "",
    )
    env.client.headers["Origin"] = env.client.app.state.web_origin
    return google, vault


def sign_in(env, google, email="person@example.test", **changes):
    started = env.client.get("/auth/google/start", follow_redirects=False)
    assert started.status_code == 302, started.text
    query = parse_qs(urlparse(started.headers["location"]).query)
    google.grant("sign-in-code", email, "openid email profile", **changes)
    return started, env.client.get(
        "/auth/google/callback",
        params=dict(code="sign-in-code", state=query["state"][0]),
        follow_redirects=False,
    )


def exchange(env, headers=None):
    response = env.client.post("/auth/oauth/exchange", json={})
    assert response.status_code == 200, response.text
    result = response.json()
    if headers is not None and "token" in result:
        headers["Authorization"] = "Bearer " + result["token"]
    return result


def session_from(env, response):
    assert response.headers["location"] == f"{WEB}/workspace?oauth=complete"
    return exchange(env)["token"]


def connect(env, google, headers, email="person@example.test", scope=None, **grant):
    response = env.client.post("/integrations/google/connect", headers=headers)
    assert response.status_code == 200, response.text
    state = parse_qs(urlparse(response.json()["url"]).query)["state"][0]
    google.grant("connect-code", email, scope or f"openid email {DRIVE}", **grant)
    return env.client.get(
        "/integrations/google/callback",
        params=dict(code="connect-code", state=state),
        follow_redirects=False,
    )


def test_google_routes_report_disabled_and_refuse_when_not_configured(integration):
    assert integration.client.get("/auth/google/config").json() == dict(enabled=False, picker=None)
    assert integration.client.get("/auth/google/start", follow_redirects=False).status_code == 404
    owner, _ = identity(integration, "off@example.test")
    assert integration.client.get("/integrations/google/status", headers=owner).status_code == 404


def test_config_exposes_only_public_picker_values(integration):
    enable(integration)
    body = integration.client.get("/auth/google/config").json()
    assert body == dict(enabled=True, picker=dict(api_key="picker-key", app_id="12345"))
    assert "secret" not in json.dumps(body)
    enable(integration, picker=False)
    assert integration.client.get("/auth/google/config").json()["picker"] is None


def test_sign_in_redirects_to_google_with_pkce_and_a_bound_cookie(integration):
    google, _ = enable(integration)
    started = integration.client.get("/auth/google/start", follow_redirects=False)
    location = started.headers["location"]
    query = parse_qs(urlparse(location).query)
    assert location.startswith("https://accounts.example/auth?")
    assert query["code_challenge_method"] == ["S256"] and query["client_id"] == [CLIENT]
    assert query["redirect_uri"] == ["http://api.test/auth/google/callback"]
    assert query["scope"] == ["openid email profile"]
    cookie = started.headers["set-cookie"]
    assert "execplus_oauth_browser=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert google.last["scopes"] == ("openid", "email", "profile")


def test_sign_in_creates_a_session_for_the_verified_email(integration):
    google, _ = enable(integration)
    _, callback = sign_in(integration, google, "New.Person@Example.test")
    assert callback.status_code == 302
    assert callback.headers["location"].startswith(f"{WEB}/workspace?oauth=complete")
    me = integration.client.get(
        "/auth/me", headers={"Authorization": f"Bearer {session_from(integration, callback)}"}
    )
    assert me.status_code == 200 and me.json()["email"] == "new.person@example.test"
    assert google.last["redirect_uri"] == "http://api.test/auth/google/callback"
    again = integration.client.get(
        "/auth/google/callback",
        params=dict(code="sign-in-code", state="whatever"),
        follow_redirects=False,
    )
    assert "oauth_error=oauth_state_invalid" in again.headers["location"]


def test_sign_in_never_links_an_existing_operator_by_email(integration):
    google, _ = enable(integration)
    _, user = identity(integration, "same@example.test")
    _, callback = sign_in(integration, google, "same@example.test")
    assert callback.headers["location"] == f"{WEB}/workspace?oauth=complete"
    assert exchange(integration) == {"error": "google_identity_conflict"}
    with integration.engine.connect() as connection:
        assert (
            connection.execute(text("SELECT count(*) FROM external_identities")).scalar_one() == 0
        )
    assert user.id


@pytest.mark.parametrize(
    "changes, code",
    [
        (dict(email_verified=False), "google_identity_invalid"),
        (dict(aud="another-client"), "google_identity_invalid"),
        (dict(nonce="replayed"), "google_identity_invalid"),
        (dict(exp=1), "google_identity_invalid"),
        (dict(iss="https://evil.example"), "google_identity_invalid"),
    ],
)
def test_sign_in_refuses_untrustworthy_identity_tokens(integration, changes, code):
    google, _ = enable(integration)
    _, callback = sign_in(integration, google, **changes)
    assert callback.headers["location"] == f"{WEB}/workspace?oauth=complete"
    assert exchange(integration) == {"error": code}
    assert "session" not in callback.headers["location"]


def test_sign_in_needs_the_cookie_the_matching_state_and_no_error(integration):
    google, _ = enable(integration)
    started = integration.client.get("/auth/google/start", follow_redirects=False)
    state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]
    google.grant("code-a", "p@example.test", "openid email profile")
    wrong = integration.client.get(
        "/auth/google/callback",
        params=dict(code="code-a", state="x" + state),
        follow_redirects=False,
    )
    assert wrong.headers["location"].endswith("oauth_error=oauth_state_invalid")
    integration.client.cookies.clear()
    missing = integration.client.get(
        "/auth/google/callback", params=dict(code="code-a", state=state), follow_redirects=False
    )
    assert missing.headers["location"].endswith("oauth_error=oauth_state_invalid")
    denied = integration.client.get(
        "/auth/google/callback",
        params=dict(error="access_denied", state=state),
        follow_redirects=False,
    )
    assert denied.headers["location"].endswith("oauth_error=oauth_state_invalid")


def test_connect_seals_the_refresh_token_and_status_reflects_it(integration):
    google, vault = enable(integration)
    owner, user = identity(integration, "person@example.test")
    assert integration.client.get("/integrations/google/status", headers=owner).json() == dict(
        connected=False, email=""
    )
    callback = connect(integration, google, owner)
    assert callback.headers["location"] == f"{WEB}/workspace?oauth=complete"
    assert google.last["redirect_uri"] == "http://api.test/integrations/google/callback"
    assert google.last["scopes"] == ("openid", "email", DRIVE)
    status = integration.client.get("/integrations/google/status", headers=owner).json()
    assert status == dict(connected=True, email="person@example.test")
    with integration.engine.connect() as connection:
        stored = connection.execute(
            text("SELECT refresh_token_encrypted FROM google_connections WHERE user_id=:u"),
            dict(u=user.id),
        ).scalar_one()
    assert stored != "rt-1" and "rt-1" not in stored and vault.unseal(stored) == "rt-1"


def test_connect_refuses_the_wrong_google_account_and_missing_permission(integration):
    google, _ = enable(integration)
    owner, _ = identity(integration, "person@example.test")
    other = connect(integration, google, owner, email="someone.else@example.test")
    assert other.headers["location"].endswith("oauth=complete")
    assert exchange(integration, owner)["error"] == "google_wrong_account"
    google.used.clear()
    narrow = connect(integration, google, owner, scope="openid email")
    assert narrow.headers["location"].endswith("oauth=complete")
    assert exchange(integration, owner)["error"] == "google_scope_missing"
    google.used.clear()
    no_refresh = connect(integration, google, owner, refresh=None)
    assert no_refresh.headers["location"].endswith("oauth=complete")
    assert exchange(integration, owner)["error"] == "google_scope_missing"
    assert (
        integration.client.get("/integrations/google/status", headers=owner).json()["connected"]
        is False
    )


def test_connect_requires_a_signed_in_user_and_a_valid_state(integration):
    _, _ = enable(integration)
    assert integration.client.post("/integrations/google/connect").status_code == 401
    forged = integration.client.get(
        "/integrations/google/callback",
        params=dict(code="c", state="forged"),
        follow_redirects=False,
    )
    assert forged.headers["location"].endswith("oauth_error=oauth_state_invalid")


def test_disconnect_revokes_at_google_and_deletes_the_stored_token(integration):
    google, _ = enable(integration)
    owner, _ = identity(integration, "person@example.test")
    connect(integration, google, owner)
    assert integration.client.delete("/integrations/google", headers=owner).status_code == 204
    assert google.revoked == ["rt-1"]
    assert (
        integration.client.get("/integrations/google/status", headers=owner).json()["connected"]
        is False
    )
    assert integration.client.delete("/integrations/google", headers=owner).status_code == 204


def import_body(**changes):
    return dict(spreadsheet_id=SHEET, **changes)


def setup_import(env, email="person@example.test"):
    google, _ = enable(env)
    owner, _ = identity(env, email)
    connect(env, google, owner, email=email)
    wid = workspace(env, owner)
    did = dataset(env, owner, wid)
    return google, owner, f"/workspaces/{wid}/datasets/{did}"


def test_picker_token_and_spreadsheet_tabs_use_the_users_own_connection(integration):
    _, owner, _ = setup_import(integration)
    token = integration.client.get("/integrations/google/picker-token", headers=owner)
    assert token.json() == dict(access_token="access-for-rt-1", expires_in=3600)
    assert token.headers["cache-control"] == "no-store"
    tabs = integration.client.get(
        f"/integrations/google/spreadsheets/{SHEET}", headers=owner
    ).json()
    assert tabs["title"] == "Orders" and [tab["id"] for tab in tabs["tabs"]] == [0, 7]


def test_import_turns_the_chosen_tab_into_a_normal_profiled_upload(integration):
    _, owner, base = setup_import(integration)
    response = integration.client.post(
        f"{base}/google-sheets/import", headers=owner, json=import_body(sheet_id=7)
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["filename"] == "Orders - Feb.csv" and body["format"] == "csv"
    content = integration.client.get(f"{base}/uploads/{body['id']}/content", headers=owner)
    assert content.content.decode().splitlines() == ["order,amt,st", "1,1250.5,P", "2,980,R"]
    profile = integration.client.get(f"{base}/uploads/{body['id']}/profile", headers=owner)
    assert profile.status_code == 200 and profile.json()["profile"]["row_count"] == 2
    first = integration.client.post(
        f"{base}/google-sheets/import", headers=owner, json=import_body()
    )
    assert first.json()["filename"] == "Orders - Jan.csv"
    with integration.engine.connect() as connection:
        events = connection.execute(
            text("SELECT count(*) FROM audit_events WHERE action='google_sheets.imported'")
        ).scalar_one()
    assert events == 2


def test_import_needs_a_connection_membership_and_a_valid_request(integration):
    _, owner, base = setup_import(integration)
    stranger, _ = identity(integration, "stranger@example.test")
    refused = integration.client.post(
        f"{base}/google-sheets/import", headers=stranger, json=import_body()
    )
    assert refused.status_code in {403, 404}
    connect_first = integration.client.post(
        f"{base}/google-sheets/import", headers=stranger, json=import_body()
    )
    assert connect_first.status_code in {403, 404}
    assert (
        integration.client.post(f"{base}/google-sheets/import", json=import_body()).status_code
        == 401
    )
    for body in (
        dict(spreadsheet_id="bad"),
        dict(spreadsheet_id=SHEET, sheet_id=-1),
        dict(spreadsheet_id=SHEET, extra=1),
    ):
        assert (
            integration.client.post(
                f"{base}/google-sheets/import", headers=owner, json=body
            ).status_code
            == 422
        )
    missing_tab = integration.client.post(
        f"{base}/google-sheets/import", headers=owner, json=import_body(sheet_id=99)
    )
    assert missing_tab.status_code == 422


def test_a_member_without_a_connection_is_asked_to_connect(integration):
    _, owner, base = setup_import(integration)
    other, _ = identity(integration, "member@example.test")
    invited = integration.client.post(
        f"{base.split('/datasets')[0]}/invitations",
        headers=owner,
        json=dict(email="member@example.test", role="member"),
    )
    assert invited.status_code == 201, invited.text
    accepted = integration.client.post(
        f"{base.split('/datasets')[0]}/invitations/{invited.json()['id']}/accept", headers=other
    )
    assert accepted.status_code in {200, 201}, accepted.text
    refused = integration.client.post(
        f"{base}/google-sheets/import", headers=other, json=import_body()
    )
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "google_not_connected"


@pytest.mark.parametrize(
    "error, status, code",
    [
        (GoogleApiError(403), 404, "google_sheet_unavailable"),
        (GoogleApiError(404), 404, "google_sheet_unavailable"),
        (GoogleApiError(413, "too_large"), 413, "sheet_too_large"),
        (GoogleApiError(429), 429, "google_rate_limited"),
        (GoogleApiError(500), 503, "google_unavailable"),
    ],
)
def test_google_failures_during_import_become_clear_errors(integration, error, status, code):
    google, owner, base = setup_import(integration)
    google.sheet_error = error
    response = integration.client.post(
        f"{base}/google-sheets/import", headers=owner, json=import_body()
    )
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_a_revoked_google_grant_removes_the_connection_and_asks_to_reconnect(integration):
    google, owner, base = setup_import(integration)
    google.refresh_error = GoogleApiError(400, "invalid_grant")
    response = integration.client.post(
        f"{base}/google-sheets/import", headers=owner, json=import_body()
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "google_reconnect"
    assert (
        integration.client.get("/integrations/google/status", headers=owner).json()["connected"]
        is False
    )


def test_empty_and_oversized_sheets_are_refused_without_creating_an_upload(integration):
    google, owner, base = setup_import(integration)
    google.sheets[SHEET][1]["Jan"] = [["only", "header"]]
    empty = integration.client.post(
        f"{base}/google-sheets/import", headers=owner, json=import_body(sheet_id=0)
    )
    assert empty.status_code == 422 and empty.json()["error"]["code"] == "empty_sheet"
    google.sheets[SHEET][1]["Jan"] = [[str(i) for i in range(501)], ["1"] * 501]
    wide = integration.client.post(
        f"{base}/google-sheets/import", headers=owner, json=import_body(sheet_id=0)
    )
    assert wide.status_code == 413
    assert integration.client.get(f"{base}/uploads", headers=owner).json() == []


def test_each_user_only_ever_uses_their_own_connection(integration):
    google, owner, _ = setup_import(integration)
    google.used.clear()
    second, second_user = identity(integration, "second@example.test")
    connect(integration, google, second, email="second@example.test", refresh="rt-second")
    assert (
        integration.client.get("/integrations/google/picker-token", headers=second).json()[
            "access_token"
        ]
        == "access-for-rt-second"
    )
    assert (
        integration.client.get("/integrations/google/picker-token", headers=owner).json()[
            "access_token"
        ]
        == "access-for-rt-1"
    )
    assert UUID(str(second_user.id))
