"""Use case: Keeps explicit workflow fixtures truthful, reproducible and reversible.

What it does: Checks independent expected totals and quality edge cases, safe
upload behavior, exact hashes and preservation of edited local fixture files.
"""

import csv
import hashlib
import importlib.util
import json
from decimal import Decimal
from io import BytesIO, StringIO

import pytest

from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.file_parser import StructuredFileParser

spec = importlib.util.spec_from_file_location(
    "workflow_kit", "scripts/create_synthetic_workflow_kit.py"
)
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)


def manifest():
    files = kit.artifacts()
    return files, {row["file"]: row for row in json.loads(files["manifest.json"])["datasets"]}


def total(entry, field):
    row = next(item for item in entry["oracles"] if item["field"] == field)
    return Decimal(row["sum_valid_numeric_cells"])


def test_repeatable_fictional_domains_have_independent_known_totals_and_integrity():
    files, entries = manifest()
    assert files == kit.artifacts()
    assert len(entries) == 9
    assert total(entries["finance-daily.csv"], "revenue") == Decimal("12714")
    assert total(entries["finance-daily.csv"], "cost") == Decimal("7557")
    assert total(entries["sales-orders.csv"], "units") == Decimal("720")
    assert total(entries["sales-orders.csv"], "revenue") == Decimal("2340")
    assert total(entries["sales-orders.csv"], "cost") == Decimal("1188")
    assert total(entries["hr-workforce.csv"], "salary") == Decimal("30900")
    assert total(entries["hr-workforce.csv"], "fte") == Decimal("21")
    assert total(entries["company-a.csv"], "amount") == 0
    assert total(entries["company-b.csv"], "amount") == 0
    assert total(entries["precision-and-nulls.csv"], "amount") == Decimal("0.000000000000000001")
    for name, entry in entries.items():
        assert entry["sha256"] == hashlib.sha256(files[name]).hexdigest()
        assert entry["shared_definitions_require_explicit_confirmation"] is True
        rows = list(csv.reader(StringIO(files[name].decode())))
        assert len(rows) == entry["rows"] + 1


def test_snapshot_inventory_is_not_presented_as_additive_across_time():
    files, entries = manifest()
    rows = list(csv.DictReader(StringIO(files["inventory-snapshots.csv"].decode())))
    final_day = max(row["date"] for row in rows)
    assert sum(int(row["on_hand"]) for row in rows if row["date"] == final_day) == 329
    assert any(
        "Do not total on_hand across dates" in note
        for note in entries["inventory-snapshots.csv"]["notes"]
    )


def test_dirty_and_formula_fixtures_are_explicit_and_never_silently_repaired():
    files, entries = manifest()
    dirty = entries["dirty-review.csv"]
    assert dirty["duplicate_rows"] == 1
    revenue = next(row for row in dirty["oracles"] if row["field"] == "revenue")
    assert revenue["invalid_numeric_cells"] == 1 and not revenue["numeric_parse_complete"]
    assert Decimal(revenue["sum_valid_numeric_cells"]) == Decimal("187.500000000000000002")
    parser = StructuredFileParser()
    for name, entry in entries.items():
        if entry["expected_rejection"]:
            with pytest.raises(IngestionError) as failure:
                parser.parse(BytesIO(files[name]), name, "text/csv")
            assert failure.value.code == entry["expected_rejection"]
        else:
            assert parser.parse(BytesIO(files[name]), name, "text/csv").row_count == entry["rows"]


def test_generator_preserves_all_existing_files_before_writing_any_changes(tmp_path):
    destination = tmp_path / "kit"
    kit.create(destination)
    before = {path.name: path.read_bytes() for path in destination.iterdir()}
    kit.create(destination)
    assert before == {path.name: path.read_bytes() for path in destination.iterdir()}
    changed = destination / "finance-daily.csv"
    changed.write_bytes(b"User changes must remain")
    (destination / "sales-orders.csv").unlink()
    with pytest.raises(FileExistsError):
        kit.create(destination)
    assert changed.read_bytes() == b"User changes must remain"
    assert not (destination / "sales-orders.csv").exists()


def test_generator_refuses_symbolic_link_destinations_and_members(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)
    with pytest.raises(ValueError):
        kit.create(link)
    outside = tmp_path / "keep"
    outside.write_bytes(b"preserve")
    (actual / "finance-daily.csv").symlink_to(outside)
    with pytest.raises(FileExistsError):
        kit.create(actual)
    assert outside.read_bytes() == b"preserve"
