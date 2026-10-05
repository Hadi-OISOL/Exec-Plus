"""Use case: Explains authorized dataset metadata without inventing business meaning.

What it does: Matches column questions and renders observed, saved and tentative interpretations.
"""

import re
from dataclasses import dataclass
from typing import Any

from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.semantics import DatasetView

_COMMON_MEANINGS = {
    "revenue": "Revenue generally means income earned from sales before expenses.",
    "sales": "Sales can refer to sold quantities or sales value; the unit distinguishes them.",
    "cost": "Cost generally means an expense or the amount spent to obtain something.",
    "quantity": "Quantity generally means a count or amount of items in a specified unit.",
    "stock": "Stock generally refers to inventory held at a particular time or location.",
    "price": "Price generally means an amount charged per item or unit.",
    "salary": "Salary generally means employee pay for a specified pay period.",
    "amount": "Amount is a generic measure; its meaning depends on the unit and business event.",
}


@dataclass(frozen=True)
class DescriptionContext:
    name: str
    profile: dict[str, Any]
    view: DatasetView
    definition: dict[str, Any] | None
    state: str


def words(text: str) -> str:
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    return " ".join(re.findall(r"[^\W_]+", separated.casefold()))


def mentioned_columns(question: str, view: DatasetView) -> tuple[str, ...]:
    normalized = " " + words(question) + " "
    matches = []
    for column in view.columns:
        label = words(column.name)
        if not label:
            continue
        for match in re.finditer(r"(?= " + re.escape(label) + r" )", normalized):
            matches.append((match.start(), match.start() + len(label), column.name))
    return tuple(
        dict.fromkeys(
            name
            for start, end, name in matches
            if not any(a <= start and end <= b and (a, b) != (start, end) for a, b, _ in matches)
        )
    )


GUIDANCE_FOCUSES = frozenset({"orientation", "quality", "structure", "next_steps"})


def guidance_focus(question: str) -> str:
    normalized = words(question)
    if normalized in {"what should i ask", "what can i ask", "where should i start"}:
        return "next_steps"
    if re.search(r"\b(missing|duplicates?|quality|errors?|clean|cleaning|issues?)\b", normalized):
        return "quality"
    if re.search(r"\b(structure|layout|shape|identifier|identifiers)\b", normalized):
        return "structure"
    if re.search(r"\b(next|suggest|suggestions|start|explore|recommend|questions)\b", normalized):
        return "next_steps"
    return "orientation"


def guidance_selection(
    question: str, view: DatasetView, previous_columns: tuple[str, ...] = ()
) -> tuple[str, ...] | None:
    normalized = words(question)
    named = mentioned_columns(question, view)
    if normalized in {
        "",
        "what",
        "what do you mean",
        "what does it mean",
        "what does that mean",
        "explain that",
        "explain again",
        "i don t understand",
        "i dont understand",
        "i do not understand",
        "can you explain again",
        "tell me more",
        "make it simpler",
        "explain simply",
    }:
        return previous_columns
    if previous_columns and normalized in {
        "and the value column",
        "what about the value column",
        "and its value",
        "what about its value",
    }:
        related = tuple(
            name + "_value" for name in previous_columns if view.column(name + "_value")
        )
        return related or previous_columns
    if re.search(r"\b(document|documents|policy|passage|contract|according)\b", normalized):
        return None
    if normalized in {
        "thanks",
        "thank you",
        "thank you so much",
        "ok thanks",
        "okay thanks",
        "shukriya",
        "what should i ask",
        "what can i ask",
        "where should i start",
        "what should i do next",
        "suggest questions",
        "suggest some questions",
        "show me the data quality",
        "check data quality",
        "check my data",
        "analyze my data",
        "analyse my data",
        "analyze this dataset",
        "analyse this dataset",
        "what do you notice",
        "what can you tell me about this data",
        "help me explore",
        "show me insights",
        "what is the structure of my data",
        "what issues are in my data",
        "are there any data quality issues",
    }:
        return ()
    meaning = bool(
        re.search(r"\b(means|meaning|definition|represents?|stands? for)\b", normalized)
        or re.search(r"\bdoes\b.*\bmean\b", normalized)
    )
    explain = bool(re.search(r"\b(explain|describe|understand|understanding)\b", normalized))
    analytical = bool(
        re.search(
            r"\b(why|caused|causes|correlation|forecast|predict|calculate|compute)\b", normalized
        )
    )
    if (meaning or explain) and not analytical:
        if named:
            if len(named) > 3:
                raise ClarificationRequiredError("Choose up to three columns to explain together.")
            return named
        if re.search(r"\b(data|dataset|file|spreadsheet|columns|help)\b", normalized):
            return ()
        if meaning:
            raise ClarificationRequiredError(
                "Which column do you mean? Use its name from the selected file so I can explain it."
            )
    if named and normalized in {"what is " + words(name) for name in named}:
        return named
    if normalized in {
        "hi",
        "hello",
        "hey",
        "help",
        "hi how can you help",
        "how can you help",
        "what can you do",
    }:
        return ()
    return None


