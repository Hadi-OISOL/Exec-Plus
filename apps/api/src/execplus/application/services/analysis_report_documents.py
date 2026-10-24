"""Use case: Prepares portable reports from reopened analytical evidence.

What it does: Copies every recorded result into exact tables and bounded chart
specifications. Callers authorize and replay records; this module never queries,
calculates a new result, changes a source or grants access.
"""

import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from execplus.domain.calendar_anomaly_requests import CALENDAR_METHODS
from execplus.domain.exports import (
    ExportChart,
    ExportContent,
    ExportSeries,
    ExportTable,
    exact_text,
    validate_export,
)
from execplus.domain.ingestion import IngestionError
from execplus.domain.models import Scalar
from execplus.domain.pdf_exports import (
    MAX_PDF_COLUMNS,
    MAX_PDF_ROWS,
    PdfDocument,
    PdfSection,
    PdfTable,
)
from execplus.domain.public_evidence import public_evidence
from execplus.domain.scenario_constraints import METHOD as CONSTRAINED_SCENARIO_METHOD
from execplus.domain.source_scenarios import METHOD as SOURCE_SCENARIO_METHOD


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, allow_nan=False)


def _scalar(value: Any) -> Scalar:
    if value is None or isinstance(value, str | bool | int | float | Decimal | date | datetime):
        return value
    if isinstance(value, UUID):
        return str(value)
    return _json(value)


def _display(value: Scalar) -> str:
    return "Missing (null)" if value is None else exact_text(value)


def _chart_value(value: Any) -> str | None:
    return None if value is None else exact_text(_scalar(value))


def _numeric_chart_cell(value: Scalar) -> bool:
    if value is None:
        return True
    if isinstance(value, bool | date | datetime):
        return False
    try:
        return Decimal(str(value)).is_finite()
    except (InvalidOperation, ValueError):
        return False


def _grouped_chart_kind(item: dict[str, Any]) -> str:
    result = item["result"]
    if len(result["columns"]) == 2 and len(result["rows"]) > 1:
        try:
            dates = [date.fromisoformat(str(row[0])) for row in result["rows"]]
            if dates == sorted(set(dates)) and all(
                day.isoformat() == str(row[0])
                for day, row in zip(dates, result["rows"], strict=True)
            ):
                return "line"
        except (TypeError, ValueError):
            pass
    return "bar"


class _Report:
    def __init__(self, title: str, generated_at: datetime) -> None:
        self.title = title
        self.generated_at = generated_at
        self.sections: list[PdfSection] = []
        self.tables: list[ExportTable] = []
        self.charts: list[ExportChart] = []

    def text(self, title: str, *paragraphs: str) -> None:
        self.sections.append(PdfSection(title, tuple(paragraphs)))

    def table(
        self, name: str, columns: tuple[str, ...], rows: tuple[tuple[Scalar, ...], ...]
    ) -> None:
        self.tables.append(ExportTable(name, columns, rows))
        for column_start in range(0, len(columns), MAX_PDF_COLUMNS):
            selected = columns[column_start : column_start + MAX_PDF_COLUMNS]
            for row_start in range(0, max(1, len(rows)), MAX_PDF_ROWS):
                end = min(row_start + MAX_PDF_ROWS, len(rows))
                detail = (
                    f"Rows {row_start + 1}-{end} of {len(rows)}; "
                    f"columns {column_start + 1}-{column_start + len(selected)} "
                    f"of {len(columns)}."
                    if rows
                    else "No recorded rows."
                )
                self.sections.append(
                    PdfSection(
                        name,
                        (detail,),
                        PdfTable(
                            selected,
                            tuple(
                                tuple(
                                    _display(value)
                                    for value in row[column_start : column_start + MAX_PDF_COLUMNS]
                                )
                                for row in rows[row_start:end]
                            ),
                        ),
                    )
                )

    def objects(self, name: str, rows: list[dict[str, Any]], columns: tuple[str, ...] = ()) -> None:
        fields = columns or tuple(dict.fromkeys(key for row in rows for key in row))
        if not fields:
            self.text(name, "No recorded rows.")
            return
        self.table(
            name, fields, tuple(tuple(_scalar(row.get(key)) for key in fields) for row in rows)
        )

    def metadata(self, name: str, values: dict[str, Any]) -> None:
        if values:
            self.table(
                name,
                ("Field", "Recorded value"),
                tuple((key, _scalar(value)) for key, value in values.items()),
            )

    def finish(self) -> ExportContent:
        content = ExportContent(
            PdfDocument(self.title, self.generated_at, tuple(self.sections)),
            tuple(self.tables),
            tuple(self.charts),
        )
        validate_export(content)
        return content


