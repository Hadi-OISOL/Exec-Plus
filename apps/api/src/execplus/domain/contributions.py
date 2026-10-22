"""Use case: Explains recorded changes through exact segment contributions.

What it does: Validates explicit comparison populations and reconciles exact
amount differences and optional volume/mix/unit-revenue accounting, never causes.
"""

from datetime import date
from fractions import Fraction
from typing import Any
from uuid import UUID, uuid4

from execplus.domain.decision_analysis import fail, number
from execplus.domain.distribution_drift import _fraction
from execplus.domain.models import QueryPlan, WorkspaceScope
from execplus.domain.profiling import TableData
from execplus.domain.semantics import DatasetView, build_where, quote_identifier, validate_read_only
from execplus.domain.studies import method_request, validated_method
from execplus.domain.understanding import governed_request

METHOD = "segment-contribution-v1"
ROOT_CAUSE_METHOD = "dimension-concentration-v1"
MAX_ROWS = 10000
MAX_GROUPS = 128
MAX_DIMENSIONS = 3
LIMITATIONS = [
    "Observed contributions are accounting differences, not proven business causes.",
    "These are selected historical populations, not forecasts or population estimates.",
    "Missing measured values remain explicit; no missing values or prices are imputed.",
    "Percent contribution divides by the signed net change; offsetting effects can exceed 100%.",
    "Exact fractions govern reconciliation; rounded chart labels never replace the exact evidence.",
]


def validate_comparison(raw: dict[str, Any], did: UUID, uid: UUID) -> dict[str, Any]:
    if (
        set(raw)
        - {"kind", "mode", "baseline", "comparison", "additive_rows_confirmed", "decompose"}
        or raw.get("kind") != "contribution"
        or not isinstance(raw.get("mode"), str)
        or raw.get("mode") not in {"period", "dataset"}
        or raw.get("additive_rows_confirmed") is not True
        or type(raw.get("decompose", False)) is not bool
    ):
        fail(
            "contribution_method", "Choose a comparison and confirm additive, non-overlapping rows."
        )
    sides = {}
    for label in ("baseline", "comparison"):
        side = raw.get(label)
        fields = {
            "column",
            "segment",
            "quantity_column",
            "filters",
            "date_column",
            "start",
            "end",
            "dimensions",
        }
        if label == "comparison":
            fields |= {"dataset_id", "upload_id", "revision_id", "understanding_id"}
        if not isinstance(side, dict) or set(side) - fields:
            fail("contribution_method", "Choose explicit fields and sources for both sides.")
        value = dict(side)
        for key in ("column", "segment"):
            if not isinstance(value.get(key), str) or not 1 <= len(value[key]) <= 200:
                fail(
                    "contribution_columns",
                    "Choose a measure and a different category on each side.",
                )
        if value["column"] == value["segment"]:
            fail("contribution_columns", "The measure and category must be different fields.")
        if raw.get("decompose"):
            q = value.get("quantity_column")
            if (
                not isinstance(q, str)
                or not q
                or len(q) > 200
                or q in {value["column"], value["segment"]}
            ):
                fail(
                    "contribution_quantity",
                    "Choose a separate quantity measure for the decomposition.",
                )
        elif value.get("quantity_column"):
            fail(
                "contribution_quantity",
                "Enable volume/mix/unit-revenue accounting to select quantity.",
            )
        if "dimensions" in value:
            dims = value["dimensions"]
            if (
                not isinstance(dims, list)
                or not 1 <= len(dims) <= MAX_DIMENSIONS
                or any(not isinstance(d, str) or not 1 <= len(d) <= 200 for d in dims)
                or len(set(dims)) != len(dims)
                or set(dims) & {value["column"], value["segment"], value.get("quantity_column")}
            ):
                fail(
                    "contribution_dimensions",
                    "Choose one to three other distinct category fields to rank.",
                )
        value["filters"] = value.get("filters", [])
        if raw["mode"] == "period":
            try:
                start, end = date.fromisoformat(value["start"]), date.fromisoformat(value["end"])
                valid = (
                    start <= end
                    and start.isoformat() == value["start"]
                    and end.isoformat() == value["end"]
                )
            except (ValueError, TypeError, KeyError):
                valid = False
            if (
                not valid
                or not isinstance(value.get("date_column"), str)
                or not value["date_column"]
            ):
                fail(
                    "contribution_period",
                    "Choose a date field and valid inclusive ISO date ranges.",
                )
        elif any(value.get(key) for key in ("date_column", "start", "end")):
            fail("contribution_period", "Choose period comparison to use date windows.")
        if label == "comparison":
            try:
                for key in ("dataset_id", "upload_id", "revision_id", "understanding_id"):
                    value[key] = str(UUID(value[key]))
            except (ValueError, TypeError, KeyError, AttributeError):
                fail("contribution_source", "Choose a current confirmed comparison snapshot.")
        sides[label] = value
    left, right = sides["baseline"], sides["comparison"]
    if len(left.get("dimensions", [])) != len(right.get("dimensions", [])):
        fail("contribution_dimensions", "Map the same number of ranked fields on both sides.")
    if raw["mode"] == "period":
        if right["dataset_id"] != str(did) or right["upload_id"] != str(uid):
            fail(
                "contribution_period",
                "Period comparisons use two windows of the same selected snapshot.",
            )
        if left["end"] >= right["start"]:
            fail(
                "contribution_overlap",
                "The comparison window must start after the baseline window ends.",
            )
        if any(
            left.get(key) != right.get(key)
            for key in (
                "column",
                "segment",
                "quantity_column",
                "date_column",
                "filters",
                "dimensions",
            )
        ):
            fail(
                "contribution_population",
                "Period comparisons require the same fields and declared filters.",
            )
    return dict(
        kind="contribution",
        mode=raw["mode"],
        **sides,
        additive_rows_confirmed=True,
        decompose=raw.get("decompose", False),
    )


