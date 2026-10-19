"""Use case: Proves the Google rules and gateway behave correctly without calling Google.

What it does: Checks PKCE, identity claims, sheet conversion, the token vault and the HTTP gateway.
"""

import base64
import hashlib
import json
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.fernet import Fernet

from execplus.application.google_ports import GoogleApiError
from execplus.domain.google_oauth import (
    import_filename,
    new_pkce,
    sheet_to_csv,
    valid_spreadsheet_id,
    verified_identity,
)
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.google import HttpGoogleGateway
from execplus.infrastructure.token_vault import FernetTokenVault

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
CLIENT = "client-id.apps.googleusercontent.com"


def claims(**changes):
    value = dict(
        iss="https://accounts.google.com",
        aud=CLIENT,
        exp=NOW.timestamp() + 600,
        nonce="n-1",
        email="Person@Example.test",
        email_verified=True,
        name="Person",
    )
    value.update(changes)
    return value


def test_pkce_challenge_is_the_sha256_of_the_verifier():
    verifier, challenge = new_pkce()
    digest = hashlib.sha256(verifier.encode()).digest()
    assert challenge == base64.urlsafe_b64encode(digest).decode().rstrip("=")
    assert new_pkce()[0] != verifier


def test_valid_identity_is_accepted_for_one_or_many_audiences():
    assert verified_identity(claims(), CLIENT, "n-1", NOW) == ("Person@Example.test", "Person")
    assert verified_identity(claims(aud=["other", CLIENT]), CLIENT, "n-1", NOW)[1] == "Person"
    assert verified_identity(claims(email_verified="true"), CLIENT, "n-1", NOW)


@pytest.mark.parametrize(
    "changes",
    [
        dict(iss="https://evil.example"),
        dict(aud="someone-else"),
        dict(aud=["a", "b"]),
        dict(exp=NOW.timestamp() - 1),
        dict(exp="soon"),
        dict(nonce="replayed"),
        dict(email_verified=False),
        dict(email_verified="false"),
        dict(email=""),
        dict(email=None),
    ],
)
def test_untrustworthy_identity_is_rejected(changes):
    with pytest.raises(IngestionError) as error:
        verified_identity(claims(**changes), CLIENT, "n-1", NOW)
    assert error.value.code == "google_identity_invalid"


def test_spreadsheet_ids_are_checked_and_filenames_are_safe():
    assert valid_spreadsheet_id("1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms")
    for bad in ("", "short", "has space and more than twenty chars", "../../etc/passwd" * 2):
        with pytest.raises(IngestionError):
            valid_spreadsheet_id(bad)
    name = import_filename("Sales / 2026\\Q1", "Tab\x00 One")
    assert name.endswith(".csv") and "/" not in name and "\\" not in name and "\x00" not in name
    assert len(import_filename("x" * 500, "y" * 500)) <= 100
    assert import_filename("", "") == "Google Sheet.csv"


def test_sheet_values_become_csv_with_clean_unique_headers():
    values = [
        ["order", "amt", "", "amt", "paid"],
        [1, 1250.5, None, "x", True],
        [2, 980],
        ["", "", "", "", ""],
    ]
    csv_text = sheet_to_csv(values).decode()
    assert csv_text.splitlines() == [
        "order,amt,column_3,amt_2,paid",
        "1,1250.5,,x,true",
        "2,980,,,",
    ]


def test_sheets_without_data_or_too_large_are_refused():
    with pytest.raises(IngestionError) as only_header:
        sheet_to_csv([["a", "b"]])
    assert only_header.value.code == "empty_sheet"
    with pytest.raises(IngestionError) as empty:
        sheet_to_csv([])
    assert empty.value.code == "empty_sheet"
    with pytest.raises(IngestionError) as wide:
        sheet_to_csv([[str(index) for index in range(501)], ["1"] * 501])
    assert wide.value.code == "sheet_too_large"


def test_vault_round_trips_and_rejects_tampering_and_other_keys():
    vault = FernetTokenVault(Fernet.generate_key().decode())
    sealed = vault.seal("refresh-token-value")
    assert "refresh-token-value" not in sealed
    assert vault.unseal(sealed) == "refresh-token-value"
    with pytest.raises(ValueError):
        vault.unseal(sealed[:-3] + "abc")
    with pytest.raises(ValueError):
        FernetTokenVault(Fernet.generate_key().decode()).unseal(sealed)
    with pytest.raises(ValueError):
        vault.unseal(sealed, max_age_seconds=-1)


