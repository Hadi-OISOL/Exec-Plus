"""Use case: Creates explicit fictional workflow and evaluation inputs.

What it does: Writes repeatable finance, sales, inventory, HR and company CSVs with
independent decimal oracles, review instructions and integrity metadata. No import
or network action occurs, and existing edited files are preserved.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, localcontext
from io import StringIO
from pathlib import Path
from typing import Any

VERSION = "execplus-synthetic-workflow-v1"


def csv_bytes(headers: tuple[str, ...], rows: Sequence[tuple[str, ...]]) -> bytes:
    stream = StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def decimal_oracle(
    headers: tuple[str, ...], rows: Sequence[tuple[str, ...]], field: str
) -> dict[str, Any]:
    """Independent fixture arithmetic; invalid cells never become zero observations."""
    index = headers.index(field)
    present: list[Decimal] = []
    missing = invalid = 0
    with localcontext() as context:
        context.prec = 80
        for row in rows:
            value = row[index]
            if value == "":
                missing += 1
                continue
            try:
                number = Decimal(value)
                if not number.is_finite():
                    raise InvalidOperation
            except InvalidOperation:
                invalid += 1
            else:
                present.append(number)
        return {
            "field": field,
            "valid_numeric_cells": len(present),
            "missing_cells": missing,
            "invalid_numeric_cells": invalid,
            "sum_valid_numeric_cells": str(sum(present, Decimal(0))) if present else None,
            "minimum": str(min(present)) if present else None,
            "maximum": str(max(present)) if present else None,
            "numeric_parse_complete": invalid == 0,
        }


def artifacts() -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    entries: list[dict[str, Any]] = []

    def add(
        name: str,
        domain: str,
        row_meaning: str,
        headers: tuple[str, ...],
        rows: Sequence[tuple[str, ...]],
        units: dict[str, str],
        notes: list[str],
        *,
        rejected: str | None = None,
    ) -> None:
        body = csv_bytes(headers, rows)
        files[name] = body
        entries.append(
            {
                "file": name,
                "domain": domain,
                "one_row": row_meaning,
                "rows": len(rows),
                "columns": list(headers),
                "units": units,
                "sha256": hashlib.sha256(body).hexdigest(),
                "bytes": len(body),
                "notes": notes,
                "expected_rejection": rejected,
                "oracles": [decimal_oracle(headers, rows, field) for field in units],
                "duplicate_rows": len(rows) - len(set(rows)),
                "shared_definitions_require_explicit_confirmation": True,
            }
        )

    start = date(2025, 1, 1)
    finance = [
        (
            (start + timedelta(days=i)).isoformat(),
            "Retail" if i % 2 else "Services",
            str(Decimal(100) + Decimal(i) / 10),
            str(Decimal(60) + Decimal(i) / 20),
        )
        for i in range(120)
    ]
    add(
        "finance-daily.csv",
        "finance",
        "one complete day of fictional activity",
        ("date", "category", "revenue", "cost"),
        finance,
        {"revenue": "USD", "cost": "USD"},
        [
            "Complete daily coverage is explicitly generated, not inferred from a date range.",
            "Revenue and cost are additive daily flows; the category labels do not explain causes.",
        ],
    )
    sales = [
        (
            f"order-{2 * i + j + 1}",
            (start + timedelta(days=i)).isoformat(),
            "North" if j == 0 else "South",
            "A" if j == 0 else "B",
            str(i % 5 + 1),
            "2.50" if j == 0 else "4.00",
            str(Decimal(i % 5 + 1) * Decimal("2.50" if j == 0 else "4.00")),
            str(Decimal(i % 5 + 1) * Decimal("1.10" if j == 0 else "2.20")),
        )
        for i in range(120)
        for j in range(2)
    ]
    add(
        "sales-orders.csv",
        "sales",
        "one fictional order line",
        ("order_id", "date", "region", "product", "units", "unit_price", "revenue", "cost"),
        sales,
        {"units": "items", "unit_price": "USD/item", "revenue": "USD", "cost": "USD"},
        [
            "unit_price is not additive; revenue = units * unit_price.",
            "The declared prices and costs are fictional inputs, not learned effects.",
        ],
    )
    inventory = [
        (
            (start + timedelta(days=i)).isoformat(),
            "A" if j == 0 else "B",
            "Main",
            str(100 + 2 * i if j == 0 else 200 - i),
            "3" if j == 0 else "1",
            "1" if j == 0 else "2",
        )
        for i in range(30)
        for j in range(2)
    ]
    add(
        "inventory-snapshots.csv",
        "inventory",
        "one SKU at the end of one day",
        ("date", "sku", "warehouse", "on_hand", "received", "dispatched"),
        inventory,
        {"on_hand": "items", "received": "items", "dispatched": "items"},
        [
            "Do not total on_hand across dates; it is a snapshot, not a flow.",
            "Final-day on_hand across the two SKUs is exactly 329 items.",
        ],
    )
    hr = [
        (
            f"employee-{i + 1}",
            ("Finance", "Sales", "Operations")[i % 3],
            str(1000 + 25 * i),
            "0.5" if i % 4 == 0 else "1",
            str(i + 1),
            "active",
        )
        for i in range(24)
    ]
    add(
        "hr-workforce.csv",
        "hr",
        "one fictional employee at a single snapshot",
        ("employee_id", "department", "salary", "fte", "tenure_months", "employment_status"),
        hr,
        {"salary": "USD/month", "fte": "full-time equivalents", "tenure_months": "months"},
        [
            "Employee identifiers are fictional and must not be summed.",
            "A snapshot does not establish hiring, turnover, fairness or causes.",
        ],
    )
    for company in ("A", "B"):
        amounts = (
            ("100.00", "-100.00", "20.00", "-20.00")
            if company == "A"
            else ("80.00", "-80.00", "-16.00", "16.00")
        )
        company_rows = [
            ("2025-01", account, amount, "USD" if company == "A" else "EUR", company)
            for account, amount in zip(
                ("Cash", "Equity", "Intercompany", "Internal offset"), amounts, strict=True
            )
        ]
        add(
            f"company-{company.lower()}.csv",
            "finance",
            "one declared company/account/period balance",
            ("period", "account", "amount", "currency", "company"),
            company_rows,
            {"amount": "USD" if company == "A" else "EUR"},
            [
                "Use a separate explicitly authorized company workspace for each file.",
                "Fictional rates: A:1 USD/USD and B:1.25 USD/EUR; confirm explicitly.",
                "No intercompany elimination or access grant is inferred or automatically applied.",
            ],
        )
    add(
        "dirty-review.csv",
        "finance",
        "one imported record requiring review",
        ("date", "category", "revenue", "cost"),
        [
            ("2025-01-01", " A ", "100.000000000000000001", "60"),
            ("2025-01-01", " A ", "100.000000000000000001", "60"),
            ("not-a-date", "B", "0", ""),
            ("2025-01-03", "B", "bad-number", "1"),
            ("2025-01-04", "B", "-12.5", "0"),
        ],
        {"revenue": "USD", "cost": "USD"},
        [
            "Duplicate, whitespace, missing cost, bad date and bad number are intentional.",
            "Oracles cover valid cells only; they never authorize dropping or coercing data.",
            "Preview cleaning and confirm field meanings before a governed calculation.",
        ],
    )
    add(
        "precision-and-nulls.csv",
        "other",
        "one synthetic exact-value observation",
        ("id", "amount", "unit"),
        [
            ("1", "9007199254740993.000000000000000001", "USD"),
            ("2", "-9007199254740993", "USD"),
            ("3", "0", "USD"),
            ("4", "", "USD"),
        ],
        {"amount": "USD"},
        [
            "Exact mathematical sum is 0.000000000000000001.",
            "An engine that cannot retain this scale must refuse or disclose its limitation.",
        ],
    )
    add(
        "formula-rejected.csv",
        "other",
        "one deliberately unsafe upload fixture",
        ("label", "amount"),
        [("=1+1", "10")],
        {"amount": "USD"},
        ["Expected upload rejection; never silently sanitize the original file."],
        rejected="unsafe_formula",
    )
    manifest = {
        "version": VERSION,
        "synthetic": True,
        "automatic_import": False,
        "description": "All companies, employees, amounts, rates and outcomes are fictional.",
        "datasets": entries,
    }
    files["manifest.json"] = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode()
    files["START-HERE.txt"] = (
        b"ExecPlus fictional workflow kit\n\n"
        b"Generate files explicitly, then upload one CSV through the normal local UI.\n"
        b"Review quality/meaning/units, preview cleaning and keep original evidence.\n"
        b"Start with finance-daily.csv; sales and inventory are different row meanings.\n"
        b"Use separate company workspaces. Grants, mappings, rates and\n"
        b"eliminations need explicit authorization. No customer data/provider is needed.\n"
        b"dirty-review.csv requires review. formula-rejected.csv must be rejected.\n"
        b"This generator never connects, uploads, confirms or changes existing data.\n"
    )
    return files


def create(destination: Path) -> None:
    files = artifacts()
    if destination.is_symlink():
        raise ValueError("Choose a real local directory, not a symbolic link.")
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        path = destination / name
        if path.is_symlink() or (path.exists() and path.read_bytes() != content):
            raise FileExistsError(f"Preserve {path}; use a new directory for changed fixtures.")
    for name, content in files.items():
        (destination / name).write_bytes(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data/synthetic-workflow-v1",
    )
    args = parser.parse_args()
    create(args.output)
    print(f"Explicit fictional files are ready in {args.output}; nothing was imported.")


if __name__ == "__main__":
    main()
