"""Use case: Connects ExecPlus to Google OAuth and the Google Sheets API.

What it does: Builds consent URLs, exchanges tokens and reads a chosen sheet within a size limit.
"""

import base64
import json
from decimal import Decimal
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from execplus.application.google_ports import (
    GoogleApiError,
    SheetTab,
    SpreadsheetInfo,
    TokenSet,
)
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.bounded_http import limited_request


def _error_code(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return ""
    value = body.get("error") if isinstance(body, dict) else ""
    return value if isinstance(value, str) else ""


class HttpGoogleGateway:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        auth_url: str,
        token_url: str,
        revoke_url: str,
        sheets_url: str,
        timeout_seconds: float = 20.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.auth_url = auth_url
        self.token_url = token_url
        self.revoke_url = revoke_url
        self.sheets_url = sheets_url.rstrip("/")
        self.client = client or httpx.Client(timeout=timeout_seconds)

    def authorization_url(
        self,
        *,
        scopes: tuple[str, ...],
        redirect_uri: str,
        state: str,
        challenge: str,
        nonce: str,
        login_hint: str = "",
        offline: bool = False,
    ) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        if offline:
            params.update(access_type="offline", prompt="consent", include_granted_scopes="true")
        else:
            params["prompt"] = "select_account"
        if login_hint:
            params["login_hint"] = login_hint
        return f"{self.auth_url}?{urlencode(params)}"

    def _token_request(self, data: dict[str, str]) -> TokenSet:
        try:
            response = limited_request(
                self.client,
                "POST",
                self.token_url,
                data={**data, "client_id": self.client_id, "client_secret": self.client_secret},
            )
        except httpx.HTTPError:
            raise GoogleApiError(503) from None
        if response.status_code != 200:
            raise GoogleApiError(response.status_code, _error_code(response))
        body = response.json()
        access = body.get("access_token")
        if not isinstance(access, str) or not access:
            raise GoogleApiError(502)
        return TokenSet(
            access,
            int(body.get("expires_in", 0) or 0),
            body.get("refresh_token") if isinstance(body.get("refresh_token"), str) else None,
            body.get("id_token") if isinstance(body.get("id_token"), str) else None,
            str(body.get("scope", "")),
        )

    def exchange_code(self, code: str, verifier: str, redirect_uri: str) -> TokenSet:
        return self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": verifier,
                "redirect_uri": redirect_uri,
            }
        )

    def refresh(self, refresh_token: str) -> TokenSet:
        return self._token_request({"grant_type": "refresh_token", "refresh_token": refresh_token})

    def revoke(self, token: str) -> None:
        try:
            limited_request(self.client, "POST", self.revoke_url, data={"token": token})
        except (httpx.HTTPError, IngestionError):
            return

    def id_token_claims(self, id_token: str) -> dict[str, Any]:
        parts = id_token.split(".")
        if len(parts) != 3:
            raise GoogleApiError(502)
        try:
            padded = parts[1] + "=" * (-len(parts[1]) % 4)
            claims = json.loads(base64.urlsafe_b64decode(padded))
        except (ValueError, json.JSONDecodeError):
            raise GoogleApiError(502) from None
        if not isinstance(claims, dict):
            raise GoogleApiError(502)
        return claims

    def _get(self, url: str, access_token: str, params: dict[str, str]) -> httpx.Response:
        try:
            return limited_request(
                self.client,
                "GET",
                url,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except httpx.HTTPError:
            raise GoogleApiError(503) from None

    def spreadsheet(self, access_token: str, spreadsheet_id: str) -> SpreadsheetInfo:
        response = self._get(
            f"{self.sheets_url}/spreadsheets/{quote(spreadsheet_id, safe='')}",
            access_token,
            {
                "fields": "properties.title,sheets.properties("
                "sheetId,title,hidden,gridProperties(rowCount,columnCount))"
            },
        )
        if response.status_code != 200:
            raise GoogleApiError(response.status_code, _error_code(response))
        body = response.json()
        tabs = []
        for sheet in body.get("sheets", []):
            properties = sheet.get("properties", {})
            if properties.get("hidden"):
                continue
            grid = properties.get("gridProperties", {})
            tabs.append(
                SheetTab(
                    int(properties.get("sheetId", 0)),
                    str(properties.get("title", "")),
                    int(grid.get("rowCount", 0)),
                    int(grid.get("columnCount", 0)),
                )
            )
        return SpreadsheetInfo(str(body.get("properties", {}).get("title", "")), tuple(tabs))

    def sheet_values(
        self, access_token: str, spreadsheet_id: str, tab_title: str, max_bytes: int
    ) -> list[list[Any]]:
        quoted = "'" + tab_title.replace("'", "''") + "'"
        url = (
            f"{self.sheets_url}/spreadsheets/{quote(spreadsheet_id, safe='')}"
            f"/values/{quote(quoted, safe='')}"
        )
        try:
            response = limited_request(
                self.client,
                "GET",
                url,
                max_bytes=max_bytes,
                params={
                    "majorDimension": "ROWS",
                    "valueRenderOption": "UNFORMATTED_VALUE",
                    "dateTimeRenderOption": "FORMATTED_STRING",
                },
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except IngestionError as error:
            raise GoogleApiError(error.status, error.code) from None
        except httpx.HTTPError:
            raise GoogleApiError(503) from None
        if response.status_code != 200:
            raise GoogleApiError(response.status_code, _error_code(response))
        try:
            values = response.json(parse_float=Decimal).get("values", [])
        except (ValueError, RecursionError):
            raise GoogleApiError(502) from None
        return values if isinstance(values, list) else []