def _column_explanation(context: DescriptionContext, name: str, simplify: bool = False) -> str:
    column = next(item for item in context.profile["columns"] if item["name"] == name)
    saved = next(
        (item for item in (context.definition or {}).get("columns", []) if item["name"] == name),
        None,
    )
    paragraphs = []
    if saved and saved.get("meaning"):
        status = (
            "Confirmed workspace definition"
            if context.state == "confirmed"
            else "Unconfirmed draft definition"
        )
        paragraphs.append(f"{name} — {status}: “{saved['meaning']}”.")
    else:
        paragraphs.append(f"{name} has no confirmed business definition yet.")
    if simplify:
        if saved and saved.get("meaning"):
            return "In plain words: " + paragraphs[0]
        pair = name + "_value" if context.view.column(name + "_value") else ""
        return (
            f"In plain words: {name} is a column in your file, but its exact business "
            "meaning has not been recorded. "
            + (
                f"Its pairing with {pair} suggests a quantity and value, but does not prove it. "
                if pair
                else ""
            )
            + "I should not call it stock or sales without confirmation.\n\n"
            f"What does {name} measure in your export? Record that under Data understanding "
            "so we can use a reviewed meaning."
        )
    kind = {
        "integer": "whole numbers",
        "decimal": "decimal numbers",
        "date": "dates",
        "boolean": "true/false values",
        "text": "text",
        "empty": "empty cells",
    }.get(column["type"], column["type"])
    paragraphs.append(f"What the file shows: the profile classifies this column as {kind}.")
    paragraphs.append(
        f"Profile observations: {column['distinct_count']} distinct present values and "
        f"{column['missing']} missing cells in this snapshot."
    )
    date_note = _date_note(context, column)
    if date_note:
        paragraphs.append(date_note)
    if column.get("type_conflicts") or column.get("invalid_dates"):
        paragraphs.append(
            "Some cells conflict with that inferred type; review Data preparation "
            "before calculating with it."
        )
    if saved and context.state == "confirmed":
        details = [
            f"{label}: {saved[key]}"
            for key, label in (
                ("unit", "Unit"),
                ("currency", "Currency"),
                ("date_meaning", "Date meaning"),
            )
            if saved.get(key)
        ]
        if details:
            paragraphs.append("Saved details: " + "; ".join(details) + ".")
    pair = (
        name + "_value"
        if context.view.column(name + "_value")
        else name[:-6]
        if name.endswith("_value") and context.view.column(name[:-6])
        else ""
    )
    tokens = words(name).split()
    if not (saved and saved.get("meaning")):
        if "erp" in tokens:
            group = " ".join(tokens[: tokens.index("erp")])
            paragraphs.append(
                "Tentative interpretation from the name: "
                + (
                    f"this is an ERP-related field labelled “{group.title()}”. "
                    if group
                    else "this is an ERP-related field. "
                )
                + "ERP commonly means Enterprise Resource Planning, a system for business records. "
                "The name alone does not tell us whether this field measures stock, "
                "sales, or another activity."
            )
        if pair:
            paragraphs.append(
                f"Related column: {pair}. The pair may separate a quantity "
                "from its associated value. "
                "That is a naming-based hypothesis, not a verified formula, unit or currency."
            )
        if not pair and "erp" not in tokens:
            common = next(
                (_COMMON_MEANINGS[token] for token in tokens if token in _COMMON_MEANINGS), ""
            )
            paragraphs.append(
                (
                    f"General terminology, not a confirmed file definition: {common} "
                    if common
                    else f"The label reads “{words(name)}”. "
                )
                + "The file still needs a business definition, unit and calculation rule."
            )
        paragraphs.append(
            f"Does {name} represent stock quantity, sales quantity, or something else?"
            if "erp" in tokens and not name.endswith("_value")
            else f"What does {name} measure or describe, and what unit should it use?"
        )
    else:
        paragraphs.append(
            "I am quoting the saved definition, not inferring a new one or calculating a value."
        )
    if context.state != "confirmed" or not (saved and saved.get("meaning")):
        paragraphs.append(
            "Record the meaning under Data understanding so future analysis "
            "can use a reviewed definition."
        )
    return "\n\n".join(paragraphs)


