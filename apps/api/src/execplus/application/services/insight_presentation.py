"""Readable, versioned highlights derived only from authorized calculation receipts.

Historical v1 wording stays in its original builder. Display rounding never changes receipts.
"""

from collections.abc import Mapping
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from typing import Any

from execplus.application.conversation import EvidenceAnswer, NumericalAnswer, answer_lineage
from execplus.application.services.intent_router import PatternAnswer
from execplus.application.services.response_synthesis import build_fact_packet
from execplus.domain.models import VerifiedMetricAnswer
from execplus.domain.response_synthesis import (
    INSIGHT_VERSION,
    RANKED_VERSION,
    FactPacket,
    FactStatement,
)

UNIT_LABEL_FIELDS = frozenset({"currency", "currency_code", "unit", "units", "uom"})


def display_number(value: object, *, half_up: bool = False) -> str:
    """Round display to two places without binary float conversion or losing tiny nonzero values."""
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("Nonfinite display value")
    if number == number.to_integral_value():
        return format(number, ",.0f")
    if abs(number) < Decimal("0.01"):
        return format(number.normalize(), "f")
    with localcontext() as ctx:
        ctx.prec = max(40, len(number.as_tuple().digits) + abs(number.adjusted()) + 4)
        rounding = ROUND_HALF_UP if half_up else ROUND_HALF_EVEN
        return format(number.quantize(Decimal("0.01"), rounding), ",f").rstrip("0").rstrip(".")


def field_label(name: str) -> str:
    return name.replace("_", " ")