def _overview(report: _Report, record: dict[str, Any], kind: str) -> None:
    report.text(
        "Saved analytical report",
        "This export contains the reopened saved result and its recorded evidence. "
        "It does not run a new model, forecast or decision calculation. "
        "Plots are approximate displays; the complete tables retain recorded values. "
        "Missing (null) differs from zero. A downloaded copy cannot be recalled after sharing.",
    )
    report.metadata(
        "Report identity",
        {
            key: record[key]
            for key in ("id", "name", "kind", "created_at", "method", "method_version")
            if key in record
        },
    )
    report.text("Report type", kind)
    if isinstance(record.get("request"), dict):
        report.metadata("Saved request and explicit assumptions", record["request"])


def _forecast(report: _Report, record: dict[str, Any]) -> None:
    result = record["result"]
    history, predictions = result["history"], result["predictions"]
    range_label = {"forecast-v2": "Empirical", "forecast-v3": "Calibrated 80%"}.get(
        str(result.get("version")), "Heuristic"
    )
    range_note = {
        "Empirical": "The reported ranges use validation errors, "
        "not calibrated confidence intervals.",
        "Calibrated 80%": "The reported ranges use separate earlier calibration windows; "
        "80% coverage assumes errors behave alike over time and is not guaranteed.",
    }.get(range_label, "The reported ranges are heuristic, not calibrated confidence intervals.")
    report.text(
        "Interpretation",
        "Historical actuals are recorded source values. Predictions and error measures are "
        f"estimates. {range_note}",
    )
    report.objects("Historical actuals", history, ("period", "actual"))
    report.objects("Held-out predictions", result["backtest"])
    report.objects(
        "Forecast estimates and ranges", predictions, ("period", "estimate", "lower", "upper")
    )
    for key, title in (
        ("method", "Recorded method"),
        ("windows", "Training and evaluation windows"),
        ("accuracy", "Held-out accuracy"),
        ("benchmark", "Naive benchmark comparison"),
        ("uncertainty", "Uncertainty and coverage limitations"),
    ):
        report.metadata(title, result[key])
    report.metadata(
        "Method selection",
        {key: value for key, value in result["selection"].items() if key != "candidates"},
    )
    report.objects("Validation candidates", result["selection"]["candidates"])
    report.text("Limitations", *result["limitations"])
    if result.get("commentary"):
        commentary = result["commentary"]
        report.text(
            "Saved commentary", commentary if isinstance(commentary, str) else _json(commentary)
        )
    count = len(history)
    metric = str(record["request"]["metric"])
    unit = str(record["evidence"].get("unit", ""))
    report.charts.append(
        ExportChart(
            "line",
            "Observed values and forecast estimates",
            "Period",
            f"{metric} ({unit})" if unit else metric,
            tuple(str(row["period"]) for row in [*history, *predictions]),
            (
                ExportSeries(
                    "Observed",
                    tuple(_chart_value(row["actual"]) for row in history)
                    + (None,) * len(predictions),
                ),
                *tuple(
                    ExportSeries(
                        label,
                        (None,) * count + tuple(_chart_value(row[field]) for row in predictions),
                    )
                    for field, label in (
                        ("estimate", "Estimate"),
                        ("lower", f"{range_label} lower"),
                        ("upper", f"{range_label} upper"),
                    )
                ),
            ),
            notes=(range_note, *result["limitations"]),
        )
    )