def projection(
    scope: WorkspaceScope,
    did: UUID,
    table: TableData,
    view: DatasetView,
    side: dict[str, Any],
    decompose: bool,
) -> tuple[QueryPlan, dict[str, Any]]:
    definition = view.definition or {}
    if definition.get("grain") not in {"record", "order", "order_item", "other"}:
        fail(
            "contribution_grain",
            "Confirm additive transaction rows; unknown grains and stock snapshots need review.",
        )
    fields = [side["segment"], side["column"]]
    if decompose:
        fields.append(side["quantity_column"])
    for name in side.get("dimensions", []):
        if name not in view.dimensions:
            fail("contribution_dimensions", "Ranked fields must be existing category fields.")
    declared = side.get("filters", [])
    if not isinstance(declared, list):
        fail("contribution_filters", "Use a list of declared filters.")
    filters = list(declared)
    if side.get("date_column"):
        name = side["date_column"]
        if name not in {c.name for c in view.columns if c.type == "date"}:
            fail(
                "contribution_date", "Choose a confirmed date column, not row order or a category."
            )
        filters += [
            dict(column=name, operator="gte", value=side["start"]),
            dict(column=name, operator="lte", value=side["end"]),
        ]
    population = None
    units: dict[str, Any] = {}
    for index, column in enumerate(fields[1:]):
        method = validated_method(
            dict(
                kind="metric",
                column=column,
                aggregation="sum",
                group_by=[side["segment"]],
                filters=filters,
            ),
            view,
        )
        request = governed_request(view, table, method_request(method))
        current = tuple(dict.fromkeys(request.filters))
        if population is not None and set(current) != set(population):
            fail(
                "contribution_population",
                "Revenue and quantity must use identical required filters.",
            )
        if len(current) > 20:
            fail("contribution_filters", "Use at most twenty effective filters per population.")
        population = current
        meaning = next(c for c in definition["columns"] if c["name"] == column)
        if meaning["unit_column"] or not (meaning["unit"] or meaning["currency"]):
            fail(
                "contribution_unit",
                "Confirm a single fixed unit for each measure; no conversion is inferred.",
            )
        if decompose and (not meaning["currency"] if index == 0 else bool(meaning["currency"])):
            fail(
                "contribution_unit",
                "The decomposition requires currency revenue and non-currency quantities.",
            )
        units["amount" if index == 0 else "quantity"] = meaning["currency"] or meaning["unit"]
        units["amount_currency" if index == 0 else "quantity_currency"] = bool(meaning["currency"])
    clauses, parameters = build_where(view, population or ())
    columns = ", ".join(quote_identifier(name) for name in fields + side.get("dimensions", []))
    sql = f'SELECT {columns} FROM "dataset"'
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += f" ORDER BY {columns} LIMIT {MAX_ROWS + 1}"
    validate_read_only(sql)
    return QueryPlan(
        uuid4(), scope.workspace_id, did, "Observed contribution evidence", sql, tuple(parameters)
    ), units


