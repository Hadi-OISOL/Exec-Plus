"""Use case: Converts one retained upload into typed Parquet and its profile-v6 profile.

What it does: Streams the source through DuckDB as text, validates cells, computes exact
profile aggregates, decides types with the in-memory profile-v6 rules (spelled-month dates
are read by the same Python parser) and casts once to Parquet
(DECIMAL(38,s), BIGINT, DATE, TIMESTAMP, BOOLEAN, VARCHAR) under memory and spill limits.
"""

import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal, cast

import duckdb
from duckdb.func import FunctionNullHandling

from execplus.domain.columnar import ColumnarConversion, ColumnStats, profile_from_stats
from execplus.domain.ingestion import IngestionError
from execplus.domain.profiling import MISSING_PLACEHOLDERS, SPELLED_DATE, parse_date
from execplus.domain.semantics import quote_identifier
from execplus.infrastructure.columnar.source_rows import open_table, stored_format
from execplus.infrastructure.file_parser import MAX_COLUMNS, validate_cell, validate_header
from execplus.infrastructure.query.duckdb_executor import conversion_message


def sql_text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


_SPACE = (
    "\t\n\r \x85\xa0\u1680"
    + "".join(map(chr, range(0x2000, 0x200B)))
    + "\u2028\u2029\u202f\u205f\u3000"
)
_PLACEHOLDERS = "(" + ", ".join(sql_text(value) for value in sorted(MISSING_PLACEHOLDERS)) + ")"
_NUMBER = r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?"
_MOMENT = (
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}"
    r"(:[0-9]{2}(\.[0-9]{1,6})?)?(Z|[+-][0-9]{2}:[0-9]{2})?"
)
_OFFSET = r"[+-][0-9]{2}:[0-9]{2}$"
_WS = r"[\t\n\r \x{85}\x{a0}\x{1680}\x{2000}-\x{200a}\x{2028}\x{2029}\x{202f}\x{205f}\x{3000}]"
_FORMULA = "^" + _WS + "*[=+@-]"
_NEGATIVE = _WS + r"*-[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?"
_MACROS = (
    f"CREATE MACRO s(v) AS CASE WHEN regexp_matches(coalesce(v, ''), {sql_text(f'^{_WS}|{_WS}$')}) "
    f"THEN trim(v, {sql_text(_SPACE)}) ELSE coalesce(v, '') END",
    f"CREATE MACRO is_num(t) AS regexp_full_match(t, {sql_text(_NUMBER)})",
    r"CREATE MACRO digits(t) AS replace(regexp_extract(t, '^-?([0-9]+(\.[0-9]+)?)', 1), '.', '')",
    r"CREATE MACRO places(t) AS length(regexp_extract(t, '\.([0-9]+)', 1)) - coalesce("
    r"try_cast(nullif(regexp_extract(t, '[eE]([+-]?[0-9]+)$', 1), '') AS BIGINT), 0)",
    "CREATE MACRO num_scale(t) AS CASE WHEN NOT contains(lower(t), 'e') "
    "THEN length(rtrim(split_part(t, '.', 2), '0')) "
    "WHEN replace(digits(t), '0', '') = '' THEN 0 "
    "ELSE greatest(0, places(t) - (length(digits(t)) - length(rtrim(digits(t), '0')))) END",
    "CREATE MACRO date_shape(t) AS regexp_full_match(t, '[0-9]{4}-[0-9]{2}-[0-9]{2}')",
    "CREATE MACRO is_date(t) AS CASE WHEN date_shape(t) THEN left(t, 4) <> '0000' "
    "AND try_cast(t AS DATE) IS NOT NULL ELSE false END",
    f"CREATE MACRO spelled(t) AS regexp_full_match(t, {sql_text(SPELLED_DATE)})",
    "CREATE MACRO any_date(t) AS CASE WHEN is_date(t) THEN try_cast(t AS DATE) "
    "WHEN spelled(t) THEN spelled_date(t) END",
    f"CREATE MACRO aware(t) AS right(t, 1) = 'Z' OR regexp_matches(t, {sql_text(_OFFSET)})",
    "CREATE MACRO moment(t) AS CASE "
    "WHEN is_date(t) THEN try_cast(t AS DATE)::TIMESTAMP "
    f"WHEN regexp_full_match(t, {sql_text(_MOMENT)}) AND left(t, 4) <> '0000' "
    "AND substr(t, 12, 2) < '24' THEN CASE "
    f"WHEN regexp_matches(t, {sql_text(_OFFSET)}) THEN CASE "
    "WHEN substr(t, -5, 2) < '24' AND substr(t, -2, 2) < '60' THEN "
    "try_cast(left(t, length(t) - 6) AS TIMESTAMP) - to_minutes("
    "(CASE WHEN substr(t, -6, 1) = '-' THEN -1 ELSE 1 END) * "
    "(CAST(substr(t, -5, 2) AS BIGINT) * 60 + CAST(substr(t, -2, 2) AS BIGINT))) END "
    "WHEN right(t, 1) = 'Z' THEN try_cast(left(t, length(t) - 1) AS TIMESTAMP) "
    "ELSE try_cast(t AS TIMESTAMP) END END",
    "CREATE MACRO control(v) AS regexp_matches(coalesce(v, ''), "
    r"'[\x01-\x08\x0b\x0c\x0e-\x1f]')",
    f"CREATE MACRO formula(v) AS regexp_matches(coalesce(v, ''), {sql_text(_FORMULA)}) "
    f"AND NOT regexp_full_match(v, {sql_text(_NEGATIVE)})",
)
_STATS = (
    "count(*) FILTER (WHERE {t} = '')",
    "count(*) FILTER (WHERE lower({t}) IN ('true', 'false'))",
    "count(*) FILTER (WHERE {d})",
    "count(*) FILTER (WHERE ({ds} OR {sp}) AND NOT {d})",
    "count(*) FILTER (WHERE {sc} = 0)",
    "count(*) FILTER (WHERE {sc} > 0)",
    "count(DISTINCT {t}) FILTER (WHERE {t} <> '')",
    "count(*) FILTER (WHERE {p})",
    "count(DISTINCT {t}) FILTER (WHERE {p})",
    "CAST(min({dv}) AS VARCHAR)",
    "CAST(max({dv}) AS VARCHAR)",
    "min(try_cast({t} AS DOUBLE)) FILTER (WHERE {sc} = 0)",
    "max(try_cast({t} AS DOUBLE)) FILTER (WHERE {sc} = 0)",
    "count({m})",
    "count(*) FILTER (WHERE {m} IS NOT NULL AND NOT {ds})",
    "count(*) FILTER (WHERE {m} IS NOT NULL AND NOT {ds} AND aware({t}))",
    "strftime(min({m}), '%Y-%m-%d')",
    "strftime(max({m}), '%Y-%m-%d')",
    "coalesce(max({sc}), 0)",
    "bool_or(control({c}))",
    "bool_or(formula({c}))",
)
_DERIVED = (
    "{t}, {c}, CASE WHEN is_num({t}) THEN num_scale({t}) END AS sc{i}, "
    "date_shape({t}) AS ds{i}, spelled({t}) AS sp{i}, any_date({t}) AS dv{i}, "
    "dv{i} IS NOT NULL AS d{i}, moment({t}) AS m{i}, "
    "lower({t}) IN " + _PLACEHOLDERS + " AS p{i}"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class DuckDBColumnarConverter:
    def __init__(
        self,
        *,
        extension_directory: Path,
        formula_cells: Literal["reject", "keep_as_text"] = "keep_as_text",
        memory_limit_mb: int = 2048,
        threads: int = 4,
        spill_limit_mb: int = 20_480,
        max_rows: int = 50_000_000,
    ) -> None:
        self.extension_directory = extension_directory
        self.formula_cells = formula_cells
        self.memory_limit_mb = memory_limit_mb
        self.threads = threads
        self.spill_limit_mb = spill_limit_mb
        self.max_rows = max_rows

    def convert(self, source: Path, filename: str, workdir: Path) -> ColumnarConversion:
        format = stored_format(filename)
        with open_table(
            source,
            filename,
            workdir,
            self.extension_directory,
            self.formula_cells,
            memory_limit_mb=self.memory_limit_mb,
            threads=self.threads,
            max_temp_bytes=self.spill_limit_mb * 1024 * 1024,
        ) as (connection, relation, _):
            headers = tuple(str(column) for column in relation.columns)
            validate_header(list(headers))
            if len(headers) > MAX_COLUMNS:
                raise IngestionError(
                    "unsupported_structure",
                    "The table exceeds supported row, column, or cell limits.",
                    422,
                )
            for header in headers:
                validate_cell(header, reject_formulas=self.formula_cells == "reject")
            raw = workdir / "raw.parquet"
            try:
                connection.create_function(
                    "spelled_date",
                    lambda value: None if value is None else parse_date(value),
                    ["varchar"],
                    "date",
                    null_handling=FunctionNullHandling.SPECIAL,
                    side_effects=False,
                )
                for macro in _MACROS:
                    connection.execute(macro)
                relation.project(
                    ", ".join(f"#{index + 1}::VARCHAR AS c{index}" for index in range(len(headers)))
                ).write_parquet(str(raw), compression="zstd")
            except duckdb.OutOfMemoryException as error:
                raise IngestionError(
                    "conversion_failed",
                    "The file needs more memory to prepare than this server allows.",
                    422,
                ) from error
            except duckdb.Error as error:
                raise IngestionError(
                    "unreadable_file",
                    "The file could not be read. Check that rows have consistent columns.",
                    422,
                ) from error
            try:
                return replace(self._typed(connection, headers, raw, workdir), format=format)
            except duckdb.Error as error:
                raise IngestionError(
                    "conversion_failed",
                    "The file could not be prepared for large-data queries.",
                    422,
                ) from error

    def _typed(
        self,
        connection: duckdb.DuckDBPyConnection,
        headers: tuple[str, ...],
        raw: Path,
        workdir: Path,
    ) -> ColumnarConversion:
        source = f"read_parquet({sql_text(str(raw))})"
        stripped = ", ".join(f"s(c{index}) AS t{index}, c{index}" for index in range(len(headers)))
        names = [
            {
                "i": index,
                "t": f"t{index}",
                "c": f"c{index}",
                "sc": f"sc{index}",
                "ds": f"ds{index}",
                "d": f"d{index}",
                "dv": f"dv{index}",
                "sp": f"sp{index}",
                "m": f"m{index}",
                "p": f"p{index}",
            }
            for index in range(len(headers))
        ]
        aggregates = [template.format(**entry) for entry in names for template in _STATS]
        derived = ", ".join(_DERIVED.format(**entry) for entry in names)
        blank_row = " AND ".join(f"t{index} = ''" for index in range(len(headers)))
        row = connection.execute(
            f"SELECT count(*), count(*) FILTER (WHERE {blank_row}), {', '.join(aggregates)} "
            f"FROM (SELECT {derived} FROM (SELECT {stripped} FROM {source}))"
        ).fetchone()
        if row is None:
            raise IngestionError("empty_table", "Include at least one data row.", 422)
        rows, blank_rows = int(row[0]), int(row[1])
        width = len(_STATS)
        values = [row[2 + index * width : 2 + (index + 1) * width] for index in range(len(headers))]
        if any(entry[-2] for entry in values):
            raise IngestionError(
                "unsafe_content", "The file contains unsupported control characters.", 422
            )
        if self.formula_cells == "reject" and any(entry[-1] for entry in values):
            raise IngestionError(
                "unsafe_formula", "Formula-like cells are unsupported. Upload values only.", 422
            )
        if blank_rows:
            raise IngestionError(
                "malformed_csv", "CSV rows must have consistent columns and cannot be empty.", 422
            )
        if rows == 0:
            raise IngestionError(
                "empty_table", "Include at least one data row below the header.", 422
            )
        if rows > self.max_rows:
            raise IngestionError(
                "unsupported_structure",
                "The table exceeds supported row, column, or cell limits.",
                422,
            )
        stats = tuple(
            ColumnStats(*[*entry[:6], rows - sum(entry[:6]), *entry[6:18]]) for entry in values
        )
        profile_without_duplicates = profile_from_stats(headers, stats, rows, 0)
        columns = cast(list[dict[str, Any]], profile_without_duplicates["columns"])
        blanked = {
            index for index, column in enumerate(columns) if "missing_placeholders" in column
        }

        def value(index: int, *, raw_text: bool = False) -> str:
            base = f"c{index}" if raw_text else f"t{index}"
            if index not in blanked:
                return f"coalesce({base}, '')" if raw_text else base
            return (
                f"CASE WHEN lower(t{index}) IN {_PLACEHOLDERS} THEN '' "
                f"ELSE coalesce({base}, '') END"
            )

        distinct = connection.execute(
            f"SELECT count(*) FROM (SELECT DISTINCT "
            f"{', '.join(value(index, raw_text=True) for index in range(len(headers)))} "
            f"FROM (SELECT {stripped} FROM {source}))"
        ).fetchone()
        profile = profile_from_stats(
            headers, stats, rows, rows - int(distinct[0] if distinct else 0)
        )
        scales = [max(12, int(entry[-3])) for entry in values]
        expressions: list[tuple[str, str, str]] = []
        for index, column in enumerate(columns):
            v = value(index)
            kind = "datetime" if column.get("datetime") is True else str(column["type"])
            scale = min(scales[index], 38)
            decimal = f"try_cast({v} AS DECIMAL(38, {scale}))"
            if int(values[index][-3]) <= 18:
                narrow = f"try_cast({v} AS DECIMAL(18, {int(values[index][-3])}))"
                decimal = (
                    f"CASE WHEN {narrow} IS NOT NULL THEN {narrow}::DECIMAL(38, {scale}) "
                    f"ELSE {decimal} END"
                )
            typed, valid = {
                "integer": (
                    f"try_cast(nullif({v}, '') AS BIGINT)",
                    f"{v} = '' OR (is_num({v}) AND num_scale({v}) = 0 "
                    f"AND try_cast({v} AS BIGINT) IS NOT NULL)",
                ),
                "decimal": (
                    f"CASE WHEN {v} <> '' THEN {decimal} END",
                    f"{v} = '' OR (is_num({v}) AND num_scale({v}) <= {scale} "
                    f"AND {decimal} IS NOT NULL)",
                ),
                "date": (f"any_date({v})", f"{v} = '' OR any_date({v}) IS NOT NULL"),
                "datetime": (f"moment({v})", f"{v} = '' OR moment({v}) IS NOT NULL"),
                "boolean": (
                    f"CASE lower({v}) WHEN 'true' THEN true WHEN 'false' THEN false END",
                    f"{v} = '' OR lower({v}) IN ('true', 'false')",
                ),
            }.get(kind, (f"nullif(t{index}, '')", "true"))
            expressions.append((typed, valid, kind))
        staged = workdir / "staged.parquet"
        staging = ", ".join(
            f"{typed} AS v{index}, NOT ({valid}) AS b{index}"
            for index, (typed, valid, _) in enumerate(expressions)
        )
        connection.execute(
            f"COPY (SELECT file_row_number AS r, {staging} FROM (SELECT file_row_number, "
            f"{stripped} FROM read_parquet({sql_text(str(raw))}, file_row_number = true))) "
            f"TO {sql_text(str(staged))} (FORMAT parquet, COMPRESSION uncompressed)"
        )
        checks = ", ".join(f"min(r) FILTER (WHERE b{index})" for index in range(len(headers)))
        first_bad = connection.execute(
            f"SELECT {checks} FROM read_parquet({sql_text(str(staged))})"
        ).fetchone()
        errors: dict[str, str] = {}
        selections = []
        for index, (name, (typed, _, kind)) in enumerate(zip(headers, expressions, strict=True)):
            bad = first_bad[index] if first_bad else None
            if bad is not None:
                errors[name] = conversion_message(name, int(bad) + 1, kind, scales[index])
                typed = f"nullif(t{index}, '')"
            selections.append(f"{typed} AS {quote_identifier(name)}")
        parquet = workdir / "typed.parquet"
        final = (
            f"SELECT {', '.join(selections)} FROM (SELECT {stripped} FROM {source})"
            if errors
            else "SELECT "
            + ", ".join(
                f"v{index} AS {quote_identifier(name)}" for index, name in enumerate(headers)
            )
            + f" FROM read_parquet({sql_text(str(staged))})"
        )
        connection.execute(
            f"COPY ({final}) TO {sql_text(str(parquet))} (FORMAT parquet, COMPRESSION zstd)"
        )
        staged.unlink()
        raw.unlink()
        return ColumnarConversion(
            "",
            headers,
            profile,
            str(parquet),
            _sha256(parquet),
            parquet.stat().st_size,
            rows,
            errors,
        )
