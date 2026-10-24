"""Use case: Describes the actual bounded operations of a conversation request.

What it does: Validates versioned step dependencies, capabilities and result verification policies.
"""

import math
import re
from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

from execplus.domain.agent_capabilities import CAPABILITY_POLICIES
from execplus.domain.dataset_access import ACCESS_KEYS
from execplus.domain.guidance import GUIDANCE_FOCUSES
from execplus.domain.ingestion import IngestionError
from execplus.domain.intent import RoutedIntent
from execplus.domain.jobs import ResourceBudget
from execplus.domain.models import QuestionKind
from execplus.domain.semantics import MISSING_OPERATORS, TIME_PERIODS

_COMPARISONS = frozenset({"eq", "ieq", "ne", "lt", "lte", "gt", "gte"})
_MISSING = frozenset(item.value for item in MISSING_OPERATORS)


@dataclass(frozen=True)
class AnalysisStep:
    id: str
    operation: str
    dependencies: tuple[str, ...]
    parameters: dict[str, Any]
    output_kind: str
    verification: str


@dataclass(frozen=True)
class AnalysisPlan:
    version: str
    sources: tuple[dict[str, str], ...]
    steps: tuple[AnalysisStep, ...]
    budget: ResourceBudget

    def __post_init__(self) -> None:
        policies = {
            operation: (policy.output_kind, policy.verification)
            for operation, policy in CAPABILITY_POLICIES.items()
        }
        seen: set[str] = set()
        required = {"dataset_id", "upload_id", "revision_id", "source_checksum", "output_checksum"}
        for source in self.sources:
            if (
                not isinstance(source, dict)
                or not required <= set(source)
                or set(source) - required - {"understanding_id"} - ACCESS_KEYS
                or (set(source) & ACCESS_KEYS and not set(source) >= ACCESS_KEYS)
            ):
                self._invalid()
            try:
                for name in ("dataset_id", "upload_id", "revision_id"):
                    UUID(source[name])
                if "understanding_id" in source:
                    UUID(source["understanding_id"])
                if "access_policy_id" in source:
                    UUID(source["access_policy_id"])
                    UUID(source["access_actor_id"])
                    if source["access_restricted"] not in {"true", "false"}:
                        self._invalid()
                    version = source["access_policy_version"]
                    if not isinstance(version, str) or not version.isdecimal() or int(version) < 1:
                        self._invalid()
            except (TypeError, ValueError, AttributeError):
                self._invalid()
            if any(
                not isinstance(source[name], str)
                or re.fullmatch("[0-9a-f]{64}", source[name]) is None
                for name in ("source_checksum", "output_checksum")
            ):
                self._invalid()
        if (
            self.version != "conversation-plan-v1"
            or not 1 <= len(self.steps) <= self.budget.max_steps
        ):
            self._invalid()
        for step in self.steps:
            if (
                not isinstance(step, AnalysisStep)
                or not isinstance(step.id, str)
                or not isinstance(step.operation, str)
                or not isinstance(step.dependencies, (tuple, list))
                or not all(isinstance(name, str) for name in step.dependencies)
                or not isinstance(step.parameters, dict)
                or not step.id
                or len(step.id) > 40
                or step.id in seen
                or not set(step.dependencies) <= seen
                or len(set(step.dependencies)) != len(step.dependencies)
                or policies.get(step.operation) != (step.output_kind, step.verification)
            ):
                self._invalid()
            expected = {
                "export_report": {"thread_id", "turn_id"},
                "map_dataset_structure": {"columns"},
                "explore_patterns": {"columns"},
                "compare_group_relationship": {"columns", "group_by"},
                "compare_cohort": {"columns", "target_column", "target_value"},
                "inspect_profile": {"columns", "focus"},
                "query": {"kind", "plan"},
                "retrieve_documents": {"query"},
                "assemble_evidence": set(),
            }[step.operation]
            if set(step.parameters) != expected:
                self._invalid()
            self._parameters(step)
            seen.add(step.id)
        if (
            sum(
                s.operation
                in {"query", "explore_patterns", "compare_group_relationship", "compare_cohort"}
                for s in self.steps
            )
            > self.budget.max_queries
        ):
            self._invalid()
        if (
            sum(s.operation == "retrieve_documents" for s in self.steps)
            > self.budget.max_retrievals
        ):
            self._invalid()
        if self.steps[-1].operation != "assemble_evidence":
            self._invalid()
        if set(self.steps[-1].dependencies) != {s.id for s in self.steps[:-1]}:
            self._invalid()

    def _parameters(self, step: AnalysisStep) -> None:
        values = step.parameters
        if step.operation == "export_report":
            try:
                UUID(values["thread_id"])
                UUID(values["turn_id"])
            except (ValueError, TypeError, AttributeError):
                self._invalid()
        elif step.operation == "map_dataset_structure":
            columns = values["columns"]
            if (
                not isinstance(columns, list)
                or len(columns) > 80
                or not all(isinstance(name, str) and 0 < len(name) <= 200 for name in columns)
                or len(set(columns)) != len(columns)
            ):
                self._invalid()
        elif step.operation in {"explore_patterns", "compare_group_relationship", "compare_cohort"}:
            columns = values["columns"]
            if (
                not isinstance(columns, list)
                or len(columns) > 12
                or not all(isinstance(name, str) and 0 < len(name) <= 200 for name in columns)
                or len(set(columns)) != len(columns)
            ):
                self._invalid()
            if step.operation == "compare_group_relationship" and (
                len(columns) != 2
                or not isinstance(values["group_by"], str)
                or not 0 < len(values["group_by"]) <= 200
                or values["group_by"] in columns
            ):
                self._invalid()
            if step.operation == "compare_cohort" and (
                not isinstance(values["target_column"], str)
                or not 0 < len(values["target_column"]) <= 200
                or not isinstance(values["target_value"], str)
                or not 0 < len(values["target_value"]) <= 200
                or "\x00" in values["target_value"]
                or values["target_column"] in columns
            ):
                self._invalid()
        elif step.operation == "inspect_profile":
            if (
                not isinstance(values["columns"], list)
                or len(values["columns"]) > 3
                or not all(isinstance(name, str) for name in values["columns"])
                or not isinstance(values["focus"], str)
                or values["focus"] not in GUIDANCE_FOCUSES
            ):
                self._invalid()
        elif step.operation == "retrieve_documents":
            if (
                not isinstance(values["query"], str)
                or not 1 <= len(values["query"].strip()) <= 500
                or "\x00" in values["query"]
            ):
                self._invalid()
        elif step.operation == "query":
            kind, plan = values["kind"], values["plan"]
            if (
                not isinstance(kind, str)
                or kind not in {"numerical", "rows"}
                or not isinstance(plan, dict)
            ):
                self._invalid()
            keys = (
                {"metric", "aggregation", "group_by", "filters"}
                if kind == "numerical"
                else {"columns", "filters", "limit"}
            )
            if kind == "numerical":
                keys = keys | ({"order", "limit", "period", "times"} & set(plan))
                if plan.get("per_day") is True:
                    keys = keys | {"per_day"}
                if "period" in plan and plan["period"] not in TIME_PERIODS:
                    self._invalid()
                if "times" in plan and (
                    not isinstance(plan["times"], str) or not 1 <= len(plan["times"]) <= 200
                ):
                    self._invalid()
                if "order" in plan and (
                    plan["order"] not in ("asc", "desc")
                    or (
                        "limit" in plan
                        and (type(plan["limit"]) is not int or not 1 <= plan["limit"] <= 1000)
                    )
                ):
                    self._invalid()
                if "limit" in plan and "order" not in plan:
                    self._invalid()
            if kind == "rows" and "order_by" in plan:
                keys = keys | {"order_by"}
                order_by = plan["order_by"]
                if (
                    not isinstance(order_by, dict)
                    or set(order_by) != {"column", "direction"}
                    or not isinstance(order_by["column"], str)
                    or not 1 <= len(order_by["column"]) <= 200
                    or order_by["direction"] not in ("asc", "desc")
                ):
                    self._invalid()
            if kind == "rows" and "extremum" in plan:
                keys = keys | {"extremum"}
                extremum = plan["extremum"]
                if (
                    not isinstance(extremum, dict)
                    or set(extremum) != {"column", "direction"}
                    or not isinstance(extremum["column"], str)
                    or not 1 <= len(extremum["column"]) <= 200
                    or extremum["direction"] not in ("min", "max")
                ):
                    self._invalid()
            if set(plan) != keys:
                self._invalid()
            filters = plan["filters"]
            if not isinstance(filters, (list, tuple)) or len(filters) > 20:
                self._invalid()
            for item in filters:
                if (
                    not isinstance(item, dict)
                    or set(item) != {"column", "operator", "value"}
                    or not isinstance(item["column"], str)
                    or not isinstance(item["operator"], str)
                    or item["operator"] not in {*_COMPARISONS, *_MISSING}
                ):
                    self._invalid()
                value = item["value"]
                if item["operator"] in _MISSING:
                    if value is not None:
                        self._invalid()
                elif not isinstance(value, (str, int, float, bool)) or (
                    isinstance(value, float) and not math.isfinite(value)
                ):
                    self._invalid()
            if kind == "numerical":
                if (
                    not isinstance(plan["metric"], str)
                    or not isinstance(plan["aggregation"], str)
                    or plan["aggregation"] not in {"sum", "avg", "count", "min", "max"}
                    or not isinstance(plan["group_by"], (tuple, list))
                    or len(plan["group_by"]) > 10
                    or not all(isinstance(name, str) for name in plan["group_by"])
                ):
                    self._invalid()
            elif (
                not isinstance(plan["columns"], (list, tuple))
                or not all(isinstance(name, str) for name in plan["columns"])
                or type(plan["limit"]) is not int
                or not 1 <= plan["limit"] <= 1000
            ):
                self._invalid()

    def _invalid(self) -> None:
        raise IngestionError(
            "invalid_analysis_plan", "The analysis plan is outside supported bounds.", 422
        )

    def body(self) -> dict[str, Any]:
        return asdict(self)


