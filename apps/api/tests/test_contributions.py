"""Use case: Checks exact recorded contributions against independent rational oracles.

What it does: Covers cancellation, missingness, entry/exit, bounds and the declared
volume/mix/unit-revenue order without model calls or inferred business causes.
"""

from copy import deepcopy
from fractions import Fraction
from uuid import uuid4

import pytest

from execplus.domain.contributions import calculate_contributions, projection, validate_comparison
from execplus.domain.ingestion import IngestionError
from execplus.domain.models import WorkspaceScope
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import dataset_view
from execplus.domain.understanding import apply_definition, infer_definition


def exact(value):
    return None if value is None else Fraction(int(value["numerator"]), int(value["denominator"]))


def test_exact_changes_distinguish_entry_exit_zero_missing_and_cancellation():
    result = calculate_contributions(
        (("A", "0.1"), ("A", "0.2"), ("B", "1"), ("Z", "0")),
        (("A", "1.3"), ("B", "0"), ("N", "0")),
        False,
    )
    assert exact(result["net_change"]) == 0 and result["reconciled"]
    assert exact(result["component_sum"]) == 0
    assert [r["segment"] for r in result["rows"]] == ["A", "B", "N", "Z"]
    assert all(r["percent_of_net"] is None for r in result["rows"])
    by = {r["segment"]: r for r in result["rows"]}
    assert by["N"]["status"] == "entered" and not by["N"]["baseline"]["present"]
    assert by["Z"]["status"] == "exited" and by["Z"]["baseline"]["present"]
    assert by["A"]["baseline"]["rows"] == by["A"]["baseline"]["measured"] == 2
    assert exact(by["A"]["delta"]) == 1 and exact(by["B"]["delta"]) == -1


def test_missing_only_is_undefined_but_partial_exclusion_is_counted():
    result = calculate_contributions(
        (("A", None), ("B", "3"), ("B", None)), (("A", "2"), ("B", "4")), False
    )
    assert result["net_change"] is None and result["baseline_total"] is None
    assert result["component_sum"] is None and not result["reconciled"]
    assert result["excluded_missing"] == 2
    by = {r["segment"]: r for r in result["rows"]}
    assert by["A"]["delta"] is None and by["A"]["status"] == "undefined"
    assert by["A"]["baseline"]["present"] and by["A"]["baseline"]["total"] is None
    assert exact(by["B"]["delta"]) == 1 and by["B"]["baseline"]["missing"] == 1


def test_nonzero_net_contributions_can_exceed_one_hundred_percent():
    value = calculate_contributions((("A", "10"), ("B", "10")), (("A", "30"), ("B", "0")), False)
    assert [exact(r["percent_of_net"]) for r in value["rows"]] == [200, -100]


def test_pvm_independent_oracle_reconciles_matched_and_entered_exited_products():
    before = (("A", "100", "10"), ("B", "200", "10"), ("D", "30", "1"))
    after = (("A", "240", "20"), ("B", "125", "5"), ("C", "80", "2"))
    value = calculate_contributions(before, after, True)
    assert exact(value["net_change"]) == 115 and value["reconciled"]
    assert {k: exact(v) for k, v in value["pvm"]["totals"].items()} == dict(
        volume=75, mix=-75, unit_revenue=65, entries=80, exits=-30
    )
    rows = value["pvm"]["components"]
    assert [[exact(row[k]) for k in ("volume", "mix", "unit_revenue")] for row in rows] == [
        [25, 75, 40],
        [50, -150, 25],
    ]
    assert value["pvm"]["reconciled"]


def test_nonterminating_ratios_keep_exact_fractions_and_label_rounded_displays():
    value = calculate_contributions(
        (("A", "1", "1"), ("B", "1", "2")), (("A", "2", "2"), ("B", "3", "3")), True
    )
    pvm = value["pvm"]["totals"]
    assert exact(pvm["volume"]) == Fraction(4, 3)
    assert exact(pvm["mix"]) == Fraction(1, 6)
    assert exact(pvm["unit_revenue"]) == Fraction(3, 2)
    assert not pvm["volume"]["display_exact"] and pvm["unit_revenue"]["display_exact"]
    assert exact(value["net_change"]) == 3 and value["pvm"]["reconciled"]


