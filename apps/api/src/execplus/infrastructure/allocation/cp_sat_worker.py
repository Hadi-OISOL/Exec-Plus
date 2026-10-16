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
        not 0 <= lo <= hi <= 100 for lo, hi in zip(value["minimum"], value["maximum"], strict=True)
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
    value = bounded_input(json.loads(encoded))
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
    print(
        json.dumps(
            dict(
                status=solver.status_name(status),
                quantities=selected,
                objective=sum(c * q for c, q in zip(value["benefits"], selected, strict=True))
                if selected is not None
                else None,
                termination="solver_completed",
            )
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(1)
