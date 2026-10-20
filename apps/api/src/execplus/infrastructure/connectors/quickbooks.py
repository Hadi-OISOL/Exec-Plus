"""Use case: Reads accounting records from QuickBooks Online with the user's own consent.

What it does: Runs the Intuit OAuth exchange and pages through query results for a chosen entity.
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

AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
REVOKE_URL = "https://developer.api.intuit.com/v2/oauth2/tokens/revoke"
SCOPE = "com.intuit.quickbooks.accounting"
MINOR_VERSION = "75"
PAGE = 1000
ENTITIES = (
    ("Invoice", "Invoices"),
    ("Bill", "Bills"),
    ("Payment", "Customer payments"),
    ("BillPayment", "Bill payments"),
    ("Purchase", "Expenses"),
    ("Customer", "Customers"),
    ("Vendor", "Vendors"),
    ("Item", "Products and services"),
    ("Account", "Chart of accounts"),
)


class QuickBooksConnector:
    id = "quickbooks"
    label = "QuickBooks Online"
    kind: Literal["oauth", "credentials"] = "oauth"
    uses_pkce = False
    description = "Invoices, bills, payments, customers, vendors, items and the chart of accounts."
    fields: tuple[ConnectorField, ...] = ()

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        environment: str = "production",
        client: httpx.Client | None = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.api = (
            "https://sandbox-quickbooks.api.intuit.com"
            if environment == "sandbox"
            else "https://quickbooks.api.intuit.com"
        )
        self.client = client or httpx.Client(timeout=DEFAULT_TIMEOUT)

    def authorization_url(self, *, redirect_uri: str, state: str, challenge: str) -> str:
        query = urlencode(
            dict(
                client_id=self.client_id,
                response_type="code",
                scope=SCOPE,
                redirect_uri=redirect_uri,
                state=state,
            )
        )
        return f"{AUTH_URL}?{query}"

    def _token(self, data: dict[str, str]) -> dict[str, Any]:
        response = send(
            self.client,
            "POST",
            TOKEN_URL,
            data=data,
            auth=(self.client_id, self.client_secret),
            headers={"Accept": "application/json"},
        )
        return json_body(response)

    def exchange_code(
        self, code: str, redirect_uri: str, verifier: str, callback: dict[str, str]
    ) -> ProviderTokens:
        realm = callback.get("realmId", "")
        if not realm.isdigit():
            raise ConnectorApiError(400, "missing_company")
        tokens = tokens_from(
            self._token(
                {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri}
            ),
            {"realm_id": realm},
        )
        name = ""
        try:
            info = json_body(
                send(
                    self.client,
                    "GET",
                    f"{self.api}/v3/company/{realm}/companyinfo/{realm}",
                    params={"minorversion": MINOR_VERSION},
                    headers=self._headers(tokens.access_token),
                )
            )
            name = str(info.get("CompanyInfo", {}).get("CompanyName", ""))
        except ConnectorApiError:
            name = ""
        return ProviderTokens(
            tokens.access_token,
            tokens.refresh_token,
            tokens.expires_in,
            {"realm_id": realm, "company_name": name},
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
                json={"token": refresh_token},
                auth=(self.client_id, self.client_secret),
                headers={"Accept": "application/json"},
            )
        except ConnectorApiError:
            return

    def account_name(self, context: dict[str, str]) -> str:
        return context.get("company_name") or f"Company {context.get('realm_id', '')}"

    @staticmethod
    def _headers(access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

    def sources(self, session: ConnectorSession, parent: str | None) -> list[Source]:
        return [Source(entity, label) for entity, label in ENTITIES] if parent is None else []

    def fetch(
        self, session: ConnectorSession, source_id: str, max_rows: int
    ) -> list[dict[str, Any]]:
        if source_id not in dict(ENTITIES):
            raise ConnectorApiError(404, "unknown_source")
        realm = session.context.get("realm_id", "")
        records: list[dict[str, Any]] = RecordBuffer()
        while len(records) < max_rows:
            size = min(PAGE, max_rows - len(records))
            body = json_body(
                send(
                    self.client,
                    "GET",
                    f"{self.api}/v3/company/{realm}/query",
                    params={
                        "query": f"select * from {source_id} "
                        f"STARTPOSITION {len(records) + 1} MAXRESULTS {size}",
                        "minorversion": MINOR_VERSION,
                    },
                    headers=self._headers(session.access_token),
                )
            )
            batch = body.get("QueryResponse", {}).get(source_id, [])
            records.extend(batch)
            if len(batch) < size:
                break
        return records
