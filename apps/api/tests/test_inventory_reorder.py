"""Use case: Verifies inventory reorder recommendations against independent calculations.

What it does: Recomputes demand, safety stock and quantities with pandas/SciPy, checks the
budget case against brute-force enumeration and the real CP-SAT worker, refuses tampered
solver evidence and exercises the governed private API with replay, review and export.
"""

import asyncio
from datetime import date, timedelta
from decimal import Decimal
from itertools import product
from math import ceil, sqrt

import pandas as pd
import pytest
from scipy.stats import norm

from execplus.domain.ingestion import IngestionError
from execplus.domain.inventory_reorder import (
    SERVICE_LEVELS,
    checked_reorder,
    prepare_reorder,
    reopen_reorder,
)
from execplus.domain.large_allocation import SolverOutcome
from execplus.infrastructure.allocation.cp_sat import CpSatAllocationSolver
from test_result_exports import download_text
from test_studies import add_member, prepare
from test_understanding import confirm, context

START = date(2026, 1, 1)
DEMAND = {
    "A": [5, 7, 6, 0, 8, 5, 6, 7, 4, 6, 5, 9, 6, 5],
    "B": [1, 0, 2, 1, 0, 0, 3, 1, 1, 0, 2, 1, 0, 1],
    "C": [12, 10, 11, 14, 9, 13, 12, 10, 11, 12, 15, 9, 10, 12],
}
TYPED = {
    "A": dict(stock="20", reorder_point="30", lead_time_days=4, unit_cost="2.50"),
    "B": dict(stock="3", reorder_point="5", lead_time_days=10, unit_cost="7"),
    "C": dict(stock="80", reorder_point="40", lead_time_days=3, unit_cost="1.25"),
}


def history_rows(skip=()):
    return tuple(
        (START + timedelta(days=day), item, Decimal(value))
        for item, values in DEMAND.items()
        for day, value in enumerate(values)
        if (item, day) not in skip
    )


def request(**changes):
    return (
        dict(
            kind="bounded_allocation",
            model="inventory-reorder-v1",
            date_column="day",
            item_column="item",
            demand_column="sold",
            stock_column=None,
            reorder_point_column=None,
            lead_time_column=None,
            unit_cost_column=None,
            default_lead_time_days=None,
            items=[dict(item=k, **v) for k, v in TYPED.items()],
            service_level="0.95",
            budget=None,
            assumptions_confirmed=True,
            filters=[],
        )
        | changes
    )


def expected(level="0.95", skip=()):
    frame = pd.DataFrame(history_rows(skip), columns=["day", "item", "sold"])
    frame["sold"] = frame["sold"].astype(float)
    days = pd.date_range(START, START + timedelta(days=13))
    rows = {}
    for item, values in TYPED.items():
        series = (
            frame[frame["item"] == item]
            .groupby("day")["sold"]
            .sum()
            .reindex(days.date, fill_value=0.0)
        )
        mean, deviation = series.mean(), series.std(ddof=1)
        lead = values["lead_time_days"]
        safety = norm.ppf(float(level)) * deviation * sqrt(lead)
        target = float(values["reorder_point"]) + mean * lead + safety
        stock = float(values["stock"])
        quantity = max(0, ceil(target - stock)) if stock <= float(values["reorder_point"]) else 0
        rows[item] = dict(
            mean=mean,
            deviation=deviation,
            safety=safety,
            target=target,
            quantity=quantity,
            cover=stock / mean,
        )
    return rows


def solve(problem):
    return asyncio.run(CpSatAllocationSolver().solve(problem))


@pytest.mark.parametrize("level", sorted(SERVICE_LEVELS))
def test_quantities_match_an_independent_pandas_scipy_recomputation(level):
    result = checked_reorder(prepare_reorder(request(service_level=level), history_rows()), None)
    reference = expected(level)
    assert result["status"] == "feasible" and result["funding"] == "complete"
    assert result["history"] == dict(start="2026-01-01", end="2026-01-14", calendar_days=14)
    for row in result["allocations"]:
        check = reference[row["candidate"]]
        assert row["quantity"] == row["recommended_quantity"] == check["quantity"]
        assert abs(float(row["mean_daily_demand"]) - check["mean"]) < 1e-6
        assert abs(float(row["daily_demand_deviation"]) - check["deviation"]) < 1e-6
        assert abs(float(row["safety_stock"]) - check["safety"]) < 1e-6
        assert abs(float(row["target_level"]) - check["target"]) < 1e-6
        assert abs(float(row["days_of_cover"]) - check["cover"]) < 1e-6
    assert [row["candidate"] for row in result["allocations"]] == sorted(
        reference, key=lambda item: reference[item]["cover"]
    )
    assert result["allocations"][-1]["candidate"] == "C"
    assert result["allocations"][-1]["quantity"] == 0
    assert abs(float(SERVICE_LEVELS[level]) - norm.ppf(float(level))) < 1e-14


