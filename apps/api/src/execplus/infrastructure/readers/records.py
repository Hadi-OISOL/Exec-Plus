"""Use case: Reads formats that DuckDB cannot open itself into exact text rows.

What it does: Streams JSON/NDJSON, table-shaped XML, XLS/XLSB/ODS sheets and SPSS/Stata/SAS
files as dictionaries of verbatim text, and writes them in bounded batches to a text-only
NDJSON file that DuckDB reads with every column typed VARCHAR.
"""

import json
import math
from collections.abc import Callable, Iterable, Iterator
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, TextIO

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import iterparse

from execplus.domain.ingestion import IngestionError

Row = dict[str, str | None]
MAX_RECORD_CHARS = 16 * 1024 * 1024
READ_CHARS = 1024 * 1024
XML_SCAN_EVENTS = 200_000


class _Number(str):
    """Raw JSON number text, kept verbatim so no float rounding ever happens."""


def _reject_constant(name: str) -> object:
    raise IngestionError("malformed_json", f"JSON value {name} is not supported.", 422)


DECODER = json.JSONDecoder(parse_float=_Number, parse_int=_Number, parse_constant=_reject_constant)


def number_text(value: float) -> str | None:
    if math.isnan(value) or math.isinf(value):
        return None
    if value.is_integer() and abs(value) < 2**53:
        return str(int(value))
    return repr(value)


def cell_text(value: object) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return number_text(value)
    if isinstance(value, datetime):
        return value.date().isoformat() if value.time() == time() else value.isoformat()
    if isinstance(value, date | time):
        return value.isoformat()
    if isinstance(value, timedelta):
        return str(value)
    return str(value)


def unique_headers(values: Iterable[object]) -> list[str]:
    headers: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(values, 1):
        base = (cell_text(value) or "").strip() or f"column_{index}"
        name, suffix = base, 2
        while name.casefold() in seen:
            name, suffix = f"{base}_{suffix}", suffix + 1
        seen.add(name.casefold())
        headers.append(name)
    return headers


class RecordWriter:
    """Append-only NDJSON of text values; column order is first-seen order."""

    def __init__(self, path: Path, max_columns: int) -> None:
        self.path = path
        self.max_columns = max_columns
        self.columns: dict[str, None] = {}
        self.rows = 0
        self._handle: TextIO = path.open("w", encoding="utf-8")

    def write(self, row: Row) -> None:
        for name in row:
            if name not in self.columns:
                if len(self.columns) >= self.max_columns:
                    raise IngestionError(
                        "unsupported_structure", "The data has too many columns.", 422
                    )
                self.columns[name] = None
        self._handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
        self._handle.write("\n")
        self.rows += 1

    def close(self) -> None:
        self._handle.close()


def write_rows(path: Path, rows: Iterable[Row], max_columns: int) -> list[str]:
    writer = RecordWriter(path, max_columns)
    try:
        for row in rows:
            writer.write(row)
    except BaseException:
        writer.close()
        path.unlink(missing_ok=True)
        raise
    writer.close()
    if writer.rows == 0 or not writer.columns:
        path.unlink(missing_ok=True)
        raise IngestionError("empty_table", "The table has no data rows.", 422)
    return list(writer.columns)


def _too_deep() -> IngestionError:
    return IngestionError("json_too_deep", "The JSON is nested too deeply.", 422)


def _json_text(value: object, depth: int, limit: int) -> str:
    if depth > limit:
        raise _too_deep()
    if isinstance(value, _Number):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if value is None or isinstance(value, bool):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ",".join(_json_text(item, depth + 1, limit) for item in value) + "]"
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(
                json.dumps(key, ensure_ascii=False) + ":" + _json_text(item, depth + 1, limit)
                for key, item in value.items()
            )
            + "}"
        )
    raise IngestionError("malformed_json", "The JSON contains an unsupported value.", 422)


def flatten(
    record: dict[str, Any], flatten_depth: int, nesting_limit: int, prefix: str = "", depth: int = 1
) -> Row:
    out: Row = {}
    for key, value in record.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict) and value and depth < flatten_depth:
            nested = flatten(value, flatten_depth, nesting_limit, name, depth + 1)
            for nested_name, nested_value in nested.items():
                if nested_name in out:
                    raise IngestionError(
                        "duplicate_field", f"The field {nested_name!r} appears twice.", 422
                    )
                out[nested_name] = nested_value
        elif name in out:
            raise IngestionError("duplicate_field", f"The field {name!r} appears twice.", 422)
        elif value is None:
            out[name] = None
        elif isinstance(value, _Number):
            out[name] = str(value)
        elif isinstance(value, bool):
            out[name] = "true" if value else "false"
        elif isinstance(value, str):
            out[name] = value
        else:
            out[name] = _json_text(value, depth, nesting_limit)
    return out


