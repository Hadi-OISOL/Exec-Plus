"""Use case: Proves every upload format reader returns exact text and refuses unsafe files.

What it does: Generates a small real sample per format (one tiny committed XLS), checks text
round-trips, sheet/table listing, encodings, archive and XML attacks, formula policies and
extension/magic-byte detection.
"""

import bz2
import gzip
import lzma
import os
import sqlite3
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import duckdb
import pandas as pd
import pyreadstat
import pytest
from openpyxl import Workbook

from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.readers import (
    ReaderOptions,
    detect_format,
    hardened_connection,
    open_source,
)

FIXTURES = Path(__file__).parent / "fixtures" / "readers"
EXTENSIONS = Path(
    os.environ.get(
        "EXECPLUS_DUCKDB_EXTENSION_DIRECTORY",
        Path(__file__).resolve().parents[3] / "data" / "duckdb-extensions",
    )
)
HAS_EXTENSIONS = all(
    any(EXTENSIONS.glob(f"v{duckdb.__version__}/*/{name}.duckdb_extension"))
    for name in ("excel", "sqlite_scanner")
)
needs_extensions = pytest.mark.skipif(
    not HAS_EXTENSIONS, reason="bundled DuckDB excel/sqlite extensions are not installed"
)


@pytest.fixture
def job(tmp_path):
    return tmp_path / "job"


def read(job, name, data, table=None, **overrides):
    job.mkdir(parents=True, exist_ok=True)
    path = job / name
    path.write_bytes(data)
    options = ReaderOptions(temp_dir=job, extension_directory=EXTENSIONS, **overrides)
    result = open_source(path, name, options)
    connection = hardened_connection(job, EXTENSIONS)
    try:
        relation = result.relation(connection, table)
        types = {str(kind) for kind in relation.types}
        return result, relation.columns, relation.fetchall(), types
    finally:
        connection.close()


def failure(job, name, data, **overrides):
    with pytest.raises(IngestionError) as raised:
        read(job, name, data, **overrides)
    return raised.value


def zipped(members, compression=ZIP_DEFLATED):
    output = BytesIO()
    with ZipFile(output, "w", compression) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return output.getvalue()


def workbook(*, formula=False, text_formula=False):
    book = Workbook()
    sheet = book.active
    sheet.title = "Sales"
    sheet.append(["amount", "region", "note"])
    sheet.append([0.1, "North", " padded "])
    sheet.append([None, None, None])
    sheet.append([2.25, "Søuth", "=1+1" if formula else "plain"])
    if text_formula:
        sheet["C4"].data_type = "s"
    extra = book.create_sheet("Notes")
    extra.append(["note"])
    for index in range(5):
        extra.append([f"n{index}"])
    output = BytesIO()
    book.save(output)
    return output.getvalue()


CSV = 'id,amount,label\n1,0.10, keep spaces \n2,12345678901234567.25,"multi\nline"\n3,,\n'
CSV_ROWS = [
    ("1", "0.10", " keep spaces "),
    ("2", "12345678901234567.25", "multi\nline"),
    ("3", None, None),
]


@pytest.mark.parametrize(
    "name,data,expected",
    [
        ("plain.csv", CSV.encode(), "utf-8"),
        ("bom.csv", b"\xef\xbb\xbf" + CSV.encode(), "utf-8"),
        ("wide.csv", CSV.encode("utf-16"), "utf-16"),
        ("tabbed.tsv", CSV.replace(",", "\t").encode(), "utf-8"),
        ("piped.txt", CSV.replace(",", "|").encode(), "utf-8"),
    ],
)
def test_delimited_text_round_trips_exactly(job, name, data, expected):
    result, columns, rows, types = read(job, name, data)
    assert result.encoding == expected and columns == ["id", "amount", "label"]
    assert rows == CSV_ROWS and types == {"VARCHAR"}