def test_days_without_rows_count_as_zero_demand():
    result = checked_reorder(prepare_reorder(request(), history_rows(skip={("A", 3)})), None)
    row = next(r for r in result["allocations"] if r["candidate"] == "A")
    reference = expected(skip={("A", 3)})["A"]
    assert abs(float(row["mean_daily_demand"]) - reference["mean"]) < 1e-6
    assert abs(float(row["daily_demand_deviation"]) - reference["deviation"]) < 1e-6


def test_budget_case_matches_brute_force_optimum_through_the_real_solver():
    full = checked_reorder(prepare_reorder(request(), history_rows()), None)
    needs = {row["candidate"]: row["quantity"] for row in full["allocations"]}
    costs = {item: Decimal(values["unit_cost"]) for item, values in TYPED.items()}
    assert full["cost"] == str(sum(costs[i] * q for i, q in needs.items()))
    budget = Decimal("60")
    prepared = prepare_reorder(request(budget=str(budget)), history_rows())
    assert prepared.problem is not None and prepared.candidates == ("B", "A")
    outcome = solve(prepared.problem)
    result = checked_reorder(prepared, outcome)
    assert result["funding"] == "budget_limited" and result["status"] == "feasible"
    funded = {row["candidate"]: row["quantity"] for row in result["allocations"]}
    weights = {"B": 2, "A": 1}
    best = max(
        sum(costs[i] * weights[i] * q for i, q in zip(("B", "A"), choice, strict=True))
        for choice in product(range(needs["B"] + 1), range(needs["A"] + 1))
        if sum(costs[i] * q for i, q in zip(("B", "A"), choice, strict=True)) <= budget
    )
    achieved = sum(costs[i] * weights[i] * funded[i] for i in ("B", "A"))
    assert achieved == best
    assert Decimal(result["cost"]) <= budget
    assert Decimal(result["unused_budget"]) == budget - Decimal(result["cost"])
    assert funded["C"] == 0
    assert reopen_reorder(prepared, result) == result
    assert result["verification"]["objective"] == "passed"


def test_tampered_solver_evidence_is_refused():
    prepared = prepare_reorder(request(budget="60"), history_rows())
    outcome = solve(prepared.problem)
    over = tuple(prepared.problem.maximum)
    for bad in (
        SolverOutcome("OPTIMAL", over, outcome.objective),
        SolverOutcome("OPTIMAL", outcome.quantities, (outcome.objective or 0) + 1),
        SolverOutcome("INFEASIBLE", None, None),
    ):
        with pytest.raises(IngestionError):
            checked_reorder(prepared, bad)


def test_latest_column_values_feed_stock_reorder_point_lead_time_and_cost():
    rows = tuple(
        (*row, Decimal(100 - day), Decimal(30), Decimal(4), Decimal("2.50"))
        for row in history_rows()
        for day in [(row[0] - START).days]
    )
    raw = request(
        items=[],
        stock_column="on_hand",
        reorder_point_column="reorder_point",
        lead_time_column="lead_days",
        unit_cost_column="unit_cost",
    )
    result = checked_reorder(prepare_reorder(raw, rows), None)
    first = {row["candidate"]: row for row in result["allocations"]}
    assert first["A"]["stock"] == "87" and first["A"]["below_reorder_point"] is False
    conflicting = (*rows, (START + timedelta(days=13), "A", Decimal(0), Decimal(1), *rows[0][4:]))
    with pytest.raises(IngestionError):
        prepare_reorder(raw, conflicting)