def _groups(rows: tuple[tuple[Any, ...], ...], decompose: bool) -> dict[str | None, dict[str, Any]]:
    if len(rows) > MAX_ROWS:
        fail(
            "contribution_rows",
            "Use at most 10,000 matching records per side; no sample is substituted.",
        )
    groups: dict[str | None, dict[str, Any]] = {}
    for row in rows:
        if len(row) != (3 if decompose else 2):
            fail("contribution_evidence", "The selected evidence columns do not match the method.")
        key = None if row[0] is None else str(row[0])
        value = groups.setdefault(
            key, dict(rows=0, present=0, missing=0, amount=Fraction(0), quantity=Fraction(0))
        )
        value["rows"] += 1
        if row[1] is None:
            value["missing"] += 1
        else:
            value["present"] += 1
            value["amount"] += Fraction(number(row[1]))
        if decompose:
            if row[1] is None or row[2] is None or number(row[2]) <= 0:
                fail(
                    "contribution_quantity",
                    "Decomposition needs complete revenue/quantity pairs "
                    "and positive quantities on every row.",
                )
            value["quantity"] += Fraction(number(row[2]))
    if len(groups) > MAX_GROUPS:
        fail(
            "contribution_groups",
            "Use at most 128 categories; filter explicitly to reduce the comparison.",
        )
    return groups


def _covered(group: dict[str, Any] | None) -> dict[str, Any]:
    if group is None:
        return dict(present=False, rows=0, measured=0, missing=0, total=_fraction(Fraction(0)))
    return dict(
        present=True,
        rows=group["rows"],
        measured=group["present"],
        missing=group["missing"],
        total=_fraction(group["amount"]) if group["present"] else None,
    )


def _member_deltas(
    baseline: tuple[tuple[Any, ...], ...], comparison: tuple[tuple[Any, ...], ...], index: int
) -> dict[str | None, Fraction]:
    deltas: dict[str | None, Fraction] = {}
    for sign, rows in ((-1, baseline), (1, comparison)):
        for row in rows:
            key = None if row[index] is None else str(row[index])
            deltas[key] = deltas.get(key, Fraction(0)) + sign * Fraction(number(row[1]))
    return deltas


def _ordered(deltas: dict[str | None, Fraction]) -> list[tuple[str | None, Fraction]]:
    return sorted(deltas.items(), key=lambda m: (-abs(m[1]), m[0] is not None, m[0] or ""))


def _concentration(field: str, deltas: dict[str | None, Fraction], net: Fraction) -> dict[str, Any]:
    gross = sum((abs(d) for d in deltas.values()), Fraction(0))
    entry: dict[str, Any] = dict(field=field, members=len(deltas))
    if len(deltas) > MAX_GROUPS:
        return entry | dict(state="too_many_groups")
    if gross == 0:
        return entry | dict(state="no_movement")
    member, delta = _ordered(deltas)[0]
    return entry | dict(
        state="ranked",
        top_member=member,
        top_delta=_fraction(delta),
        concentration=_fraction(abs(delta) / gross),
        top_share_of_net=_fraction(delta / net) if net else None,
        gross_movement=_fraction(gross),
    )


