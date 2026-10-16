"""Use case: Describes recoverable qualitative-reading validation problems safely.

What it does: Gives bounded correction prompts and diagnostics fixed issue codes without
including model replies, field values or private context.
"""

from enum import Enum


class ReadingIssue(str, Enum):
    TEXT_BOUNDS = "text_bounds"
    PROSE_EVIDENCE = "prose_evidence"
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


READING_CORRECTIONS = {
    ReadingIssue.TEXT_BOUNDS: (
        "Use nonempty plain strings: summary at most 360 characters and each "
        "connection meaning at most 200 characters. Prefer one short sentence."
    ),
    ReadingIssue.PROSE_EVIDENCE: (
        "Prose must contain no numerical quantities, dates, markup, links or line breaks. "
        "Only an exact supplied field name may contain digits."
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