def _decision(report: _Report, record: dict[str, Any], kind: str) -> None:
    run, result = record["run"], record["run"]["result"]
    report.metadata(
        "Current source and review status",
        {
            key: record[key]
            for key in ("current", "review_version", "decision_status", "approval_effective")
            if key in record
        },
    )
    if record.get("current") is False:
        report.text(
            "Historical source",
            "This saved result uses an earlier source or definition. It remains historical "
            "evidence; any recorded approval is not currently effective.",
        )
    report.text("Limitations", *result.get("limitations", []))
    if result.get("assumptions"):
        report.text("Declared model assumptions", *result["assumptions"])
    excluded = {
        "limitations",
        "assumptions",
        "alternatives",
        "allocations",
        "findings",
        "groups",
        "history",
        "distribution",
        "observations",
        "capacity_sensitivity",
    }
    report.metadata(
        "Recorded summary and coverage",
        {key: value for key, value in result.items() if key not in excluded},
    )
    if kind == "scenario" and result.get("version") in {
        SOURCE_SCENARIO_METHOD,
        CONSTRAINED_SCENARIO_METHOD,
    }:
        _source_scenario(report, run, result)
    elif kind == "scenario":
        alternatives = result["alternatives"]
        scenario_notes = (
            "Hypothetical outcomes under the saved assumptions, not observed or causal effects.",
            *result.get("assumptions", []),
            *result.get("limitations", []),
        )
        report.objects("Scenario alternatives and assumptions", alternatives)
        for alternative in alternatives:
            if "path" in alternative:
                name = str(alternative["name"])
                path = alternative["path"]
                report.objects(f"{name}: recorded daily checkpoints", path, ("day", "value"))
                report.charts.append(
                    ExportChart(
                        "line",
                        f"{name}: hypothetical checkpoints",
                        "Assumed days",
                        str(result["metric"]),
                        tuple(str(row["day"]) for row in path),
                        (
                            ExportSeries(
                                "Conditional value",
                                tuple(_chart_value(row["value"]) for row in path),
                            ),
                        ),
                        notes=scenario_notes,
                    )
                )
        report.charts.append(
            ExportChart(
                "bar",
                "Baseline and conditional alternatives",
                "Alternative",
                str(result["metric"]),
                ("Baseline", *(str(row["name"]) for row in alternatives)),
                (
                    ExportSeries(
                        "Conditional value",
                        (
                            _chart_value(result["baseline"]),
                            *(_chart_value(row["result"]) for row in alternatives),
                        ),
                    ),
                ),
                notes=scenario_notes,
            )
        )
    elif kind == "anomaly" and run["method_version"] in CALENDAR_METHODS:
        _calendar_anomaly(report, run, result)
    elif kind == "anomaly" and result.get("version") == "multivariate-anomaly-v1":
        _multivariate_anomaly(report, result)
    elif kind == "anomaly":
        report.objects(
            "Unusual values (not proof of errors)",
            result["findings"],
            tuple(dict.fromkeys(key for row in result["findings"] for key in row))
            or ("value", "count", "absolute_difference", "score"),
        )
        if "groups" in result:
            report.objects("Group coverage and baselines", result["groups"])
        if result["findings"]:
            report.charts.append(
                ExportChart(
                    "bar",
                    "Flagged record counts by recorded finding",
                    "Finding",
                    "Records",
                    tuple(
                        f"{row.get('segment', '')}: {row['value']} [{row['id']}]"
                        for row in result["findings"]
                    ),
                    (
                        ExportSeries(
                            "Flagged records",
                            tuple(_chart_value(row["count"]) for row in result["findings"]),
                        ),
                    ),
                )
            )
    elif kind == "allocation":
        report.text(
            "Decision boundary",
            "No external action executes when a recommendation is approved or exported. "
            "Benefits describe the declared assumptions, not independently proven effects.",
        )
        report.objects(
            "Selected quantities and exact contributions",
            result["allocations"],
            tuple(dict.fromkeys(key for row in result["allocations"] for key in row))
            or ("candidate", "quantity", "cost", "benefit"),
        )
        if result.get("version") in {
            "multi-resource-allocation-v1",
            "multi-resource-allocation-v2",
            "scheduled-allocation-v1",
        }:
            report.objects("Every declared resource limit and exact use", result["resources"])
            report.objects(
                "Per-action resource contributions",
                [
                    {"candidate": row["candidate"], "quantity": row["quantity"], **resource}
                    for row in result["allocations"]
                    for resource in row["resources"]
                ],
                ("candidate", "quantity", "column", "per_unit", "used"),
            )
        if result.get("schedule"):
            report.objects("Per-period budgets and exact use", result["schedule"]["periods"])
            report.objects(
                "Ordering rules",
                result["schedule"]["precedence"],
                ("candidate", "after"),
            )
        if result.get("capacity_sensitivity"):
            _capacity_comparison(report, run, result)
        if result["allocations"]:
            measure = str(run["request"]["benefit_column"])
            larger_method = result.get("version") in {
                "multi-resource-allocation-v1",
                "multi-resource-allocation-v2",
                "scheduled-allocation-v1",
            }
            unit = run.get("evidence", {}).get("units", {}).get(measure, "")
            report.charts.append(
                ExportChart(
                    "bar",
                    "Declared benefit by selected candidate",
                    "Candidate",
                    f"{measure} ({unit})" if larger_method and unit else measure,
                    tuple(str(row["candidate"]) for row in result["allocations"]),
                    (
                        ExportSeries(
                            "Assumed benefit",
                            tuple(_chart_value(row["benefit"]) for row in result["allocations"]),
                        ),
                    ),
                    notes=(
                        result["reason"],
                        "Benefits use fixed per-unit assumptions, not proven real-world effects.",
                        "No external action executes. Full limits and exact source evidence "
                        "are retained in the image metadata.",
                    )
                    if larger_method
                    else (
                        result.get("reason", "Benefits are conditional on the declared inputs."),
                        *result.get("limitations", []),
                    ),
                )
            )
    report.objects("Private review history", record.get("reviews", []))


