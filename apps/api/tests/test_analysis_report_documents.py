"""Use case: Keeps analytical exports faithful to saved computations.

What it does: Checks every row, decimal, exclusion, uncertainty and recorded rule
using actual deterministic domain outputs and real PDF text extraction.
"""

import copy
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from uuid import UUID

import pytest
from pypdf import PdfReader

from execplus.application.services.analysis_report_documents import build_analysis_report
from execplus.domain.advanced_forecasting import advanced_forecast
from execplus.domain.allocation_constraints import allocate_selection_rules
from execplus.domain.analysis_extensions import allocate_resources, detect_segments
from execplus.domain.decision_analysis import allocate, detect_distribution
from execplus.domain.forecasting import ForecastPoint, ForecastRequest, compare_forecast, forecast
from execplus.domain.ingestion import IngestionError
from execplus.domain.pdf_exports import document_text, validate_document
from execplus.domain.scenarios import compare_scenarios
from execplus.infrastructure.exports.reportlab_pdf import ReportLabPdfRenderer

NOW = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)
RID = UUID("12345678-1234-4234-8234-123456789abc")
SOURCE = {
    "dataset_id": str(RID),
    "upload_id": str(RID),
    "revision_id": str(RID),
    "understanding_id": str(RID),
    "source_checksum": "a" * 64,
    "output_checksum": "b" * 64,
}


def saved(result, request=None):
    return {
        "id": RID,
        "name": "Fictional evidence",
        "created_at": NOW,
        "method_version": result.get("method_version", result.get("version")),
        "request": request or {},
        "result": result,
        "evidence": {
            "sources": [SOURCE],
            "unit": "USD",
            "units": {"metric": "USD"},
            "definition": {"row_grain": "record", "columns": []},
        },
    }


def decision(result, request=None, current=True):
    return {
        "run": saved(result, request),
        "current": current,
        "review_version": 1,
        "decision_status": "approved",
        "approval_effective": current,
        "reviews": [
            {"target": "decision", "status": "approved", "note": "Fictional review", "sequence": 1}
        ],
    }


def table(content, name):
    return next(item for item in content.tables if item.name == name)


def text(content):
    return "\n".join(document_text(content.document))


def forecast_record(count=40):
    points = tuple(
        ForecastPoint(
            date(2020, 1, 1) + timedelta(days=i),
            Decimal("0.10000000000000000000000000000000000001") + i,
        )
        for i in range(count)
    )
    result = forecast(points, ForecastRequest("daily", 4, 7)).to_record()
    return saved(
        result, {"metric": "Revenue_USD", "frequency": "daily", "coverage_confirmed": True}
    )


def test_forecast_copies_actuals_estimates_full_windows_and_uncertainty_without_mutating():
    record = forecast_record()
    original = copy.deepcopy(record)
    content = build_analysis_report("forecast", record, NOW)
    assert record == original
    assert table(content, "Historical actuals").rows == tuple(
        (row["period"], row["actual"]) for row in record["result"]["history"]
    )
    assert table(content, "Forecast estimates and ranges").rows == tuple(
        tuple(row[key] for key in ("period", "estimate", "lower", "upper"))
        for row in record["result"]["predictions"]
    )
    rendered = text(content)
    assert "not calibrated confidence intervals" in rendered
    assert "coverage_guaranteed" in rendered and "false" in rendered
    assert "test_training" in rendered and "forecast_training" in rendered
    assert SOURCE["source_checksum"] in rendered
    chart = content.charts[0]
    assert chart.series[0].values[-4:] == (None,) * 4
    assert chart.series[1].values[:40] == (None,) * 40
    assert chart.series[1].values[-1] == record["result"]["predictions"][-1]["estimate"]
    assert len(chart.labels) == 44