def test_high_precision_null_category_and_no_matched_products():
    value = calculate_contributions(
        ((None, "9007199254740993.100000000001", "1"),),
        (("None", "9007199254740993.100000000003", "1"),),
        True,
    )
    assert exact(value["net_change"]) == Fraction(2, 10**12)
    assert value["pvm"]["state"] == "no_matched_products"
    assert value["pvm"]["reconciled"]
    assert len(value["rows"]) == 2


@pytest.mark.parametrize(
    "row", [("A", None, "1"), ("A", "1", None), ("A", "1", "0"), ("A", "1", "-1")]
)
def test_pvm_refuses_incomplete_or_nonpositive_quantity(row):
    with pytest.raises(IngestionError, match="complete revenue/quantity"):
        calculate_contributions((row,), (("A", "2", "1"),), True)


@pytest.mark.parametrize(
    "rows", [tuple(("A", "1") for _ in range(10001)), tuple((str(i), "1") for i in range(129))]
)
def test_never_treats_a_truncated_population_as_complete(rows):
    with pytest.raises(IngestionError):
        calculate_contributions(rows, (), False)


def fixture():
    table = TableData(
        ("date", "segment", "revenue", "quantity"),
        (("2026-01-01", "A", "10", "2"), ("2026-02-01", "A", "12", "3")),
    )
    view = dataset_view(profile(table))
    definition = infer_definition(profile(table))
    definition["grain"] = "record"
    for column in definition["columns"]:
        if column["name"] == "revenue":
            column.update(role="metric", currency="USD", unit="")
        if column["name"] == "quantity":
            column.update(role="metric", unit="items", currency="")
    view = apply_definition(view, definition)
    did, uid = uuid4(), uuid4()
    side = dict(
        column="revenue",
        segment="segment",
        quantity_column="quantity",
        filters=[],
        date_column="date",
        start="2026-01-01",
        end="2026-01-31",
    )
    other = {
        **side,
        "dataset_id": str(did),
        "upload_id": str(uid),
        "revision_id": str(uuid4()),
        "understanding_id": str(uuid4()),
        "start": "2026-02-01",
        "end": "2026-02-28",
    }
    method = dict(
        kind="contribution",
        mode="period",
        baseline=side,
        comparison=other,
        additive_rows_confirmed=True,
        decompose=True,
    )
    return table, view, did, uid, method


@pytest.mark.parametrize(
    "change",
    [dict(mode=[]), dict(additive_rows_confirmed=False), dict(decompose="yes"), dict(extra="no")],
)
def test_comparison_rejects_malformed_or_unconfirmed_methods(change):
    _, _, did, uid, method = fixture()
    with pytest.raises(IngestionError):
        validate_comparison(method | change, did, uid)


def test_periods_require_nonoverlap_same_fields_and_exact_date_strings():
    _, _, did, uid, method = fixture()
    assert validate_comparison(method, did, uid)["mode"] == "period"
    for key, value in (
        ("start", "2026-01-31"),
        ("column", "quantity"),
        ("end", "20260228"),
        ("upload_id", str(uuid4())),
    ):
        changed = deepcopy(method)
        changed["comparison"][key] = value
        with pytest.raises(IngestionError):
            validate_comparison(changed, did, uid)


def test_projection_uses_declared_filters_and_rejects_stock_and_mixed_populations():
    table, view, did, _uid, method = fixture()
    scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"owner"}), frozenset({did}))
    plan, units = projection(scope, did, table, view, method["baseline"], True)
    assert '"date" >= ?' in plan.sql and '"date" <= ?' in plan.sql and "LIMIT 10001" in plan.sql
    assert units["amount"] == "USD" and units["quantity"] == "items"
    bad = deepcopy(view.definition)
    bad["grain"] = "inventory_snapshot"
    with pytest.raises(IngestionError):
        projection(scope, did, table, apply_definition(view, bad), method["baseline"], True)
    bad = deepcopy(view.definition)
    bad["metrics"] = [
        dict(
            column="quantity",
            aggregation="sum",
            filters=[dict(column="segment", operator="eq", value="A")],
        )
    ]
    with pytest.raises(IngestionError, match="identical required filters"):
        projection(scope, did, table, apply_definition(view, bad), method["baseline"], True)
