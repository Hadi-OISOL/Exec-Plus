"""Use case: Checks fictional starter files before users rely on their walkthrough.

What it does: Independently verifies coverage, fixed totals, planted observations and version bytes.
"""

import csv
import json
import runpy
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
from io import StringIO
from itertools import product
from pathlib import Path

import pytest

from execplus.domain.samples import sample_csv


def rows(sample_id):
    return list(csv.DictReader(StringIO(sample_csv(sample_id).decode())))


@pytest.mark.parametrize(
    ("sample_id", "checksum"),
    [
        ("retail-v1", "6975c6835c76ecdf44cd757c5865374159fce3152ffb166d9b37cffd2d6f71cd"),
        ("actions-v1", "4688a99349cd88b5624a9fde25d18a74972d23b6a5bcfe3e316e631249ce672f"),
    ],
)
def test_starter_sample_versions_have_frozen_bytes(sample_id, checksum):
    assert sha256(sample_csv(sample_id)).hexdigest() == checksum


def test_retail_demo_has_complete_unique_region_days_and_exact_known_totals():
    data = rows("retail-v1")
    expected_dates = {(date(2025, 1, 1) + timedelta(days=i)).isoformat() for i in range(365)}
    assert len(data) == 1095
    assert len(data[0]) == 13
    assert len({row["Record_ID"] for row in data}) == len(data)
    assert all(all(value for value in row.values()) for row in data)
    assert Counter(row["Region"] for row in data) == dict(North=365, Central=365, South=365)
    for region in ("North", "Central", "South"):
        assert {row["Date"] for row in data if row["Region"] == region} == expected_dates
    expected = {
        "Orders": "141464",
        "Revenue_USD": "8235156.60",
        "Ad_Spend_USD": "901678.00",
        "Visits": "2546220",
        "Returns": "7309",
        "Support_Tickets": "20325",
    }
    for column, total in expected.items():
        assert sum(Decimal(row[column]) for row in data) == Decimal(total)
    assert {
        (row["Date"], row["Region"], row["Support_Tickets"])
        for row in data
        if int(row["Support_Tickets"]) > 100
    } == {
        ("2025-03-15", "North", "180"),
        ("2025-07-01", "Central", "240"),
        ("2025-10-14", "South", "300"),
    }


def test_action_demo_has_independently_enumerated_unique_best_choice():
    data = rows("actions-v1")
    feasible = []
    for quantities in product((0, 1), repeat=len(data)):
        chosen = {row["Action"] for row, quantity in zip(data, quantities, strict=True) if quantity}
        cost, benefit, hours = (
            sum(Decimal(row[field]) * q for row, q in zip(data, quantities, strict=True))
            for field in ("Cost_USD", "Benefit_USD", "Staff_Hours")
        )
        if cost > 1000 or hours > 10:
            continue
        if "Email campaign" in chosen and "Tracking setup" not in chosen:
            continue
        if {"Search ads", "Social ads"} <= chosen:
            continue
        feasible.append((benefit, cost, hours, chosen))
    best_benefit = max(item[0] for item in feasible)
    winners = [item for item in feasible if item[0] == best_benefit]
    assert winners == [
        (
            Decimal(160),
            Decimal(1000),
            Decimal(9),
            {"Tracking setup", "Email campaign", "Search ads"},
        )
    ]


def test_local_kit_manifest_matches_files_and_reruns_preserve_edits(tmp_path):
    script = Path(__file__).resolve().parents[3] / "scripts/create_demo_kit.py"
    create = runpy.run_path(str(script))["create"]
    create(tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["synthetic"] is True
    for name, checksum in manifest["files"].items():
        assert sha256((tmp_path / name).read_bytes()).hexdigest() == checksum
    create(tmp_path)
    edited = tmp_path / "execplus-retail-daily-v1.csv"
    edited.write_text("My edited data,keep this\n")
    with pytest.raises(FileExistsError, match="Preserve"):
        create(tmp_path)
    assert edited.read_text() == "My edited data,keep this\n"