def _capacity_comparison(report: _Report, run: dict[str, Any], result: dict[str, Any]) -> None:
    comparison = result["capacity_sensitivity"]
    report.text(
        "Capacity comparison and approval",
        "Approval applies only to the original model. "
        "Alternatives require a separately saved model and review. "
        "These are hypothetical capacities.",
    )
    report.table(
        "Declared capacity alternatives",
        (
            "Resource",
            "Unit",
            "Capacity",
            "Solver status",
            "Benefit",
            "Cost",
            "Benefit difference",
            "Cost difference",
        ),
        tuple(
            (
                comparison["column"],
                comparison["unit"],
                item["capacity"],
                item["result"]["solver_status"],
                item["result"]["benefit"],
                item["result"]["cost"],
                item["difference"]["benefit"] if item["difference"] else None,
                item["difference"]["cost"] if item["difference"] else None,
            )
            for item in comparison["variants"]
        ),
    )
    report.objects("Original model infeasibility evidence", result["infeasibility"])
    for index, item in enumerate(comparison["variants"], start=1):
        value = item["result"]
        label = f"Capacity alternative {index}"
        report.objects(f"{label}: exact quantities", value["allocations"])
        report.objects(f"{label}: exact resource use", value["resources"])
        report.objects(f"{label}: infeasibility evidence", value["infeasibility"])
        report.metadata(f"{label}: retained solver evidence", value["solver_evidence"])
    if not any(item["result"]["benefit"] is not None for item in comparison["variants"]):
        return
    measure = str(run["request"]["benefit_column"])
    unit = run["evidence"]["units"][measure]
    report.charts.append(
        ExportChart(
            "bar",
            "Conditional benefit by declared capacity",
            f"{comparison['column']} ({comparison['unit']})",
            f"{measure} ({unit})",
            tuple(item["capacity"] for item in comparison["variants"]),
            (
                ExportSeries(
                    "Conditional benefit",
                    tuple(item["result"]["benefit"] for item in comparison["variants"]),
                ),
            ),
            notes=(
                "Null values mean no usable selection, never zero benefit.",
                "Only optimal outcomes prove the declared model optimum; "
                "feasible selections can differ between bounded searches.",
                "Every capacity is an explicit assumption; no causal uplift is inferred.",
            ),
        )
    )


