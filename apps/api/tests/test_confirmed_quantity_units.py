"""Use case: Distinguishes confirmed quantities from per-row unit labels.

What it does: Treats numeric units fields as quantities while retaining mixed
currency, missing-label and explicit unit-column guards without confirmation.
"""

import pytest

from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import AggregationKind, MetricRequest, dataset_view
from execplus.domain.understanding import apply_definition, governed_request, infer_definition


def test_confirmed_numeric_units_are_quantities_and_do_not_split_sales_revenue():
    table = TableData(("units", "revenue"), (("2", "10"), ("3", "15")))
    view = dataset_view(profile(table))
    definition = infer_definition(profile(table))
    definition["columns"][0]["unit"] = "items"
    definition["columns"][1]["unit"] = "USD"
    confirmed = apply_definition(view, definition)
    for metric in ("units", "revenue"):
        request = MetricRequest(metric, AggregationKind.SUM)
        assert governed_request(confirmed, table, request) == request


@pytest.mark.parametrize("declared", [False, True])
def test_numeric_units_field_is_a_quantity_even_without_confirmation(declared):
    table = TableData(("units", "revenue"), (("2", "10"), ("3", "15")))
    view = dataset_view(profile(table))
    if declared:
        definition = infer_definition(profile(table))
        definition["columns"][1]["unit"] = "USD"
        view = apply_definition(view, definition)
    for metric in ("revenue", "units"):
        request = MetricRequest(metric, AggregationKind.SUM)
        assert governed_request(view, table, request) == request


def test_text_units_labels_keep_the_mixed_unit_guard_without_confirmation():
    table = TableData(("units", "weight"), (("kg", "10"), ("lb", "15")))
    view = dataset_view(profile(table))
    with pytest.raises(ClarificationRequiredError, match="units"):
        governed_request(view, table, MetricRequest("weight", AggregationKind.SUM))


@pytest.mark.parametrize("labels", [("USD", "EUR"), ("USD", "")])
def test_confirmed_fixed_quantity_never_suppresses_mixed_or_missing_currency_labels(labels):
    table = TableData(
        ("units", "revenue", "currency"), (("2", "10", labels[0]), ("3", "15", labels[1]))
    )
    definition = infer_definition(profile(table))
    definition["columns"][0]["unit"] = "items"
    definition["columns"][1]["unit"] = "USD"
    view = apply_definition(dataset_view(profile(table)), definition)
    with pytest.raises(ClarificationRequiredError, match="currency"):
        governed_request(view, table, MetricRequest("revenue", AggregationKind.SUM))


def test_explicit_per_row_unit_mapping_still_applies_even_with_fixed_description():
    table = TableData(("units", "revenue", "measure_label"), (("2", "10", "kg"), ("3", "15", "lb")))
    definition = infer_definition(profile(table))
    definition["columns"][0]["unit"] = "items"
    definition["columns"][1].update(unit="declared value", unit_column="measure_label")
    view = apply_definition(dataset_view(profile(table)), definition)
    with pytest.raises(ClarificationRequiredError, match="measure_label"):
        governed_request(view, table, MetricRequest("revenue", AggregationKind.SUM))


def test_numeric_currency_codes_never_gain_the_quantity_name_exception():
    table = TableData(("currency", "revenue"), (("840", "10"), ("978", "15")))
    definition = infer_definition(profile(table))
    definition["columns"][0].update(role="metric", unit="currency code")
    definition["columns"][1]["unit"] = "declared value"
    view = apply_definition(dataset_view(profile(table)), definition)
    with pytest.raises(ClarificationRequiredError, match="currency"):
        governed_request(view, table, MetricRequest("revenue", AggregationKind.SUM))
