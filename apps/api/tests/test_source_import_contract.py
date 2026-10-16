"""Use case: Rejects invalid operator source contracts before network access.

What it does: Checks exact endpoint, selection and snapshot boundaries without
accepting malformed untrusted configuration as usable connector metadata.
"""

import hashlib
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from execplus.domain.ingestion import IngestionError
from execplus.domain.source_imports import PostgresSource, SourceSnapshot, SourceTable


def source():
    return PostgresSource(
        uuid4(),
        uuid4(),
        1,
        "Approved source",
        "db.example.test",
        "192.0.2.42",
        5432,
        "warehouse",
        "readonly",
        (SourceTable("public", "sales", ("id", "amount")),),
    )


@pytest.mark.parametrize(
    "change",
    [
        {"address": 123},
        {"address": "169.254.169.254"},
        {"address": "0.0.0.0"},
        {"host": "db.test password=secret"},
        {"secret_ref": None},
        {"secret_ref": "../secret"},
        {"tables": ("sales",)},
        {"version": True},
        {"port": True},
        {"max_rows": 10001},
    ],
)
def test_malformed_source_configuration_is_refused(change):
    with pytest.raises(IngestionError):
        replace(source(), **change)


@pytest.mark.parametrize("columns", [(None,), ([],), ("id", "id"), (), ("id\x00",)])
def test_selection_requires_distinct_literal_names(columns):
    with pytest.raises(IngestionError):
        SourceTable("public", "sales", columns)


def test_disabled_or_unapproved_source_cannot_be_selected():
    for candidate, columns in [
        (replace(source(), enabled=False), ("id",)),
        (source(), ("salary",)),
    ]:
        with pytest.raises(IngestionError) as caught:
            candidate.select("public", "sales", columns)
        assert caught.value.status == 404


@pytest.mark.parametrize(
    "change",
    [
        {"columns": None},
        {"columns": ("id",)},
        {"columns": (("id", "int4"), ("id", "int4"))},
        {"extracted_at": None},
        {"source_version": True},
        {"source_version": 0},
        {"row_count": 0},
        {"checksum": "not-a-hash"},
    ],
)
def test_incomplete_snapshot_contract_is_refused(change):
    content = b"id\n1\n"
    snapshot = SourceSnapshot(
        content,
        (("id", "int4"),),
        1,
        datetime.now(timezone.utc),
        1,
        hashlib.sha256(content).hexdigest(),
    )
    with pytest.raises(IngestionError):
        replace(snapshot, **change)


def import_record():
    from execplus.domain.source_imports import ImportSelection, SourceImport

    current = source()
    now = datetime.now(timezone.utc)
    return SourceImport(
        uuid4(),
        current.workspace_id,
        uuid4(),
        now,
        uuid4(),
        ImportSelection(current.id, current.version, uuid4(), current.tables[0]),
        {},
        "extracting",
        now,
    )


def test_import_selection_signature_preserves_exact_order_and_action():
    value = import_record().selection
    assert value.signature() == replace(value).signature()
    assert (
        value.signature()
        != replace(value, table=replace(value.table, columns=("amount", "id"))).signature()
    )
    assert value.signature() != replace(value, mode="refresh", expected_feed_version=1).signature()
    assert value.signature() != replace(value, source_version=2).signature()


@pytest.mark.parametrize(
    "change",
    [
        {"source_version": True},
        {"source_version": 0},
        {"mode": "query"},
        {"mode": "refresh"},
        {"expected_feed_version": 1},
        {"mode": "refresh", "expected_feed_version": True},
    ],
)
def test_import_selection_rejects_missing_or_invented_target_state(change):
    with pytest.raises(IngestionError):
        replace(import_record().selection, **change)


@pytest.mark.parametrize(
    "change",
    [
        {"status": "success"},
        {"upload_id": uuid4()},
        {"failure_code": "password=private"},
        {"status": "failed"},
        {"status": "imported"},
        {"status": "staged"},
        {"membership_created_at": datetime(2026, 1, 1)},
    ],
)
def test_unfinished_import_cannot_claim_completion_or_store_raw_failure(change):
    with pytest.raises(IngestionError):
        replace(import_record(), **change)


def test_completed_import_metadata_is_exact_and_contains_no_connection_or_record_content():
    from execplus.domain.source_imports import snapshot_metadata

    value = import_record()
    content = b"id,amount\n1,0.100000000000\n"
    snapshot = SourceSnapshot(
        content,
        (("id", "int4"), ("amount", "numeric")),
        1,
        value.created_at,
        1,
        hashlib.sha256(content).hexdigest(),
    )
    completed = replace(
        value,
        status="imported",
        completed_at=value.created_at,
        upload_id=uuid4(),
        snapshot=snapshot_metadata(snapshot),
    )
    assert completed.snapshot["columns"] == [["id", "int4"], ["amount", "numeric"]]
    assert "0.100000000000" not in repr(completed)
    for change in [
        {"columns": [["hidden", "text"], ["amount", "numeric"]]},
        {"row_count": True},
        {"row_count": 0},
        {"checksum": "unknown"},
        {"extracted_at": "2026-10-16"},
        {"sql": "SELECT private"},
    ]:
        with pytest.raises(IngestionError):
            replace(completed, snapshot=completed.snapshot | change)


def test_failed_import_has_only_an_allowlisted_failure_code():
    value = import_record()
    result = replace(
        value, status="failed", completed_at=value.created_at, failure_code="source_timeout"
    )
    assert result.snapshot is None and result.upload_id is None
    with pytest.raises(IngestionError):
        replace(result, failure_code="source password and host leaked here")
