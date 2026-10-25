"""Use case: Opens any supported upload as selectable tables of exact text for the ingest job.

What it does: Detects the format, unpacks guarded archives, lists sheets/tables cheaply and
materializes a chosen table as a DuckDB relation whose columns are all VARCHAR, enforcing the
configured policy for formula-like cells.
"""

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Literal
from zipfile import ZipFile

import duckdb
from defusedxml.ElementTree import fromstring

from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.readers import records
from execplus.infrastructure.readers.archives import ArchiveLimits, inspect_container, unpack
from execplus.infrastructure.readers.connection import hardened_connection
from execplus.infrastructure.readers.detection import (
    ARCHIVES,
    HEAD_BYTES,
    TEXT_FORMATS,
    detect_format,
)
from execplus.infrastructure.readers.text import to_utf8

FormulaPolicy = Literal["reject", "keep_as_text"]
CALAMINE_FORMATS = frozenset({"xls", "xlsb", "ods"})
STAT_FORMATS = frozenset(records.STAT_READERS)
DIMENSION = re.compile(rb'<(?:\w+:)?dimension\s+ref="[A-Z]+\d+:[A-Z]+(\d+)"')
FORMULA_START = r"^\s*[=+@]"
NUMERIC_DASH = r"\s*-\d+(\.\d+)?([eE][+-]?\d+)?"


@dataclass(frozen=True)
class ReaderOptions:
    temp_dir: Path
    extension_directory: Path
    formula_cells: FormulaPolicy = "keep_as_text"
    encoding: str | None = None
    max_archive_members: int = 1000
    max_expanded_bytes: int = 4 * 1024**3
    max_compression_ratio: int = 200
    max_archive_depth: int = 2
    max_calamine_bytes: int = 50 * 1024 * 1024
    max_columns: int = 2000
    json_flatten_depth: int = 5
    json_max_nesting: int = 64
    batch_rows: int = 50_000

    @property
    def archive_limits(self) -> ArchiveLimits:
        return ArchiveLimits(
            self.max_archive_members, self.max_expanded_bytes, self.max_compression_ratio
        )


@dataclass(frozen=True)
class TableInfo:
    name: str
    approx_rows: int | None = None