def _multivariate_anomaly(report: _Report, result: dict[str, Any]) -> None:
    report.objects("Every reference and comparison record", result["records"])
    report.objects("Unusual combinations to review", result["findings"])
    report.metadata("Reference-only fitted model", result["reference"])
    report.metadata("Declared squared-distance threshold", result["threshold"])
    compared = [row for row in result["records"] if row["phase"] == "comparison"]
    report.table(
        "Exact comparison distances",
        ("Record", "Numerator", "Denominator", "Display", "Display exact", "Flagged"),
        tuple(
            (
                row["record_id"],
                row["squared_distance"]["numerator"],
                row["squared_distance"]["denominator"],
                row["squared_distance"]["display"],
                row["squared_distance"]["display_exact"],
                row["flagged"],
            )
            for row in compared
        ),
    )
    report.charts.append(
        ExportChart(
            "bar",
            "Observed combination distances",
            "Record identifier",
            "Squared distance",
            tuple(row["record_id"] for row in compared),
            (
                ExportSeries(
                    "Squared distance (display)",
                    tuple(row["squared_distance"]["display"] for row in compared),
                ),
            ),
            notes=(
                "The chart uses decimal displays; exact fractions determine flags. "
                "Distances are not probabilities.",
                *result["limitations"],
            ),
        )
    )


def _calendar_anomaly(report: _Report, run: dict[str, Any], result: dict[str, Any]) -> None:
    metric = run["request"]["metric"]
    unit = run["evidence"]["units"][metric]
    notes = tuple(result["limitations"])
    report.objects("Recorded review findings", result["findings"])
    if "history" in result:
        history = result["history"]
        rolling = result["version"] == "rolling-anomaly-v1"
        reference_label = "Trailing reference" if rolling else "Seasonal reference"
        report.objects(
            "Every chronological period and trailing reference"
            if rolling
            else "Every chronological period and seasonal reference",
            history,
        )
        if not rolling:
            report.metadata("Frozen training reference", result["reference"])
        report.charts.append(
            ExportChart(
                "line",
                "Observed periods and trailing reference"
                if rolling
                else "Observed periods and seasonal reference",
                "Observed period",
                f"{metric} ({unit})",
                tuple(row["period"] for row in history),
                tuple(
                    ExportSeries(label, tuple(_chart_value(row[field]) for row in history))
                    for field, label in (("actual", "Observed"), ("expected", reference_label))
                ),
                notes=(
                    "Every trailing reference uses only earlier comparable periods."
                    if rolling
                    else "Later observed values are compared with earlier seasonal references; "
                    "this is not a future forecast. Training ends "
                    f"{result['reference']['training_end']}.",
                    *notes,
                ),
            )
        )
    else:
        observations = result["observations"]
        report.objects("Every period in both declared windows", observations)
        report.objects(
            "Exact empirical distribution and distance contributions", result["distribution"]
        )
        report.table(
            "Exact distribution distances",
            ("Measure", "Numerator", "Denominator", "Display", "Display is exact"),
            tuple(
                (
                    name,
                    result[key]["numerator"],
                    result[key]["denominator"],
                    result[key]["display"],
                    result[key]["display_exact"],
                )
                for key, name in (
                    ("maximum_cdf_separation", "Maximum cumulative share separation"),
                    ("wasserstein_distance", "Average distribution distance"),
                )
            ),
        )
        report.charts.append(
            ExportChart(
                "line",
                "Observed values in the two declared windows",
                "Observed period",
                f"{metric} ({unit})",
                tuple(row["period"] for row in observations),
                tuple(
                    ExportSeries(
                        name.title(),
                        tuple(
                            row["value"] if row["window"] == name else None for row in observations
                        ),
                    )
                    for name in ("reference", "comparison")
                ),
                notes=(
                    "The two windows are separate observed series. A gap between windows "
                    "has no observations and is not filled or joined.",
                    *notes,
                ),
            )
        )