def explain_dataset(
    context: DescriptionContext,
    columns: tuple[str, ...],
    simplify: bool = False,
    focus: str = "orientation",
) -> tuple[str, tuple[str, ...]]:
    if focus not in GUIDANCE_FOCUSES:
        raise ClarificationRequiredError(
            "Choose dataset orientation, quality, structure or next steps."
        )
    if columns:
        if len(columns) > 3 or any(context.view.column(name) is None for name in columns):
            raise ClarificationRequiredError("Choose existing columns from the selected file.")
        if focus == "quality":
            selected = [entry for entry in context.profile["columns"] if entry["name"] in columns]
            message = "\n\n".join(
                f"{entry['name']}: {entry['missing']} missing cells, "
                f"{entry['type_conflicts']} numeric/boolean type conflicts and "
                f"{entry['invalid_dates']} invalid dates. "
                f"The profile found {entry['distinct_count']} distinct present values."
                for entry in selected
            )
            notes = [note for entry in selected if (note := _date_note(context, entry))]
            return (
                "\n\n".join([message, *notes])
                + "\n\nThese are observed profile checks, not proof of business accuracy. "
                "No source values have been changed.",
                ("Check data quality", "Show the first 10 records"),
            )
        message = "\n\n".join(_column_explanation(context, name, simplify) for name in columns)
        related = tuple(name + "_value" for name in columns if context.view.column(name + "_value"))
        suggestions = (
            *(f"What does {name} mean?" for name in related),
            "Help me understand this dataset",
        )
        return message, suggestions[:3]
    if focus == "quality":
        return _quality_explanation(context), suggested_exploration(context)
    if focus == "next_steps":
        return _next_steps(context), suggested_exploration(context)
    profile, view = context.profile, context.view
    paragraphs = [
        f"Let's look at your selected file: {context.name}.",
        f"It contains {profile['row_count']} rows and {profile['column_count']} columns.",
    ]
    identifiers = [
        column.name
        for column in view.columns
        if "identifier" in column.tags
        or set(words(column.name).split()) & {"id", "code", "sku", "postal", "zip"}
    ]
    dimensions = [
        column.name
        for column in view.columns
        if column.name in view.dimensions and column.name not in identifiers
    ]
    metrics = [
        column.name
        for column in view.columns
        if column.name in view.metrics and column.name not in identifiers
    ]
    if identifiers:
        paragraphs.append(
            "Possible record identifiers: "
            + ", ".join(identifiers[:3])
            + ". Their names suggest identifiers; uniqueness and what one row "
            "represents still need review."
        )
    if dimensions:
        paragraphs.append(
            "Columns that can describe or group records: " + ", ".join(dimensions[:3]) + "."
        )
    pairs = [name for name in metrics if view.column(name + "_value")]
    if pairs:
        paragraphs.append(
            f"Repeated measure/value pairs, such as {pairs[0]} and {pairs[0]}_value, "
            "suggest measures arranged across columns by location or business unit. "
            "This is inferred from the names; quantities, units and currencies "
            "are not established by the layout."
        )
    elif metrics:
        paragraphs.append(
            "Numeric fields available to explore: "
            + ", ".join(metrics[:3])
            + ". We should confirm what each measures before interpreting a total."
        )
    if context.state == "confirmed" and context.definition:
        paragraphs.append(
            f"Saved row meaning: {context.definition['grain']}; "
            f"saved domain: {context.definition['domain']}."
        )
    else:
        paragraphs.append(
            "I can describe the file and inspect its structure now. Its business meaning is "
            "inferred; a label alone does not establish what an amount or quantity represents."
        )
    if not any(column.type == "date" for column in view.columns):
        paragraphs.append(
            "No column is currently classified as a date, "
            "so time-based analysis is not established. Timestamp text or separate "
            "day/month fields may need date preparation first."
        )
    paragraphs.append(_quality_explanation(context, compact=True))
    if focus == "structure":
        constants = [entry["name"] for entry in profile["columns"] if entry["distinct_count"] == 1]
        if constants:
            paragraphs.append(
                "Columns with one distinct present value: "
                + ", ".join(constants[:4])
                + ". These do not separate records in this snapshot; missing cells may still vary."
            )
        for entry in profile["columns"]:
            if entry["type"] == "date" and entry.get("date_min"):
                paragraphs.append(
                    f"{entry['name']} contains valid dates from {entry['date_min']} to "
                    f"{entry['date_max']}. This range does not prove complete time coverage."
                )
                break
    paragraphs.append(
        "Start with the questions below. I can inspect records, calculate a named measure, "
        "or break it down by a category; each calculated answer keeps its source evidence."
    )
    return "\n\n".join(paragraphs), suggested_exploration(context)


