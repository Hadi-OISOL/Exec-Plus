"""Use case: Reads accounting records from Zoho Books with the user's own consent.

What it does: Runs the Zoho OAuth exchange for the right data centre and pages through a list.
"""

import re
from typing import Any
from urllib.parse import urlencode

import httpx

from execplus.application.connector_ports import (
    ConnectorApiError,
    ConnectorField,
    ConnectorSession,
    ProviderTokens,
)
from execplus.domain.connectors import Source
from execplus.infrastructure.connectors.base import (
    DEFAULT_TIMEOUT,
    json_body,
    send,
    tokens_from,
)

SCOPES = ",".join(
    f"ZohoBooks.{module}.READ"
    for module in (
        "invoices",
        "bills",
        "contacts",
        "customerpayments",
        "vendorpayments",
        "expenses",
        "salesorders",
        "purchaseorders",
        "creditnotes",
        "settings",
        "accountants",
    )
)
ACCOUNTS_HOST = re.compile(r"https://accounts\.zoho\.[a-z.]{2,10}")
API_HOST = re.compile(r"https://(www\.)?zohoapis\.[a-z.]{2,10}")
PAGE = 200
LISTS = (
    ("invoices", "Invoices"),
    ("bills", "Bills"),
    ("customerpayments", "Customer payments"),
    ("vendorpayments", "Vendor payments"),
    ("expenses", "Expenses"),
    ("contacts", "Customers and vendors"),
    ("items", "Items"),
    ("chartofaccounts", "Chart of accounts"),
    ("salesorders", "Sales orders"),
    ("purchaseorders", "Purchase orders"),
    ("creditnotes", "Credit notes"),
)


class ZohoBooksConnector:
    id = "zoho_books"
    label = "Zoho Books"
    kind = "oauth"
    uses_pkce = False
    description = "Invoices, bills, payments, expenses, contacts, items and the chart of accounts."
    fields: tuple[ConnectorField, ...] = ()

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        data_center: str = "com",
        client: httpx.Client | None = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.accounts = f"https://accounts.zoho.{data_center}"
        self.client = client or httpx.Client(timeout=DEFAULT_TIMEOUT)

    def authorization_url(self, *, redirect_uri: str, state: str, challenge: str) -> str:
        query = urlencode(
            dict(
                scope=SCOPES,
                client_id=self.client_id,
                response_type="code",
                redirect_uri=redirect_uri,
                access_type="offline",
                prompt="consent",
                state=state,
            )
        )
        return f"{self.accounts}/oauth/v2/auth?{query}"

    def _token(self, accounts: str, data: dict[str, str]) -> dict[str, Any]:
        body = json_body(
            send(
                self.client,
                "POST",
                f"{accounts}/oauth/v2/token",
                data={**data, "client_id": self.client_id, "client_secret": self.client_secret},
            )
        )
        if "error" in body:
            raise ConnectorApiError(400, str(body["error"]))
        return body

    def exchange_code(
        self, code: str, redirect_uri: str, verifier: str, callback: dict[str, str]
    ) -> ProviderTokens:
        accounts = callback.get("accounts-server", "")
        accounts = accounts if ACCOUNTS_HOST.fullmatch(accounts) else self.accounts
        body = self._token(
            accounts,
            {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        )
        api_domain = str(body.get("api_domain", ""))
        if not API_HOST.fullmatch(api_domain):
            api_domain = "https://www.zohoapis.com"
        tokens = tokens_from(body)
        listing = json_body(
            send(
                self.client,
                "GET",
                f"{api_domain}/books/v3/organizations",
                headers={"Authorization": f"Zoho-oauthtoken {tokens.access_token}"},
            )
        )
        organisations = listing.get("organizations", [])
        if not organisations:
            raise ConnectorApiError(403, "no_organisation")
        chosen = organisations[0]
        return ProviderTokens(
            tokens.access_token,
            tokens.refresh_token,
            tokens.expires_in,
            {
                "api_domain": api_domain,
                "accounts_server": accounts,
                "organization_id": str(chosen.get("organization_id", "")),
                "organization_name": str(chosen.get("name", "")),
            },
        )

    def refresh(self, refresh_token: str, context: dict[str, str]) -> ProviderTokens:
        accounts = context.get("accounts_server", self.accounts)
        body = self._token(
            accounts, {"grant_type": "refresh_token", "refresh_token": refresh_token}
        )
        return tokens_from(body, context)

    def revoke(self, refresh_token: str) -> None:
        try:
            send(
                self.client,
                "POST",
                f"{self.accounts}/oauth/v2/token/revoke",
                params={"token": refresh_token},
            )
        except ConnectorApiError:
            return

    def account_name(self, context: dict[str, str]) -> str:
        return context.get("organization_name") or "Zoho Books organisation"

    def sources(self, session: ConnectorSession, parent: str | None) -> list[Source]:
        return [Source(name, label) for name, label in LISTS] if parent is None else []

    def fetch(
        self, session: ConnectorSession, source_id: str, max_rows: int
    ) -> list[dict[str, Any]]:
        if source_id not in dict(LISTS):
            raise ConnectorApiError(404, "unknown_source")
        base = session.context.get("api_domain", "")
        if not API_HOST.fullmatch(base):
            raise ConnectorApiError(400, "invalid_domain")
        records: list[dict[str, Any]] = []
        page = 1
        while len(records) < max_rows:
            body = json_body(
                send(
                    self.client,
                    "GET",
                    f"{base}/books/v3/{source_id}",
                    params={
                        "organization_id": session.context.get("organization_id", ""),
                        "page": str(page),
                        "per_page": str(PAGE),
                    },
                    headers={"Authorization": f"Zoho-oauthtoken {session.access_token}"},
                )
            )
            if body.get("code", 0) != 0:
                raise ConnectorApiError(400, str(body.get("code")))
            records.extend(body.get(source_id, []))
            if not body.get("page_context", {}).get("has_more_page"):
                break
            page += 1
        return records[:max_rows]