def _decode(text: str, start: int = 0) -> tuple[object, int]:
    try:
        return DECODER.raw_decode(text, start)
    except RecursionError as error:
        raise _too_deep() from error


def _array_items(stream: TextIO) -> Iterator[object]:
    buffer, position, eof, state = "", 0, False, "open"
    while True:
        while position < len(buffer) and buffer[position] in " \t\r\n":
            position += 1
        if position >= len(buffer):
            if eof:
                break
            chunk = stream.read(READ_CHARS)
            buffer, position, eof = buffer[position:] + chunk, 0, not chunk
            continue
        char = buffer[position]
        if state == "open":
            if char != "[":
                raise IngestionError(
                    "malformed_json", "A .json file must hold an array of records.", 422
                )
            position, state = position + 1, "first"
            continue
        if state == "done":
            raise IngestionError("malformed_json", "Unexpected data after the JSON array.", 422)
        if char == "]" and state in {"first", "next"}:
            position, state = position + 1, "done"
            continue
        if state == "next":
            if char != ",":
                raise IngestionError("malformed_json", "The JSON array is malformed.", 422)
            position, state = position + 1, "value"
            continue
        try:
            value, end = _decode(buffer, position)
        except json.JSONDecodeError as error:
            if eof:
                raise IngestionError(
                    "malformed_json", "The JSON array is malformed.", 422
                ) from error
            if len(buffer) - position > MAX_RECORD_CHARS:
                raise IngestionError(
                    "record_too_large", "One JSON record is larger than 16 MiB.", 422
                ) from error
            chunk = stream.read(READ_CHARS)
            buffer, position, eof = buffer[position:] + chunk, 0, not chunk
            continue
        yield value
        position, state = end, "next"
    if state != "done":
        raise IngestionError("malformed_json", "The JSON array is not closed.", 422)


def _lines(stream: TextIO) -> Iterator[object]:
    while line := stream.readline(MAX_RECORD_CHARS + 1):
        if len(line) > MAX_RECORD_CHARS:
            raise IngestionError("record_too_large", "One JSON record is larger than 16 MiB.", 422)
        if not line.strip():
            continue
        try:
            value, end = _decode(line.strip())
        except json.JSONDecodeError as error:
            raise IngestionError("malformed_json", "A JSON line is malformed.", 422) from error
        if end != len(line.strip()):
            raise IngestionError("malformed_json", "Put one JSON record per line.", 422)
        yield value


def json_rows(
    path: Path, newline_delimited: bool, flatten_depth: int, nesting: int
) -> Iterator[Row]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        if not newline_delimited:
            head = stream.read(64).lstrip()
            stream.seek(0)
            if head.startswith("{"):
                newline_delimited = True
        records = _lines(stream) if newline_delimited else _array_items(stream)
        try:
            for record in records:
                if not isinstance(record, dict):
                    raise IngestionError(
                        "malformed_json", "Each JSON record must be an object.", 422
                    )
                yield flatten(record, flatten_depth, nesting)
        except UnicodeDecodeError as error:
            raise IngestionError("encoding_error", "JSON files must be UTF-8 text.", 422) from error


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _xml_events(path: Path, events: tuple[str, ...]) -> Iterator[tuple[str, Any]]:
    try:
        yield from iterparse(
            str(path), events=events, forbid_dtd=True, forbid_entities=True, forbid_external=True
        )
    except (DefusedXmlException, SyntaxError) as error:
        raise IngestionError(
            "unsafe_xml" if isinstance(error, DefusedXmlException) else "malformed_xml",
            "The XML uses DTDs/entities or is not well formed.",
            422,
        ) from error


def xml_tables(path: Path) -> list[tuple[str, int | None]]:
    """List repeating record elements, shallowest and most frequent first."""
    counts: dict[tuple[int, str], int] = {}
    depth, seen, complete = -1, 0, True
    for event, element in _xml_events(path, ("start", "end")):
        if event == "start":
            depth += 1
            key = (depth, _local(element.tag))
            counts[key] = counts.get(key, 0) + 1
            seen += 1
            if seen >= XML_SCAN_EVENTS:
                complete = False
                break
        else:
            depth -= 1
            element.clear()
    tables: list[tuple[str, int | None]] = []
    names: set[str] = set()
    for (_, name), count in sorted(counts.items(), key=lambda item: (item[0][0], -item[1])):
        if count >= 2 and name not in names:
            names.add(name)
            tables.append((name, count if complete else None))
    if not tables:
        raise IngestionError(
            "unsupported_structure", "The XML has no repeating record element.", 422
        )
    return tables[:20]


