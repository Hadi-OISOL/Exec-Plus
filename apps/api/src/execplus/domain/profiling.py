"""Use case: Defines reproducible profiling and reversible table transformations.

What it does: Computes bounded metadata and quality explanations without model calls.
"""

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import TypedDict
from uuid import UUID

from execplus.domain.ingestion import IngestionError

ALGORITHM = "profile-v1"


class Cleaning(TypedDict):
    trim: bool
    drop_duplicates: bool
    drop_missing: bool
    mapping: dict[str, str]


@dataclass(frozen=True)
class TableData:
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    def checksum(self) -> str:
        encoded = json.dumps(
            [self.headers, self.rows], ensure_ascii=False, separators=(",", ":")
        ).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class Revision:
    id: UUID
    workspace_id: UUID
    dataset_id: UUID
    upload_id: UUID
    parent_id: UUID | None
    algorithm: str
    source_checksum: str
    output_checksum: str
    recipe: list[Cleaning]
    profile: dict[str, object]
    created_by: UUID
    created_at: datetime


@dataclass(frozen=True)
class UsageEvent:
    id: UUID
    workspace_id: UUID
    actor_id: UUID
    kind: str
    quantity: int
    resource_id: UUID
    created_at: datetime


def cell_type(value: str) -> str:
    value = value.strip()
    if not value:
        return "empty"
    if value.lower() in {"true", "false"}:
        return "boolean"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            date.fromisoformat(value)
            return "date"
        except ValueError:
            return "invalid_date"
    if re.fullmatch(r"-?(0|[1-9]\d*)(\.\d+)?([eE][+-]?\d+)?", value):
        try:
            number = Decimal(value)
            if number.is_finite():
                return "integer" if number == number.to_integral_value() else "decimal"
        except InvalidOperation:
            pass
    return "text"


def profile(table: TableData) -> dict[str, object]:
    columns: list[dict[str, object]] = []
    missing = conflicts = invalid = 0
    for index, name in enumerate(table.headers):
        values = [row[index].strip() for row in table.rows]
        types = Counter(cell_type(value) for value in values)
        present = len(values) - types["empty"]
        words = set(re.findall(r"[a-z]+", name.lower()))
        date_hint = bool(words & {"date", "day"})
        numeric = types["integer"] + types["decimal"]
        if date_hint or types["date"] + types["invalid_date"] > present / 2:
            inferred = "date"
        elif present and numeric > present / 2:
            inferred = "decimal" if types["decimal"] else "integer"
        elif present and types["boolean"] > present / 2:
            inferred = "boolean"
        else:
            inferred = "text" if present else "empty"
        invalid_dates = present - types["date"] if inferred == "date" else types["invalid_date"]
        type_conflicts = present - numeric if inferred in {"integer", "decimal"} else 0
        if inferred == "boolean":
            type_conflicts = present - types["boolean"]
        identifier = bool(words & {"id", "code", "sku", "zip", "postal"})
        role = "metric" if inferred in {"integer", "decimal"} and not identifier else "dimension"
        tags = sorted(words & {"revenue", "sales", "cost", "amount", "quantity", "stock", "price"})
        if identifier:
            tags.append("identifier")
        if inferred == "date":
            tags.append("date")
        dates = sorted(value for value in values if cell_type(value) == "date")
        columns.append(
            {
                "name": name,
                "type": inferred,
                "role": role,
                "semantic_tags": tags,
                "missing": types["empty"],
                "type_conflicts": type_conflicts,
                "invalid_dates": invalid_dates,
                "distinct_count": len(set(values) - {""}),
                "date_min": dates[0] if dates else None,
                "date_max": dates[-1] if dates else None,
            }
        )
        missing += types["empty"]
        conflicts += type_conflicts
        invalid += invalid_dates
    rows = len(table.rows)
    cells = rows * len(table.headers)
    duplicates = rows - len(set(table.rows))
    checks = [
        (
            "missing_values",
            missing,
            cells,
            "Fill missing cells in the source or preview removing incomplete rows.",
        ),
        (
            "duplicate_rows",
            duplicates,
            rows,
            "Review repeated rows; remove duplicates only when they are accidental.",
        ),
        (
            "type_conflicts",
            conflicts,
            cells,
            "Correct values that differ from the majority numeric or boolean type in the source.",
        ),
        (
            "invalid_dates",
            invalid,
            cells,
            "Use real calendar dates in YYYY-MM-DD format; ambiguous dates need source correction.",
        ),
        (
            "unsupported_structures",
            0,
            1,
            "Structure passed upload validation. Unsupported files are rejected before storage.",
        ),
    ]
    penalty = sum(Decimal(count) / max(total, 1) for _, count, total, _ in checks)
    score = (Decimal(100) - 20 * penalty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "algorithm": ALGORITHM,
        "row_count": rows,
        "column_count": len(table.headers),
        "columns": columns,
        "quality_score": str(score),
        "quality_checks": [
            {"code": code, "count": count, "denominator": total, "explanation": explanation}
            for code, count, total, explanation in checks
        ],
    }


def transform(table: TableData, step: Cleaning) -> TableData:
    mapping = step["mapping"]
    if set(mapping) - set(table.headers):
        raise IngestionError("invalid_mapping", "Map only columns in the current revision.", 422)
    headers = tuple(mapping[name].strip() if name in mapping else name for name in table.headers)
    targets = [value.strip() for value in mapping.values()]
    if (
        any(not name or len(name) > 100 or any(ord(c) < 32 for c in name) for name in targets)
        or len({name.strip().casefold() for name in headers}) != len(headers)
        or any(name.lstrip().startswith(("=", "+", "-", "@")) for name in targets)
    ):
        raise IngestionError(
            "invalid_mapping", "Use unique, printable column names (1-100 characters).", 422
        )
    rows = table.rows
    if step["trim"]:
        rows = tuple(tuple(value.strip() for value in row) for row in rows)
    if step["drop_missing"]:
        rows = tuple(row for row in rows if all(value.strip() for value in row))
    if step["drop_duplicates"]:
        rows = tuple(dict.fromkeys(rows))
    if not rows:
        raise IngestionError(
            "empty_result", "This cleaning would remove every row. Change the options.", 422
        )
    return TableData(headers, rows)


def reconstruct(table: TableData, revision: Revision) -> TableData:
    if revision.algorithm != ALGORITHM:
        raise IngestionError("unsupported_version", "This profiling version is unavailable.", 409)
    for step in revision.recipe:
        table = transform(table, step)
    if table.checksum() != revision.output_checksum:
        raise IngestionError(
            "lineage_mismatch", "The reconstructed data failed its integrity check.", 409
        )
    return table
