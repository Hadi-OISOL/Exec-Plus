"""Use case: Reads one stored upload format into an all-text DuckDB relation.

What it does: Gives every format the same contract (validated headers plus a relation of
VARCHAR columns in source order) so new formats plug into the columnar ingest unchanged.
"""

import csv
from collections.abc import Callable
from io import TextIOWrapper
from pathlib import Path

import duckdb

from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.file_parser import (
    CSV_DELIMITERS,
    MAX_COLUMNS,
    StructuredFileParser,
    validate_cell,
    validate_header,
)

Reader = Callable[
    [duckdb.DuckDBPyConnection, Path, str, Path],
    tuple[tuple[str, ...], duckdb.DuckDBPyRelation],
]


def sql_text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _headers(path: Path, delimiter: str) -> tuple[str, ...]:
    with path.open("rb") as raw:
        wrapper = TextIOWrapper(raw, encoding="utf-8-sig", newline="")
        try:
            header = next(csv.reader(wrapper, delimiter=delimiter, strict=True), [])
        except (csv.Error, UnicodeError) as error:
            raise IngestionError(
                "malformed_csv", "Use a well-formed UTF-8 CSV with consistent quoting.", 422
            ) from error
    validate_header(list(header))
    if len(header) > MAX_COLUMNS:
        raise IngestionError(
            "unsupported_structure", "The table exceeds supported row, column, or cell limits.", 422
        )
    for cell in header:
        validate_cell(cell)
    return tuple(header)


def _csv_relation(
    connection: duckdb.DuckDBPyConnection, path: Path, delimiter: str, width: int
) -> duckdb.DuckDBPyRelation:
    columns = "{" + ", ".join(f"'c{index}': 'VARCHAR'" for index in range(width)) + "}"
    return connection.sql(
        f"SELECT * FROM read_csv({sql_text(str(path))}, delim={sql_text(delimiter)}, "
        "quote='\"', escape='\"', header=true, auto_detect=false, strict_mode=true, "
        f"null_padding=false, encoding='utf-8', columns={columns})"
    )


def read_csv(
    connection: duckdb.DuckDBPyConnection, path: Path, format: str, workdir: Path
) -> tuple[tuple[str, ...], duckdb.DuckDBPyRelation]:
    delimiter = CSV_DELIMITERS[format]
    headers = _headers(path, delimiter)
    return headers, _csv_relation(connection, path, delimiter, len(headers))


def read_xlsx(
    connection: duckdb.DuckDBPyConnection, path: Path, format: str, workdir: Path
) -> tuple[tuple[str, ...], duckdb.DuckDBPyRelation]:
    """shortcut: reuses the bounded openpyxl validator (legacy XLSX limits); a streaming
    reader from the format research replaces this when large workbooks are required."""
    with path.open("rb") as content:
        _, table = StructuredFileParser().parse_table(
            content,
            "workbook.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            stored_format="xlsx",
        )
    staged = workdir / "workbook.csv"
    with staged.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_ALL)
        writer.writerow(table.headers)
        writer.writerows(table.rows)
    return table.headers, _csv_relation(connection, staged, ",", len(table.headers))


READERS: dict[str, Reader] = {
    **{format: read_csv for format in CSV_DELIMITERS},
    "xlsx": read_xlsx,
}