def _xml_fields(element: Any, prefix: str, depth: int, limit: int, out: dict[str, Any]) -> None:
    for key, value in element.attrib.items():
        out[f"{prefix}@{_local(key)}"] = value
    children = list(element)
    if not children:
        if element.text:
            out[prefix.rstrip(".") or "#text"] = element.text
        return
    if element.text and element.text.strip():
        out[f"{prefix}#text"] = element.text
    for child in children:
        name = prefix + _local(child.tag)
        if (list(child) or child.attrib) and depth < limit:
            _xml_fields(child, name + ".", depth + 1, limit, out)
            continue
        value = "".join(child.itertext()) or None
        if name in out:
            existing = out[name]
            out[name] = [*existing, value] if isinstance(existing, list) else [existing, value]
        else:
            out[name] = value


def xml_rows(path: Path, record: str, flatten_depth: int) -> Iterator[Row]:
    stack: list[Any] = []
    inside = 0
    for event, element in _xml_events(path, ("start", "end")):
        if event == "start":
            stack.append(element)
            if _local(element.tag) == record:
                inside += 1
            continue
        stack.pop()
        if _local(element.tag) != record:
            if not inside and stack:
                stack[-1].remove(element)
            continue
        inside -= 1
        if inside:
            continue
        fields: dict[str, Any] = {}
        _xml_fields(element, "", 1, flatten_depth, fields)
        yield {
            key: json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
            for key, value in fields.items()
        }
        if stack:
            stack[-1].remove(element)


def sheet_rows(rows: Iterable[list[Any]]) -> Iterator[Row]:
    iterator = iter(rows)
    header = next(iterator, None)
    if header is None:
        raise IngestionError("empty_table", "The sheet is empty.", 422)
    names = unique_headers(header)
    for values in iterator:
        if len(values) > len(names):
            names = unique_headers([*header, *[None] * (len(values) - len(header))])
        texts = [cell_text(value) for value in values]
        if any(text is not None for text in texts):
            yield dict(zip(names, texts, strict=False))


def calamine_sheets(path: Path) -> list[str]:
    from python_calamine import CalamineWorkbook, PasswordError

    try:
        with CalamineWorkbook.from_path(str(path)) as workbook:
            return list(workbook.sheet_names)
    except PasswordError as error:
        raise IngestionError("encrypted_workbook", "Remove the workbook password.", 422) from error
    except Exception as error:
        raise IngestionError("malformed_excel", "The workbook is not readable.", 422) from error


def calamine_rows(path: Path, sheet: str) -> Iterator[Row]:
    from python_calamine import CalamineWorkbook

    try:
        with CalamineWorkbook.from_path(str(path)) as workbook:
            data = workbook.get_sheet_by_name(sheet).iter_rows()
            yield from sheet_rows(data)
    except IngestionError:
        raise
    except Exception as error:
        raise IngestionError("malformed_excel", "The worksheet is not readable.", 422) from error


STAT_READERS = {
    "sav": "read_sav",
    "dta": "read_dta",
    "sas7bdat": "read_sas7bdat",
    "xpt": "read_xport",
}


def stat_metadata(path: Path, format: str) -> tuple[int | None, dict[str, Any]]:
    import pyreadstat

    reader: Callable[..., Any] = getattr(pyreadstat, STAT_READERS[format])
    try:
        _, meta = reader(str(path), metadataonly=True)
    except Exception as error:
        raise IngestionError(
            "malformed_statistics_file", "The file is not readable.", 422
        ) from error
    labels = {
        column: {cell_text(key) or "": str(value) for key, value in mapping.items()}
        for column, mapping in (meta.variable_value_labels or {}).items()
    }
    rows = meta.number_rows if isinstance(meta.number_rows, int) and meta.number_rows >= 0 else None
    return rows, {
        "value_labels": labels,
        "column_labels": {
            name: label for name, label in (meta.column_names_to_labels or {}).items() if label
        },
    }


def stat_rows(path: Path, format: str, batch_rows: int, convert_dates: bool) -> Iterator[Row]:
    """Read in row_offset/row_limit batches.

    pyreadstat.read_file_in_chunks never stops for dict output when a file (XPT, some SAV)
    does not report its row count, so the loop ends on the first short batch instead.
    """
    import pyreadstat

    reader: Callable[..., Any] = getattr(pyreadstat, STAT_READERS[format])
    offset = 0
    try:
        while True:
            chunk, _ = reader(
                str(path),
                row_offset=offset,
                row_limit=batch_rows,
                output_format="dict",
                disable_datetime_conversion=not convert_dates,
            )
            names = list(chunk)
            count = len(chunk[names[0]]) if names else 0
            for values in zip(*(chunk[name] for name in names), strict=True):
                yield {name: cell_text(value) for name, value in zip(names, values, strict=True)}
            if count < batch_rows:
                break
            offset += count
    except (IngestionError, OverflowError):
        raise
    except Exception as error:
        raise IngestionError(
            "malformed_statistics_file", "The file is not readable.", 422
        ) from error