def conversation_plan(intent: RoutedIntent, sources: tuple[dict[str, str], ...]) -> AnalysisPlan:
    if intent.kind == QuestionKind.DIAGRAM:
        return diagram_conversation_plan(intent.guide_columns, sources)
    if intent.data_steps:
        compound_steps = tuple(
            AnalysisStep(
                f"data_{index}",
                "query",
                (),
                conversation_plan(step, sources).steps[0].parameters,
                "query_result",
                "execution_receipt",
            )
            for index, step in enumerate(intent.data_steps, 1)
        )
        return AnalysisPlan(
            "conversation-plan-v1",
            sources,
            (
                *compound_steps,
                AnalysisStep(
                    "answer",
                    "assemble_evidence",
                    tuple(step.id for step in compound_steps),
                    {},
                    "answer",
                    "authorized_evidence",
                ),
            ),
            ResourceBudget(max_queries=2),
        )
    steps: list[AnalysisStep] = []
    data = intent.data_intent if intent.kind == QuestionKind.MIXED else intent
    if data and data.kind in {QuestionKind.NUMERICAL, QuestionKind.ROWS}:
        if data.kind == QuestionKind.NUMERICAL and data.request is not None:
            parameters = asdict(data.request)
        elif data.kind == QuestionKind.ROWS and data.rows is not None:
            parameters = {**asdict(data.rows), "limit": data.limit}
        else:
            raise IngestionError("invalid_analysis_plan", "The data step is invalid.", 422)
        optional = (
            ("extremum", "order_by")
            if data.kind == QuestionKind.ROWS
            else ("order", "limit", "period", "times")
        )
        parameters = {
            key: value
            for key, value in parameters.items()
            if (key not in optional or value is not None) and (key != "per_day" or value)
        }
        steps.append(
            AnalysisStep(
                "data",
                "query",
                (),
                {"kind": data.kind.value, "plan": parameters},
                "query_result",
                "execution_receipt",
            )
        )
    if intent.kind == QuestionKind.OVERVIEW:
        steps.append(
            AnalysisStep(
                "profile",
                "inspect_profile",
                (),
                {"columns": list(intent.guide_columns), "focus": intent.guide_focus},
                "profile",
                "source_checksum",
            )
        )
    if intent.kind in {QuestionKind.TEXTUAL, QuestionKind.MIXED} and intent.document_query:
        steps.append(
            AnalysisStep(
                "documents",
                "retrieve_documents",
                (),
                {"query": intent.document_query},
                "citations",
                "authorized_citation_checksum",
            )
        )
    steps.append(
        AnalysisStep(
            "answer",
            "assemble_evidence",
            tuple(s.id for s in steps),
            {},
            "answer",
            "authorized_evidence",
        )
    )
    return AnalysisPlan("conversation-plan-v1", sources, tuple(steps), ResourceBudget())


