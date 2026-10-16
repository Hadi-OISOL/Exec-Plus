"""Use case: Describes recoverable qualitative-reading validation problems safely.

What it does: Gives bounded correction prompts and diagnostics fixed issue codes without
including model replies, field values or private context.
"""

from enum import Enum


class ReadingIssue(str, Enum):
    TEXT_BOUNDS = "text_bounds"
    PROSE_NUMBERS = "prose_numbers"
    PROSE_LINKS = "prose_links"
    PROSE_MARKUP = "prose_markup"
    PROSE_CONTROL = "prose_control"
    SHAPE = "shape"
    CONNECTIONS = "connections"
    CONNECTION = "connection"
    FIELDS = "fields"
    EXPLORATIONS = "explorations"
    EXPLORATION = "exploration"
    EXPLORATION_FIELDS = "exploration_fields"


class ReadingValidationError(ValueError):
    def __init__(self, issue: ReadingIssue, message: str) -> None:
        super().__init__(message)
        self.issue = issue


READING_PROSE_RULES = (
    "Write summary and each connection meaning as one short, single-line plain sentence. "
    "Do not put digits, dates, numerical quantities, URLs, backticks, angle brackets, "
    "tabs, newlines or other control characters in those prose strings. "
    "Do not repeat counts or dates from the saved description or notes. "
    "Put exact field identifiers in connections.columns and explore.metric/group_by; "
    "explain their purpose in prose instead of repeating identifiers. "
)


READING_CORRECTIONS = {
    ReadingIssue.TEXT_BOUNDS: (
        "Use nonempty plain strings: summary at most 360 characters and each "
        "connection meaning at most 200 characters. Prefer one short sentence."
    ),
    ReadingIssue.PROSE_NUMBERS: (
        "Remove digits and dates from summary and connection meanings, including counts "
        "copied from descriptions or notes. Keep field identifiers in columns and explore."
    ),
    ReadingIssue.PROSE_LINKS: (
        "Remove URLs from summary and connection meanings. Do not put source links there."
    ),
    ReadingIssue.PROSE_MARKUP: (
        "Use plain text in summary and connection meanings: no backticks, angle brackets, "
        "HTML or code."
    ),
    ReadingIssue.PROSE_CONTROL: (
        "Use one single-line sentence for summary and each connection meaning. "
        "Remove line breaks, tabs and other control characters."
    ),
    ReadingIssue.SHAPE: "Use exactly the summary, connections and explore keys at the top level.",
    ReadingIssue.CONNECTIONS: "Supply one to three connection objects in the connections array.",
    ReadingIssue.CONNECTION: "Each connection must contain exactly columns and meaning.",
    ReadingIssue.FIELDS: (
        "Each connection needs one to six unique exact field names from the supplied columns."
    ),
    ReadingIssue.EXPLORATIONS: "The explore array may contain zero, one or two choices only.",
    ReadingIssue.EXPLORATION: "Each explore choice must contain exactly metric and group_by.",
    ReadingIssue.EXPLORATION_FIELDS: (
        "Copy metric only from exploration_catalog.metric_fields; copy group_by from "
        "exploration_catalog.group_fields or use an empty string. Do not suggest other fields."
    ),
}