def suggested_exploration(context: DescriptionContext) -> tuple[str, ...]:
    view = context.view
    columns = {entry["name"]: entry for entry in context.profile["columns"]}
    metrics = [
        column.name
        for column in view.columns
        if column.name in view.metrics
        and not columns[column.name].get("type_conflicts")
        and not set(words(column.name).split()) & {"id", "code", "sku", "postal", "zip"}
    ]
    dimensions = [
        column.name
        for column in view.columns
        if column.name in view.dimensions
        and "identifier" not in column.tags
        and column.type != "date"
        and 1 < columns[column.name]["distinct_count"] <= 30
    ]
    prompts = []
    if metrics:
        metric = metrics[0]
        saved = next(
            (
                entry
                for entry in (context.definition or {}).get("metrics", [])
                if entry.get("column") == metric
            ),
            None,
        )
        metric_tokens = set(words(metric).split())
        aggregation = (saved or {}).get(
            "aggregation",
            "avg" if metric_tokens & {"price", "rate", "ratio", "percentage", "score"} else "sum",
        )
        label = {
            "sum": "total",
            "avg": "average",
            "min": "minimum",
            "max": "maximum",
            "count": "count",
        }.get(aggregation, "total")
        if context.state == "confirmed" or (
            context.definition is None
            and context.state == "inferred"
            and not any(source.get("understanding_id") for source in view.sources)
        ):
            units = [
                column.name
                for column in view.columns
                if column.name in view.dimensions
                and column.name.casefold() in {"currency", "currency_code", "unit", "units", "uom"}
                and (columns[column.name]["distinct_count"] > 1 or columns[column.name]["missing"])
            ]
            grouping = " by " + ", ".join(units) if units else ""
            prompts.append(f"What is the {label} of {metric}{grouping}?")
            category = next((name for name in dimensions if name not in units), None)
            if category:
                prompts.append(f"Show the {label} of {metric} by " + ", ".join([*units, category]))
        else:
            prompts.append(f"What does {metric} mean?")
    prompts.append("Show the first 10 records")
    if any(check["count"] for check in context.profile["quality_checks"]):
        prompts.append("Check data quality")
    elif metrics:
        prompts.append(f"What does {metrics[0]} mean?")
    return tuple(dict.fromkeys(prompts))[:4]