def _source_scenario(report: _Report, run: dict[str, Any], result: dict[str, Any]) -> None:
    fields = (
        "quantity",
        "revenue",
        "variable_cost",
        "fixed_cost",
        "total_cost",
        "contribution",
        "remaining",
        "margin_percent",
    )
    baseline, alternatives = result["baseline"], result["alternatives"]
    units = run["evidence"]["units"]
    currency = units[run["request"]["sales_column"]]
    report.table(
        "Source model baseline",
        ("Measure", "Exact value", "Unit"),
        tuple(
            (
                field,
                baseline[field],
                units[run["request"]["quantity_column"]]
                if field == "quantity"
                else "%"
                if field == "margin_percent"
                else currency,
            )
            for field in fields
        ),
    )
    report.table(
        "Conditional source model results",
        ("Alternative", *fields),
        tuple(
            (item["name"], *(item["result"][field] for field in fields)) for item in alternatives
        ),
    )
    report.table(
        "Changes from baseline",
        ("Alternative", *fields[:-1]),
        tuple(
            (item["name"], *(item["difference"][field] for field in fields[:-1]))
            for item in alternatives
        ),
    )
    drivers = ("price", "quantity", "variable_cost", "fixed_cost")
    report.table(
        "Declared percentage changes",
        ("Alternative", *drivers),
        tuple(
            (item["name"], *(item["assumptions"][field] for field in drivers))
            for item in alternatives
        ),
    )
    if result.get("constraints"):
        checks = [("Source baseline", result["baseline_constraints"])]
        checks.extend((item["name"], item["constraints"]) for item in alternatives)
        if result.get("sensitivity"):
            checks.extend(
                (f"Sensitivity {point['percent_change']}%", point["constraints"])
                for point in result["sensitivity"]["points"]
            )
        report.table(
            "Declared scenario limits and exact checks",
            (
                "Outcome",
                "Measure",
                "Bound",
                "Threshold",
                "Unit",
                "Actual display",
                "Exact ratio",
                "Status",
                "Explanation",
            ),
            tuple(
                (
                    name,
                    item["field"],
                    item["operator"],
                    item["value"],
                    item["unit"],
                    item["actual"],
                    _json(item["exact_actual"]),
                    item["status"],
                    item["reason"],
                )
                for name, values in checks
                for item in values
            ),
        )
    notes = tuple([*result["assumptions"], *result["limitations"], *result["warnings"]])
    report.table(
        "Model assumptions and limits",
        ("Kind", "Statement"),
        tuple(
            (kind, statement)
            for kind in ("assumptions", "limitations", "warnings")
            for statement in result[kind]
        ),
    )
    report.text("Source model warnings", *result["warnings"])
    report.charts.append(
        ExportChart(
            "bar",
            "Remaining amount under declared assumptions",
            "Alternative",
            f"Remaining amount ({currency})",
            ("Baseline", *(item["name"] for item in alternatives)),
            (
                ExportSeries(
                    "Remaining amount",
                    (
                        baseline["remaining"],
                        *(item["result"]["remaining"] for item in alternatives),
                    ),
                ),
            ),
            notes=notes,
        )
    )
    sensitivity = result.get("sensitivity")
    if sensitivity:
        report.metadata(
            "Sensitivity reference",
            {key: value for key, value in sensitivity.items() if key != "points"},
        )
        report.table(
            "Single-driver sensitivity",
            ("Percent change", *fields),
            tuple(
                (point["percent_change"], *(point["result"][field] for field in fields))
                for point in sensitivity["points"]
            ),
        )
        report.charts.append(
            ExportChart(
                "bar",
                "Single-driver sensitivity",
                f"{sensitivity['driver']} change (%)",
                f"Remaining amount ({currency})",
                tuple(point["percent_change"] for point in sensitivity["points"]),
                (
                    ExportSeries(
                        "Remaining amount",
                        tuple(point["result"]["remaining"] for point in sensitivity["points"]),
                    ),
                ),
                notes=notes,
            )
        )


