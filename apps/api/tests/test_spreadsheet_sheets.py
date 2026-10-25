"""Use case: Proves multi-sheet spreadsheets skip empty leading sheets and import any sheet.

What it does: Generates XLSX/ODS workbooks with an empty first sheet and several data sheets,
checks sheet listing with row counts, the stored "r:<suffix>#<n>" format and its exact
reconstruction, old "r:xlsx" first-sheet replay, and the HTTP list/import-sheet contract
(auth, unknown sheet, quota) on real PostgreSQL/MinIO.
"""

import os
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import duckdb
import pytest
from openpyxl import Workbook

from execplus.domain.ingestion import IngestionError, stored_table
from execplus.infrastructure.columnar.converter import DuckDBColumnarConverter
from execplus.infrastructure.columnar.source_rows import read_source_table, stored_format
from execplus.infrastructure.readers import ReaderOptions, hardened_connection, open_source

EXTENSIONS = Path(
    os.environ.get(
        "EXECPLUS_DUCKDB_EXTENSION_DIRECTORY",
        Path(__file__).resolve().parents[3] / "data" / "duckdb-extensions",
    )
)
needs_excel = pytest.mark.skipif(
    not any(EXTENSIONS.glob(f"v{duckdb.__version__}/*/excel.duckdb_extension")),
    reason="bundled DuckDB excel extension is not installed",
)


def book(first_has_data=False):
    workbook = Workbook()
    first = workbook.active
    first.title = "Cover"
    if first_has_data:
        first.append(["name", "amount"])
        first.append(["cover", "9"])
    leads = workbook.create_sheet("Leads")
    leads.append(["name", "amount"])
    leads.append(["Ana", "0.10"])
    leads.append(["Bo", "0.20"])
    archive = workbook.create_sheet("Archive")
    archive.append(["name", "amount"])
    for index in range(4):
        archive.append([f"old{index}", f"{index}.5"])
    notes = workbook.create_sheet("Notes")
    notes.append(["note"])
    notes.append(["call back"])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def ods_table(name, rows):
    body = "".join(
        "<table:table-row>"
        + "".join(
            f'<table:table-cell office:value-type="string"><text:p>{cell}</text:p>'
            "</table:table-cell>"
            for cell in row
        )
        + "</table:table-row>"
        for row in rows
    )
    return f'<table:table table:name="{name}">{body}</table:table>'


def ods_book():
    tables = (
        ods_table("Empty", [])
        + ods_table("Leads", [("name", "amount"), ("Ana", "0.10"), ("Bo", "0.20")])
        + ods_table("Archive", [("name", "amount"), ("old", "1.5")])
    )
    content = (
        '<?xml version="1.0" encoding="UTF-8"?><office:document-content '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2">'
        f"<office:body><office:spreadsheet>{tables}</office:spreadsheet></office:body>"
        "</office:document-content>"
    )
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet")
        archive.writestr("content.xml", content)
        archive.writestr(
            "META-INF/manifest.xml",
            '<?xml version="1.0"?><manifest:manifest xmlns:manifest='
            '"urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"/>',
        )
    return output.getvalue()


def converter():
    return DuckDBColumnarConverter(extension_directory=EXTENSIONS, memory_limit_mb=512, threads=1)


def convert(tmp_path, name, data, table=None):
    source = tmp_path / name
    source.write_bytes(data)
    work = tmp_path / f"work-{table}"
    work.mkdir()
    return converter().convert(source, name, work, table)


def parquet_rows(conversion):
    return (
        duckdb.connect()
        .execute("SELECT * FROM read_parquet(?) ORDER BY 1", [conversion.parquet])
        .fetchall()
    )


def test_stored_table_format_is_backward_compatible():
    assert stored_format("a.xlsx") == "r:xlsx" and stored_format("a.xlsx", 2) == "r:xlsx#2"
    assert stored_table("r:xlsx") == ("xlsx", 0) and stored_table("r:ods#3") == ("ods", 3)
    assert stored_table("xlsx") == ("xlsx", 0) and stored_table("csv;s") == ("csv;s", 0)


@needs_excel
def test_xlsx_lists_sheets_skips_empty_first_and_replays_chosen_sheet(tmp_path):
    data = book()
    listed = converter().tables(_write(tmp_path, "b.xlsx", data), "b.xlsx", tmp_path)
    assert listed == (("Cover", 0), ("Leads", 2), ("Archive", 4), ("Notes", 1))
    first = convert(tmp_path, "b.xlsx", data)
    assert first.format == "r:xlsx#1" and first.rows == 2
    assert [row[0] for row in parquet_rows(first)] == ["Ana", "Bo"]
    chosen = convert(tmp_path, "b.xlsx", data, "Archive")
    assert chosen.format == "r:xlsx#2" and chosen.rows == 4
    for conversion, expected in ((first, "Ana"), (chosen, "old0")):
        _, table = read_source_table(
            BytesIO(data), conversion.format, EXTENSIONS, "keep_as_text", 100
        )
        assert table.headers == ("name", "amount") and table.rows[0][0] == expected
    with pytest.raises(IngestionError) as raised:
        convert(tmp_path, "b.xlsx", data, "Missing")
    assert raised.value.status == 404


