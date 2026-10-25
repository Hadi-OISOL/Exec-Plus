"""Use case: Converts one retained upload into typed Parquet and its profile-v5 profile.

What it does: Streams the source through DuckDB as text, validates cells, computes exact
profile aggregates, decides types with the profile-v4 rules and casts once to Parquet
(DECIMAL(38,s), BIGINT, DATE, TIMESTAMP, BOOLEAN, VARCHAR) under memory and spill limits.
"""

import hashlib
from pathlib import Path
from typing import Any, cast

import duckdb

from execplus.domain.columnar import ColumnarConversion, ColumnStats, profile_from_stats
from execplus.domain.ingestion import IngestionError
from execplus.domain.profiling import MISSING_PLACEHOLDERS
from execplus.domain.semantics import quote_identifier
from execplus.infrastructure.columnar.readers import READERS, sql_text
from execplus.infrastructure.query.duckdb_executor import conversion_message

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
_MACROS = (
    f"CREATE MACRO s(v) AS trim(coalesce(v, ''), {sql_text(_SPACE)})",
    f"CREATE MACRO is_num(t) AS regexp_full_match(t, {sql_text(_NUMBER)})",
    r"CREATE MACRO digits(t) AS replace(regexp_extract(t, '^-?([0-9]+(\.[0-9]+)?)', 1), '.', '')",
    r"CREATE MACRO places(t) AS length(regexp_extract(t, '\.([0-9]+)', 1)) - coalesce("
    r"try_cast(nullif(regexp_extract(t, '[eE]([+-]?[0-9]+)$', 1), '') AS BIGINT), 0)",
    "CREATE MACRO num_scale(t) AS CASE WHEN replace(digits(t), '0', '') = '' THEN 0 "
    "ELSE greatest(0, places(t) - (length(digits(t)) - length(rtrim(digits(t), '0')))) END",
    "CREATE MACRO date_shape(t) AS regexp_full_match(t, '[0-9]{4}-[0-9]{2}-[0-9]{2}')",
    "CREATE MACRO is_date(t) AS date_shape(t) AND left(t, 4) <> '0000' "
    "AND try_cast(t AS DATE) IS NOT NULL",
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
    f"CREATE MACRO formula(v) AS starts_with(ltrim(coalesce(v, ''), {sql_text(_SPACE)}), '=') "
    f"OR starts_with(ltrim(coalesce(v, ''), {sql_text(_SPACE)}), '+') "
    f"OR starts_with(ltrim(coalesce(v, ''), {sql_text(_SPACE)}), '@') "
    f"OR (starts_with(ltrim(coalesce(v, ''), {sql_text(_SPACE)}), '-') AND NOT "
    f"regexp_full_match(ltrim(coalesce(v, ''), {sql_text(_SPACE)}), "
    r"'-[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?'))",
)
_STATS = (
    "count(*) FILTER (WHERE {t} = '')",
    "count(*) FILTER (WHERE lower({t}) IN ('true', 'false'))",
    "count(*) FILTER (WHERE is_date({t}))",
    "count(*) FILTER (WHERE date_shape({t}) AND NOT is_date({t}))",
    "count(*) FILTER (WHERE is_num({t}) AND num_scale({t}) = 0)",
    "count(*) FILTER (WHERE is_num({t}) AND num_scale({t}) > 0)",
    "count(DISTINCT {t}) FILTER (WHERE {t} <> '')",
    "count(*) FILTER (WHERE lower({t}) IN " + _PLACEHOLDERS + ")",
    "count(DISTINCT {t}) FILTER (WHERE lower({t}) IN " + _PLACEHOLDERS + ")",
    "min({t}) FILTER (WHERE is_date({t}))",
    "max({t}) FILTER (WHERE is_date({t}))",
    "min(try_cast({t} AS DOUBLE)) FILTER (WHERE is_num({t}) AND num_scale({t}) = 0)",
    "max(try_cast({t} AS DOUBLE)) FILTER (WHERE is_num({t}) AND num_scale({t}) = 0)",
    "count(moment({t}))",
    "count(*) FILTER (WHERE moment({t}) IS NOT NULL AND NOT date_shape({t}))",
    "count(*) FILTER (WHERE moment({t}) IS NOT NULL AND NOT date_shape({t}) AND aware({t}))",
    "strftime(min(moment({t})), '%Y-%m-%d')",
    "strftime(max(moment({t})), '%Y-%m-%d')",
    "coalesce(max(num_scale({t})) FILTER (WHERE is_num({t})), 0)",
    "bool_or(control({c}))",
    "bool_or(formula({c}))",
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
        memory_limit_mb: int = 2048,
        threads: int = 4,
        spill_limit_mb: int = 20_480,
        max_rows: int = 50_000_000,
    ) -> None:
        self.memory_limit_mb = memory_limit_mb
        self.threads = threads
        self.spill_limit_mb = spill_limit_mb
        self.max_rows = max_rows

    def _connect(self, source: Path, workdir: Path) -> duckdb.DuckDBPyConnection:
        connection = duckdb.connect(
            ":memory:",
            config={
                "memory_limit": f"{self.memory_limit_mb}MB",
                "threads": str(self.threads),
                "temp_directory": str(workdir / "spill"),
                "max_temp_directory_size": f"{self.spill_limit_mb}MB",
                "autoinstall_known_extensions": "false",
                "autoload_known_extensions": "false",
                "allow_unsigned_extensions": "false",
                "allow_community_extensions": "false",
            },
        )
        connection.execute("SET TimeZone = 'UTC'")
        connection.execute(f"SET allowed_paths = [{sql_text(str(source))}]")
        connection.execute(f"SET allowed_directories = [{sql_text(str(workdir) + '/')}]")
        connection.execute("SET enable_external_access = false")
        connection.execute("SET lock_configuration = true")
        for macro in _MACROS:
            connection.execute(macro)
        return connection

    def convert(self, source: Path, format: str, workdir: Path) -> ColumnarConversion:
        reader = READERS.get(format)
        if reader is None:
            raise IngestionError("unsupported_format", "This stored format is unavailable.", 409)
        connection = self._connect(source, workdir)
        try:
            raw = workdir / "raw.parquet"
            try:
                headers, relation = reader(connection, source, format, workdir)
                relation.project(
                    ", ".join(f"#{index + 1}::VARCHAR AS c{index}" for index in range(len(headers)))
                ).write_parquet(str(raw), compression="zstd")
            except duckdb.Error as error:
                raise IngestionError(
                    "malformed_csv",
                    "CSV rows must have consistent columns and well-formed UTF-8 quoting.",
                    422,
                ) from error
            return self._typed(connection, headers, raw, workdir)
        except duckdb.Error as error:
            raise IngestionError(
                "conversion_failed", "The file could not be prepared for large-data queries.", 422
            ) from error
        finally:
            connection.close()

    def _typed(
        self,
        connection: duckdb.DuckDBPyConnection,
        headers: tuple[str, ...],
        raw: Path,
        workdir: Path,
    ) -> ColumnarConversion:
        source = f"read_parquet({sql_text(str(raw))})"
        stripped = ", ".join(f"s(c{index}) AS t{index}, c{index}" for index in range(len(headers)))
        aggregates = [
            template.format(t=f"t{index}", c=f"c{index}")
            for index in range(len(headers))
            for template in _STATS
        ]
        blank_row = " AND ".join(f"t{index} = ''" for index in range(len(headers)))
        row = connection.execute(
            f"SELECT count(*), count(*) FILTER (WHERE {blank_row}), {', '.join(aggregates)} "
            f"FROM (SELECT {stripped} FROM {source})"
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
        if any(entry[-1] for entry in values):
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
            typed, valid = {
                "integer": (
                    f"try_cast(nullif({v}, '') AS BIGINT)",
                    f"{v} = '' OR (is_num({v}) AND num_scale({v}) = 0 "
                    f"AND try_cast({v} AS BIGINT) IS NOT NULL)",
                ),
                "decimal": (
                    f"try_cast(nullif({v}, '') AS DECIMAL(38, {scale}))",
                    f"{v} = '' OR (is_num({v}) AND num_scale({v}) <= {scale} "
                    f"AND try_cast({v} AS DECIMAL(38, {scale})) IS NOT NULL)",
                ),
                "date": (f"try_cast(nullif({v}, '') AS DATE)", f"{v} = '' OR is_date({v})"),
                "datetime": (f"moment({v})", f"{v} = '' OR moment({v}) IS NOT NULL"),
                "boolean": (
                    f"CASE lower({v}) WHEN 'true' THEN true WHEN 'false' THEN false END",
                    f"{v} = '' OR lower({v}) IN ('true', 'false')",
                ),
            }.get(kind, (f"nullif(t{index}, '')", "true"))
            expressions.append((typed, valid, kind))
        checks = ", ".join(
            f"min(file_row_number) FILTER (WHERE NOT ({valid}))" for _, valid, _ in expressions
        )
        first_bad = connection.execute(
            f"SELECT {checks} FROM (SELECT file_row_number, {stripped} "
            f"FROM read_parquet({sql_text(str(raw))}, file_row_number = true))"
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
        connection.execute(
            f"COPY (SELECT {', '.join(selections)} FROM (SELECT {stripped} FROM {source})) "
            f"TO {sql_text(str(parquet))} (FORMAT parquet, COMPRESSION zstd)"
        )
        raw.unlink()
        return ColumnarConversion(
            headers,
            profile,
            str(parquet),
            _sha256(parquet),
            parquet.stat().st_size,
            rows,
            errors,
        )