def test_maximum_forecast_history_has_all_1200_rows_in_tables_and_real_pdf():
    record = forecast_record(1200)
    content = build_analysis_report("forecast", record, NOW)
    rows = table(content, "Historical actuals").rows
    assert len(rows) == 1200
    sections = [
        section for section in content.document.sections if section.title == "Historical actuals"
    ]
    assert [len(section.table.rows) for section in sections] == [1000, 200]
    validate_document(content.document)
    pdf = ReportLabPdfRenderer().render(content.document)
    reader = PdfReader(BytesIO(pdf))
    extracted = "\n".join(page.extract_text() for page in reader.pages)
    for period, actual in rows:
        assert period in extracted and actual in extracted
    assert len(reader.pages) < 100


def test_advanced_forecast_keeps_rolling_windows_empirical_limits_and_exact_chart_series():
    points = tuple(
        ForecastPoint(date(2024, 1, 1) + timedelta(days=i), Decimal(i)) for i in range(40)
    )
    result = advanced_forecast(points, ForecastRequest("daily", 4, 7)).to_record()
    content = build_analysis_report("forecast", saved(result, {"metric": "Revenue_USD"}), NOW)
    assert "rolling" in text(content).lower()
    assert content.charts[0].series[2].name == "Empirical lower"
    assert "not calibrated confidence intervals" in content.charts[0].notes[0]
    assert content.charts[0].series[1].values[-4:] == ("40", "41", "42", "43")
    assert len(table(content, "Validation candidates").rows) == len(
        result["selection"]["candidates"]
    )


def test_forecast_comparison_preserves_missing_actuals_and_pending_reasons():
    original = forecast_record()
    result = compare_forecast(original["result"], ())
    content = build_analysis_report("forecast_comparison", saved(result), NOW)
    rows = table(content, "Forecast versus later actuals")
    assert len(rows.rows) == 4
    for row in rows.rows:
        assert row[rows.columns.index("actual")] is None
        assert row[rows.columns.index("status")] == "pending"
    assert content.charts[0].series[0].values == (None,) * 4
    assert "not zero" in text(content)


def test_scenario_report_copies_compound_daily_inputs_outputs_and_negative_warning():
    request = {
        "kind": "scenario_comparison",
        "metric": "Revenue_USD",
        "aggregation": "sum",
        "assumptions_confirmed": True,
        "alternatives": [
            {
                "name": "Price and volume",
                "operation": "compound_percent",
                "drivers": [
                    {"name": "Price", "percent_change": "20"},
                    {"name": "Volume", "percent_change": "10"},
                ],
            },
            {
                "name": "Daily assumption",
                "operation": "daily_change",
                "daily_change": "-10",
                "days": 20,
            },
        ],
    }
    result = compare_scenarios(request, (("100", 3, 3),))
    content = build_analysis_report("scenario", decision(result, request, current=False), NOW)
    rows = table(content, "Scenario alternatives and assumptions")
    assert rows.rows[0][rows.columns.index("result")] == "132.00"
    assert rows.rows[1][rows.columns.index("result")] == "-100"
    assert table(content, "Daily assumption: recorded daily checkpoints").rows[-1] == (20, "-100")
    assert "crosses below zero" in text(content)
    assert "not forecasts or causal effects" in text(content)
    assert ("approval_effective", False) in table(content, "Current source and review status").rows
    assert content.charts[-1].series[0].values == ("100", "132.00", "-100")


@pytest.mark.parametrize("segmented", [False, True])
def test_anomaly_report_keeps_weighted_findings_excluded_groups_and_raw_scores(segmented):
    result = (
        detect_segments(
            [("North", "10", 8), ("North", "100", 1), ("Sparse", "5", 2), (None, "1", 1)],
            "3.5",
            "0",
            8,
        )
        if segmented
        else detect_distribution([("10", 8), ("100", 2)])
    )
    content = build_analysis_report("anomaly", decision(result, {"metric": "Revenue_USD"}), NOW)
    findings = table(content, "Unusual values (not proof of errors)")
    assert findings.rows[0][findings.columns.index("value")] == "100"
    assert findings.rows[0][findings.columns.index("score")] is None
    assert "not probabilities" in text(content)
    if segmented:
        groups = table(content, "Group coverage and baselines")
        assert {row[groups.columns.index("status")] for row in groups.rows} == {
            "missing_group",
            "insufficient_support",
            "evaluated",
        }
        assert ("excluded_records", 3) in table(content, "Recorded summary and coverage").rows
    assert "Flagged record counts" in content.charts[0].title