def build_insight_packet(
    answer: object,
    *,
    units: Mapping[str, str] | None = None,
    version: str = INSIGHT_VERSION,
    mixed_units: frozenset[str] = frozenset(),
) -> FactPacket | None:
    """v3 ranks single-field results without a confirmed unit unless rows may mix units."""
    legacy = build_fact_packet(answer, units=units)
    if legacy is None:
        return None
    facts: list[FactStatement] = []
    ranked = version == RANKED_VERSION

    def display(value: object) -> str:
        return display_number(value, half_up=ranked)

    def add(text: str, ref: str, kind: str = "observation") -> None:
        facts.append(FactStatement("pending", (text,), (ref,), kind))

    def numerical(data: NumericalAnswer) -> None:
        line = answer_lineage(data)
        ref = str(line.query_id)
        unit = (units or {}).get(ref, "")
        suffix = "" if unit in {"", "unitless"} or line.aggregation == "count" else f" {unit}"
        metric = field_label(line.metric)
        if isinstance(data, VerifiedMetricAnswer):
            value = display(data.value)
            if line.aggregation == "count":
                noun = "matching records" if line.metric == "*" else f"nonmissing {metric} values"
                add(f"There are {value} {noun}.", ref)
            else:
                operation = {
                    "sum": "total",
                    "avg": "average",
                    "min": "lowest",
                    "max": "highest",
                }.get(line.aggregation, line.aggregation)
                add(f"The {operation} {metric} is {value}{suffix}.", ref)
        else:
            result = data[0]
            unlabeled = not (unit or line.aggregation == "count")
            comparable = (
                ranked
                and ref not in mixed_units
                and not {name.casefold() for name in line.grouping} & UNIT_LABEL_FIELDS
            )
            if (
                line.aggregation != "rows"
                and "__value" in result.columns
                and unlabeled
                and not comparable
            ):
                add(
                    "The grouped results are available in the chart and table. "
                    "A common confirmed unit is needed before ranking their values.",
                    ref,
                    "limitation",
                )
            elif line.aggregation != "rows" and "__value" in result.columns:
                index = result.columns.index("__value")
                valid = [row for row in result.rows if row[index] is not None]
                ordered = sorted(valid, key=lambda row: Decimal(str(row[index])), reverse=True)

                def label(row: tuple[Any, ...]) -> str:
                    return ", ".join(
                        f"{field_label(name)}: {'missing' if value is None else value}"
                        for name, value in zip(result.columns, row, strict=True)
                        if name != "__value"
                    )

                def measure(row: tuple[Any, ...]) -> str:
                    return display(row[index]) + (
                        " records" if line.aggregation == "count" and line.metric == "*" else suffix
                    )

                if ordered:
                    high, low = Decimal(str(ordered[0][index])), Decimal(str(ordered[-1][index]))
                    leaders = [row for row in ordered if Decimal(str(row[index])) == high]
                    names = "; ".join(label(row) for row in leaders[:3])
                    if len(leaders) > 3:
                        names += f"; and {len(leaders) - 3} other groups"
                    op = {
                        "sum": "total",
                        "avg": "average",
                        "count": "count",
                        "min": "minimum",
                        "max": "maximum",
                    }.get(line.aggregation, line.aggregation)
                    add(
                        f"Among the returned groups, {names} "
                        f"{'share' if len(leaders) > 1 else 'has'} the highest {op}: "
                        f"{measure(ordered[0])}.",
                        ref,
                    )
                    if low != high:
                        add(
                            f"At the other end, {label(ordered[-1])} has {measure(ordered[-1])}.",
                            ref,
                        )
                    add(
                        f"The chart and table include all {len(result.rows)} returned groups. "
                        "Missing values are not ranked.",
                        ref,
                        "scope",
                    )
                    if unlabeled:
                        add(
                            f"No unit is confirmed for {metric}; groups are compared as "
                            "recorded in that one field.",
                            ref,
                            "limitation",
                        )
                else:
                    add("No nonmissing group values are available to rank.", ref, "limitation")
            else:
                add(
                    f"I found {len(result.rows)} returned records. "
                    "Open the table to inspect their fields.",
                    ref,
                )
                if result.matched_records is not None:
                    add(
                        f"{result.matched_records} records match the request; "
                        f"{len(result.rows)} are shown.",
                        ref,
                        "scope",
                    )
        for statement in legacy.statements:
            if (
                ref in statement.evidence_ids
                and statement.kind in {"scope", "limitation"}
                and "first three rows" not in statement.variants[0]
            ):
                facts.append(statement)
        if line.aggregation != "count":
            add(
                "Display values are rounded where useful; "
                "the evidence and downloads retain the exact values.",
                ref,
                "limitation",
            )

    try:
        if isinstance(answer, PatternAnswer):
            result = answer.evidence["result"]
            ref = str(answer.evidence["query_id"])
            target = result["target"]["value"]
            coverage = result["coverage"]
            add(
                f"{coverage['target_rows']} records are labelled {target}, "
                f"compared with {coverage['other_rows']} at other recorded stages or labels.",
                ref,
            )
            for item in result["numeric"][:3]:
                if item["status"] != "compared":
                    continue
                unit = "" if item["unit"] == "unitless" else " " + item["unit"]
                add(
                    f"{field_label(item['column'])} averages "
                    f"{display(item['target_mean'])}{unit} in {target} records, "
                    f"versus {display(item['other_mean'])}{unit} in the others.",
                    ref,
                )
            facts.extend(s for s in legacy.statements if s.kind in {"scope", "limitation"})
            add(
                "These are rounded comparisons, not a recipe for changing the outcome. "
                "Compare similar cases before making a decision.",
                ref,
                "limitation",
            )
        elif isinstance(answer, EvidenceAnswer):
            for data in (
                (answer.data,) if answer.data is not None else ()
            ) + answer.additional_data:
                numerical(data)
            numeric_refs = {
                str(answer_lineage(data).query_id)
                for data in ((answer.data,) if answer.data is not None else ())
                + answer.additional_data
            }
            facts.extend(s for s in legacy.statements if not set(s.evidence_ids) & numeric_refs)
        elif isinstance(answer, VerifiedMetricAnswer | tuple):
            numerical(answer)
        else:
            return None
        # IDs describe the immutable v2 bank, never reuse v1 IDs to validate new text.
        return FactPacket(
            tuple(
                FactStatement(f"F{i + 1}", s.variants, s.evidence_ids, s.kind)
                for i, s in enumerate(facts)
            ),
            version,
        )
    except (ValueError, TypeError, KeyError, InvalidOperation):
        return None
