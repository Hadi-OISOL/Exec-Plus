"""Use case: Verifies dashboard templates only apply when their KPIs are supported.

What it does: Proves template applicability is deterministic and profile-derived.
"""

from execplus.domain.dashboard_templates import TEMPLATES, applicable_templates
from execplus.domain.semantics import dataset_view


def finance_view():
    return dataset_view(
        {
            "columns": [
                {"name": "date", "type": "date", "role": "dimension", "semantic_tags": ["date"]},
                {
                    "name": "revenue",
                    "type": "decimal",
                    "role": "metric",
                    "semantic_tags": ["revenue"],
                },
                {"name": "cost", "type": "decimal", "role": "metric", "semantic_tags": ["cost"]},
            ]
        }
    )


def test_finance_template_applies_when_revenue_and_cost_are_present():
    templates = applicable_templates(finance_view())
    assert {template.id for template in templates} == {"finance.overview"}


def test_sales_template_does_not_apply_to_a_finance_only_dataset():
    templates = applicable_templates(finance_view())
    assert "sales.overview" not in {template.id for template in templates}


def test_no_templates_apply_to_a_dataset_without_any_matching_kpi():
    empty = dataset_view({"columns": [{"name": "notes", "type": "text", "role": "dimension"}]})
    assert applicable_templates(empty) == ()


def test_applicable_templates_is_deterministic():
    assert applicable_templates(finance_view()) == applicable_templates(finance_view())


def test_template_ids_are_unique():
    ids = [template.id for template in TEMPLATES]
    assert len(ids) == len(set(ids))