def _root_cause(
    baseline: tuple[tuple[Any, ...], ...],
    comparison: tuple[tuple[Any, ...], ...],
    fields: tuple[str, ...],
    width: int,
) -> dict[str, Any]:
    result: dict[str, Any] = dict(
        method=ROOT_CAUSE_METHOD,
        limitation=(
            "Concentration ranks where the exact recorded change is located. "
            "It is accounting attribution, not a proven business cause."
        ),
    )
    if any(row[1] is None for rows in (baseline, comparison) for row in rows):
        return result | dict(state="undefined_missing_values", fields=[], drilldown=None)
    indexes = [0] + [width + offset for offset in range(len(fields) - 1)]
    net = sum((Fraction(number(r[1])) for r in comparison), Fraction(0)) - sum(
        (Fraction(number(r[1])) for r in baseline), Fraction(0)
    )
    entries = [
        _concentration(field, _member_deltas(baseline, comparison, index), net)
        for field, index in zip(fields, indexes, strict=True)
    ]
    ranked = sorted(
        (i for i, e in enumerate(entries) if e["state"] == "ranked"),
        key=lambda i: (-exact(entries[i]["concentration"]), i),
    )
    drilldown = None
    if ranked and len(fields) > 1:
        top = ranked[0]
        member = entries[top]["top_member"]
        index = indexes[top]

        def inside(rows: tuple[tuple[Any, ...], ...]) -> tuple[tuple[Any, ...], ...]:
            return tuple(r for r in rows if (None if r[index] is None else str(r[index])) == member)

        subset = inside(baseline), inside(comparison)
        candidates = []
        for i, (field, other) in enumerate(zip(fields, indexes, strict=True)):
            if i == top:
                continue
            deltas = _member_deltas(*subset, other)
            entry = _concentration(field, deltas, exact(entries[top]["top_delta"]))
            if entry["state"] == "ranked":
                candidates.append((-exact(entry["concentration"]), i, deltas, entry))
        if candidates:
            _, _, deltas, entry = min(candidates, key=lambda c: (c[0], c[1]))
            drilldown = dict(
                within_field=fields[top],
                within_member=member,
                field=entry["field"],
                concentration=entry["concentration"],
                rows=[dict(member=k, delta=_fraction(d)) for k, d in _ordered(deltas)],
                reconciled=sum(deltas.values(), Fraction(0)) == exact(entries[top]["top_delta"]),
            )
    return result | dict(
        state="available" if ranked else "no_change",
        fields=[entries[i] for i in ranked] + [e for i, e in enumerate(entries) if i not in ranked],
        drilldown=drilldown,
    )


def exact(value: dict[str, Any]) -> Fraction:
    return Fraction(int(value["numerator"]), int(value["denominator"]))


