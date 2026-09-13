"""Use case: Curates domain-specific dashboard templates backed by the KPI library.

What it does: Names a fixed KPI selection per business domain and reports which
templates a dataset's profile actually supports, deterministically.
"""

from dataclasses import dataclass

from execplus.domain.kpi_library import KpiDomain, compatible_kpis
from execplus.domain.semantics import DatasetView


@dataclass(frozen=True, slots=True)
class DashboardTemplate:
    id: str
    domain: KpiDomain
    name: str
    description: str
    card_kpi_ids: tuple[str, ...]
    trend_kpi_id: str | None
    breakdown_kpi_id: str | None


TEMPLATES: tuple[DashboardTemplate, ...] = (
    DashboardTemplate(
        "finance.overview",
        KpiDomain.FINANCE,
        "Finance overview",
        "Revenue and cost totals with a cost trend and category breakdown.",
        ("finance.total_revenue", "finance.total_cost"),
        "finance.total_cost",
        "finance.total_cost",
    ),
    DashboardTemplate(
        "sales.overview",
        KpiDomain.SALES,
        "Sales overview",
        "Total sales and average order value.",
        ("sales.total_sales", "sales.average_order_value"),
        "sales.total_sales",
        "sales.total_sales",
    ),
    DashboardTemplate(
        "inventory.overview",
        KpiDomain.INVENTORY,
        "Inventory overview",
        "Total stock on hand and average price.",
        ("inventory.total_stock", "inventory.average_price"),
        "inventory.total_stock",
        "inventory.total_stock",
    ),
)


def applicable_templates(view: DatasetView) -> tuple[DashboardTemplate, ...]:
    matched_ids = {match.definition.id for match in compatible_kpis(view)}
    return tuple(
        template
        for template in TEMPLATES
        if set(template.card_kpi_ids) <= matched_ids
    )
