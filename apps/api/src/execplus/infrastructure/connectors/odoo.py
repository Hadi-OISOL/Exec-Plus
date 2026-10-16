"""Use case: Reads accounting and contact records from an Odoo server with a user's API key.

What it does: Authenticates over JSON-RPC, keeps only existing fields and pages through results.
"""

from typing import Any
from urllib.parse import urlparse

import httpx

from execplus.application.connector_ports import (
    ConnectorApiError,
    ConnectorField,
    ConnectorSession,
)
from execplus.domain.connectors import Source
from execplus.infrastructure.connectors.base import DEFAULT_TIMEOUT, HostPolicy, json_body, send

PAGE = 500
INVOICE_TYPES = ["out_invoice", "out_refund"]
BILL_TYPES = ["in_invoice", "in_refund"]
LISTS: dict[str, tuple[str, str, list[Any], tuple[str, ...]]] = {
    "invoices": (
        "Customer invoices",
        "account.move",
        [["move_type", "in", INVOICE_TYPES]],
        (
            "name",
            "partner_id",
            "invoice_date",
            "invoice_date_due",
            "move_type",
            "state",
            "payment_state",
            "currency_id",
            "amount_untaxed",
            "amount_tax",
            "amount_total",
            "amount_residual",
            "invoice_origin",
            "ref",
        ),
    ),
    "vendor_bills": (
        "Vendor bills",
        "account.move",
        [["move_type", "in", BILL_TYPES]],
        (
            "name",
            "partner_id",
            "invoice_date",
            "invoice_date_due",
            "move_type",
            "state",
            "payment_state",
            "currency_id",
            "amount_untaxed",
            "amount_tax",
            "amount_total",
            "amount_residual",
            "ref",
        ),
    ),
    "invoice_lines": (
        "Invoice and bill lines",
        "account.move.line",
        [["move_id.move_type", "in", INVOICE_TYPES + BILL_TYPES], ["display_type", "=", "product"]],
        (
            "move_id",
            "partner_id",
            "date",
            "product_id",
            "name",
            "quantity",
            "price_unit",
            "discount",
            "price_subtotal",
            "price_total",
            "account_id",
            "currency_id",
        ),
    ),
    "payments": (
        "Payments",
        "account.payment",
        [],
        (
            "name",
            "partner_id",
            "date",
            "payment_type",
            "partner_type",
            "state",
            "amount",
            "currency_id",
            "journal_id",
        ),
    ),
    "partners": (
        "Customers and vendors",
        "res.partner",
        [],
        (
            "name",
            "email",
            "phone",
            "city",
            "country_id",
            "customer_rank",
            "supplier_rank",
            "create_date",
        ),
    ),
    "products": (
        "Products",
        "product.product",
        [],
        ("name", "default_code", "list_price", "standard_price", "type", "categ_id", "active"),
    ),
    "chart_of_accounts": (
        "Chart of accounts",
        "account.account",
        [],
        ("code", "name", "account_type", "reconcile", "currency_id"),
    ),
    "sales_orders": (
        "Sales orders",
        "sale.order",
        [],
        (
            "name",
            "partner_id",
            "date_order",
            "state",
            "amount_untaxed",
            "amount_tax",
            "amount_total",
            "currency_id",
        ),
    ),
    "purchase_orders": (
        "Purchase orders",
        "purchase.order",
        [],
        (
            "name",
            "partner_id",
            "date_order",
            "state",
            "amount_untaxed",
            "amount_tax",
            "amount_total",
            "currency_id",
        ),
    ),
}


class OdooConnector:
    id = "odoo"
    label = "Odoo"
    kind = "credentials"
    description = (
        "Customer invoices, vendor bills, lines, payments, contacts, products and accounts."
    )
    fields = (
        ConnectorField("url", "Odoo address", placeholder="https://yourcompany.odoo.com"),
        ConnectorField("database", "Database name"),
        ConnectorField("login", "Login (email or username)"),
        ConnectorField("api_key", "API key", secret=True),
    )

    def __init__(self, policy: HostPolicy, client: httpx.Client | None = None) -> None:
        self.policy = policy
        self.client = client or httpx.Client(timeout=DEFAULT_TIMEOUT)

    def _call(self, base: str, service: str, method: str, args: list[Any]) -> Any:
        body = json_body(
            send(
                self.client,
                "POST",
                f"{base}/jsonrpc",
                json={
                    "jsonrpc": "2.0",
                    "method": "call",
                    "params": {"service": service, "method": method, "args": args},
                    "id": 1,
                },
            )
        )
        if "error" in body:
            data = body["error"].get("data", {}) if isinstance(body["error"], dict) else {}
            name = str(data.get("name", ""))
            status = 403 if "AccessError" in name else 404 if "KeyError" in name else 400
            raise ConnectorApiError(status, "odoo_error")
        return body.get("result")

    def _login(self, credentials: dict[str, str]) -> tuple[str, int]:
        base = self.policy.check_url(credentials.get("url", ""))
        for name in ("database", "login", "api_key"):
            if not credentials.get(name, "").strip():
                raise ConnectorApiError(422, "missing_field")
        uid = self._call(
            base,
            "common",
            "authenticate",
            [credentials["database"], credentials["login"], credentials["api_key"], {}],
        )
        if not isinstance(uid, int) or isinstance(uid, bool):
            raise ConnectorApiError(401, "invalid_login")
        return base, uid

    def validate(self, credentials: dict[str, str]) -> str:
        base, _ = self._login(credentials)
        return f"{urlparse(base).hostname} / {credentials['database']}"

    def sources(self, session: ConnectorSession, parent: str | None) -> list[Source]:
        return [Source(key, value[0]) for key, value in LISTS.items()] if parent is None else []

    def _execute(
        self,
        base: str,
        credentials: dict[str, str],
        uid: int,
        model: str,
        method: str,
        args: list[Any],
        kwargs: dict[str, Any],
    ) -> Any:
        return self._call(
            base,
            "object",
            "execute_kw",
            [credentials["database"], uid, credentials["api_key"], model, method, args, kwargs],
        )

    def fetch(
        self, session: ConnectorSession, source_id: str, max_rows: int
    ) -> list[dict[str, Any]]:
        if source_id not in LISTS:
            raise ConnectorApiError(404, "unknown_source")
        _, model, domain, wanted = LISTS[source_id]
        credentials = session.context
        base, uid = self._login(credentials)
        available = self._execute(
            base, credentials, uid, model, "fields_get", [], {"attributes": ["type"]}
        )
        fields = [name for name in wanted if name in available]
        records: list[dict[str, Any]] = []
        while len(records) < max_rows:
            batch = self._execute(
                base,
                credentials,
                uid,
                model,
                "search_read",
                [domain],
                {
                    "fields": fields,
                    "limit": min(PAGE, max_rows - len(records)),
                    "offset": len(records),
                    "order": "id",
                },
            )
            records.extend(self._clean(row, available) for row in batch)
            if len(batch) < PAGE:
                break
        return records

    @staticmethod
    def _clean(row: dict[str, Any], available: dict[str, Any]) -> dict[str, Any]:
        cleaned: dict[str, Any] = {}
        for key, value in row.items():
            kind = available.get(key, {}).get("type")
            if kind == "many2one":
                if isinstance(value, list) and len(value) == 2:
                    cleaned[f"{key}_id"], cleaned[f"{key}_name"] = value
                else:
                    cleaned[f"{key}_id"], cleaned[f"{key}_name"] = None, None
            elif value is False and kind != "boolean":
                cleaned[key] = None
            else:
                cleaned[key] = value
        return cleaned