def test_cp1252_is_detected_and_transcoded(job):
    text = "city,price\n" + "".join(f"Café Señor Müller {i},€{i}.50\n" for i in range(200))
    result, _, rows, _ = read(job, "west.csv", text.encode("cp1252"))
    assert result.encoding == "cp1252" and rows[0] == ("Café Señor Müller 0", "€0.50")


def test_encoding_override_and_strict_decoding(job):
    data = "a,b\nCafé,1\n".encode("latin-1")
    result, _, rows, _ = read(job, "x.csv", data, encoding="latin-1")
    assert result.encoding == "iso8859-1" and rows == [("Café", "1")]
    assert failure(job, "y.csv", data, encoding="utf-8").code == "encoding_error"
    assert failure(job, "z.csv", b"a,b\n1,\x00\n").code == "content_mismatch"
    late = b"a,b\n" + b"1,2\n" * 2000 + b"1,\x00\n"
    assert failure(job, "late.csv", late).code == "unsafe_content"


@needs_extensions
def test_xlsx_lists_sheets_and_reads_stored_text(job):
    result, columns, rows, types = read(job, "book.xlsx", workbook())
    assert [(table.name, table.approx_rows) for table in result.tables] == [
        ("Sales", 3),
        ("Notes", 5),
    ]
    assert columns == ["amount", "region", "note"] and types == {"VARCHAR"}
    assert rows == [("0.1", "North", " padded "), ("2.25", "Søuth", "plain")]
    _, _, notes, _ = read(job, "book2.xlsx", workbook(), table="Notes")
    assert notes[-1] == ("n4",)


@needs_extensions
def test_xlsm_macros_are_ignored_never_run(job):
    data = workbook()
    output = BytesIO()
    with ZipFile(BytesIO(data)) as source, ZipFile(output, "w", ZIP_DEFLATED) as target:
        for item in source.infolist():
            target.writestr(item, source.read(item))
        target.writestr("xl/vbaProject.bin", b'Attribute VB_Name = "Evil"')
    result, _, rows, _ = read(job, "macro.xlsm", output.getvalue())
    assert "macros_ignored" in result.notes and len(rows) == 2


@needs_extensions
def test_real_excel_formulas_follow_the_policy(job):
    data = workbook(formula=True)
    assert failure(job, "f.xlsx", data, formula_cells="reject").code == "unsafe_formula"
    result, _, rows, _ = read(job, "g.xlsx", data, formula_cells="keep_as_text")
    assert "formulas_read_as_cached_values" in result.notes
    assert rows[1][2] is None


@needs_extensions
def test_formula_like_text_follows_the_policy(job):
    data = workbook(formula=True, text_formula=True)
    _, _, rows, _ = read(job, "t.xlsx", data)
    assert rows[1][2] == "=1+1"
    assert failure(job, "u.xlsx", data, formula_cells="reject").code == "unsafe_formula"


@pytest.mark.parametrize("value", ["=HYPERLINK(1)", "+cmd", "@SUM(1)", "-1+2", "\t=1"])
def test_formula_like_csv_cells_kept_verbatim_or_rejected(job, value):
    data = f'a,b\n"{value}",-12.5\n'.encode()
    _, _, rows, _ = read(job, "f.csv", data)
    assert rows == [(value, "-12.5")]
    assert failure(job, "g.csv", data, formula_cells="reject").code == "unsafe_formula"
    _, _, numeric, _ = read(job, "h.csv", b"a\n-12.5\n", formula_cells="reject")
    assert numeric == [("-12.5",)]


@pytest.mark.parametrize(
    "name,pack",
    [
        ("data.csv.gz", gzip.compress),
        ("data.csv.bz2", bz2.compress),
        ("data.csv.xz", lzma.compress),
        ("data.zip", lambda data: zipped({"folder/data.csv": data, "__MACOSX/._data.csv": b"x"})),
    ],
)
def test_archives_with_one_supported_file(job, name, pack):
    result, _, rows, _ = read(job, name, pack(CSV.encode()))
    assert result.format == "csv" and rows == CSV_ROWS and len(result.containers) == 1


