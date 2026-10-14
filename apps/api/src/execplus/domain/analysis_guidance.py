"""Use case: Connects explicit advanced-analysis requests to governed tools.

What it does: Explains eligibility and offers setup actions without inventing inputs.
"""

import re

from execplus.domain.analysis_readiness import forecast_options
from execplus.domain.guidance import DescriptionContext, mentioned_columns, words


def analysis_guidance(
    context: DescriptionContext, question: str
) -> tuple[str, tuple[dict[str, str], ...]] | None:
    text = words(question)
    if re.search(r"\b(total|sum|average|mean|count|minimum|maximum|list|records)\b", text):
        return None
    if re.search(r"\b(document|policy|according)\b", text):
        return None
    if re.search(r"\b(forecast|forecasts|forecasting|predict|prediction|predictions)\b", text):
        tool, label = "forecasts", "Set up a forecast"
        options = forecast_options(context)
        if options["blockers"]:
            message = " ".join(item["message"] for item in options["blockers"])
            if context.state == "confirmed":
                message = "I am using your saved data meanings. " + message
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
    elif re.search(r"\b(anomalies|anomaly|outliers?)\b|unusual values", text):
        tool, label = "anomalies", "Inspect unusual values"
        message = (
            "Use your saved measure meanings to inspect unusual values, optionally "
            "within groups. Choose a measure and review the threshold; findings are "
            "not proof of an error."
        )
    elif re.search(r"\b(scenarios?|what if)\b", text):
        tool, label = "scenarios", "Compare scenarios"
        message = (
            "Use a saved measure as the baseline, then declare the changes to "
            "compare. Scenario results depend on those assumptions; they do not "
            "establish causes."
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
    named = [
        name for name in mentioned_columns(question, context.view) if name in context.view.metrics
    ]
    action = dict(tool=tool, label=label)
    if len(named) == 1:
        action["metric"] = named[0]
    return message, (action,)