def gateway(handler):
    return HttpGoogleGateway(
        CLIENT,
        "secret",
        "https://accounts.example/auth",
        "https://oauth.example/token",
        "https://oauth.example/revoke",
        "https://sheets.example/v4",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_authorization_url_carries_pkce_and_offline_access_only_when_asked():
    google = gateway(lambda request: httpx.Response(200))
    url = google.authorization_url(
        scopes=("openid", "email"),
        redirect_uri="http://api/cb",
        state="s",
        challenge="c",
        nonce="n",
        login_hint="a@b.test",
        offline=True,
    )
    query = {key: value[0] for key, value in parse_qs(urlparse(url).query).items()}
    assert query["code_challenge_method"] == "S256" and query["code_challenge"] == "c"
    assert query["access_type"] == "offline" and query["prompt"] == "consent"
    assert query["scope"] == "openid email" and query["login_hint"] == "a@b.test"
    assert query["client_id"] == CLIENT and "client_secret" not in query
    plain = google.authorization_url(
        scopes=("openid",), redirect_uri="x", state="s", challenge="c", nonce="n"
    )
    assert "access_type" not in plain and "select_account" in plain


def test_code_exchange_sends_the_verifier_and_maps_failures():
    seen = {}

    def handler(request):
        seen.update(parse_qs(request.content.decode()))
        if seen["code"] == ["bad"]:
            return httpx.Response(400, json={"error": "invalid_grant"})
        return httpx.Response(
            200,
            json=dict(
                access_token="at", expires_in=3600, refresh_token="rt", id_token="a.b.c", scope="s"
            ),
        )

    google = gateway(handler)
    tokens = google.exchange_code("good", "verifier-1", "http://api/cb")
    assert (tokens.access_token, tokens.refresh_token, tokens.scope) == ("at", "rt", "s")
    assert seen["code_verifier"] == ["verifier-1"] and seen["client_secret"] == ["secret"]
    with pytest.raises(GoogleApiError) as error:
        google.exchange_code("bad", "v", "http://api/cb")
    assert (error.value.status, error.value.code) == (400, "invalid_grant")


def test_network_failures_become_a_service_unavailable_error():
    def handler(request):
        raise httpx.ConnectError("down")

    with pytest.raises(GoogleApiError) as error:
        gateway(handler).refresh("rt")
    assert error.value.status == 503


def test_id_token_claims_are_decoded_and_malformed_tokens_rejected():
    payload = (
        base64.urlsafe_b64encode(json.dumps({"email": "a@b.test"}).encode()).decode().rstrip("=")
    )
    google = gateway(lambda request: httpx.Response(200))
    assert google.id_token_claims(f"h.{payload}.s") == {"email": "a@b.test"}
    for bad in (
        "nodots",
        "a.b",
        "a.!!!.c",
        "a." + base64.urlsafe_b64encode(b"[1]").decode() + ".c",
    ):
        with pytest.raises(GoogleApiError):
            google.id_token_claims(bad)


def test_spreadsheet_lists_visible_tabs_and_values_use_quoted_ranges_and_raw_numbers():
    calls = []

    def handler(request):
        calls.append(request)
        if "/values/" in request.url.path:
            return httpx.Response(200, json={"values": [["a"], [1]]})
        return httpx.Response(
            200,
            json=dict(
                properties=dict(title="Book"),
                sheets=[
                    dict(
                        properties=dict(
                            sheetId=0, title="Data", gridProperties=dict(rowCount=10, columnCount=3)
                        )
                    ),
                    dict(properties=dict(sheetId=5, title="Hidden", hidden=True)),
                ],
            ),
        )

    google = gateway(handler)
    info = google.spreadsheet("tok", "id1")
    assert info.title == "Book" and [tab.title for tab in info.tabs] == ["Data"]
    assert calls[0].headers["authorization"] == "Bearer tok"
    assert google.sheet_values("tok", "id1", "O'Brien", 1_000) == [["a"], [1]]
    request = calls[1]
    assert "%27O%27%27Brien%27" in str(request.url) or "'O''Brien'" in request.url.path
    assert request.url.params["valueRenderOption"] == "UNFORMATTED_VALUE"
    assert request.url.params["dateTimeRenderOption"] == "FORMATTED_STRING"


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500])
def test_google_errors_keep_their_status(status):
    google = gateway(lambda request: httpx.Response(status, json={"error": "x"}))
    with pytest.raises(GoogleApiError) as error:
        google.spreadsheet("tok", "id1")
    assert error.value.status == status
    with pytest.raises(GoogleApiError) as values:
        google.sheet_values("tok", "id1", "Data", 1_000)
    assert values.value.status == status


def test_oversized_sheet_responses_are_cut_off():
    google = gateway(lambda request: httpx.Response(200, json={"values": [["x" * 500]] * 50}))
    with pytest.raises(GoogleApiError) as error:
        google.sheet_values("tok", "id1", "Data", 1_000)
    assert error.value.status == 413
