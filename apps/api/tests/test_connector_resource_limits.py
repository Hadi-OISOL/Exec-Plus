"""Use case: Refuses oversized external data before it becomes a retained upload.

What it does: Exercises streaming, compression, page accumulation and database row/column guards.
"""

import httpx
import pytest

from execplus.application.connector_ports import ConnectorSession
from execplus.domain import connectors as domain
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.bounded_http import limited_request
from execplus.infrastructure.connectors import database as postgres
from execplus.infrastructure.connectors import xero
from test_connectors_database import database  # noqa: F401
from test_connectors_logic import client, xero_handler


class Chunks(httpx.SyncByteStream):
    def __init__(self):
        self.read = 0
        self.closed = False

    def __iter__(self):
        for _ in range(100):
            self.read += 1
            yield b"x" * 65536

    def close(self):
        self.closed = True


@pytest.mark.parametrize("encoding", ["identity", "gzip"])
def test_streaming_stops_before_oversized_or_compressed_bodies_are_buffered(encoding):
    stream = Chunks()

    def handler(request):
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(200, headers={"Content-Encoding": encoding}, stream=stream)

    with client(handler) as transport, pytest.raises(IngestionError) as caught:
        limited_request(transport, "GET", "https://source.test/data", max_bytes=65536)
    assert caught.value.status == 413
    assert stream.read == (2 if encoding == "identity" else 0)
    assert stream.closed


def test_records_refuse_huge_fields_and_cumulative_pages_before_append(monkeypatch):
    monkeypatch.setattr(domain, "MAX_IMPORT_BYTES", 120)
    records = domain.RecordBuffer()
    records.append({"value": "x" * 60})
    with pytest.raises(IngestionError):
        records.append({"value": "y" * 60})
    assert len(records) == 1
    with pytest.raises(IngestionError):
        domain.records_to_csv([{"value": "x" * 121}])


def test_records_refuse_wide_rows_and_accumulated_columns_and_cells(monkeypatch):
    monkeypatch.setattr(domain, "MAX_COLUMNS", 2)
    with pytest.raises(IngestionError):
        domain.records_to_csv([{"a": 1, "b": 2, "c": 3}])
    with pytest.raises(IngestionError):
        domain.records_to_csv([{"a": 1}, {"b": 2}, {"c": 3}])
    monkeypatch.setattr(domain, "MAX_CELLS", 2)
    with pytest.raises(IngestionError):
        domain.records_to_csv([{"a": 1}, {"a": 2}, {"a": 3}])


def test_provider_pagination_obeys_cumulative_byte_budget(monkeypatch):
    monkeypatch.setattr(domain, "MAX_IMPORT_BYTES", 120)
    monkeypatch.setattr(xero, "PAGE", 1)
    seen = []
    pages = {1: [{"value": "x" * 60}], 2: [{"value": "y" * 60}]}
    connector = xero.XeroConnector("c", "s", "x", client(xero_handler(pages, seen)))
    with pytest.raises(IngestionError) as caught:
        connector.fetch(ConnectorSession("token", {"tenant_id": "t"}), "Invoices", 100)
    assert caught.value.code == "source_too_large"
    assert len(seen) == 2


def test_postgres_refuses_oversized_rows_and_wide_projections(database, monkeypatch):  # noqa: F811
    schema, credentials, _ = database
    connector = postgres.PostgresConnector(postgres.HostPolicy(True))
    session = ConnectorSession("", credentials)
    monkeypatch.setattr(postgres, "MAX_IMPORT_BYTES", 10)
    with pytest.raises(IngestionError) as caught:
        connector.fetch(session, f"table/{schema}/orders", 10)
    assert caught.value.code == "source_too_large"
    monkeypatch.setattr(postgres, "MAX_COLUMNS", 2)
    with pytest.raises(IngestionError):
        connector.fetch(session, f"table/{schema}/orders", 10)


def test_google_sheet_bounds_values_and_encoded_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    from execplus.domain import google_oauth

    monkeypatch.setattr(google_oauth, "MAX_IMPORT_BYTES", 20)
    for values in [[["field"], ["x" * 21]], [["a"], ['"' * 10]]]:
        with pytest.raises(IngestionError, match="size limits"):
            google_oauth.sheet_to_csv(values)


@pytest.mark.parametrize(
    ("rows", "status", "code"),
    [
        (
            [{"customer_name": "first", "customer": {"name": "second"}}],
            422,
            "ambiguous_source_columns",
        ),
        ([{"field": "x" * 201}], 413, "source_too_large"),
    ],
)
def test_import_rejects_invalid_source_without_partial_upload(
    integration, monkeypatch: pytest.MonkeyPatch, rows, status, code
) -> None:
    from test_connectors_service import setup_import

    oauth, _, owner, _, base = setup_import(integration)
    monkeypatch.setattr(domain, "MAX_IMPORT_BYTES", 200)
    oauth.rows = rows
    response = integration.client.post(
        f"{base}/connectors/quickbooks/import", headers=owner, json={"source_id": "Invoice"}
    )
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert integration.client.get(f"{base}/uploads", headers=owner).json() == []