def test_no_anomaly_findings_is_an_explicit_empty_table_not_an_invented_chart():
    content = build_analysis_report("anomaly", decision(detect_distribution([("10", 8)])), NOW)
    assert table(content, "Unusual values (not proof of errors)").rows == ()
    assert not content.charts


@pytest.mark.parametrize("resources", [False, True])
def test_allocation_report_has_exact_all_quantities_constraints_and_review(resources):
    bounds = {"A": (0, 2), "B": (0, 2)}
    result = (
        allocate_resources(
            [("A", "2", "8", "1"), ("B", "1", "7", "2")], "4", "1", bounds, True, "2"
        )
        if resources
        else allocate([("A", "2", "8"), ("B", "1", "7")], "4", "1", bounds, True)
    )
    request = {
        "benefit_column": "Expected_units",
        "bounds": bounds,
    }
    content = build_analysis_report("allocation", decision(result, request), NOW)
    rows = table(content, "Selected quantities and exact contributions")
    assert len(rows.rows) == 2
    assert [row[rows.columns.index("quantity")] for row in rows.rows] == [
        row["quantity"] for row in result["allocations"]
    ]
    assert content.charts[0].series[0].values == tuple(
        row["benefit"] for row in result["allocations"]
    )
    assert "No external action executes" in text(content)
    assert "Fictional review" in text(content)


def test_selection_rule_allocation_preserves_actual_registered_rules_and_constraints():
    prerequisites = [{"candidate": "A", "requires": "B"}]
    exclusions = [{"first": "B", "second": "C"}]
    result = allocate_selection_rules(
        [("A", "2", "8", None), ("B", "1", "7", None), ("C", "1", "9", None)],
        "4",
        "1",
        {"A": (0, 2), "B": (0, 2), "C": (0, 2)},
        True,
        prerequisites,
        exclusions,
    )
    content = build_analysis_report(
        "allocation",
        decision(
            result,
            {
                "benefit_column": "Expected_units",
                "prerequisites": prerequisites,
                "exclusions": exclusions,
            },
        ),
        NOW,
    )
    rules = dict(table(content, "Recorded summary and coverage").rows)["selection_rules"]
    assert json.loads(rules) == {"prerequisites": prerequisites, "exclusions": exclusions}
    assert "not timing or scheduling constraints" in text(content)
    assert dict(table(content, "Recorded summary and coverage").rows)["solver_status"] == "optimal"


def test_infeasible_allocation_has_reason_and_no_fabricated_selected_benefit():
    result = allocate([("A", "2", "8")], "1", "1", {"A": (1, 1)}, True)
    content = build_analysis_report(
        "allocation", decision(result, {"benefit_column": "Expected_units"}), NOW
    )
    assert not content.charts
    assert table(content, "Selected quantities and exact contributions").rows == ()
    summary = dict(table(content, "Recorded summary and coverage").rows)
    assert summary["cost"] is None and summary["benefit"] is None
    assert summary["status"] == "infeasible"


def query_item():
    return {
        "result": {
            "query_id": RID,
            "columns": ("Region", "Total"),
            "rows": (("  North  ", Decimal("9007199254740993.123456789012")), ("South", None)),
            "records_analyzed": 3,
            "matched_records": None,
        },
        "lineage": {
            "query_id": RID,
            "aggregation": "sum",
            "grouping": ("Region",),
            "filters": ("Region != East",),
            "sql": "SELECT region, SUM(amount) FROM data GROUP BY region",
            "receipt": {"sources": [SOURCE], "outcome": "executed"},
        },
    }


