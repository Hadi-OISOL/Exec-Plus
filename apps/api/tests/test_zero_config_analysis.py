"""Use case: Proves unusual-value checks and forecasts start without user settings.

What it does: Covers inferred no-date files, planted outliers, drafts and one-click forecasts.
"""

import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.forecast_defaults import quick_start
from execplus.domain.guidance import DescriptionContext
from execplus.domain.models import QueryResult
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import dataset_view
from execplus.domain.unusual_values import scan_request, scan_result
from test_studies import prepare
from test_workspace_integration import dataset, identity, upload, workspace

REFERENCE = Path(__file__).resolve().parents[3] / "data/reference-data/test_100rows.csv"


def farm(outlier: bool = False) -> bytes:
    rows = ["id,Soil_Type,Soil_pH,Rainfall_mm,Region"]
    for index in range(40):
        rain = "9000" if outlier and index == 7 else str(800 + index * 10)
        rows.append(
            f"{630000 + index},{['Clay', 'Silt'][index % 2]},{Decimal(60 + index % 9) / 10},"
            f"{rain},{['North', 'South'][index % 2]}"
        )
    return ("\n".join(rows) + "\n").encode()


def daily() -> bytes:
    rows = ["Date,Region,Revenue_USD"]
    for index in range(60):
        day = date(2025, 1, 1) + timedelta(days=index)
        rows.extend(
            f"{day},{region},{100 + index + offset}" for region, offset in (("A", 0), ("B", 5))
        )
    return ("\n".join(rows) + "\n").encode()


def context(content: bytes, state: str = "inferred", **source: str):
    rows = list(csv.reader(io.StringIO(content.decode())))
    table = TableData(tuple(rows[0]), tuple(tuple(row) for row in rows[1:]))
    facts = profile(table)
    view = dataset_view(facts)
    if source:
        view = type(view)(view.columns, view.metrics, view.dimensions, (source,), None)
    return DescriptionContext("Farm", facts, view, None, state), table


def executed(content: bytes, request):
    rows = list(csv.DictReader(io.StringIO(content.decode())))
    names = [n for n in (request["identifier"], request["group_column"]) if n]
    names += request["measures"]
    values = tuple(
        tuple(
            (Decimal(row[n]) if row[n] else None) if n in request["measures"] else row[n]
            for n in names
        )
        for row in rows
    )
    return QueryResult(uuid4(), tuple(names), tuple(sorted(values, key=str)), len(values))


def test_scan_needs_no_inputs_and_reports_planted_row_exactly():
    content = farm(outlier=True)
    value, table = context(content)
    request = scan_request(value, table)
    assert request["identifier"] == "id"
    assert set(request["measures"]) == {"Soil_pH", "Rainfall_mm"}
    assert request["meaning"] == "inferred"
    result = scan_result(executed(content, request), request)
    top = result["findings"][0]
    assert top["row"] == "id 630007"
    assert top["column"] == "Rainfall_mm"
    assert top["value"] == "9000"
    assert top["direction"] == "high"
    assert "unusually high" in top["explanation"]
    assert result["total_findings"] == 1
    assert result["closest"] == []


def test_scan_flags_single_value_away_from_constant_reference():
    content = b"city,amount,cost\n" + b"".join(b"A%d,10.10,1.00\n" % i for i in range(8))
    content += b"Z,100.10,1.00\n"
    value, table = context(content)
    request = scan_request(value, table)
    assert {"column": "cost", "reason": "Every value is the same."} in request["exclusions"]
    result = scan_result(executed(content, request), request)
    assert [(item["column"], item["value"]) for item in result["findings"]] == [("amount", "100.1")]
    assert result["findings"][0]["method"] == "constant_reference"


def test_scan_without_outliers_says_nothing_stands_out_and_shows_extremes():
    content = farm()
    value, table = context(content)
    request = scan_request(value, table)
    result = scan_result(executed(content, request), request)
    assert result["findings"] == []
    assert "Nothing stands out" in result["summary"]
    assert 1 <= len(result["closest"]) <= 3
    assert all("still inside the usual range" in item["explanation"] for item in result["closest"])


