"""Use case: Makes the conversation planner aware of bounded, implemented operations.

What it does: Publishes immutable capability descriptions with readiness and limits;
this is a catalog of trusted services, never an arbitrary code or plugin executor.
"""

from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True, slots=True)
class AgentCapability:
    operation: str
    purpose: str
    route: str
    requirements: str
    limits: str


@dataclass(frozen=True, slots=True)
class CapabilityPolicy:
    input_contract: str
    output_kind: str
    verification: str
    authorization: tuple[str, ...] = ("workspace_membership", "source_access", "current_revision")
    timeout_seconds: int = 100
    input_bytes: int = 20 * 1024 * 1024
    max_model_calls: int = 0
    max_result_records: int | None = None
    error_codes: tuple[str, ...] = (
        "clarification_required",
        "unsupported_question",
        "source_changed",
        "not_found",
        "provider_unavailable",
        "query_data_error",
    )


CAPABILITY_POLICIES = MappingProxyType(
    {
        "query": CapabilityPolicy(
            "MetricRequest | RowRequest", "query_result", "execution_receipt"
        ),
        "inspect_profile": CapabilityPolicy(
            "columns, focus", "profile", "source_checksum", max_model_calls=2
        ),
        "map_dataset_structure": CapabilityPolicy("DiagramRequest", "diagram", "source_checksum"),
        "explore_patterns": CapabilityPolicy(
            "columns: tuple[str, ...]", "patterns", "analysis_receipt"
        ),
        "compare_group_relationship": CapabilityPolicy(
            "columns: tuple[str, str], group_by: str", "patterns", "analysis_receipt"
        ),
        "compare_cohort": CapabilityPolicy(
            "target_column: str, target_value: str, columns: tuple[str, ...]",
            "patterns",
            "analysis_receipt",
        ),
        "retrieve_documents": CapabilityPolicy(
            "bounded question", "citations", "authorized_citation_checksum", max_model_calls=1
        ),
        "export_report": CapabilityPolicy(
            "thread_id, turn_id", "report_link", "authorized_saved_answer"
        ),
        "assemble_evidence": CapabilityPolicy(
            "verified results", "answer", "authorized_evidence", max_model_calls=1
        ),
    }
)


CAPABILITIES = (
    AgentCapability(
        "query",
        "Calculate a named measure or inspect returned records.",
        "numerical or rows",
        "Existing fields; saved units, roles and required filters apply.",
        "One governed data query; at most one thousand returned records.",
    ),
    AgentCapability(
        "inspect_profile",
        "Explain observed file structure, quality or saved meanings.",
        "overview",
        "Authorized source metadata.",
        "No invented results or inferred units.",
    ),
    AgentCapability(
        "map_dataset_structure",
        "Draw the selected file's fields grouped by saved role.",
        "diagram",
        "Authorized source metadata; unconfirmed roles are marked unreviewed.",
        "Eighty fields; membership links only, no inferred joins or causal effects.",
    ),
    AgentCapability(
        "explore_patterns",
        "Compute supported descriptive relationships.",
        "explicit pattern question",
        "Confirmed fixed-unit fields and complete covered population.",
        "Ten thousand matching rows; no causal conclusion or learned prediction.",
    ),
    AgentCapability(
        "compare_group_relationship",
        "Compare pooled and within-group relationships.",
        "explicit group-comparison question",
        "Two confirmed measures and one category.",
        "Twelve groups; adequate complete pairs; no causal interpretation.",
    ),
    AgentCapability(
        "compare_cohort",
        "Compare one recorded category value with the other rows and explain observed differences.",
        "cohort_comparison",
        "Confirmed text category, exact recorded label and fixed-unit measures.",
        "Ten thousand rows; twelve measures; no causal, treatment or time-to-outcome claim.",
    ),
    AgentCapability(
        "retrieve_documents",
        "Find accessible supporting-document evidence.",
        "textual or mixed",
        "Authorized indexed supporting documents.",
        "One bounded retrieval; citations remain source statements, not calculations.",
    ),
    AgentCapability(
        "export_report",
        "Offer a PDF of an eligible saved answer in this conversation.",
        "explicit PDF request",
        "An authorized completed supported answer is required.",
        "No new analysis, automatic download or external delivery.",
    ),
)


def capability_catalog(
    *, patterns: bool, documents: bool, reports: bool = False, compound: bool = False
) -> list[dict[str, Any]]:
    excluded = set()
    if not patterns:
        excluded.update({"explore_patterns", "compare_group_relationship", "compare_cohort"})
    if not documents:
        excluded.add("retrieve_documents")
    if not reports:
        excluded.add("export_report")
    return [
        {
            **asdict(item),
            "limits": (
                "Two independent governed data queries; at most one thousand records per result."
                if compound and item.operation == "query"
                else item.limits
            ),
            "contract": asdict(CAPABILITY_POLICIES[item.operation]),
        }
        for item in CAPABILITIES
        if item.operation not in excluded
    ]