def _dashboard(report: _Report, record: dict[str, Any]) -> None:
    board = record["board"]
    report.metadata("Saved dashboard", board)
    report.text(
        "Dashboard scope",
        "Every pinned saved study and every returned evidence table is included. "
        "The dashboard's sharing does not grant access to a study that is no longer available. "
        "Coverage tables describe returned populations, not a guarantee of completeness.",
    )
    for index, saved in enumerate(record["studies"], 1):
        study, version = saved["study"], saved["version"]
        title = f"Study {index}: {study['name']}"
        report.metadata(title, study)
        report.metadata(
            f"{title} - version",
            {key: value for key, value in version.items() if key != "evidence"},
        )
        report.text(f"{title} - limitations", *version["evidence"].get("limitations", []))
        if version["method"]["kind"] == "contribution":
            from execplus.application.services.contribution_reports import add_contribution

            add_contribution(report, title, version["evidence"])
        for position, item in enumerate(saved["results"], 1):
            chart_kind = (
                ("line" if version["evidence"].get("component") == "line" else "bar")
                if (position == 1 and version["method"]["kind"] in {"metric", "distribution"})
                else None
            )
            _query_result(
                report,
                f"{title} - result {position}",
                item,
                chart_kind,
                version["evidence"].get("definition"),
            )
        report.metadata(f"{title} - saved source and definition evidence", version["evidence"])


def _query_result(
    report: _Report,
    title: str,
    item: dict[str, Any],
    chart_kind: str | None,
    definition: dict[str, Any] | None = None,
) -> None:
    result, lineage = item["result"], item["lineage"]
    columns = tuple(result["columns"])
    rows = tuple(tuple(_scalar(cell) for cell in row) for row in result["rows"])
    report.table(title, columns, rows)
    report.metadata(
        f"{title} scope",
        {key: value for key, value in result.items() if key not in {"rows", "columns"}},
    )
    report.metadata(f"{title} lineage", lineage)
    if (
        chart_kind
        and rows
        and len(columns) > 1
        and lineage.get("aggregation") != "records"
        and any(row[-1] is not None for row in rows)
        and all(_numeric_chart_cell(row[-1]) for row in rows)
    ):
        metric = lineage.get("metric")
        measure = metric or ("Recorded value" if columns[-1] == "__value" else columns[-1])
        aggregation = lineage.get("aggregation")
        operation = {
            "sum": "Total",
            "avg": "Average",
            "count": "Count",
            "min": "Minimum",
            "max": "Maximum",
        }.get(aggregation, "Recorded")
        unit = ""
        if definition and aggregation != "count":
            field: dict[str, Any] = next(
                (field for field in definition.get("columns", []) if field["name"] == metric),
                {},
            )
            if not field.get("unit_column"):
                unit = field.get("currency") or field.get("unit") or ""
        label = f"{measure} ({unit})" if unit else measure
        groups = ", ".join(columns[:-1]) or "Result"
        chart_title = f"{operation} {measure} by {groups}" if metric else title
        report.charts.append(
            ExportChart(
                chart_kind,
                chart_title,
                groups,
                label,
                tuple(" | ".join(_display(cell) for cell in row[:-1]) or "Result" for row in rows),
                (ExportSeries(label, tuple(_chart_value(row[-1]) for row in rows)),),
            )
        )