def study():
    return {
        "study": {"name": "Regional revenue", "id": RID, "shared": True},
        "version": {
            "number": 1,
            "method": {"kind": "metric", "group_by": ["Region"]},
            "evidence": {
                "sources": [SOURCE],
                "component": "bar",
                "limitations": ["Recorded coverage limitation"],
            },
        },
        "results": [query_item(), query_item()],
    }


@pytest.mark.parametrize("kind", ["dashboard", "study", "dashboard_queries"])
def test_dashboard_exports_all_selected_results_typed_cells_exact_filters_and_sources(kind):
    record = (
        {"board": {"name": "Weekly review", "pins": [str(RID)]}, "studies": [study()]}
        if kind == "dashboard"
        else study()
        if kind == "study"
        else {
            "name": "Selected executed dashboard results",
            "results": [query_item(), query_item()],
        }
    )
    original = copy.deepcopy(record)
    content = build_analysis_report(kind, record, NOW)
    exact = [item for item in content.tables if item.columns == ("Region", "Total")]
    assert len(exact) == 2
    assert all(item.rows == query_item()["result"]["rows"] for item in exact)
    assert record == original
    assert "Region != East" in text(content) and SOURCE["source_checksum"] in text(content)
    assert content.charts[0].series[0].values == ("9007199254740993.123456789012", None)
    assert content.charts[0].labels[0] == "  North  "
    if kind == "dashboard_queries":
        assert "not a claim that every dashboard panel" in text(content)


def test_raw_record_tables_are_exported_without_treating_last_text_column_as_measure():
    item = query_item()
    item["lineage"]["aggregation"] = "records"
    item["result"]["rows"] = (("North", "Human text"),)
    content = build_analysis_report("dashboard_queries", {"results": [item]}, NOW)
    assert not content.charts
    assert table(content, "Executed result 1").rows == (("North", "Human text"),)


@pytest.mark.parametrize("value", ["Human text", True, None, "NaN"])
def test_grouped_non_numeric_or_empty_results_have_no_numeric_export_chart(value):
    item = query_item()
    item["result"]["rows"] = (("North", value),)
    content = build_analysis_report("dashboard_queries", {"results": [item]}, NOW)
    assert not content.charts


def test_scalar_card_does_not_shift_dashboard_png_chart_indices():
    card = query_item()
    card["result"]["columns"] = ("Total",)
    card["result"]["rows"] = ((Decimal("12.345"),),)
    content = build_analysis_report("dashboard_queries", {"results": [card, query_item()]}, NOW)
    assert len(content.charts) == 1
    assert content.charts[0].title == "Executed result 2"


def test_dashboard_chart_labels_use_saved_measure_and_keep_all_exact_dates_and_nulls():
    item = query_item()
    item["lineage"].update(metric="amount", grouping=("date",))
    item["result"]["columns"] = ("date", "__value")
    item["result"]["rows"] = (
        ("2024-01-01", Decimal("0.100000000000000000001")),
        ("2024-01-02", None),
        ("2024-01-03", Decimal("-2.30")),
        ("2024-01-04", Decimal("0")),
    )
    original = copy.deepcopy(item)
    content = build_analysis_report("dashboard_queries", {"results": [item]}, NOW)
    chart = content.charts[0]
    assert chart.title == "Total amount by date"
    assert chart.y_label == chart.series[0].name == "amount"
    assert chart.kind == "line"
    assert chart.labels == ("2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04")
    assert chart.series[0].values == ("0.100000000000000000001", None, "-2.30", "0")
    assert table(content, "Executed result 1").columns == ("date", "__value")
    assert table(content, "Executed result 1").rows == original["result"]["rows"]
    assert item == original


@pytest.mark.parametrize(
    "aggregation,unit_column,expected",
    [("sum", "", "amount (USD)"), ("count", "", "amount"), ("sum", "currency", "amount")],
)
def test_saved_study_chart_unit_comes_only_from_fixed_recorded_definition(
    aggregation, unit_column, expected
):
    saved = study()
    saved["version"]["evidence"]["definition"] = {
        "columns": [
            {"name": "amount", "unit": "currency", "currency": "USD", "unit_column": unit_column}
        ]
    }
    saved["results"][0]["lineage"].update(metric="amount", aggregation=aggregation)
    saved["results"][0]["result"]["columns"] = ("Region", "__value")
    content = build_analysis_report("study", saved, NOW)
    assert content.charts[0].y_label == content.charts[0].series[0].name == expected


