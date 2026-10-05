"""Use case: Covers real-world delimited CSV intake without changing old snapshots.

What it does: Checks dialect evidence, retained source bytes, formula rejection and exact replay.
"""

from functools import partial
from io import BytesIO

import pytest

from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.file_parser import StructuredFileParser
from test_workspace_integration import dataset, identity, upload, workspace


@pytest.mark.parametrize("delimiter,format", [(";", "csv;s"), ("\t", "csv;t"), (",", "csv")])
def test_dialect_is_retained_and_exact_cells_are_reconstructed(delimiter, format):
    parser = StructuredFileParser()
    content = BytesIO(
        f'city{delimiter}amount{delimiter}note\nLahore{delimiter}0.10{delimiter}"quoted{delimiter}text"\n'.encode()
    )
    structure = parser.parse(content, "source.csv", "text/csv")
    assert (structure.format, structure.row_count, structure.column_count) == (format, 1, 3)
    table = parser.read_table(content, structure.format)
    assert table.rows == (("Lahore", "0.10", f"quoted{delimiter}text"),)


def test_original_single_column_comma_reconstruction_does_not_change():
    content = BytesIO(b"city;amount\nLahore;0.10\n")
    parser = StructuredFileParser()
    assert parser.parse(content, "legacy.csv", "text/csv").format == "csv;s"
    original = parser.read_table(content, "csv")
    assert original.headers == ("city;amount",)
    assert original.rows == (("Lahore;0.10",),)


def test_old_single_column_source_keeps_its_original_validation_even_with_uneven_semicolons():
    content = BytesIO(b"label;extra\nold;free;text\n")
    parser = StructuredFileParser()
    original = parser.parse(content, "legacy.csv", "text/csv", stored_format="csv")
    assert (original.format, original.row_count, original.column_count) == ("csv", 1, 1)
    assert parser.read_table(content, original.format).rows == (("old;free;text",),)
    with pytest.raises(IngestionError):
        parser.parse(content, "new.csv", "text/csv")


def test_quoted_header_punctuation_does_not_change_comma_dialect():
    content = BytesIO(b'"label;with;punctuation",amount\nx,1\n')
    parser = StructuredFileParser()
    assert parser.parse(content, "source.csv", "text/csv").format == "csv"
    assert parser.read_table(content, "csv").headers == ("label;with;punctuation", "amount")


@pytest.mark.parametrize("delimiter", [";", "\t"])
@pytest.mark.parametrize("value,code", [("=1+2", "unsafe_formula"), ("@SUM(x)", "unsafe_formula")])
def test_other_dialects_preserve_formula_rejection(delimiter, value, code):
    parser = StructuredFileParser()
    content = BytesIO(f"name{delimiter}value\nx{delimiter}{value}\n".encode())
    with pytest.raises(IngestionError) as raised:
        parser.parse(content, "source.csv", "text/csv")
    assert raised.value.code == code


@pytest.mark.parametrize("delimiter", [";", "\t"])
def test_other_dialects_reject_inconsistent_width(delimiter):
    content = BytesIO(f"city{delimiter}amount\nLahore{delimiter}1{delimiter}extra\n".encode())
    with pytest.raises(IngestionError) as raised:
        StructuredFileParser().parse(content, "source.csv", "text/csv")
    assert raised.value.code == "malformed_csv"


@pytest.mark.parametrize("delimiter,format", [(";", "csv;s"), ("\t", "csv;t")])
def test_dialect_upload_retains_original_and_exact_query_receipt(integration, delimiter, format):
    env = integration
    owner, _ = identity(env, "dialect@example.test")
    wid = workspace(env, owner)
    did = dataset(env, owner, wid)
    content = f"city{delimiter}amount\nLahore{delimiter}0.10\nLahore{delimiter}0.20\n".encode()
    response = upload(env, owner, wid, did, content)
    assert response.status_code == 201, response.text
    assert response.json()["format"] == format
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{response.json()['id']}"
    assert env.client.get(root + "/content", headers=owner).content == content
    query = env.client.post(
        root + "/query", headers=owner, json={"metric": "amount", "aggregation": "sum"}
    )
    assert query.status_code == 200, query.text
    assert query.json()["rows"] == [["0.300000000000"]]
    replay = env.client.post(
        f"/workspaces/{wid}/queries/{query.json()['lineage']['query_id']}/replay", headers=owner
    )
    assert replay.status_code == 200
    assert replay.json()["rows"] == query.json()["rows"]


def test_legacy_single_column_upload_reopens_original_profile(integration, monkeypatch):
    env = integration
    owner, _ = identity(env, "legacy-dialect@example.test")
    wid = workspace(env, owner)
    did = dataset(env, owner, wid)
    parser = env.runtime.service.parser
    original_parse = parser.parse
    monkeypatch.setattr(parser, "parse", partial(original_parse, stored_format="csv"))
    response = upload(env, owner, wid, did, b"label;extra\nold;free;text\n")
    assert response.status_code == 201
    assert response.json()["format"] == "csv"
    monkeypatch.setattr(parser, "parse", original_parse)
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{response.json()['id']}"
    result = env.client.get(root + "/profile", headers=owner)
    assert result.status_code == 200, result.text
    assert result.json()["profile"]["column_count"] == 1
    assert result.json()["profile"]["columns"][0]["name"] == "label;extra"
    assert (
        env.client.get(root + "/content", headers=owner).content == b"label;extra\nold;free;text\n"
    )