@needs_extensions
def test_zip_of_xlsx_also_runs_the_container_guard(job):
    result, _, rows, _ = read(job, "books.zip", zipped({"book.xlsx": workbook()}))
    assert result.format == "xlsx" and result.containers == ("zip",) and len(rows) == 2


def test_zip_bomb_and_compression_bomb_are_refused(job):
    zeros = b"0" * (24 * 1024 * 1024)
    assert failure(job, "bomb.zip", zipped({"a.csv": b"a\n" + zeros})).code == "unsafe_archive"
    assert failure(job, "bomb.csv.gz", gzip.compress(b"a\n" + zeros)).code == "unsafe_archive"
    small = zipped({"a.csv": b"a\n" + b"1\n" * 5000}, ZIP_STORED)
    assert failure(job, "cap.zip", small, max_expanded_bytes=1000).code == "unsafe_archive"
    many = zipped({f"{index}.txt": b"a\n1\n" for index in range(20)})
    assert failure(job, "many.zip", many, max_archive_members=10).code == "unsafe_archive"


def test_archive_structure_rules(job):
    assert failure(job, "two.zip", zipped({"a.csv": b"a\n1", "b.csv": b"a\n1"})).code == (
        "archive_contents"
    )
    assert failure(job, "none.zip", zipped({"a.exe": b"MZ"})).code == "archive_contents"
    assert failure(job, "evil.zip", zipped({"../a.csv": b"a\n1"})).code == "unsafe_archive"
    assert failure(job, "data.gz", gzip.compress(b"a\n1")).code == "archive_contents"
    inner = zipped({"a.csv.gz": gzip.compress(b"a\n1\n")})
    _, _, rows, _ = read(job, "outer.zip", inner)
    assert rows == [("1",)]
    nested = zipped({"b.zip": zipped({"c.zip": zipped({"a.csv": b"a\n1"})})})
    assert failure(job, "deep.zip", nested).code == "archive_nesting"


def test_json_array_and_ndjson_flatten_with_exact_numbers(job):
    text = (
        '[{"id": 1, "amount": 12345678901234567.25, "customer": {"name": "Ana", '
        '"geo": {"city": "Lahore"}}, "tags": ["a", 1.10], "ok": true},\n'
        ' {"id": 2, "amount": null, "extra": "only here"}]'
    )
    _, columns, rows, types = read(job, "data.json", text.encode())
    assert columns == ["id", "amount", "customer.name", "customer.geo.city", "tags", "ok", "extra"]
    assert rows[0] == ("1", "12345678901234567.25", "Ana", "Lahore", '["a",1.10]', "true", None)
    assert rows[1] == ("2", None, None, None, None, None, "only here") and types == {"VARCHAR"}
    lines = '{"a": 0.10}\n\n{"a": -1e3, "b": {"c": "x"}}\n'
    _, columns, rows, _ = read(job, "data.ndjson", b"\xef\xbb\xbf" + lines.encode())
    assert columns == ["a", "b.c"] and rows == [("0.10", None), ("-1e3", "x")]


def test_json_depth_and_shape_limits(job):
    deep = '[{"a": ' + "[" * 100_000 + "]" * 100_000 + "}]"
    assert failure(job, "deep.json", deep.encode()).code == "json_too_deep"
    moderate = '[{"a": ' + "[" * 80 + "]" * 80 + "}]"
    assert failure(job, "mid.json", moderate.encode()).code == "json_too_deep"
    assert failure(job, "scalars.json", b"[1, 2]").code == "malformed_json"
    assert failure(job, "nan.json", b'[{"a": NaN}]').code == "malformed_json"
    assert failure(job, "open.json", b'[{"a": 1}').code == "malformed_json"
    assert failure(job, "dup.json", b'[{"a.b": 1, "a": {"b": 2}}]').code == "duplicate_field"


