"""Use case: Gives each uploaded dataset an immediate evidence-backed briefing.

What it does: Executes bounded descriptive explorations with existing permission and receipt rules.
"""

import asyncio
from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

from execplus.application.services.analytics import AnalyticsService
from execplus.domain.discovery import (
    VERSION,
    DiscoveryFinding,
    DiscoveryStep,
    discovery_finding,
    discovery_quality,
    discovery_steps,
    name_words,
)
from execplus.domain.errors import (
    ClarificationRequiredError,
    UnsafeQueryError,
    UnsupportedQuestionError,
)
from execplus.domain.evidence import receipt
from execplus.domain.guidance import DescriptionContext
from execplus.domain.ingestion import User
from execplus.domain.models import CalculationLineage, QueryResult, WorkspaceScope
from execplus.domain.profiling import TableData
from execplus.domain.semantics import DatasetView
from execplus.domain.studies import count_plan


@dataclass(frozen=True)
class DiscoveryBrief:
    metadata: dict[str, Any]
    findings: tuple[DiscoveryFinding, ...]


async def _distribution(
    service: AnalyticsService,
    actor: User,
    dataset_id: UUID,
    name: str,
    scope: WorkspaceScope,
    table: TableData,
    view: DatasetView,
    step: DiscoveryStep,
) -> tuple[QueryResult, CalculationLineage]:
    plan = count_plan(
        scope, dataset_id, view, step.request(), present_only=False, distribution=True
    )
    lineage = CalculationLineage(
        query_id=plan.query_id,
        workspace_id=scope.workspace_id,
        dataset_id=dataset_id,
        dataset_name=name,
        records_analyzed=len(table.rows),
        metric=step.metric,
        aggregation="count",
        grouping=(step.metric,),
        filters=(),
        sql=plan.sql,
        model_route="deterministic:discovery-v1",
    )
    with service.uow() as repo:
        service._authorize(repo, actor, scope.workspace_id)
    try:
        result = await service.executor.execute(plan, scope, table, view)
    except (Exception, asyncio.CancelledError):
        service._persist(actor, replace(lineage, receipt=receipt(plan, view.sources, None)))
        raise
    lineage = replace(lineage, receipt=receipt(plan, view.sources, result))
    service._persist(actor, lineage)
    return result, lineage


def _metadata(context: DescriptionContext) -> dict[str, Any]:
    profile = context.profile
    steps = discovery_steps(context)
    measures = list(dict.fromkeys(step.metric for step in steps if not step.distribution))
    categories = [step.metric for step in steps if step.distribution]
    identifiers = [
        column.name
        for column in context.view.columns
        if "identifier" in column.tags
        or name_words(column.name) & {"id", "code", "sku", "zip", "postal"}
    ]
    introduction = []
    if measures:
        introduction.append(f"Start with {', '.join(measures)} to understand the numerical range.")
    if categories:
        introduction.append(f"The {categories[0]} field lets you compare groups of records.")
    if identifiers:
        introduction.append(
            f"{', '.join(identifiers[:3])} look like identifiers: "
            "use them to find records rather than add their codes."
        )
    if not introduction:
        introduction.append("Start with the column meanings and individual records.")
    limitations = []
    for column in profile["columns"]:
        words = name_words(column["name"])
        if words & {"day", "month", "year"} and column["invalid_dates"]:
            limitations.append(
                f"{column['name']} is not recognized as a complete date. "
                "It may be a calendar component such as day of month; "
                "this does not by itself mean the source values are wrong."
            )
        elif words & {"date", "time", "timestamp"} and column["type"] == "text":
            limitations.append(
                f"{column['name']} is currently read as text. "
                "Time analysis requires supported dates or reviewed source preparation."
            )
    return {
        "version": VERSION,
        "dataset_name": context.name,
        "summary": (
            " ".join(introduction) + "\n\n"
            "Ask about a finding or choose a column to explore further."
        ),
        "definition_state": context.state,
        "sources": context.view.sources,
        "shape": {
            "rows": profile["row_count"],
            "columns": profile["column_count"],
            "metrics": len(context.view.metrics),
            "dimensions": len(context.view.dimensions),
        },
        "quality": discovery_quality(context),
        "suggestions": [],
        "limitations": limitations,
    }


async def discover(
    service: AnalyticsService,
    actor: User,
    workspace_id: UUID,
    dataset_id: UUID,
    upload_id: UUID,
) -> DiscoveryBrief:
    context, table, scope = await asyncio.to_thread(
        service.descriptive_snapshot, actor, workspace_id, dataset_id, upload_id
    )
    view, name = context.view, context.name
    metadata = _metadata(context)
    findings = []
    if (
        any(source.get("understanding_id") for source in view.sources)
        and context.state != "confirmed"
    ):
        metadata["limitations"].append(
            "Review and confirm Data understanding for this revision before calculating. "
            "You can still inspect the profile and original file."
        )
        metadata["summary"] = (
            f"Your file contains {context.profile['row_count']} rows and "
            f"{context.profile['column_count']} columns. "
            "You can explore its structure and quality. "
            "A saved business definition needs review before new calculations."
        )
        metadata["suggestions"] = [
            "Help me understand my data",
            "Are there any data quality issues?",
        ]
        await asyncio.to_thread(
            service.recheck_description, actor, workspace_id, dataset_id, upload_id, view.sources
        )
        return DiscoveryBrief(metadata, ())
    for step in discovery_steps(context):
        try:
            if step.distribution:
                result, lineage = await _distribution(
                    service, actor, dataset_id, name, scope, table, view, step
                )
            else:
                result, lineage = await service._execute(
                    actor,
                    dataset_id,
                    name,
                    scope,
                    table,
                    view,
                    step.request(),
                    "deterministic:discovery-v1",
                )
            findings.append(discovery_finding(context, step, result, lineage))
        except (ClarificationRequiredError, UnsafeQueryError, UnsupportedQuestionError) as error:
            message = f"{step.metric}: {error}"
            if message not in metadata["limitations"]:
                metadata["limitations"].append(message)
    metadata["suggestions"] = list(
        dict.fromkeys(
            [finding.question for finding in findings if finding.aggregation != "min"]
            + ["Are there any data quality issues?", "Help me understand my data"]
        )
    )[:6]
    if not findings:
        metadata["limitations"].append(
            "No suitable measures or small category groups were found for automatic findings. "
            "Ask about a named column or inspect the file profile."
        )
    metadata["limitations"].append(
        "This briefing covers selected columns, not every possible pattern. "
        "Extremes and category counts do not establish causes or errors."
    )
    await asyncio.to_thread(
        service.recheck_description, actor, workspace_id, dataset_id, upload_id, view.sources
    )
    return DiscoveryBrief(metadata, tuple(findings))
