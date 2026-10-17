"""Use case: Describes portable content from already authorized conversation results.

What it does: Preserves exact scalar cells and recorded graph/statistical output
without planning new queries or changing result populations.
"""

import json
from dataclasses import asdict
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from execplus.application.services.data_diagrams import DiagramAnswer
from execplus.application.services.intent_router import PatternAnswer
from execplus.domain.exports import ExportChart, ExportSeries, ExportTable, exact_text
from execplus.domain.models import CalculationLineage, QueryResult, Scalar, VerifiedMetricAnswer
from execplus.domain.pdf_exports import PdfSection, PdfTable
from execplus.domain.public_evidence import public_evidence


def result_chart(table: ExportTable, title: str) -> tuple[ExportChart, ...]:
    if len(table.columns) != 2 or not table.rows:
        return ()
    values: list[str | None] = []
    for row in table.rows:
        if row[1] is None:
            values.append(None)
            continue
        if isinstance(row[1], bool):
            return ()
        try:
            if not Decimal(str(row[1])).is_finite():
                return ()
        except InvalidOperation:
            return ()
        values.append(str(row[1]))
    kind = "bar"
    try:
        dates = [date.fromisoformat(str(row[0])) for row in table.rows]
        if len(dates) > 1 and dates == sorted(set(dates)):
            kind = "line"
    except ValueError:
        pass
    return (
        ExportChart(
            kind,
            title,
            table.columns[0],
            table.columns[1],
            tuple("Missing (null)" if row[0] is None else exact_text(row[0]) for row in table.rows),
            (ExportSeries(table.columns[1], tuple(values)),),
        ),
    )


def thread_tables(answer: object) -> tuple[ExportTable, ...]:
    if isinstance(answer, VerifiedMetricAnswer):
        return (ExportTable(answer.label, (answer.label,), ((answer.value,),)),)
    if (
        isinstance(answer, tuple)
        and len(answer) == 2
        and isinstance(answer[0], QueryResult)
        and isinstance(answer[1], CalculationLineage)
    ):
        return (ExportTable("Exact returned values", answer[0].columns, answer[0].rows),)
    if isinstance(answer, DiagramAnswer):
        columns = ("Field", "Stored type", "Role", "Meaning", "Unit", "Currency", "Unit column")
        return (
            ExportTable(
                "Included fields",
                columns,
                tuple(
                    (
                        node.label,
                        node.data_type,
                        node.role,
                        node.meaning,
                        node.unit,
                        node.currency,
                        node.unit_column,
                    )
                    for node in answer.diagram.nodes
                    if node.kind == "field"
                ),
            ),
        )
    if isinstance(answer, PatternAnswer):
        result = answer.evidence["result"]
        if result.get("version") == "cohort-comparison-v1":
            return (
                ExportTable(
                    "Group comparison",
                    (
                        "Measure",
                        "Unit",
                        "Target count",
                        "Other count",
                        "Target mean",
                        "Other mean",
                        "Difference",
                        "Target median",
                        "Other median",
                        "Status",
                    ),
                    tuple(
                        tuple(
                            item[key]
                            for key in (
                                "column",
                                "unit",
                                "target_count",
                                "other_count",
                                "target_mean",
                                "other_mean",
                                "difference",
                                "target_median",
                                "other_median",
                                "status",
                            )
                        )
                        for item in result["numeric"]
                    ),
                ),
                ExportTable(
                    "Category mix",
                    (
                        "Category",
                        "Value",
                        "Target count",
                        "Other count",
                        "Target share",
                        "Other share",
                    ),
                    tuple(
                        (
                            item["column"],
                            level["value"],
                            level["target_count"],
                            level["other_count"],
                            level["target_share"],
                            level["other_share"],
                        )
                        for item in result["categories"]
                        for level in item["levels"]
                    ),
                ),
                ExportTable(
                    "Comparison method and evidence",
                    ("Path", "Exact recorded value"),
                    tuple(flatten_record(result)),
                ),
            )
        return (
            ExportTable(
                "Recorded pattern output",
                ("Path", "Exact recorded value"),
                tuple(flatten_record(result)),
            ),
        )
    return ()


