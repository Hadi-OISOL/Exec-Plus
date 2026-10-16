"""Use case: Builds complete portable company worksheets from verified saved output.

What it does: Copies exact contributions, translations, eliminations and raw source
rows into protected reports without inventing rates or changing arithmetic.
"""

import json
from datetime import datetime
from typing import Any

from execplus.application.services.analysis_report_documents import _Report
from execplus.domain.exports import ExportChart, ExportContent, ExportSeries


def build_consolidation_report(record: dict[str, Any], generated_at: datetime) -> ExportContent:
    run, sources = record["run"], record["source_rows"]
    result = run["result"]
    report = _Report(run["name"], generated_at)
    report.text(
        "Worksheet scope",
        result["limitation"],
        f"Period: {result['period_start']} to {result['period_end']}.",
        f"Reporting currency: {result['reporting_currency']}; "
        f"sign convention: {result['sign_convention']}.",
        "Sources currently match saved definitions."
        if record["current"]
        else "Historical worksheet: at least one company has a newer source or meaning.",
    )
    for key, label in (
        ("combined", "Combined balances"),
        ("elimination_totals", "Elimination adjustments"),
        ("consolidated", "Consolidated balances"),
    ):
        report.table(
            label,
            ("Group account", result["reporting_currency"]),
            tuple((item["group_account"], item["amount"]) for item in result[key]),
        )
    report.table(
        "Exact totals", ("Stage", result["reporting_currency"]), tuple(result["totals"].items())
    )
    for company in result["contributions"]:
        report.table(
            f"Contribution: {company['name']}",
            ("Group account", result["reporting_currency"]),
            tuple((item["group_account"], item["amount"]) for item in company["accounts"]),
        )
        report.table(
            f"Rates: {company['name']}",
            ("Key", "Basis", "Rate", "As of", "Reference"),
            tuple(
                tuple(item[key] for key in ("key", "basis", "value", "as_of", "reference"))
                for item in company["rates"]
            ),
        )
    report.table(
        "Account translation and elimination",
        (
            "Company",
            "Source account",
            "Group account",
            "Mapped company",
            "Internal",
            "Source amount",
            "Rate key",
            "Translated",
            "Elimination",
            "Remaining",
        ),
        tuple(
            tuple(
                item.get(key)
                for key in (
                    "company_id",
                    "account",
                    "group_account",
                    "counterparty",
                    "internal",
                    "source_amount",
                    "rate_key",
                    "translated_amount",
                    "elimination",
                    "remaining",
                )
            )
            for item in result["source_balances"]
        ),
    )
    for index, journal in enumerate(result["eliminations"], 1):
        report.text(
            f"Elimination journal {index}", json.dumps(journal, sort_keys=True, ensure_ascii=False)
        )
    report.text(
        "Unresolved items", *(result["warnings"] or ["No arithmetic warning was recorded."])
    )
    report.text(
        "Remaining internal balances",
        json.dumps(result["remaining_internal_balances"], sort_keys=True),
    )
    for source in sources:
        report.table(
            f"Original ledger rows: {source['company_id']}",
            tuple(source["columns"]),
            tuple(tuple(row) for row in source["rows"]),
        )
    report.text(
        "Explicit inputs and raw-counterparty mapping",
        json.dumps(run["request"], sort_keys=True, ensure_ascii=False),
    )
    report.text(
        "Private source and calculation evidence",
        json.dumps(run["evidence"], sort_keys=True, ensure_ascii=False),
    )
    chart = ExportChart(
        "bar",
        "Consolidated balances",
        "Group account",
        result["reporting_currency"],
        tuple(item["group_account"] for item in result["consolidated"]),
        (
            ExportSeries(
                result["reporting_currency"],
                tuple(item["amount"] for item in result["consolidated"]),
            ),
        ),
        notes=(
            result["limitation"],
            "Exact source rows, mappings and rates are included in this export.",
        ),
    )
    report.charts.append(chart)
    return report.finish()