@needs_excel
def test_old_first_sheet_format_still_reads_the_first_sheet(tmp_path):
    data = book(first_has_data=True)
    conversion = convert(tmp_path, "b.xlsx", data)
    assert conversion.format == "r:xlsx"
    _, table = read_source_table(BytesIO(data), "r:xlsx", EXTENSIONS, "keep_as_text", 100)
    assert table.rows == (("cover", "9"),)


def test_ods_lists_row_counts_and_skips_empty_leading_table(tmp_path):
    data = ods_book()
    path = _write(tmp_path, "b.ods", data)
    result = open_source(path, "b.ods", ReaderOptions(tmp_path, EXTENSIONS))
    assert [(info.name, info.approx_rows) for info in result.tables] == [
        ("Empty", 0),
        ("Leads", 2),
        ("Archive", 1),
    ]
    connection = hardened_connection(tmp_path, EXTENSIONS)
    try:
        assert result.first_filled(connection) == "Leads"
    finally:
        connection.close()
    conversion = convert(tmp_path, "b.ods", data)
    assert conversion.format == "r:ods#1" and conversion.rows == 2
    _, table = read_source_table(BytesIO(data), "r:ods#2", EXTENSIONS, "keep_as_text", 100)
    assert table.rows == (("old", "1.5"),)


def _write(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    return path


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@needs_excel
def test_sheet_listing_and_import_api(integration, tmp_path):
    from test_columnar_integration import enable_columnar
    from test_workspace_integration import dataset, identity, upload, workspace

    env = integration
    enable_columnar(env, tmp_path)
    env.runtime.service.converter.extension_directory = EXTENSIONS
    owner, user = identity(env, "sheets@example.test")
    outsider, _ = identity(env, "sheets-outsider@example.test")
    wid = workspace(env, owner)
    did = dataset(env, owner, wid)
    response = upload(env, owner, wid, did, book(), name="leads.xlsx", mime=XLSX)
    assert response.status_code == 201, response.text
    assert response.json()["format"] == "r:xlsx#1" and response.json()["row_count"] == 2
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{response.json()['id']}/sheets"
    listing = env.client.get(root, headers=owner)
    assert listing.status_code == 200, listing.text
    assert listing.json() == {
        "imported": "Leads",
        "sheets": [
            {"name": "Cover", "rows": 0},
            {"name": "Leads", "rows": 2},
            {"name": "Archive", "rows": 4},
            {"name": "Notes", "rows": 1},
        ],
    }
    assert env.client.get(root, headers=outsider).status_code in {403, 404}
    denied = env.client.post(root + "/import", headers=outsider, json={"sheet": "Archive"})
    assert denied.status_code in {403, 404}
    missing = env.client.post(root + "/import", headers=owner, json={"sheet": "Nope"})
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "unknown_sheet"
    same = env.client.post(root + "/import", headers=owner, json={"sheet": "Leads"})
    assert same.status_code == 409
    imported = env.client.post(root + "/import", headers=owner, json={"sheet": "Archive"})
    assert imported.status_code == 201, imported.text
    created = imported.json()
    assert created["dataset_id"] != did and created["format"] == "r:xlsx#2"
    assert created["row_count"] == 4
    names = [
        item["name"] for item in env.client.get(f"/workspaces/{wid}/datasets", headers=owner).json()
    ]
    assert "Sales - Archive" in names
    new_root = f"/workspaces/{wid}/datasets/{created['dataset_id']}/uploads/{created['id']}"
    assert env.client.get(new_root + "/sheets", headers=owner).json()["imported"] == "Archive"
    used = env.client.get("/me/storage", headers=owner).json()["used_bytes"]
    env.runtime.operations.set_storage_quota(None, user.id, used + 10)
    count = len(env.client.get(f"/workspaces/{wid}/datasets", headers=owner).json())
    over = env.client.post(root + "/import", headers=owner, json={"sheet": "Notes"})
    assert over.status_code == 409 and over.json()["error"]["code"] == "quota_exceeded"
    assert len(env.client.get(f"/workspaces/{wid}/datasets", headers=owner).json()) == count