@pytest.mark.parametrize(
    "changes",
    [
        dict(items=[dict(item="A", stock="1")]),
        dict(stock_column="on_hand"),
        dict(service_level="0.8"),
        dict(items=[dict(item="Z", **TYPED["A"])]),
        dict(budget="10", items=[dict(item="A", **(TYPED["A"] | dict(unit_cost=None)))]),
        dict(default_lead_time_days=0),
        dict(assumptions_confirmed=False),
        dict(date_column="sold"),
    ],
)
def test_invalid_reorder_requests_are_refused(changes):
    with pytest.raises(IngestionError):
        prepare_reorder(request(**changes), history_rows())


def test_short_history_is_refused():
    with pytest.raises(IngestionError):
        prepare_reorder(request(), tuple(r for r in history_rows() if r[0] < START + timedelta(6)))


CSV = "day,item,sold,on_hand,reorder_point,lead_days,unit_cost\n" + "".join(
    f"{(START + timedelta(days=day)).isoformat()},{item},{value},"
    f"{TYPED[item]['stock']},{TYPED[item]['reorder_point']},"
    f"{TYPED[item]['lead_time_days']},{TYPED[item]['unit_cost']}\n"
    for item, values in DEMAND.items()
    for day, value in enumerate(values)
)


def fixture(env):
    headers, actor, wid, did, uid, root = prepare(env, CSV.encode())
    current = context(env, headers, root)
    for column in current["definition"]["columns"]:
        if column["name"] in {"sold", "on_hand", "reorder_point"}:
            column.update(role="metric", unit="units", currency="")
        elif column["name"] == "lead_days":
            column.update(role="metric", unit="days", currency="")
        elif column["name"] == "unit_cost":
            column.update(role="metric", unit="", currency="USD")
    response = confirm(env, headers, root, current)
    assert response.status_code == 201, response.text
    return headers, actor, wid, did, uid, root


def create(env, headers, root, **changes):
    options = env.client.get(root + "/decision-analysis/options", headers=headers)
    assert options.status_code == 200, options.text
    value = options.json()
    assert "day" in value["inventory_reorder"]["dates"]
    body = (
        dict(
            name="Reorder plan",
            revision_id=value["revision_id"],
            understanding_id=value["understanding_id"],
            date_column="day",
            item_column="item",
            demand_column="sold",
            stock_column="on_hand",
            reorder_point_column="reorder_point",
            lead_time_column="lead_days",
            unit_cost_column="unit_cost",
            service_level="0.95",
            assumptions_confirmed=True,
        )
        | changes
    )
    return env.client.post(
        root + "/decision-analysis/inventory-reorders", headers=headers, json=body
    )


def test_reorder_api_saves_private_replayable_reviewable_exportable_plans(integration):
    env = integration
    headers, _, wid, did, _, root = fixture(env)
    response = create(env, headers, root, budget="60")
    assert response.status_code == 201, response.text
    body = response.json()
    run = body["run"]
    assert run["method_version"] == "inventory-reorder-v1"
    assert run["result"]["funding"] == "budget_limited"
    domain = checked_reorder(
        prepare_reorder(request(budget="60"), history_rows()),
        solve(prepare_reorder(request(budget="60"), history_rows()).problem),
    )
    for saved, recomputed in zip(run["result"]["allocations"], domain["allocations"], strict=True):
        for key, value in saved.items():
            if isinstance(value, str) and key != "candidate":
                assert Decimal(value) == Decimal(recomputed[key]), key
            else:
                assert value == recomputed[key], key
    runs = f"/workspaces/{wid}/datasets/{did}/decision-analysis/{run['id']}"
    reopened = env.client.get(runs, headers=headers)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["run"] == run
    review = env.client.post(
        runs + "/reviews",
        headers=headers,
        json=dict(
            target="decision", status="approved", note="Order within budget", expected_version=0
        ),
    )
    assert review.status_code == 201, review.text
    assert review.json()["approval_effective"] is True
    exported = download_text(
        env.client.get(
            f"/workspaces/{wid}/datasets/{did}/analyses/{run['id']}/export.xlsx?kind=allocation",
            headers=headers,
        ),
        "xlsx",
    )
    assert run["result"]["allocations"][0]["target_level"] in exported
    other, _ = add_member(env, headers, wid)
    assert env.client.get(runs, headers=other).status_code == 404
    unlimited = create(env, headers, root)
    assert unlimited.status_code == 201, unlimited.text
    assert unlimited.json()["run"]["result"]["funding"] == "complete"
    conflict = create(env, headers, root, items=[dict(item="A", stock="1")])
    assert conflict.status_code == 422, conflict.text