def calculate_contributions(
    baseline: tuple[tuple[Any, ...], ...],
    comparison: tuple[tuple[Any, ...], ...],
    decompose: bool,
    fields: tuple[str, ...] = (),
) -> dict[str, Any]:
    width = 3 if decompose else 2
    full = baseline, comparison
    if fields:
        if not 2 <= len(fields) <= MAX_DIMENSIONS + 1 or any(
            len(row) != width + len(fields) - 1 for rows in full for row in rows
        ):
            fail("contribution_evidence", "The ranked fields do not match the method evidence.")
        baseline = tuple(row[:width] for row in baseline)
        comparison = tuple(row[:width] for row in comparison)
    left, right = _groups(baseline, decompose), _groups(comparison, decompose)
    keys = set(left) | set(right)
    if len(keys) > MAX_GROUPS:
        fail("contribution_groups", "Use at most 128 categories across the two populations.")
    rows: list[dict[str, Any]] = []
    totals: list[Fraction | None] = []
    for groups in (left, right):
        totals.append(
            None
            if any(not g["present"] for g in groups.values())
            else sum((g["amount"] for g in groups.values()), Fraction(0))
        )
    net = totals[1] - totals[0] if totals[1] is not None and totals[0] is not None else None
    for key in sorted(keys, key=lambda v: (v is not None, v or "")):
        before, after = left.get(key), right.get(key)
        known = all(g is None or g["present"] for g in (before, after))
        delta = (
            (after["amount"] if after else Fraction(0))
            - (before["amount"] if before else Fraction(0))
            if known
            else None
        )
        rows.append(
            dict(
                segment=key,
                baseline=_covered(before),
                comparison=_covered(after),
                delta=_fraction(delta) if delta is not None else None,
                percent_of_net=_fraction(delta / net * 100) if delta is not None and net else None,
                status="undefined"
                if not known
                else "entered"
                if before is None
                else "exited"
                if after is None
                else "matched",
            )
        )
    rows.sort(
        key=lambda r: (
            r["delta"] is None,
            -abs(Fraction(int(r["delta"]["numerator"]), int(r["delta"]["denominator"])))
            if r["delta"]
            else Fraction(0),
            r["segment"] is not None,
            r["segment"] or "",
        )
    )
    component_sum = (
        sum(
            (
                Fraction(int(r["delta"]["numerator"]), int(r["delta"]["denominator"]))
                for r in rows
                if r["delta"]
            ),
            Fraction(0),
        )
        if all(r["delta"] is not None for r in rows)
        else None
    )
    result: dict[str, Any] = dict(
        method=METHOD,
        baseline_total=_fraction(totals[0]) if totals[0] is not None else None,
        comparison_total=_fraction(totals[1]) if totals[1] is not None else None,
        net_change=_fraction(net) if net is not None else None,
        component_sum=_fraction(component_sum) if component_sum is not None else None,
        reconciled=net is not None and component_sum == net,
        rows=rows,
        baseline_rows=len(baseline),
        comparison_rows=len(comparison),
        excluded_missing=sum(g["missing"] for group in (left, right) for g in group.values()),
        pvm=None,
    )
    if decompose:
        matched = sorted(set(left) & set(right), key=lambda v: (v is not None, v or ""))
        q0 = sum((left[k]["quantity"] for k in matched), Fraction(0))
        q1 = sum((right[k]["quantity"] for k in matched), Fraction(0))
        components: list[dict[str, Any]] = []
        for key in matched:
            a, b = left[key], right[key]
            p0, p1 = a["amount"] / a["quantity"], b["amount"] / b["quantity"]
            volume = (q1 - q0) * a["quantity"] / q0 * p0
            mix = q1 * (b["quantity"] / q1 - a["quantity"] / q0) * p0
            price = b["quantity"] * (p1 - p0)
            components.append(
                dict(
                    segment=key,
                    volume=_fraction(volume),
                    mix=_fraction(mix),
                    unit_revenue=_fraction(price),
                )
            )
        values = {
            name: sum(
                (
                    Fraction(int(r[name]["numerator"]), int(r[name]["denominator"]))
                    for r in components
                ),
                Fraction(0),
            )
            for name in ("volume", "mix", "unit_revenue")
        }
        values["entries"] = sum((right[k]["amount"] for k in set(right) - set(left)), Fraction(0))
        values["exits"] = -sum((left[k]["amount"] for k in set(left) - set(right)), Fraction(0))
        result["pvm"] = dict(
            state="available" if matched else "no_matched_products",
            order="volume → mix → unit revenue",
            components=components,
            totals={key: _fraction(value) for key, value in values.items()},
            reconciled=sum(values.values(), Fraction(0)) == net,
            limitation=(
                "Observed revenue per unit is not a catalog price or a causal price effect. "
                "The chosen order allocates interaction terms; "
                "entries and exits use only observed revenue."
            ),
        )
    if fields:
        result["root_cause"] = _root_cause(*full, fields, width)
    return result
