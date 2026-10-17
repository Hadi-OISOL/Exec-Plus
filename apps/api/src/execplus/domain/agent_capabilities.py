"""Use case: Makes the conversation planner aware of bounded, implemented operations.

What it does: Publishes immutable capability descriptions with readiness and limits;
this is a catalog of trusted services, never an arbitrary code or plugin executor.
"""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AgentCapability:
    operation: str
    purpose: str
    route: str
    requirements: str
    limits: str


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
    *, patterns: bool, documents: bool, reports: bool = False
) -> list[dict[str, Any]]:
    excluded = set()
    if not patterns:
        excluded.update({"explore_patterns", "compare_group_relationship", "compare_cohort"})
    if not documents:
        excluded.add("retrieve_documents")
    if not reports:
        excluded.add("export_report")
    return [asdict(item) for item in CAPABILITIES if item.operation not in excluded]