def _forecast_comparison(report: _Report, record: dict[str, Any]) -> None:
    result = record["result"]
    rows = result["rows"]
    range_label = (
        "Empirical"
        if record.get("evidence", {}).get("request", {}).get("engine") == "advanced-v2"
        else "Heuristic"
    )
    report.text(
        "Comparison scope",
        "Only observed complete forecast periods are scored. Missing actuals remain pending, "
        "not zero. Saved estimates and ranges retain their original meaning; "
        "the ranges are not calibrated confidence intervals.",
    )
    report.objects("Forecast versus later actuals", rows)
    report.metadata("Comparison accuracy", result["metrics"])
    report.metadata(
        "Comparison coverage", {key: result[key] for key in ("observed_count", "pending_count")}
    )
    if rows:
        report.charts.append(
            ExportChart(
                "line",
                "Saved forecast versus observed actuals",
                "Period",
                "Recorded value",
                tuple(str(row["period"]) for row in rows),
                tuple(
                    ExportSeries(label, tuple(_chart_value(row[field]) for row in rows))
                    for field, label in (
                        ("actual", "Actual"),
                        ("estimate", "Estimate"),
                        ("lower", f"{range_label} lower"),
                        ("upper", f"{range_label} upper"),
                    )
                ),
                notes=(
                    "Pending actual values are missing, not zero. "
                    "The original forecast is unchanged.",
                    "Recorded error ranges are not calibrated confidence intervals.",
                    *result.get("limitations", []),
                ),
            )
        )


def build_analysis_report(
    kind: str, record: dict[str, Any], generated_at: datetime
) -> ExportContent:
    """Copy an already authorized/replayed service payload into portable report content."""
    record = public_evidence(record)
    if kind not in {
        "forecast",
        "forecast_comparison",
        "scenario",
        "anomaly",
        "allocation",
        "dashboard",
        "dashboard_queries",
        "study",
    }:
        raise IngestionError(
            "export_unsupported", "This analytical report type is unavailable.", 422
        )
    try:
        core = (
            record["board"]
            if kind == "dashboard"
            else record["study"]
            if kind == "study"
            else record
            if kind in {"forecast", "forecast_comparison", "dashboard_queries"}
            else record["run"]
        )
        name = core.get("name") or (
            "Saved forecast comparison"
            if kind == "forecast_comparison"
            else "Selected executed dashboard results"
        )
        report = _Report(f"Syntelio - {kind}: {name}", generated_at)
        _overview(report, core, kind)
        if kind == "dashboard":
            _dashboard(report, record)
        elif kind == "study":
            _dashboard(
                report, {"board": {"name": name, "scope": "One saved study"}, "studies": [record]}
            )
        elif kind == "dashboard_queries":
            report.text(
                "Selected executed dashboard results",
                "Only the explicitly selected already-executed query results are included. "
                "This is not a claim that every dashboard panel or every source row is exported.",
            )
            for index, item in enumerate(record["results"], 1):
                _query_result(report, f"Executed result {index}", item, _grouped_chart_kind(item))
        elif kind == "forecast":
            _forecast(report, record)
            report.metadata("Saved source and definition evidence", core["evidence"])
        elif kind == "forecast_comparison":
            _forecast_comparison(report, record)
            report.metadata("Saved source and definition evidence", core["evidence"])
        else:
            _decision(report, record, kind)
            report.metadata("Saved source and definition evidence", core["evidence"])
        return report.finish()
    except (KeyError, TypeError, ValueError, IndexError, AttributeError) as error:
        raise IngestionError(
            "export_integrity", "The saved report structure is incomplete or inconsistent.", 409
        ) from error
