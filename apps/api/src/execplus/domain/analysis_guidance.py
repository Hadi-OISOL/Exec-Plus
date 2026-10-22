"""Use case: Connects explicit advanced-analysis requests to governed tools.

What it does: Explains eligibility and offers setup actions without inventing inputs.
"""

import re

from execplus.domain.analysis_readiness import fixed_unit_columns, forecast_options
from execplus.domain.guidance import DescriptionContext, mentioned_columns, words


def analysis_guidance(
    context: DescriptionContext, question: str
) -> tuple[str, tuple[dict[str, str], ...]] | None:
    text = words(question)
    if re.search(r"\b(total|sum|average|mean|count|minimum|maximum|list|records)\b", text):
        return None
    if re.search(r"\b(document|policy|according)\b", text):
        return None
    daily = bool(re.search(r"\b(days?|daily|per day)\b", text))
    named = [
        name for name in mentioned_columns(question, context.view) if name in context.view.metrics
    ]
    if re.search(r"\b(forecast|forecasts|forecasting|predict|prediction|predictions)\b", text):
        tool, label = "forecasts", "Set up a forecast"
        options = forecast_options(context)
        if options["blockers"]:
            message = " ".join(item["message"] for item in options["blockers"])
            if context.state == "confirmed":
                message = "I am using your saved data meanings. " + message
            if context.state == "confirmed" and any(
                item["code"] == "date" for item in options["blockers"]
            ):
                eligible = {column["name"] for column in fixed_unit_columns(context)}
                missing = [name for name in named if name not in eligible]
                if missing or not eligible:
                    measure = ", ".join(missing) if missing else "a numeric measure"
                    return (
                        message
                        + f" A daily what-if also needs a confirmed fixed unit for {measure}. "
                        "Your other answers are saved. "
                        "I can still check relationships among eligible fields.",
                        (
                            dict(tool="prepare", label="Complete missing units"),
                            dict(tool="patterns", label="Find patterns in eligible fields"),
                        ),
                    )
                scenario = dict(
                    tool="scenarios", label="Try a daily what-if", scenario_mode="daily_change"
                )
                if len(named) == 1:
                    scenario["metric"] = named[0]
                return (
                    message + " I can find relationships in the rows you have. Or choose a "
                    "daily change and a number of days for a what-if calculation. That uses "
                    "your assumption; it does not predict what will happen.",
                    (
                        dict(tool="patterns", label="Find patterns in this data"),
                        scenario,
                    ),
                )
            return (
                message
                + " You can still compare observed measurements and inspect unusual values.",
                (
                    dict(tool="overview", label="Explore observed data"),
                    dict(tool="prepare", label="Review missing details"),
                ),
            )
        message = (
            "Your saved meanings provide a date column and measures with units. "
            "Choose the measure, daily or monthly periods and horizon, then confirm which periods "
            "are complete. The forecast tool will check the history and calculate the estimate."
        )
    elif re.search(
        r"\b(anomalies|anomaly|anomalous|outliers?)\b"
        r"|\b(unusual|weird|strange|abnormal|suspicious|spikes?)\b"
        r"|\bodd (values?|rows?|entries)\b",
        text,
    ):
        scan = dict(tool="anomalies", label="Scan for unusual values")
        if len(named) == 1:
            scan["metric"] = named[0]
        return (
            "I can scan every eligible measure for unusual values automatically, without any "
            "settings. Open the scan to see flagged rows and the values closest to unusual. "
            "A flagged value is a candidate to check, not proof of an error.",
            (scan,),
        )
    elif re.search(r"\b(scenarios?|what if)\b", text) or (
        daily and re.search(r"\b(happen|happens|change|changes|after|over)\b", text)
    ):
        tool, label = "scenarios", "Compare scenarios"
        message = (
            "Use a saved measure as the baseline, then declare the changes to "
            "compare. Scenario results depend on those assumptions; they do not "
            "establish causes."
        )
        if daily:
            message = (
                "Choose a measure, the change you assume each day and how many days to apply it. "
                "I can calculate those steps without dates. This is a constant-change what-if, "
                "not a learned forecast or proof that one thing causes another."
            )
    elif re.search(r"\b(allocat\w*|prescriptive)\b|budget recommendation", text):
        tool, label = "allocations", "Set up a recommendation"
        message = (
            "Use saved field meanings to choose candidates, costs and benefits. "
            "Supply the budget and resource limits and confirm the fixed-cost "
            "assumptions before calculating a recommendation."
        )
    else:
        return None
    if context.state != "confirmed":
        return (
            "Your answers are retained, but this source still needs confirmed "
            "meanings before this analysis.",
            (dict(tool="prepare", label="Finish data review"),),
        )
    eligible = {column["name"] for column in fixed_unit_columns(context)}
    missing_units = [name for name in named if name not in eligible]
    if missing_units or not eligible:
        measure = ", ".join(missing_units) if missing_units else "a numeric measure"
        return (
            "Your saved meanings are in use. "
            f"Confirm a fixed unit for {measure} before this analysis. "
            "Other saved answers do not need to be repeated.",
            (dict(tool="prepare", label="Complete missing details"),),
        )
    action = dict(tool=tool, label=label)
    if tool == "scenarios" and daily:
        action["scenario_mode"] = "daily_change"
    if len(named) == 1:
        action["metric"] = named[0]
    return message, (action,)