@pytest.mark.skipif(not REFERENCE.exists(), reason="The local reference farm file is not present")
def test_reference_farm_file_scan_runs_without_inputs():
    content = REFERENCE.read_bytes()
    value, table = context(content)
    request = scan_request(value, table)
    result = scan_result(executed(content, request), request)
    assert len(result["measures"]) == 11
    assert result["rows"] == 100
    assert result["findings"] or result["closest"]


def test_small_file_explains_why_no_column_can_be_scanned():
    value, table = context(b"name,amount\na,1\nb,2\nc,3\n")
    with pytest.raises(ClarificationRequiredError, match="amount: Fewer than eight"):
        scan_request(value, table)


def test_saved_draft_meaning_blocks_calculation_with_one_clear_step():
    value, table = context(farm(), revision_id="r", understanding_id="u")
    with pytest.raises(ClarificationRequiredError, match="Confirm them once"):
        scan_request(value, table)


def test_no_date_forecast_returns_friendly_alternatives():
    value, _ = context(farm())
    start = quick_start(value, dict(date_columns=[], state="needs_review", metrics=[]))
    assert start["kind"] == "no_timeline"
    assert start["title"] == "This file has no dates, so we can't forecast over time"
    tools = {item["tool"]: item["available"] for item in start["alternatives"]}
    assert tools == {"unusual_values": True, "patterns": False, "scenario": False}


def test_dated_file_gets_daily_forecast_defaults():
    value, _ = context(daily(), "confirmed")
    start = quick_start(
        value,
        dict(
            date_columns=["Date"],
            state="ready",
            metrics=[dict(name="Revenue_USD", unit="USD", aggregations=["sum", "avg"])],
        ),
    )
    assert start["kind"] == "forecast"
    assert start | {"message": ""} == dict(
        kind="forecast",
        name="Revenue_USD forecast",
        time_column="Date",
        metric="Revenue_USD",
        unit="USD",
        aggregation="sum",
        frequency="daily",
        horizon=14,
        coverage_start="2025-01-01",
        coverage_end="2025-03-01",
        periods=60,
        message="",
    )


def test_unconfirmed_file_scans_and_forecast_explains_without_demands(integration):
    env = integration
    headers, _ = identity(env, f"zero-{uuid4().hex}@example.test")
    wid = workspace(env, headers)
    did = dataset(env, headers, wid)
    content = REFERENCE.read_bytes() if REFERENCE.exists() else farm(outlier=True)
    uid = upload(env, headers, wid, did, content, name="farm.csv").json()["id"]
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{uid}"
    response = env.client.post(root + "/decision-analysis/unusual-values", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == "ready"
    assert body["meaning"] == "inferred"
    assert body["findings"] or body["closest"]
    replay = env.client.post(
        f"/workspaces/{wid}/queries/{body['query_id']}/replay", headers=headers
    )
    assert replay.status_code == 200, replay.text
    other, _ = identity(env, f"other-{uuid4().hex}@example.test")
    denied = env.client.post(root + "/decision-analysis/unusual-values", headers=other)
    assert denied.status_code in {403, 404}
    options = env.client.get(root + "/forecasts/options", headers=headers)
    assert options.status_code == 200, options.text
    assert options.json()["quick_start"]["kind"] == "no_timeline"


def test_dated_confirmed_file_forecasts_with_one_click_defaults(integration):
    env = integration
    owner, _, _, _, _, root = prepare(env, daily())
    options = env.client.get(root + "/forecasts/options", headers=owner).json()
    start = options["quick_start"]
    assert start["kind"] == "forecast"
    assert start["frequency"] == "daily"
    created = env.client.post(
        root + "/forecasts",
        headers=owner,
        json=dict(
            name=start["name"],
            time_column=start["time_column"],
            metric=start["metric"],
            aggregation=start["aggregation"],
            filters=[],
            frequency=start["frequency"],
            horizon=start["horizon"],
            season_length=None,
            coverage_start=start["coverage_start"],
            coverage_end=start["coverage_end"],
            coverage_confirmed=True,
            revision_id=options["revision_id"],
            understanding_id=options["understanding_id"],
        ),
    )
    assert created.status_code == 201, created.text
    assert len(created.json()["result"]["predictions"]) == start["horizon"]
    scan = env.client.post(root + "/decision-analysis/unusual-values", headers=owner)
    assert scan.status_code == 200, scan.text
    assert scan.json()["meaning"] == "confirmed"
