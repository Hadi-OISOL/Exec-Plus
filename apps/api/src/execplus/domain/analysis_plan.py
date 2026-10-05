"""Use case: Describes the actual bounded operations of a conversation request.

What it does: Validates versioned step dependencies, capabilities and result verification policies.
"""

import math
import re
from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

from execplus.domain.guidance import GUIDANCE_FOCUSES
from execplus.domain.ingestion import IngestionError
from execplus.domain.intent import RoutedIntent
from execplus.domain.jobs import ResourceBudget
from execplus.domain.models import QuestionKind


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
            "inspect_profile": ("profile", "source_checksum"),
            "query": ("query_result", "execution_receipt"),
            "retrieve_documents": ("citations", "authorized_citation_checksum"),
            "assemble_evidence": ("answer", "authorized_evidence"),
        }
        seen: set[str] = set()
        required = {"dataset_id", "upload_id", "revision_id", "source_checksum", "output_checksum"}
        for source in self.sources:
            if (
                not isinstance(source, dict)
                or not required <= set(source)
                or set(source) - required - {"understanding_id"}
            ):
                self._invalid()
            try:
                for name in ("dataset_id", "upload_id", "revision_id"):
                    UUID(source[name])
                if "understanding_id" in source:
                    UUID(source["understanding_id"])
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
                "inspect_profile": {"columns", "focus"},
                "query": {"kind", "plan"},
                "retrieve_documents": {"query"},
                "assemble_evidence": set(),
            }[step.operation]
            if set(step.parameters) != expected:
                self._invalid()
            self._parameters(step)
            seen.add(step.id)
        if sum(s.operation == "query" for s in self.steps) > self.budget.max_queries:
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
        if step.operation == "inspect_profile":
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
                    or item["operator"] not in {"eq", "ieq", "ne", "lt", "lte", "gt", "gte"}
                ):
                    self._invalid()
                value = item["value"]
                if not isinstance(value, (str, int, float, bool)) or (
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
    steps: list[AnalysisStep] = []
    data = intent.data_intent if intent.kind == QuestionKind.MIXED else intent
    if data and data.kind in {QuestionKind.NUMERICAL, QuestionKind.ROWS}:
        if data.kind == QuestionKind.NUMERICAL and data.request is not None:
            parameters = asdict(data.request)
        elif data.kind == QuestionKind.ROWS and data.rows is not None:
            parameters = {**asdict(data.rows), "limit": data.limit}
        else:
            raise IngestionError("invalid_analysis_plan", "The data step is invalid.", 422)
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