def _quality_explanation(context: DescriptionContext, compact: bool = False) -> str:
    checks = {entry["code"]: entry for entry in context.profile["quality_checks"]}
    labels = {
        "missing_values": "missing cells",
        "duplicate_rows": "repeated rows beyond the first identical row",
        "type_conflicts": "cells conflicting with an inferred numeric or boolean type",
        "invalid_dates": "cells not recognized as full ISO dates",
    }
    issues = [
        f"{checks[key]['count']} {label}" for key, label in labels.items() if checks[key]["count"]
    ]
    if not issues:
        text = (
            "The profile found no missing cells, exact duplicate rows, numeric/boolean type "
            "conflicts or invalid dates. These checks describe file consistency; they do not "
            "prove the records are correct, complete or representative."
        )
        notes = [
            note for column in context.profile["columns"] if (note := _date_note(context, column))
        ]
        return "\n\n".join([text, *notes[:2]])
    paragraphs = ["The profile found " + "; ".join(issues) + "."]
    if compact:
        return paragraphs[0] + " Ask 'check data quality' to see what to review first."
    paragraphs.extend(
        note for column in context.profile["columns"] if (note := _date_note(context, column))
    )
    affected = sorted(
        context.profile["columns"],
        key=lambda item: (
            -item["type_conflicts"] - item["invalid_dates"],
            -item["missing"],
            item["name"],
        ),
    )
    for entry in affected[:4]:
        observations = []
        if entry["missing"]:
            observations.append(f"{entry['missing']} missing cells")
        if entry["type_conflicts"]:
            observations.append(f"{entry['type_conflicts']} type conflicts")
        if entry["invalid_dates"]:
            observations.append(f"{entry['invalid_dates']} invalid dates")
        if observations:
            paragraphs.append(entry["name"] + ": " + ", ".join(observations) + ".")
    if checks["type_conflicts"]["count"] or checks["invalid_dates"]["count"]:
        paragraphs.append(
            "First review the conflicting types and dates in Data preparation. Calculations "
            "that reference incompatible cells will identify the affected column and data row."
        )
    if checks["missing_values"]["count"]:
        paragraphs.append(
            "Missing does not mean zero. A missing measure is excluded from its sum or average, "
            "so inspect coverage before interpreting the result."
        )
    if checks["duplicate_rows"]["count"]:
        paragraphs.append(
            "Repeated rows may be legitimate events. Preview a cleaning change before accepting "
            "it; I have not deleted or filled any source values."
        )
    return "\n\n".join(paragraphs)


def _date_note(context: DescriptionContext, column: dict[str, Any]) -> str:
    tokens = set(words(column["name"]).split())
    if (
        "day" in tokens
        and column["invalid_dates"]
        and not column.get("date_min")
        and column["invalid_dates"] + column["missing"] == context.profile["row_count"]
    ):
        return (
            f"{column['name']} may describe a day-of-month component rather than a complete date. "
            "The existing profile expects full YYYY-MM-DD dates, so its date warnings do not "
            "by themselves prove the source is wrong. I have not reinterpreted these values."
        )
    if tokens & {"date", "timestamp", "datetime"} and column["type"] == "text":
        return (
            f"{column['name']} has a date-like label but is profiled as text. Timestamp or "
            "non-ISO formats may need date preparation; a time trend is not inferred from "
            "the label alone."
        )
    return ""


def _next_steps(context: DescriptionContext) -> str:
    prompts = suggested_exploration(context)
    return (
        f"For {context.name}, start with a small question and build on its answer. "
        "The suggested questions use columns that actually exist in this file.\n\n"
        + "\n".join(f"• {prompt}" for prompt in prompts)
        + "\n\nAfter a calculation, try 'break that down by' followed by a category column, "
        "or ask for records matching a value. I keep the previous executed measure and filters "
        "as context. Explaining a column does not change your data or approve a business "
        "definition."
    )
