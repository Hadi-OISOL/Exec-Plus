"""Use case: Reads accounting records from Xero with the user's own consent.

What it does: Runs the Xero OAuth exchange, finds the organisation and pages through a chosen list.
"""

from typing import Any, Literal
from urllib.parse import urlencode

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

AUTH_URL = "https://login.xero.com/identity/connect/authorize"
TOKEN_URL = "https://identity.xero.com/connect/token"
REVOKE_URL = "https://identity.xero.com/connect/revocation"
CONNECTIONS_URL = "https://api.xero.com/connections"
API_URL = "https://api.xero.com/api.xro/2.0"
PAGE = 100
LISTS = (
    ("Invoices", "Invoices and bills", True),
    ("Contacts", "Contacts", True),
    ("Payments", "Payments", True),
    ("BankTransactions", "Bank transactions", True),
    ("CreditNotes", "Credit notes", True),
    ("Items", "Products and services", False),
    ("Accounts", "Chart of accounts", False),
)


class XeroConnector:
    id = "xero"
    label = "Xero"
    kind: Literal["oauth", "credentials"] = "oauth"
    uses_pkce = True
    description = (
        "Invoices and bills, contacts, payments, bank transactions and the chart of accounts."
    )
    fields: tuple[ConnectorField, ...] = ()

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        scopes: str,
        client: httpx.Client | None = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = scopes
        self.client = client or httpx.Client(timeout=DEFAULT_TIMEOUT)

    def authorization_url(self, *, redirect_uri: str, state: str, challenge: str) -> str:
        query = urlencode(
            dict(
                response_type="code",
                client_id=self.client_id,
                redirect_uri=redirect_uri,
                scope=self.scopes,
                state=state,
                code_challenge=challenge,
                code_challenge_method="S256",
            )
        )
        return f"{AUTH_URL}?{query}"

    def _token(self, data: dict[str, str]) -> dict[str, Any]:
        return json_body(
            send(
                self.client,
                "POST",
                TOKEN_URL,
                data=data,
                auth=(self.client_id, self.client_secret),
                headers={"Accept": "application/json"},
            )
        )

    def exchange_code(
        self, code: str, redirect_uri: str, verifier: str, callback: dict[str, str]
    ) -> ProviderTokens:
        tokens = tokens_from(
            self._token(
                {
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "code_verifier": verifier,
                }
            )
        )
        response = send(
            self.client,
            "GET",
            CONNECTIONS_URL,
            headers={
                "Authorization": f"Bearer {tokens.access_token}",
                "Accept": "application/json",
            },
        )
        organisations = response.json()
        if not isinstance(organisations, list) or not organisations:
            raise ConnectorApiError(403, "no_organisation")
        chosen = organisations[0]
        return ProviderTokens(
            tokens.access_token,
            tokens.refresh_token,
            tokens.expires_in,
            {
                "tenant_id": str(chosen.get("tenantId", "")),
                "tenant_name": str(chosen.get("tenantName", "")),
            },
        )

    def refresh(self, refresh_token: str, context: dict[str, str]) -> ProviderTokens:
        return tokens_from(
            self._token({"grant_type": "refresh_token", "refresh_token": refresh_token}), context
        )

    def revoke(self, refresh_token: str) -> None:
        try:
            send(
                self.client,
                "POST",
                REVOKE_URL,
                data={"token": refresh_token},
                auth=(self.client_id, self.client_secret),
            )
        except ConnectorApiError:
            return

    def account_name(self, context: dict[str, str]) -> str:
        return context.get("tenant_name") or "Xero organisation"

    def sources(self, session: ConnectorSession, parent: str | None) -> list[Source]:
        return [Source(name, label) for name, label, _ in LISTS] if parent is None else []

    def fetch(
        self, session: ConnectorSession, source_id: str, max_rows: int
    ) -> list[dict[str, Any]]:
        listing = next((item for item in LISTS if item[0] == source_id), None)
        if listing is None:
            raise ConnectorApiError(404, "unknown_source")
        headers = {
            "Authorization": f"Bearer {session.access_token}",
            "xero-tenant-id": session.context.get("tenant_id", ""),
            "Accept": "application/json",
        }
        records: list[dict[str, Any]] = RecordBuffer()
        page = 1
        while len(records) < max_rows:
            params = {"page": str(page)} if listing[2] else {}
            body = json_body(
                send(self.client, "GET", f"{API_URL}/{source_id}", params=params, headers=headers)
            )
            batch = body.get(source_id, [])
            records.extend(batch)
            if not listing[2] or len(batch) < PAGE:
                break
            page += 1
        return records[:max_rows]
