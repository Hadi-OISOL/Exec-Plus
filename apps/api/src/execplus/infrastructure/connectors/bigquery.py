"""Use case: Reads whole tables from Google BigQuery with the user's own consent.

What it does: Browses projects, datasets and tables and copies rows through the free table-data API.
"""

import base64
import json
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import quote, unquote, urlencode

import httpx

from execplus.application.connector_ports import (
    ConnectorApiError,
    ConnectorField,
    ConnectorSession,
    ProviderTokens,
)
from execplus.domain.connectors import RecordBuffer, Source
from execplus.infrastructure.connectors.base import (
    DEFAULT_TIMEOUT,
    json_body,
    send,
    tokens_from,
)

SCOPES = ("openid", "email", "https://www.googleapis.com/auth/bigquery.readonly")
API_URL = "https://bigquery.googleapis.com/bigquery/v2"
PAGE = 10_000
MAX_LISTED = 500


def _identifier(value: str) -> str:
    return quote(value, safe="")


class BigQueryConnector:
    id = "bigquery"
    label = "Google BigQuery"
    kind: Literal["oauth", "credentials"] = "oauth"
    uses_pkce = True
    description = "Tables in your BigQuery projects, copied read-only without running queries."
    fields: tuple[ConnectorField, ...] = ()

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        auth_url: str,
        token_url: str,
        revoke_url: str,
        client: httpx.Client | None = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.auth_url = auth_url
        self.token_url = token_url
        self.revoke_url = revoke_url
        self.client = client or httpx.Client(timeout=DEFAULT_TIMEOUT)

    def authorization_url(self, *, redirect_uri: str, state: str, challenge: str) -> str:
        query = urlencode(
            dict(
                client_id=self.client_id,
                redirect_uri=redirect_uri,
                response_type="code",
                scope=" ".join(SCOPES),
                state=state,
                code_challenge=challenge,
                code_challenge_method="S256",
                access_type="offline",
                prompt="consent",
            )
        )
        return f"{self.auth_url}?{query}"

    def _token(self, data: dict[str, str]) -> dict[str, Any]:
        return json_body(
            send(
                self.client,
                "POST",
                self.token_url,
                data={**data, "client_id": self.client_id, "client_secret": self.client_secret},
            )
        )

    def exchange_code(
        self, code: str, redirect_uri: str, verifier: str, callback: dict[str, str]
    ) -> ProviderTokens:
        body = self._token(
            {
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": verifier,
                "redirect_uri": redirect_uri,
            }
        )
        tokens = tokens_from(body)
        if "bigquery.readonly" not in str(body.get("scope", "")):
            raise ConnectorApiError(403, "scope_missing")
        email = ""
        token = body.get("id_token")
        if isinstance(token, str) and token.count(".") == 2:
            try:
                payload = token.split(".")[1]
                claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
                email = str(claims.get("email", ""))
            except (ValueError, json.JSONDecodeError):
                email = ""
        return ProviderTokens(
            tokens.access_token, tokens.refresh_token, tokens.expires_in, {"account": email}
        )

    def refresh(self, refresh_token: str, context: dict[str, str]) -> ProviderTokens:
        return tokens_from(
            self._token({"grant_type": "refresh_token", "refresh_token": refresh_token}), context
        )

    def revoke(self, refresh_token: str) -> None:
        try:
            send(self.client, "POST", self.revoke_url, data={"token": refresh_token})
        except ConnectorApiError:
            return

    def account_name(self, context: dict[str, str]) -> str:
        return context.get("account") or "Google BigQuery"

    def _get(self, session: ConnectorSession, path: str, **params: str) -> dict[str, Any]:
        return json_body(
            send(
                self.client,
                "GET",
                f"{API_URL}{path}",
                params=params,
                headers={"Authorization": f"Bearer {session.access_token}"},
            )
        )

    def sources(self, session: ConnectorSession, parent: str | None) -> list[Source]:
        if parent is None:
            body = self._get(session, "/projects", maxResults=str(MAX_LISTED))
            return [
                Source(f"p/{_identifier(item['id'])}", item.get("friendlyName") or item["id"], True)
                for item in body.get("projects", [])
            ]
        kind, *parts = parent.split("/")
        if kind == "p" and len(parts) == 1:
            project = unquote(parts[0])
            body = self._get(
                session, f"/projects/{_identifier(project)}/datasets", maxResults=str(MAX_LISTED)
            )
            return [
                Source(
                    f"d/{_identifier(project)}/{_identifier(item['datasetReference']['datasetId'])}",
                    item["datasetReference"]["datasetId"],
                    True,
                )
                for item in body.get("datasets", [])
            ]
        if kind == "d" and len(parts) == 2:
            project, dataset = unquote(parts[0]), unquote(parts[1])
            body = self._get(
                session,
                f"/projects/{_identifier(project)}/datasets/{_identifier(dataset)}/tables",
                maxResults=str(MAX_LISTED),
            )
            return [
                Source(
                    f"t/{_identifier(project)}/{_identifier(dataset)}/"
                    f"{_identifier(item['tableReference']['tableId'])}",
                    item["tableReference"]["tableId"],
                )
                for item in body.get("tables", [])
                if item.get("type", "TABLE") == "TABLE"
            ]
        raise ConnectorApiError(404, "unknown_source")

    def fetch(
        self, session: ConnectorSession, source_id: str, max_rows: int
    ) -> list[dict[str, Any]]:
        kind, *parts = source_id.split("/")
        if kind != "t" or len(parts) != 3:
            raise ConnectorApiError(404, "unknown_source")
        project, dataset, table = (unquote(part) for part in parts)
        base = f"/projects/{_identifier(project)}/datasets/{_identifier(dataset)}"
        schema = self._get(session, f"{base}/tables/{_identifier(table)}")
        fields = schema.get("schema", {}).get("fields", [])
        if not fields:
            raise ConnectorApiError(422, "no_schema")
        records: list[dict[str, Any]] = RecordBuffer()
        token = ""
        while len(records) < max_rows:
            params = {"maxResults": str(min(PAGE, max_rows - len(records)))}
            if token:
                params["pageToken"] = token
            body = self._get(session, f"{base}/tables/{_identifier(table)}/data", **params)
            for row in body.get("rows", []):
                records.append(
                    {
                        field["name"]: self._convert(cell.get("v"), field)
                        for field, cell in zip(fields, row.get("f", []), strict=False)
                    }
                )
            token = body.get("pageToken", "")
            if not token or not body.get("rows"):
                break
        return records[:max_rows]

    def _convert(self, value: Any, field: dict[str, Any]) -> Any:
        if value is None:
            return None
        kind = field.get("type", "STRING")
        if field.get("mode") == "REPEATED":
            single = {**field, "mode": "NULLABLE"}
            return [self._convert(item.get("v"), single) for item in value]
        if kind in {"RECORD", "STRUCT"}:
            return {
                sub["name"]: self._convert(cell.get("v"), sub)
                for sub, cell in zip(field.get("fields", []), value.get("f", []), strict=False)
            }
        if kind == "TIMESTAMP":
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
        if kind == "BYTES":
            return "(binary)"
        return value
