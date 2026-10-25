"""Use case: Describes Parquet-backed profile-v5/v6 snapshots and their scale-safe profiles.

What it does: Turns exact per-column aggregate counts into the profile-v6 shape (profile-v4
rules plus spelled-month dates; earlier uploads keep their stored profile-v5), records the
immutable columnar manifest, and supplies a table whose rows are only materialized from
the retained original when a row-level feature needs them.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Protocol

from execplus.domain.ingestion import IngestionError
from execplus.domain.profiling import PROFILE_V6, TableData, _identifier_header
from execplus.domain.sampling import SEED, sample_positions

COLUMNAR_FORMAT = "parquet-v1"
_CALENDAR_BOUNDS = {"day": 31, "dayofmonth": 31, "month": 12, "monthofyear": 12, "year": 9999}
_TYPED = frozenset({"integer", "decimal", "date", "boolean"})


@dataclass(frozen=True, slots=True)
class ColumnStats:
    """Exact counts over stripped cells; placeholder cells are counted inside `text`."""

    empty: int
    boolean: int
    date: int
    invalid_date: int
    integer: int
    decimal: int
    text: int
    distinct: int
    placeholders: int
    distinct_placeholders: int
    date_min: str | None
    date_max: str | None
    integer_min: float | None
    integer_max: float | None
    moments: int
    timed: int
    aware: int
    moment_min: str | None
    moment_max: str | None


@dataclass(frozen=True, slots=True)
class ColumnarManifest:
    key: str
    sha256: str
    size: int
    rows: int
    errors: dict[str, str]

    def record(self) -> dict[str, object]:
        return {
            "format": COLUMNAR_FORMAT,
            "key": self.key,
            "sha256": self.sha256,
            "size": self.size,
            "rows": self.rows,
            "errors": dict(self.errors),
        }

    @classmethod
    def of(cls, profile: dict[str, Any]) -> "ColumnarManifest | None":
        entry = profile.get("columnar")
        if not isinstance(entry, dict):
            return None
        if entry.get("format") != COLUMNAR_FORMAT:
            raise IngestionError(
                "unsupported_version", "This columnar snapshot version is unavailable.", 409
            )
        return cls(
            str(entry["key"]),
            str(entry["sha256"]),
            int(entry["size"]),
            int(entry["rows"]),
            {str(name): str(message) for name, message in dict(entry["errors"]).items()},
        )


@dataclass(frozen=True, slots=True)
class ColumnarConversion:
    format: str
    headers: tuple[str, ...]
    profile: dict[str, object]
    parquet: str
    sha256: str
    size: int
    rows: int
    errors: dict[str, str]


class ParquetReader(Protocol):
    def values(self, path: str, column: str, limit: int) -> tuple[str, ...]: ...

    def missing(self, path: str, column: str) -> int: ...

    def rows_at(self, path: str, positions: tuple[int, ...]) -> tuple[tuple[str, ...], ...]: ...


class ColumnarTable(TableData):
    """A snapshot queried from typed Parquet; legacy row consumers get the original strings."""

    manifest: ColumnarManifest
    _parquet_path: Callable[[], str]
    _materialize: Callable[[], TableData]
    _head: Callable[[int], tuple[tuple[str, ...], ...]]
    _rows: tuple[tuple[str, ...], ...] | None
    _reader: ParquetReader | None

    def __init__(
        self,
        headers: tuple[str, ...],
        manifest: ColumnarManifest,
        parquet_path: Callable[[], str],
        materialize: Callable[[], TableData],
        head: Callable[[int], tuple[tuple[str, ...], ...]] | None = None,
        reader: ParquetReader | None = None,
    ) -> None:
        object.__setattr__(self, "_reader", reader)
        object.__setattr__(self, "headers", headers)
        object.__setattr__(self, "manifest", manifest)
        object.__setattr__(self, "_parquet_path", parquet_path)
        object.__setattr__(self, "_materialize", materialize)
        object.__setattr__(self, "_rows", None)
        object.__setattr__(self, "_head", head or (lambda limit: self.rows[:limit]))

    @property
    def rows(self) -> tuple[tuple[str, ...], ...]:
        rows = self._rows
        if rows is None:
            table = self._materialize()
            if table.headers != self.headers or len(table.rows) != self.manifest.rows:
                raise IngestionError(
                    "lineage_mismatch", "The retained source failed its integrity check.", 409
                )
            rows = table.rows
            object.__setattr__(self, "_rows", rows)
        return rows

    @property
    def row_count(self) -> int:
        return self.manifest.rows

    def head(self, limit: int) -> tuple[tuple[str, ...], ...]:
        """First rows as canonical text from Parquet (decimals without padding zeros)."""
        return self._head(limit)

    def parquet_path(self) -> str:
        return self._parquet_path()

    def _scan(self) -> ParquetReader:
        if self._reader is None:
            raise IngestionError(
                "storage_unavailable", "The columnar snapshot is unavailable.", 503
            )
        return self._reader

    def values(self, name: str, limit: int) -> tuple[str, ...]:
        """Exact distinct non-missing values over every row, first-seen order, at most `limit`."""
        return self._scan().values(self.parquet_path(), name, limit)

    def missing(self, name: str) -> int:
        """Exact count of missing cells over every row."""
        return self._scan().missing(self.parquet_path(), name)

    def sample(self, size: int, seed: int = SEED) -> TableData:
        """A reproducible uniform sample of rows as canonical text, kept in file order."""
        positions = sample_positions(self.row_count, size, seed)
        return TableData(self.headers, self._scan().rows_at(self.parquet_path(), positions))

    def checksum(self) -> str:
        return self.manifest.sha256


def _words(name: str) -> set[str]:
    return set(re.findall(r"[a-z]+", name.lower()))


def _column(name: str, stats: ColumnStats, rows: int, blank: bool) -> dict[str, Any]:
    placeholder = stats.placeholders if blank else 0
    empty = stats.empty + placeholder
    present = rows - empty
    numeric = stats.integer + stats.decimal
    words = _words(name)
    if words & {"date", "day"} or stats.date + stats.invalid_date > present / 2:
        inferred = "date"
    elif present and numeric > present / 2:
        inferred = "decimal" if stats.decimal else "integer"
    elif present and stats.boolean > present / 2:
        inferred = "boolean"
    else:
        inferred = "text" if present else "empty"
    invalid_dates = present - stats.date if inferred == "date" else stats.invalid_date
    type_conflicts = present - numeric if inferred in {"integer", "decimal"} else 0
    if inferred == "boolean":
        type_conflicts = present - stats.boolean
    identifier = bool(words & {"id", "code", "sku", "zip", "postal"})
    tags = sorted(words & {"revenue", "sales", "cost", "amount", "quantity", "stock", "price"})
    if identifier:
        tags.append("identifier")
    if inferred == "date":
        tags.append("date")
    return {
        "name": name,
        "type": inferred,
        "role": "metric" if inferred in {"integer", "decimal"} and not identifier else "dimension",
        "semantic_tags": tags,
        "missing": empty,
        "type_conflicts": type_conflicts,
        "invalid_dates": invalid_dates,
        "distinct_count": stats.distinct - (stats.distinct_placeholders if blank else 0),
        "date_min": stats.date_min,
        "date_max": stats.date_max,
    }


def typed_placeholder_columns(
    headers: tuple[str, ...], stats: tuple[ColumnStats, ...], rows: int
) -> frozenset[str]:
    return frozenset(
        name
        for name, entry in zip(headers, stats, strict=True)
        if entry.placeholders and _column(name, entry, rows, True)["type"] in _TYPED
    )


def profile_from_stats(
    headers: tuple[str, ...],
    stats: tuple[ColumnStats, ...],
    rows: int,
    duplicates: int,
) -> dict[str, object]:
    """Applies the in-memory profile-v6 rules to exact aggregates."""
    blanked = typed_placeholder_columns(headers, stats, rows)
    columns = []
    for name, entry in zip(headers, stats, strict=True):
        column = _column(name, entry, rows, name in blanked)
        present = rows - int(column["missing"])
        identifier = _identifier_header(name)
        bound = _CALENDAR_BOUNDS.get(re.sub(r"[^a-z]", "", name.lower()))
        calendar = (
            not identifier
            and bound is not None
            and present > 0
            and entry.integer == present
            and entry.integer_min is not None
            and entry.integer_max is not None
            and entry.integer_min >= 1
            and entry.integer_max <= bound
        )
        if identifier or calendar:
            column.update(
                type="text" if identifier else "integer",
                role="dimension",
                type_conflicts=0,
                invalid_dates=0,
                date_min=None,
                date_max=None,
                semantic_tags=sorted(
                    (set(column["semantic_tags"]) - {"date"})
                    | {"identifier" if identifier else "calendar_component"}
                ),
            )
        elif (
            column["role"] == "dimension"
            and column["type"] in {"text", "date"}
            and not {"identifier", "calendar_component"} & set(column["semantic_tags"])
            and present > 0
            and entry.moments == present
            and entry.timed > 0
            and entry.aware in {0, entry.moments}
        ):
            column.update(
                type="date",
                datetime=True,
                timezone="UTC" if entry.aware else "as_given",
                type_conflicts=0,
                invalid_dates=0,
                date_min=entry.moment_min,
                date_max=entry.moment_max,
                semantic_tags=sorted(set(column["semantic_tags"]) | {"date", "datetime"}),
            )
        if name in blanked:
            column["missing_placeholders"] = entry.placeholders
        columns.append(column)
    cells = rows * len(headers)
    conflicts = sum(int(column["type_conflicts"]) for column in columns)
    invalid = sum(int(column["invalid_dates"]) for column in columns)
    checks = [
        (
            "missing_values",
            sum(int(column["missing"]) for column in columns),
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
        "algorithm": PROFILE_V6,
        "row_count": rows,
        "column_count": len(headers),
        "columns": columns,
        "quality_score": str(score),
        "quality_checks": [
            {"code": code, "count": count, "denominator": total, "explanation": explanation}
            for code, count, total, explanation in checks
        ],
    }