@pytest.mark.parametrize(
    "labels,kind",
    [
        (("2024-01-01", "2024-01-02"), "line"),
        (("2024-01-02", "2024-01-01"), "bar"),
        (("2024-01-01", "2024-01-01"), "bar"),
        (("20240101", "20240102"), "bar"),
        (("North", "South"), "bar"),
    ],
)
def test_dashboard_line_uses_actual_ordered_unique_iso_dates_only(labels, kind):
    item = query_item()
    item["result"]["rows"] = tuple((label, Decimal(index)) for index, label in enumerate(labels))
    content = build_analysis_report("dashboard_queries", {"results": [item]}, NOW)
    assert content.charts[0].kind == kind
    assert content.charts[0].labels == labels


def test_very_wide_returned_result_keeps_every_column_in_split_pdf_tables():
    item = query_item()
    item["lineage"]["aggregation"] = "records"
    item["result"]["columns"] = tuple(f"Field{i}" for i in range(23))
    item["result"]["rows"] = (tuple(f"Value{i}" for i in range(23)),)
    content = build_analysis_report("dashboard_queries", {"results": [item]}, NOW)
    assert len(table(content, "Executed result 1").columns) == 23
    assert [
        len(section.table.columns)
        for section in content.document.sections
        if section.title == "Executed result 1"
    ] == [20, 3]
    validate_document(content.document)


@pytest.mark.parametrize(
    "kind,record",
    [("forecast", {}), ("anomaly", {"run": {}}), ("dashboard", {"board": {}, "studies": [{}]})],
)
def test_incomplete_authorized_payload_is_refused_instead_of_an_empty_success(kind, record):
    with pytest.raises(IngestionError) as error:
        build_analysis_report(kind, record, NOW)
    assert error.value.code == "export_integrity"


def test_unsupported_report_kind_does_not_assume_a_generic_compatible_shape():
    with pytest.raises(IngestionError) as error:
        build_analysis_report("new-unregistered-analysis", {}, NOW)
    assert error.value.code == "export_unsupported"


def test_nested_parameters_remain_literal_json_without_formulas_or_source_mutation():
    item = query_item()
    item["lineage"]["filters"] = ['=HYPERLINK("https://invalid","x")', "<b>literal</b>"]
    content = build_analysis_report("dashboard_queries", {"results": [item]}, NOW)
    lineage = dict(table(content, "Executed result 1 lineage").rows)
    assert json.loads(lineage["filters"]) == item["lineage"]["filters"]


def test_restricted_export_omits_original_fingerprints_before_nested_json_serialization():
    saved = study()
    restricted = {
        **SOURCE,
        "source_checksum": "private-source-fingerprint",
        "output_checksum": "private-output-fingerprint",
        "access_restricted": "true",
    }
    saved["version"]["evidence"]["sources"] = [restricted]
    saved["results"][0]["lineage"]["receipt"]["sources"] = [restricted]
    saved["results"][1]["lineage"]["receipt"]["sources"] = [restricted]
    original = copy.deepcopy(saved)
    content = build_analysis_report("study", saved, NOW)
    rendered = text(content)
    assert "private-source-fingerprint" not in rendered
    assert "private-output-fingerprint" not in rendered
    assert "withheld_for_restricted_access" in rendered
    nested = dict(table(content, "Study 1: Regional revenue - result 1 lineage").rows)
    source = json.loads(nested["receipt"])["sources"][0]
    assert "source_checksum" not in source and "output_checksum" not in source
    assert source["dataset_id"] == str(SOURCE["dataset_id"])
    assert content.charts[0].series[0].values == ("9007199254740993.123456789012", None)
    assert saved == original