def _sql(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


@dataclass
class ReadResult:
    format: str
    path: Path
    tables: tuple[TableInfo, ...]
    options: ReaderOptions
    containers: tuple[str, ...] = ()
    encoding: str | None = None
    notes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    _materialized: dict[str, Path] = field(default_factory=dict, repr=False)

    def table_name(self, table: str | None) -> str:
        names = [info.name for info in self.tables]
        if table is None:
            return names[0]
        if table not in names:
            raise IngestionError("unknown_table", "Choose one of the listed sheets or tables.", 404)
        return table

    def first_filled(self, connection: duckdb.DuckDBPyConnection) -> str:
        """Return the first table with a data row, skipping empty leading sheets."""
        if len(self.tables) == 1:
            return self.tables[0].name
        for info in self.tables:
            if info.approx_rows == 0:
                continue
            try:
                if self.relation(connection, info.name).limit(1).fetchall():
                    return info.name
            except IngestionError as error:
                if error.code != "unreadable_file":
                    raise
        return self.tables[0].name

    def relation(
        self, connection: duckdb.DuckDBPyConnection, table: str | None = None
    ) -> duckdb.DuckDBPyRelation:
        """Return the chosen table as a lazy relation with every column typed VARCHAR."""
        name = self.table_name(table)
        try:
            relation = connection.sql(self._query(connection, name))
            if self.options.formula_cells == "reject":
                _reject_formulas(connection, relation)
        except duckdb.Error as error:
            raise IngestionError(
                "unreadable_file", f"The {self.format} data could not be read: {error}", 422
            ) from error
        return relation

    def _query(self, connection: duckdb.DuckDBPyConnection, name: str) -> str:
        path = _sql(str(self.path))
        if self.format in TEXT_FORMATS:
            delimiter = ", delim='\\t'" if self.format == "tsv" else ""
            return f"SELECT * FROM read_csv({path}, all_varchar=true, header=true{delimiter})"
        if self.format in {"xlsx", "xlsm"}:
            source = (
                f"read_xlsx({path}, sheet={_sql(name)}, all_varchar=true, header=true, "
                "stop_at_empty=false)"
            )
            columns = [
                column for column, *_ in connection.sql(f"DESCRIBE FROM {source}").fetchall()
            ]
            empty = " AND ".join(f"{_identifier(column)} IS NULL" for column in columns)
            return f"SELECT * FROM {source} WHERE NOT ({empty})"
        if self.format == "parquet":
            return f"SELECT COLUMNS(*)::VARCHAR FROM read_parquet({path})"
        if self.format == "sqlite":
            return f"SELECT * FROM sqlite_scan({path}, {_sql(name)})"
        rows_path = self._materialized.get(name) or self._materialize(name)
        types = ", ".join(f"{_sql(column)}: 'VARCHAR'" for column in self.metadata["columns"][name])
        return (
            f"SELECT * FROM read_json({_sql(str(rows_path))}, format='newline_delimited', "
            f"columns={{{types}}}, maximum_object_size=67108864)"
        )

    def _materialize(self, name: str) -> Path:
        options = self.options
        target = options.temp_dir / f"rows-{len(self._materialized)}.ndjson"
        if self.format in {"json", "ndjson"}:
            rows = records.json_rows(
                self.path,
                self.format == "ndjson",
                options.json_flatten_depth,
                options.json_max_nesting,
            )
        elif self.format == "xml":
            rows = records.xml_rows(self.path, name, options.json_flatten_depth)
        elif self.format in CALAMINE_FORMATS:
            rows = records.calamine_rows(self.path, name)
        else:
            try:
                columns = records.write_rows(
                    target,
                    records.stat_rows(self.path, self.format, options.batch_rows, True),
                    options.max_columns,
                )
            except OverflowError:
                rows = records.stat_rows(self.path, self.format, options.batch_rows, False)
                self.notes = (*self.notes, "dates_not_converted")
            else:
                return self._store(name, target, columns)
        return self._store(name, target, records.write_rows(target, rows, options.max_columns))

    def _store(self, name: str, target: Path, columns: list[str]) -> Path:
        self.metadata.setdefault("columns", {})[name] = columns
        self._materialized[name] = target
        return target


def _reject_formulas(
    connection: duckdb.DuckDBPyConnection, relation: duckdb.DuckDBPyRelation
) -> None:
    checks = " OR ".join(
        f"regexp_matches({column}, {_sql(FORMULA_START)}) OR "
        f"(regexp_matches({column}, '^\\s*-') AND NOT regexp_full_match({column}, "
        f"{_sql(NUMERIC_DASH)}))"
        for column in map(_identifier, relation.columns)
    )
    if relation.filter(checks).limit(1).fetchall():
        raise IngestionError(
            "unsafe_formula", "Formula-like cells are unsupported. Upload values only.", 422
        )


def _xlsx_tables(path: Path) -> list[TableInfo]:
    namespace = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    with ZipFile(path) as archive:
        workbook = fromstring(archive.read("xl/workbook.xml"))
        relations = fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.get("Id"): item.get("Target", "") for item in relations}
        tables = []
        for sheet in workbook.iter():
            if sheet.tag.rsplit("}", 1)[-1] != "sheet":
                continue
            target = targets.get(sheet.get(namespace), "").lstrip("/")
            member = target if target.startswith("xl/") else f"xl/{target}"
            rows = None
            if member in archive.namelist():
                with archive.open(member) as stream:
                    match = DIMENSION.search(stream.read(4096))
                rows = max(int(match.group(1)) - 1, 0) if match else None
            tables.append(TableInfo(sheet.get("name", ""), rows))
    return tables