def test_parquet_input_becomes_text_with_row_count(job):
    job.mkdir(parents=True)
    connection = duckdb.connect()
    target = str(job / "in.parquet")
    connection.execute(
        "COPY (SELECT 1.10::DECIMAL(38,2) AS amount, 0.5::DOUBLE AS ratio, 'x' AS name "
        f"UNION ALL SELECT NULL, 2.0, 'y') TO '{target}' (FORMAT parquet)"
    )
    connection.close()
    result, _, rows, types = read(job, "in.parquet", (job / "in.parquet").read_bytes())
    assert result.tables[0].approx_rows == 2 and types == {"VARCHAR"}
    assert sorted(rows, key=str) == sorted([("1.10", "0.5", "x"), (None, "2.0", "y")], key=str)


@needs_extensions
def test_sqlite_lists_tables_and_reads_all_varchar(job):
    job.mkdir(parents=True)
    path = job / "source.db"
    database = sqlite3.connect(path)
    database.execute("CREATE TABLE orders(amount NUMERIC, note TEXT)")
    database.execute("CREATE TABLE customers(name TEXT)")
    database.execute("CREATE VIEW v AS SELECT * FROM orders")
    database.executemany("INSERT INTO orders VALUES (?, ?)", [("12.50", "a"), ("abc", None)])
    database.commit()
    database.close()
    data = path.read_bytes()
    result, _, rows, types = read(job, "copy.sqlite", data, table="orders")
    assert [table.name for table in result.tables] == ["customers", "orders"]
    assert rows == [("12.5", "a"), ("abc", None)] and types == {"VARCHAR"}
    with pytest.raises(IngestionError):
        read(job, "copy2.sqlite", data, table="v")


def test_xls_fixture_via_calamine(job):
    result, columns, rows, _ = read(job, "sample.xls", (FIXTURES / "sample.xls").read_bytes())
    assert [table.name for table in result.tables] == ["Sales", "Notes"]
    assert columns == ["amount", "region", "day", "count"]
    assert rows == [("0.1", "North", "2024-01-31", "3"), ("2.25", "Søuth", "2024-02-01", "4")]
    assert (
        failure(job, "big.xls", (FIXTURES / "sample.xls").read_bytes(), max_calamine_bytes=100).code
        == "file_too_large"
    )


