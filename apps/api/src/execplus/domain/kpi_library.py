"""Use case: Curates versioned, cross-domain KPI definitions and matches them to a dataset.

What it does: Deterministically explains which governed KPIs a dataset's profile
supports, without ever computing a business number itself.
"""

from dataclasses import dataclass
from enum import Enum

from execplus.domain.semantics import AggregationKind, DatasetView


class KpiDomain(str, Enum):
    FINANCE = "finance"
    SALES = "sales"
    INVENTORY = "inventory"
    HR = "hr"


class KpiUnit(str, Enum):
    CURRENCY = "currency"
    COUNT = "count"
    RATIO = "ratio"


@dataclass(frozen=True, slots=True)
class KpiDefinition:
    id: str
    domain: KpiDomain
    version: int
    name: str
    description: str
    unit: KpiUnit
    aggregation: AggregationKind
    required_tag: str


@dataclass(frozen=True, slots=True)
class KpiMatch:
    definition: KpiDefinition
    column: str
    explanation: str


# Each definition names the single semantic tag (from domain/profiling.py's
# vocabulary) its metric column must carry. Composite KPIs that combine several
# columns (e.g. gross margin = revenue - cost) are out of scope until the query
# engine supports multi-column expressions; every definition here is answerable
# by a single SUM/AVG/COUNT/MIN/MAX over one tagged column.
LIBRARY: tuple[KpiDefinition, ...] = (
    KpiDefinition(
        "finance.total_revenue",
        KpiDomain.FINANCE,
        1,
        "Total revenue",
        "Sum of all revenue-tagged values in the dataset.",
        KpiUnit.CURRENCY,
        AggregationKind.SUM,
        "revenue",
    ),
    KpiDefinition(
        "finance.total_cost",
        KpiDomain.FINANCE,
        1,
        "Total cost",
        "Sum of all cost-tagged values in the dataset.",
        KpiUnit.CURRENCY,
        AggregationKind.SUM,
        "cost",
    ),
    KpiDefinition(
        "sales.total_sales",
        KpiDomain.SALES,
        1,
        "Total sales",
        "Sum of all sales-tagged values in the dataset.",
        KpiUnit.CURRENCY,
        AggregationKind.SUM,
        "sales",
    ),
    KpiDefinition(
        "sales.average_order_value",
        KpiDomain.SALES,
        1,
        "Average order value",
        "Average of all amount-tagged values in the dataset.",
        KpiUnit.CURRENCY,
        AggregationKind.AVG,
        "amount",
    ),
    KpiDefinition(
        "inventory.total_stock",
        KpiDomain.INVENTORY,
        1,
        "Total stock",
        "Sum of all stock-tagged values in the dataset.",
        KpiUnit.COUNT,
        AggregationKind.SUM,
        "stock",
    ),
    KpiDefinition(
        "inventory.average_price",
        KpiDomain.INVENTORY,
        1,
        "Average price",
        "Average of all price-tagged values in the dataset.",
        KpiUnit.CURRENCY,
        AggregationKind.AVG,
        "price",
    ),
    KpiDefinition(
        "hr.total_headcount",
        KpiDomain.HR,
        1,
        "Total headcount",
        "Sum of all headcount-tagged values in the dataset.",
        KpiUnit.COUNT,
        AggregationKind.SUM,
        "headcount",
    ),
    KpiDefinition(
        "hr.average_salary",
        KpiDomain.HR,
        1,
        "Average salary",
        "Average of all salary-tagged values in the dataset.",
        KpiUnit.CURRENCY,
        AggregationKind.AVG,
        "salary",
    ),
)


def kpi_by_id(kpi_id: str) -> KpiDefinition | None:
    return next((definition for definition in LIBRARY if definition.id == kpi_id), None)


def _resolve(view: DatasetView, tag: str) -> str | None:
    for name in sorted(view.metrics):
        column = view.column(name)
        if column is not None and (tag in column.tags or column.name == tag):
            return name
    return None


def compatible_kpis(view: DatasetView) -> tuple[KpiMatch, ...]:
    matches = []
    for definition in LIBRARY:
        column = _resolve(view, definition.required_tag)
        if column is not None:
            explanation = (
                f"{definition.name!r} applies because {column!r} is a metric column "
                f"tagged {definition.required_tag!r}."
            )
            matches.append(KpiMatch(definition, column, explanation))
    return tuple(matches)
