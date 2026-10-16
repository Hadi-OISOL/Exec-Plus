"""Use case: Selects complete prepared ledger rows for an exact consolidation.

What it does: Requires confirmed fields and currency, refuses hidden required
filters, and preserves raw account and counterparty identities in query evidence.
"""

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from execplus.domain.ingestion import IngestionError
from execplus.domain.models import QueryPlan, QueryResult, Scalar, WorkspaceScope
from execplus.domain.profiling import TableData
from execplus.domain.semantics import (
    AggregationKind,
    DatasetView,
    MetricRequest,
    quote_identifier,
    validate_read_only,
)
from execplus.domain.understanding import governed_request

MAX_LEDGER_ROWS = 10_000


def invalid(message: str) -> IngestionError:
    return IngestionError("consolidation_source", message, 422)


def projection_fields(view: DatasetView, table: TableData, raw: dict[str, Any]) -> tuple[str, ...]:
    definition = view.definition or {}
    meanings = {item["name"]: item for item in definition.get("columns", [])}
    account, amount = raw["account_column"], raw["amount_column"]
    counterparty = raw.get("counterparty_column")
    fields = (account, amount, counterparty) if counterparty else (account, amount)
    if (
        not view.sources[0].get("understanding_id")
        or len(set(fields)) != len(fields)
        or any(name not in meanings or name not in table.headers for name in fields)
        or meanings.get(account, {}).get("role") not in {"dimension", "identifier", "ordinal"}
        or amount not in view.metrics
        or meanings.get(amount, {}).get("role") != "metric"
        or (counterparty and meanings[counterparty]["role"] not in {"dimension", "identifier"})
    ):
        raise invalid("Choose confirmed account, amount and optional counterparty fields.")
    meaning = meanings[amount]
    if (
        meaning.get("unit_column")
        or not raw.get("currency")
        or (meaning.get("currency") or meaning.get("unit")) != raw["currency"]
    ):
        raise invalid("The company currency must match the amount field's confirmed fixed unit.")
    request = governed_request(view, table, MetricRequest(amount, AggregationKind.SUM))
    if request.filters:
        raise invalid(
            "This amount has required row filters. Prepare an explicitly complete ledger "
            "without measure-specific row exclusions before consolidating."
        )
    if not table.rows or len(table.rows) > MAX_LEDGER_ROWS:
        raise invalid("Use a complete prepared ledger with one to 10,000 rows per company.")
    return fields


def ledger_plan(
    scope: WorkspaceScope, did: UUID, view: DatasetView, table: TableData, raw: dict[str, Any]
) -> QueryPlan:
    fields = projection_fields(view, table, raw)
    selected = ", ".join(quote_identifier(name) for name in fields)
    sql = f'SELECT {selected} FROM "dataset" ORDER BY {selected} LIMIT {MAX_LEDGER_ROWS + 1}'
    validate_read_only(sql)
    return QueryPlan(uuid4(), scope.workspace_id, did, "Read complete prepared ledger", sql)


def identity(value: Scalar, label: str) -> str:
    if isinstance(value, bool) or not isinstance(value, str | int):
        raise invalid(f"Every {label} must be an exact text or integer identifier.")
    text = str(value)
    if not text.strip() or len(text) > 200 or "\x00" in text:
        raise invalid(f"Every {label} needs a nonempty identifier of at most 200 characters.")
    return text


def exact_ledger_rows(value: QueryResult) -> tuple[tuple[str, Decimal, str | None], ...]:
    if not 1 <= len(value.rows) <= MAX_LEDGER_ROWS or len(value.columns) not in {2, 3}:
        raise invalid("The complete ledger must contain one to 10,000 rows.")
    rows = []
    for row in value.rows:
        account = identity(row[0], "account")
        amount = row[1]
        if isinstance(amount, bool) or not isinstance(amount, int | Decimal):
            raise invalid(
                "Every ledger amount must be an exact number; missing amounts stop the run."
            )
        numeric = Decimal(amount)
        if not numeric.is_finite():
            raise invalid("Every ledger amount must be finite.")
        party = None if len(row) == 2 or row[2] is None else identity(row[2], "counterparty")
        rows.append((account, numeric, party))
    return tuple(rows)
