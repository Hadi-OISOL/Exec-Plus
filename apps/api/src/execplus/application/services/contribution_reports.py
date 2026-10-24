"""Use case: Adds exact contribution findings to existing protected study exports.

What it does: Includes reconciled totals, rational components, coverage, ranked change
fields with their drilldown, assumptions and chart values while the existing report keeps both
replayed receipt tables.
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from execplus.domain.exports import ExportChart, ExportSeries

if TYPE_CHECKING:
    from execplus.application.services.analysis_report_documents import _Report


def display(value: dict[str, Any] | None) -> Decimal | None:
    return Decimal(value["display"]) if value is not None else None


def add_contribution(report: "_Report", title: str, evidence: dict[str, Any]) -> None:
    value = evidence["calculation"]
    unit = evidence["units"]["amount"]
    report.text(
        title + " - interpretation",
        "Recorded segment changes, not proven causes.",
        "Exact numerator/denominator evidence governs reconciliation. "
        "Decimal chart values can be rounded.",
    )
    report.table(
        title + " - totals",
        ("Baseline", "Comparison", "Net change", "Component sum", "Reconciled", "Unit"),
        (
            (
                display(value["baseline_total"]),
                display(value["comparison_total"]),
                display(value["net_change"]),
                display(value["component_sum"]),
                value["reconciled"],
                unit,
            ),
        ),
    )
    rows = value["rows"]
    report.table(
        title + " - contributions",
        (
            "Category",
            "Baseline",
            "Comparison",
            "Change",
            "Exact numerator",
            "Exact denominator",
            "Percent of signed net",
            "State",
        ),
        tuple(
            (
                row["segment"],
                display(row["baseline"]["total"]),
                display(row["comparison"]["total"]),
                display(row["delta"]),
                row["delta"]["numerator"] if row["delta"] else None,
                row["delta"]["denominator"] if row["delta"] else None,
                display(row["percent_of_net"]),
                row["status"],
            )
            for row in rows
        ),
    )
    report.table(
        title + " - coverage",
        (
            "Category",
            "Baseline present",
            "Baseline rows",
            "Baseline measured",
            "Baseline missing",
            "Comparison present",
            "Comparison rows",
            "Comparison measured",
            "Comparison missing",
        ),
        tuple(
            (
                row["segment"],
                *[
                    row[side][key]
                    for side in ("baseline", "comparison")
                    for key in ("present", "rows", "measured", "missing")
                ],
            )
            for row in rows
        ),
    )
    if rows and any(row["delta"] is not None for row in rows):
        report.charts.append(
            ExportChart(
                "bar",
                title + " - recorded contributions",
                "Category",
                unit,
                tuple(
                    "(Missing category)" if row["segment"] is None else row["segment"]
                    for row in rows
                ),
                (
                    ExportSeries(
                        "Recorded change",
                        tuple(row["delta"]["display"] if row["delta"] else None for row in rows),
                    ),
                ),
                notes=("Observed accounting differences, not proven causes.",),
            )
        )
    pvm = value.get("pvm")
    if pvm:
        report.text(
            title + " - decomposition method",
            pvm["order"],
            pvm["limitation"],
            "Volume = (Q1 - Q0) * baseline quantity share * baseline unit revenue. "
            "Mix = Q1 * share change * baseline unit revenue. "
            "Unit revenue = comparison quantity * unit revenue change.",
        )
        report.table(
            title + " - decomposition",
            (
                "Component",
                "Decimal display",
                "Exact numerator",
                "Exact denominator",
                "Display exact",
            ),
            tuple(
                (
                    key,
                    display(amount),
                    amount["numerator"],
                    amount["denominator"],
                    amount["display_exact"],
                )
                for key, amount in pvm["totals"].items()
            ),
        )
        report.objects(title + " - per-category decomposition", pvm["components"])
        report.metadata(
            title + " - decomposition status",
            dict(state=pvm["state"], reconciled=pvm["reconciled"]),
        )
    cause = value.get("root_cause")
    if cause:
        add_root_cause(report, title, cause, unit)


def add_root_cause(report: "_Report", title: str, cause: dict[str, Any], unit: str) -> None:
    report.text(
        title + " - where the change is concentrated",
        f"Method: {cause['method']}. State: {cause['state']}.",
        cause["limitation"],
        "Concentration = top member's absolute change / total absolute movement in that field.",
    )
    report.table(
        title + " - ranked change fields",
        (
            "Rank",
            "Field",
            "State",
            "Members",
            "Top member",
            "Top member change",
            "Concentration",
            "Concentration numerator",
            "Concentration denominator",
            "Share of signed net",
            "Unit",
        ),
        tuple(
            (
                index + 1 if field["state"] == "ranked" else None,
                field["field"],
                field["state"],
                field["members"],
                field.get("top_member"),
                display(field.get("top_delta")),
                display(field.get("concentration")),
                field["concentration"]["numerator"] if field.get("concentration") else None,
                field["concentration"]["denominator"] if field.get("concentration") else None,
                display(field.get("top_share_of_net")),
                unit,
            )
            for index, field in enumerate(cause["fields"])
        ),
    )
    drill = cause.get("drilldown")
    if drill:
        report.table(
            title + " - drilldown inside the top member",
            (
                "Inside field",
                "Inside member",
                "Field",
                "Member",
                "Change",
                "Exact numerator",
                "Exact denominator",
                "Unit",
            ),
            tuple(
                (
                    drill["within_field"],
                    drill["within_member"],
                    drill["field"],
                    row["member"],
                    display(row["delta"]),
                    row["delta"]["numerator"],
                    row["delta"]["denominator"],
                    unit,
                )
                for row in drill["rows"]
            ),
        )
        report.metadata(
            title + " - drilldown adds back",
            dict(
                within_field=drill["within_field"],
                within_member=drill["within_member"],
                reconciled=drill["reconciled"],
            ),
        )
