"""Use case: Opens a retained profile-v5 upload through the shared format readers.

What it does: Names the stored reader format ("r:<suffix>"), opens the first table as an
all-text relation on a hardened DuckDB connection, and reads bounded exact text rows for
row-level features, so ingest and later reads see the same strings.
"""

import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Literal

import duckdb

from execplus.domain.ingestion import FileStructure, IngestionError
from execplus.domain.profiling import TableData
from execplus.infrastructure.readers import (
    ReaderOptions,
    ReadResult,
    hardened_connection,
    open_source,
)

READER_PREFIX = "r:"
_COMPRESSED = frozenset({"gz", "bz2", "xz"})


def stored_format(filename: str) -> str:
    suffixes = [suffix.lower().lstrip(".") for suffix in PurePosixPath(filename).suffixes]
    chain = suffixes[-2:] if suffixes and suffixes[-1] in _COMPRESSED else suffixes[-1:]
    format = READER_PREFIX + ".".join(chain)
    if not chain or len(format) > 16:
        raise IngestionError("unsupported_format", "This file type is not supported.", 415)
    return format


def is_reader_format(format: str | None) -> bool:
    return bool(format) and str(format).startswith(READER_PREFIX)


@contextmanager
def open_table(
    source: Path,
    filename: str,
    workdir: Path,
    extension_directory: Path,
    formula_cells: Literal["reject", "keep_as_text"],
    *,
    memory_limit_mb: int = 1024,
    threads: int = 2,
    max_temp_bytes: int = 8 * 1024**3,
) -> Iterator[tuple[duckdb.DuckDBPyConnection, duckdb.DuckDBPyRelation, ReadResult]]:
    (workdir / "read").mkdir(parents=True, exist_ok=True)
    result = open_source(
        source, filename, ReaderOptions(workdir / "read", extension_directory, formula_cells)
    )
    connection = hardened_connection(
        workdir,
        extension_directory,
        read_directories=(source.parent, result.path.parent),
        memory_limit_mb=memory_limit_mb,
        threads=threads,
        max_temp_bytes=max_temp_bytes,
    )
    try:
        yield connection, result.relation(connection), result
    finally:
        connection.close()


@contextmanager
def _stored_relation(
    content: BinaryIO,
    format: str,
    extension_directory: Path,
    formula_cells: Literal["reject", "keep_as_text"],
) -> Iterator[duckdb.DuckDBPyRelation]:
    with tempfile.TemporaryDirectory(prefix="execplus-read-") as work:
        name = "source." + format.removeprefix(READER_PREFIX)
        source = Path(work) / name
        content.seek(0)
        with source.open("wb") as handle:
            shutil.copyfileobj(content, handle, 1024 * 1024)
        content.seek(0)
        with open_table(source, name, Path(work), extension_directory, formula_cells) as opened:
            yield opened[1]


def _text_row(row: tuple[object, ...]) -> tuple[str, ...]:
    return tuple("" if value is None else str(value) for value in row)


def read_source_table(
    content: BinaryIO,
    format: str,
    extension_directory: Path,
    formula_cells: Literal["reject", "keep_as_text"],
    limit: int,
    *,
    extended_limit: int | None = None,
    max_cells: int | None = None,
) -> tuple[FileStructure, TableData]:
    """Exact text rows; up to `limit`, or up to `extended_limit` while within `max_cells`."""
    with _stored_relation(content, format, extension_directory, formula_cells) as relation:
        headers = tuple(str(column) for column in relation.columns)
        bound = limit
        if extended_limit and max_cells:
            bound = max(limit, min(extended_limit, max_cells // max(1, len(headers))))
        fetched = relation.fetchmany(bound + 1)
    if len(fetched) > bound:
        raise IngestionError(
            "large_dataset_step",
            f"This step reads every row and is not yet available for files over {bound:,} rows. "
            "Ask a calculation question instead.",
            422,
        )
    rows = tuple(_text_row(row) for row in fetched)
    return FileStructure(format, len(rows), len(headers), 1), TableData(headers, rows)


def read_source_rows_at(
    content: BinaryIO,
    format: str,
    extension_directory: Path,
    formula_cells: Literal["reject", "keep_as_text"],
    positions: tuple[int, ...],
    total: int,
) -> TableData:
    """Exact text rows at sorted zero-based positions, streamed in file order."""
    wanted = set(positions)
    rows: list[tuple[str, ...]] = []
    seen = 0
    with _stored_relation(content, format, extension_directory, formula_cells) as relation:
        headers = tuple(str(column) for column in relation.columns)
        while batch := relation.fetchmany(10_000):
            rows.extend(_text_row(row) for index, row in enumerate(batch, seen) if index in wanted)
            seen += len(batch)
    if seen != total:
        raise IngestionError(
            "lineage_mismatch", "The retained source failed its integrity check.", 409
        )
    return TableData(headers, tuple(rows))