ODS_CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2">
<office:body><office:spreadsheet><table:table table:name="Data">
<table:table-row><table:table-cell office:value-type="string">
<text:p>amount</text:p></table:table-cell><table:table-cell office:value-type="string">
<text:p>name</text:p></table:table-cell></table:table-row><table:table-row>
<table:table-cell office:value-type="float" office:value="0.1"{formula}><text:p>0.1</text:p>
</table:table-cell><table:table-cell office:value-type="string"><text:p>Ana</text:p>
</table:table-cell></table:table-row>
</table:table></office:spreadsheet></office:body></office:document-content>"""


def ods(formula=""):
    return zipped(
        {
            "mimetype": "application/vnd.oasis.opendocument.spreadsheet",
            "content.xml": ODS_CONTENT.replace("{formula}", formula).replace("\n", ""),
            "META-INF/manifest.xml": (
                '<?xml version="1.0"?><manifest:manifest xmlns:manifest='
                '"urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"/>'
            ),
        }
    )


def test_ods_via_calamine_and_formula_policy(job):
    result, _, rows, _ = read(job, "a.ods", ods())
    assert [table.name for table in result.tables] == ["Data"] and rows == [("0.1", "Ana")]
    formula = ' table:formula="of:=0.05*2"'
    assert failure(job, "b.ods", ods(formula), formula_cells="reject").code == "unsafe_formula"
    assert "formulas_read_as_cached_values" in read(job, "c.ods", ods(formula))[0].notes


def statistics_frame():
    return pd.DataFrame(
        {"amount": [0.1, 2.5, None], "group": [1.0, 2.0, 1.0], "name": ["a", "", "c"]}
    )


@pytest.mark.parametrize(
    "name,writer",
    [
        ("survey.sav", pyreadstat.write_sav),
        ("survey.dta", pyreadstat.write_dta),
        ("survey.xpt", pyreadstat.write_xport),
    ],
)
def test_statistics_files_keep_labels_as_metadata(job, name, writer):
    job.mkdir(parents=True)
    path = job / f"made-{name}"
    labels = {"group": {1.0: "Male", 2.0: "Female"}}
    kwargs = {"variable_value_labels": labels} if name != "survey.xpt" else {}
    writer(statistics_frame(), str(path), column_labels=["Amount PKR", "Group", "Name"], **kwargs)
    result, columns, rows, types = read(job, name, path.read_bytes(), batch_rows=2)
    assert columns == ["amount", "group", "name"] and types == {"VARCHAR"}
    assert rows == [("0.1", "1", "a"), ("2.5", "2", None), (None, "1", "c")]
    assert result.metadata["column_labels"]["amount"] == "Amount PKR"
    if name != "survey.xpt":
        assert result.metadata["value_labels"]["group"] == {"1": "Male", "2": "Female"}
        assert result.tables[0].approx_rows == 3


XML = b"""<?xml version="1.0"?>
<export xmlns="urn:x"><meta>v1</meta><orders>
<order id="1"><amount>0.10</amount>
<customer><name> Ana </name><city>Lahore</city></customer><tag>a</tag><tag>b</tag></order>
<order id="2"><amount>12345678901234567.25</amount></order>
</orders></export>"""


def test_table_shaped_xml_detects_records(job):
    result, columns, rows, types = read(job, "orders.xml", XML)
    assert result.tables[0].name == "order" and result.tables[0].approx_rows == 2
    assert columns == ["@id", "amount", "customer.name", "customer.city", "tag"]
    assert rows[0] == ("1", "0.10", " Ana ", "Lahore", '["a", "b"]')
    assert rows[1] == ("2", "12345678901234567.25", None, None, None) and types == {"VARCHAR"}


@pytest.mark.parametrize(
    "payload",
    [
        b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
        b"<r><i>&x;</i><i>1</i></r>",
        b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaaaaaaaa">'
        b'<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;"><!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;">]>'
        b"<r><i>&c;</i><i>1</i></r>",
    ],
)
def test_xxe_and_billion_laughs_are_refused(job, payload):
    assert failure(job, "evil.xml", payload).code == "unsafe_xml"


@pytest.mark.parametrize(
    "name,head,expected",
    [
        ("a.csv", b"a,b\n1,2", "csv"),
        ("a.CSV", b"\xff\xfea\x00", "csv"),
        ("a.xlsx", b"PK\x03\x04rest", "xlsx"),
        ("a.xlsb", b"PK\x03\x04rest", "xlsb"),
        ("a.xls", bytes.fromhex("d0cf11e0a1b11ae1") + b"\x00" * 8, "xls"),
        ("a.jsonl", b'{"a":1}', "ndjson"),
        ("a.json", b" \n[{}]", "json"),
        ("a.parquet", b"PAR1xxxx", "parquet"),
        ("a.db", b"SQLite format 3\x00", "sqlite"),
        ("a.zsav", b"$FL3@(#)", "sav"),
        ("a.dta", b"<stata_dta><header>", "dta"),
        (
            "a.sas7bdat",
            b"\x00" * 12 + bytes.fromhex("c2ea8160b31411cfbd92080009c7318c181f1011"),
            "sas7bdat",
        ),
        ("a.xpt", b"HEADER RECORD*******LIBRARY HEADER RECORD!!!!!!!", "xpt"),
        ("a.xml", b"\xef\xbb\xbf<?xml version='1.0'?><r/>", "xml"),
        ("a.csv.gz", b"\x1f\x8b\x08", "gz"),
        ("a.zip", b"PK\x05\x06", "zip"),
    ],
)
def test_detect_format_accepts_matching_content(name, head, expected):
    assert detect_format(name, head) == expected


@pytest.mark.parametrize(
    "name,head,code",
    [
        ("a.exe", b"MZ", "unsupported_format"),
        ("noext", b"a,b", "unsupported_format"),
        ("a.csv", b"PK\x03\x04", "content_mismatch"),
        ("a.csv", b"MZ\x90\x00", "content_mismatch"),
        ("a.csv", b"<html><body>", "content_mismatch"),
        ("a.csv", b"a,b\x00\x00", "content_mismatch"),
        ("a.xlsx", bytes.fromhex("d0cf11e0a1b11ae1"), "content_mismatch"),
        ("a.xls", b"PK\x03\x04", "content_mismatch"),
        ("a.parquet", b"a,b\n", "content_mismatch"),
        ("a.json", b"a,b\n", "content_mismatch"),
        ("a.sqlite", b"PAR1", "content_mismatch"),
        ("a.gz", b"BZh9", "content_mismatch"),
        ("a.sav", b"a,b", "content_mismatch"),
    ],
)
def test_detect_format_rejects_wrong_extensions(name, head, code):
    with pytest.raises(IngestionError) as raised:
        detect_format(name, head)
    assert raised.value.code == code and raised.value.status == 415
    assert detect_format.__name__ == "detect_format"


def test_hardened_connection_cannot_reach_other_files_or_loosen_settings(job):
    connection = hardened_connection(job, EXTENSIONS)
    try:
        with pytest.raises(duckdb.Error):
            connection.sql("SELECT * FROM read_csv('/etc/passwd')").fetchall()
        with pytest.raises(duckdb.Error):
            connection.execute("SET enable_external_access = true")
        with pytest.raises(duckdb.Error):
            connection.execute("INSTALL avro")
        assert connection.sql(
            "SELECT current_setting('autoinstall_known_extensions')"
        ).fetchone() == (False,)
    finally:
        connection.close()


def test_single_file_upload_keeps_formula_text_and_exports_neutralise_it():
    from datetime import datetime, timezone

    from openpyxl import load_workbook

    from execplus.config import Settings
    from execplus.domain.exports import ExportContent, ExportTable
    from execplus.domain.pdf_exports import PdfDocument
    from execplus.infrastructure.exports.portable import PortableRenderer
    from execplus.infrastructure.file_parser import StructuredFileParser

    assert Settings().formula_cells == "keep_as_text"
    data = b'name,value\n"=HYPERLINK(""x"")",1\n"\t+cmd",-2\n@SUM(1),3\n'
    parser = StructuredFileParser(formula_cells=Settings().formula_cells)
    _, table = parser.parse_table(BytesIO(data), "f.csv", "text/csv")
    assert [row[0] for row in table.rows] == ['=HYPERLINK("x")', "\t+cmd", "@SUM(1)"]
    with pytest.raises(IngestionError) as raised:
        StructuredFileParser(formula_cells="reject").parse(BytesIO(data), "f.csv", "text/csv")
    assert raised.value.code == "unsafe_formula"
    book = Workbook()
    book.active.append(["name"])
    book.active.append(["=1+1"])
    stream = BytesIO()
    book.save(stream)
    _, sheet = parser.parse_table(BytesIO(stream.getvalue()), "f.xlsx", XLSX_TYPE)
    assert sheet.rows == (("=1+1",),)
    content = ExportContent(
        PdfDocument("Formula check", datetime(2026, 10, 25, tzinfo=timezone.utc), ()),
        (ExportTable("Upload", table.headers, table.rows),),
        (),
    )
    renderer = PortableRenderer()
    with ZipFile(BytesIO(renderer.render(content, "csv"))) as archive:
        exported = archive.read("result-1.csv").decode("utf-8-sig")
    assert '"\'=HYPERLINK(""x"")"' in exported and '"\'\t+cmd"' in exported
    assert '"\'@SUM(1)"' in exported
    workbook_out = load_workbook(BytesIO(renderer.render(content, "xlsx")), data_only=False)
    cells = [row[0] for row in list(workbook_out["Upload"].rows)[1:]]
    assert all(cell.data_type == "s" for cell in cells)
    assert cells[0].value == '=HYPERLINK("x")'


XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
