"""Use case: Runs one trusted integer allocation in a disposable process.

What it does: Enforces OS limits before importing CP-SAT and emits bounded typed JSON only.
"""

import json
import os
import resource
import sys
from typing import Any

LIMIT = 2**53 - 1


def bounded_input(value: Any) -> dict[str, Any]:
    keys = {"benefits", "resources", "capacities", "minimum", "maximum", "requires", "excludes"}
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("Invalid solver input")
    n = len(value["benefits"])
    if not 1 <= n <= 50 or not 1 <= len(value["resources"]) <= 4:
        raise ValueError("Invalid solver dimensions")
    if len(value["capacities"]) != len(value["resources"]) or any(
        len(column) != n for column in [value["minimum"], value["maximum"], *value["resources"]]
    ):
        raise ValueError("Invalid solver dimensions")
    for column in [
        value["benefits"],
        value["minimum"],
        value["maximum"],
        value["capacities"],
        *value["resources"],
    ]:
        if any(type(x) is not int or not 0 <= x <= LIMIT for x in column):
            raise ValueError("Invalid integer coefficient")
    if any(
        not 0 <= lo <= hi <= 1_000_000
        for lo, hi in zip(value["minimum"], value["maximum"], strict=True)
    ):
        raise ValueError("Invalid quantity bound")
    if any(
        sum(x * q for x, q in zip(column, value["maximum"], strict=True)) > LIMIT
        for column in [value["benefits"], *value["resources"]]
    ):
        raise ValueError("Unsafe integer scale")
    for name in ("requires", "excludes"):
        if len(value[name]) > 40 or any(
            len(pair) != 2
            or any(type(x) is not int or not 0 <= x < n for x in pair)
            or pair[0] == pair[1]
            for pair in value[name]
        ):
            raise ValueError("Invalid selection rule")
    return value


def bounded_schedule(value: Any) -> dict[str, Any]:
    keys = {"base", "period_costs", "period_capacities", "after"}
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("Invalid schedule input")
    base = bounded_input(value["base"])
    n, periods = len(base["benefits"]), len(value["period_capacities"])
    if not 2 <= periods <= 12 or len(value["period_costs"]) != n:
        raise ValueError("Invalid schedule dimensions")
    for column in (value["period_costs"], value["period_capacities"]):
        if any(type(x) is not int or not 0 <= x <= LIMIT for x in column):
            raise ValueError("Invalid integer coefficient")
    if sum(c * q for c, q in zip(value["period_costs"], base["maximum"], strict=True)) > LIMIT:
        raise ValueError("Unsafe integer scale")
    if len(value["after"]) > 40 or any(
        len(pair) != 2
        or any(type(x) is not int or not 0 <= x < n for x in pair)
        or pair[0] == pair[1]
        for pair in value["after"]
    ):
        raise ValueError("Invalid precedence rule")
    return value


def main() -> None:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (5, 6))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ[name] = "1"
    encoded = sys.stdin.buffer.read(100_001)
    if len(encoded) > 100_000:
        raise ValueError("Oversized solver input")
    loaded = json.loads(encoded)
    schedule = bounded_schedule(loaded) if isinstance(loaded, dict) and "base" in loaded else None
    value = schedule["base"] if schedule else bounded_input(loaded)
    import ortools
    from ortools.sat.python import cp_model

    if ortools.__version__ != "9.15.6755":
        raise ValueError("Unsupported solver version")
    model = cp_model.CpModel()
    quantities = [
        model.new_int_var(lo, hi, f"q{i}")
        for i, (lo, hi) in enumerate(zip(value["minimum"], value["maximum"], strict=True))
    ]
    chosen = [model.new_bool_var(f"c{i}") for i in range(len(quantities))]
    for quantity, selected in zip(quantities, chosen, strict=True):
        model.add(quantity >= 1).only_enforce_if(selected)
        model.add(quantity == 0).only_enforce_if(selected.Not())
    for column, capacity in zip(value["resources"], value["capacities"], strict=True):
        model.add(sum(c * q for c, q in zip(column, quantities, strict=True)) <= capacity)
    for first, required in value["requires"]:
        model.add(chosen[first] <= chosen[required])
    for first, second in value["excludes"]:
        model.add(chosen[first] + chosen[second] <= 1)
    slots: list[list[Any]] = []
    if schedule:
        count = len(schedule["period_capacities"])
        parts: list[list[Any]] = []
        for index, (quantity, selected) in enumerate(zip(quantities, chosen, strict=True)):
            upper = value["maximum"][index]
            slots.append([model.new_bool_var(f"p{index}_{p}") for p in range(count)])
            parts.append([model.new_int_var(0, upper, f"q{index}_{p}") for p in range(count)])
            model.add(sum(slots[index]) == selected)
            for part, slot in zip(parts[index], slots[index], strict=True):
                model.add(part <= upper * slot)
            model.add(sum(parts[index]) == quantity)
        for p, capacity in enumerate(schedule["period_capacities"]):
            model.add(
                sum(c * parts[i][p] for i, c in enumerate(schedule["period_costs"])) <= capacity
            )
        starts = [sum(p * slot for p, slot in enumerate(row)) for row in slots]
        for later, earlier in schedule["after"]:
            model.add(chosen[later] <= chosen[earlier])
            model.add(starts[earlier] + 1 <= starts[later]).only_enforce_if(chosen[later])
    model.maximize(sum(c * q for c, q in zip(value["benefits"], quantities, strict=True)))
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_time_in_seconds = 1.5
    solver.parameters.max_deterministic_time = 0.25
    solver.parameters.log_search_progress = False
    status = solver.solve(model)
    selected = (
        [solver.value(q) for q in quantities]
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        else None
    )
    output: dict[str, Any] = dict(
        status=solver.status_name(status),
        quantities=selected,
        objective=sum(c * q for c, q in zip(value["benefits"], selected, strict=True))
        if selected is not None
        else None,
        termination="solver_completed",
    )
    if schedule:
        output["periods"] = (
            [next((p for p, slot in enumerate(row) if solver.value(slot)), None) for row in slots]
            if selected is not None
            else None
        )
    print(json.dumps(output))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(1)