def flatten_record(value: Any, path: str = "result") -> list[tuple[str, Scalar]]:
    if isinstance(value, dict):
        return [
            row for key, child in value.items() for row in flatten_record(child, f"{path}.{key}")
        ]
    if isinstance(value, list | tuple):
        return [
            row
            for index, child in enumerate(value)
            for row in flatten_record(child, f"{path}[{index}]")
        ]
    return [(path, value)]


def thread_charts(answer: object) -> tuple[ExportChart, ...]:
    if isinstance(answer, DiagramAnswer):
        diagram = answer.diagram
        return (
            ExportChart(
                "diagram",
                diagram.title,
                nodes=tuple(asdict(node) for node in diagram.nodes),
                edges=tuple(asdict(edge) for edge in diagram.edges),
                notes=diagram.limitations,
            ),
        )
    if isinstance(answer, PatternAnswer):
        result = answer.evidence["result"]
        findings = result.get("findings", []) + result.get("exploratory", [])
        if "chart" in result:
            findings = [result]
        if result.get("pooled"):
            findings = [
                {
                    **result["pooled"],
                    "title": "Pooled relationship",
                    "notes": result.get("limitations", []) + result["pooled"].get("notes", []),
                }
            ]
        charts = []
        for finding in findings:
            chart = finding.get("chart", {})
            if chart.get("kind") not in {"bar", "scatter", "matrix"} or not chart.get("points"):
                continue
            points = chart["points"]
            if chart["kind"] == "matrix":
                charts.append(
                    ExportChart(
                        "bar",
                        finding.get("title", "Recorded category combinations"),
                        f"{chart['x']} / {chart['y']}",
                        "Records",
                        tuple(f"{point['x']} / {point['y']}" for point in points),
                        (ExportSeries("Records", tuple(str(point["count"]) for point in points)),),
                        notes=tuple(finding.get("notes", [])),
                    )
                )
                continue
            charts.append(
                ExportChart(
                    chart["kind"],
                    finding.get("title", "Recorded relationship"),
                    chart.get("x", ""),
                    chart.get("y", "") + (f" ({chart['y_unit']})" if chart.get("y_unit") else ""),
                    tuple(str(point["x"]) for point in points),
                    (
                        ExportSeries(
                            chart.get("y", "Value"),
                            tuple(
                                None if point.get("y") is None else str(point["y"])
                                for point in points
                            ),
                        ),
                    ),
                    notes=(
                        *finding.get("notes", []),
                        "Exploratory association, not causality or prediction accuracy.",
                    ),
                )
            )
        return tuple(charts)
    tables = thread_tables(answer)
    if isinstance(answer, tuple) and tables:
        return result_chart(tables[0], "Exact returned comparison")
    return ()


def extended_sections(answer: DiagramAnswer | PatternAnswer) -> tuple[PdfSection, ...]:
    if isinstance(answer, DiagramAnswer):
        diagram = answer.diagram
        intro = (
            diagram.description,
            f"Definition state: {diagram.definition_state}; method: {diagram.version}.",
            f"Included fields: {diagram.shown_fields} of {diagram.total_fields}.",
            *diagram.limitations,
        )
        if diagram.version == "dataset-structure-v1":
            intro += (
                "This earlier map uses analysis groups, not necessarily the saved field roles.",
            )
        sections = [PdfSection(diagram.title, intro)]
    else:
        sections = [
            PdfSection(
                "Measured patterns and comparisons",
                (
                    (
                        "Recorded descriptive relationships are not causal effects, "
                        "prediction accuracy or statistical significance."
                    ),
                    json.dumps(
                        public_evidence(answer.evidence),
                        ensure_ascii=False,
                        default=str,
                        sort_keys=True,
                        indent=2,
                    ),
                ),
            )
        ]
    for table in thread_tables(answer):
        for start in range(0, len(table.rows), 1000):
            sections.append(
                PdfSection(
                    table.name,
                    (
                        (
                            f"Rows {start + 1}-{min(start + 1000, len(table.rows))} of "
                            f"{len(table.rows)}."
                        ),
                    ),
                    PdfTable(
                        table.columns,
                        tuple(
                            tuple(exact_text(cell) for cell in row)
                            for row in table.rows[start : start + 1000]
                        ),
                    ),
                )
            )
    return tuple(sections)
