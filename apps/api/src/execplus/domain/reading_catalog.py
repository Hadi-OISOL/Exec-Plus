"""Use case: Gives qualitative readings a bounded catalog of real exploration operations.

What it does: Adapts the EDA structure/quality checklist and SQL measure/group workflow
into immutable recipes, filtered to available operations and supplied dataset fields.

Adapted under MIT: Copyright (c) 2026 AIpoch; medical-research-skills commit
686e09dfdb45d9fa1a08664f06bb93769b3c9d91, scientific-skills/Data Analysis/
exploratory-data-analysis/references/general_scientific_formats.md (CSV EDA Approach)
and assets/report_template.md. Copyright (c) 2025 Baraa Khatib Salkini;
sql-data-analytics-project commit b99f16a26197ff0d36131867af319238aec23dd8,
03_scripts/03_date_range_exploration.sql, 04_measures_exploration.sql and
05_magnitude_analysis.sql. Full notices and license texts: THIRD_PARTY_NOTICES.md.
"""

from dataclasses import dataclass
from typing import Any

from execplus.domain.semantics import DatasetView


@dataclass(frozen=True, slots=True)
class ReadingRecipe:
    key: str
    operation: str
    purpose: str
    requires: str = ""


READING_RECIPES = (
    ReadingRecipe("structure", "inspect_profile", "Inspect row and column structure."),
    ReadingRecipe(
        "quality", "inspect_profile", "Review missing values, duplicates and type conflicts."
    ),
    ReadingRecipe("date_range", "inspect_profile", "Inspect recorded date boundaries.", "dates"),
    ReadingRecipe("records", "query", "Inspect original records.", "fields"),
    ReadingRecipe(
        "measures", "query", "Ask for a governed measure using its declared calculation.", "metrics"
    ),
    ReadingRecipe("groups", "query", "Compare a governed measure across groups.", "groups"),
)
READING_OPERATIONS = frozenset({"inspect_profile", "query"})


def exploration_catalog(
    view: DatasetView,
    available_operations: frozenset[str] = READING_OPERATIONS,
    column_limit: int = 80,
) -> dict[str, Any]:
    columns = view.columns[: max(0, min(column_limit, 80))]
    metrics = [column.name for column in columns if column.name in view.metrics]
    groups = [column.name for column in columns if column.name in view.dimensions]
    requirements = {
        "": True,
        "fields": bool(columns),
        "metrics": bool(metrics),
        "groups": bool(metrics and groups),
        "dates": any(column.type == "date" for column in columns),
    }
    return {
        "metric_fields": metrics if "query" in available_operations else [],
        "group_fields": groups if "query" in available_operations else [],
        "recipes": [
            {"key": recipe.key, "operation": recipe.operation, "purpose": recipe.purpose}
            for recipe in READING_RECIPES
            if recipe.operation in available_operations and requirements[recipe.requires]
        ],
        "calculation_readiness": "Requires saved meanings, units and the normal query checks.",
    }