def report_conversation_plan(thread_id: UUID, turn_id: UUID) -> AnalysisPlan:
    return AnalysisPlan(
        "conversation-plan-v1",
        (),
        (
            AnalysisStep(
                "report",
                "export_report",
                (),
                {"thread_id": str(thread_id), "turn_id": str(turn_id)},
                "report_link",
                "authorized_saved_answer",
            ),
            AnalysisStep(
                "answer", "assemble_evidence", ("report",), {}, "answer", "authorized_evidence"
            ),
        ),
        ResourceBudget(),
    )


def diagram_conversation_plan(
    columns: tuple[str, ...], sources: tuple[dict[str, str], ...]
) -> AnalysisPlan:
    return AnalysisPlan(
        "conversation-plan-v1",
        sources,
        (
            AnalysisStep(
                "diagram",
                "map_dataset_structure",
                (),
                {"columns": list(columns)},
                "diagram",
                "source_checksum",
            ),
            AnalysisStep(
                "answer", "assemble_evidence", ("diagram",), {}, "answer", "authorized_evidence"
            ),
        ),
        ResourceBudget(),
    )


def pattern_conversation_plan(
    columns: tuple[str, ...],
    sources: tuple[dict[str, str], ...],
    *,
    group_by: str | None = None,
) -> AnalysisPlan:
    return AnalysisPlan(
        "conversation-plan-v1",
        sources,
        (
            AnalysisStep(
                "patterns",
                "compare_group_relationship" if group_by is not None else "explore_patterns",
                (),
                {
                    "columns": list(columns),
                    **({"group_by": group_by} if group_by is not None else {}),
                },
                "patterns",
                "analysis_receipt",
            ),
            AnalysisStep(
                "answer", "assemble_evidence", ("patterns",), {}, "answer", "authorized_evidence"
            ),
        ),
        ResourceBudget(),
    )


def cohort_conversation_plan(
    target_column: str,
    target_value: str,
    columns: tuple[str, ...],
    sources: tuple[dict[str, str], ...],
) -> AnalysisPlan:
    return AnalysisPlan(
        "conversation-plan-v1",
        sources,
        (
            AnalysisStep(
                "comparison",
                "compare_cohort",
                (),
                {
                    "target_column": target_column,
                    "target_value": target_value,
                    "columns": list(columns),
                },
                "patterns",
                "analysis_receipt",
            ),
            AnalysisStep(
                "answer", "assemble_evidence", ("comparison",), {}, "answer", "authorized_evidence"
            ),
        ),
        ResourceBudget(),
    )