def _sqlite_tables(path: Path) -> list[TableInfo]:
    uri = f"file:{path.resolve()}?mode=ro&immutable=1"
    try:
        database = sqlite3.connect(uri, uri=True)
        try:
            names = database.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        finally:
            database.close()
    except sqlite3.Error as error:
        raise IngestionError(
            "malformed_sqlite", "The SQLite database is not readable.", 422
        ) from error
    return [TableInfo(name) for (name,) in names]


def _parquet_tables(path: Path, options: ReaderOptions) -> list[TableInfo]:
    connection = hardened_connection(
        options.temp_dir, options.extension_directory, read_directories=(path.parent,)
    )
    try:
        (rows,) = connection.execute(
            f"SELECT num_rows FROM parquet_file_metadata({_sql(str(path))})"
        ).fetchone() or (None,)
    except duckdb.Error as error:
        raise IngestionError(
            "malformed_parquet", "The Parquet file is not readable.", 422
        ) from error
    finally:
        connection.close()
    return [TableInfo(path.stem, int(rows) if rows is not None else None)]


def open_source(
    path: Path,
    filename: str,
    options: ReaderOptions,
    *,
    _depth: int = 0,
    _containers: tuple[str, ...] = (),
) -> ReadResult:
    """Detect, guard and list the tables of one uploaded file."""
    with path.open("rb") as handle:
        head = handle.read(HEAD_BYTES)
    format = detect_format(filename, head)
    if format in ARCHIVES:
        if _depth >= options.max_archive_depth:
            raise IngestionError("archive_nesting", "Archives are nested too deeply.", 422)
        inner = unpack(
            path, format, filename, options.temp_dir / f"unpacked-{_depth}", options.archive_limits
        )
        return open_source(
            inner, inner.name, options, _depth=_depth + 1, _containers=(*_containers, format)
        )
    notes: list[str] = []
    metadata: dict[str, Any] = {}
    encoding = None
    stem = PurePosixPath(filename).stem
    if format in {"xlsx", "xlsm", "xlsb", "ods"}:
        facts = inspect_container(path, format, options.archive_limits)
        if facts.has_macros:
            notes.append("macros_ignored")
        if facts.has_formulas:
            if options.formula_cells == "reject":
                raise IngestionError(
                    "unsafe_formula", "Excel formulas are unsupported. Upload values only.", 422
                )
            notes.append("formulas_read_as_cached_values")
    if format in CALAMINE_FORMATS and path.stat().st_size > options.max_calamine_bytes:
        raise IngestionError(
            "file_too_large",
            f"{format.upper()} files must be at most "
            f"{options.max_calamine_bytes // (1024 * 1024)} MiB; save as XLSX or CSV.",
            413,
        )
    if format in TEXT_FORMATS:
        path, encoding = to_utf8(path, options.temp_dir / "text", options.encoding)
        tables = [TableInfo(stem)]
    elif format in {"json", "ndjson"}:
        tables = [TableInfo(stem)]
    elif format in {"xlsx", "xlsm"}:
        try:
            tables = _xlsx_tables(path)
        except (KeyError, SyntaxError, ValueError) as error:
            raise IngestionError("malformed_excel", "The workbook is not readable.", 422) from error
    elif format in CALAMINE_FORMATS:
        tables = [TableInfo(name, rows) for name, rows in records.calamine_sheets(path)]
    elif format == "parquet":
        tables = _parquet_tables(path, options)
    elif format == "sqlite":
        tables = _sqlite_tables(path)
    elif format == "xml":
        tables = [TableInfo(name, rows) for name, rows in records.xml_tables(path)]
    else:
        rows, metadata = records.stat_metadata(path, format)
        tables = [TableInfo(stem, rows)]
    if not tables:
        raise IngestionError("empty_table", "The file has no tables.", 422)
    return ReadResult(
        format=format,
        path=path,
        tables=tuple(tables),
        options=options,
        containers=_containers,
        encoding=encoding,
        notes=tuple(notes),
        metadata=metadata,
    )
