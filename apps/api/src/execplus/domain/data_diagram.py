"""Use case: Answers requests to see how a file's fields fit into its saved structure.

What it does: Builds bounded, typed membership diagrams from authorized source metadata,
without inferring joins, causal effects, measured relationships or business definitions.
"""

import re
from dataclasses import asdict, dataclass
from typing import Any

from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.guidance import DescriptionContext, mentioned_columns, words

MAX_DIAGRAM_FIELDS = 80
DIAGRAM_VERSION = "dataset-structure-v2"
LEGACY_DIAGRAM_VERSION = "dataset-structure-v1"
ROLE_LABELS = {
    "metric": "Measures",
    "dimension": "Categories",
    "identifier": "Identifiers",
    "ordinal": "Ordered categories",
    "ignored": "Excluded fields",
    "unreviewed": "Fields awaiting review",
}
STRUCTURE_REQUEST_VOCABULARY = (
    "a an the this that these those my our your their its s selected current uploaded "
    "file files data dataset source table column columns field fields measures categories "
    "identifiers ordinal ordered ignored diagram diagrams flowchart flowcharts mindmap mindmaps "
    "map schema structure "
    "structural arrangement hierarchy organization organisation organized organised layout "
    "representation visual visually interactive overview simple basic clear clean "
    "can could will would you please "
    "show me us give draw "
    "make create build generate produce visualize visualise sketch display see i want need "
    "how do does are is be as to of for from in into on with and or just only each every all "
    "include includes including containing contains connect connected connections fit fits "
    "together converge converges relate related relationship relationships help understand "
    "it tie ties thanks thank"
)
STRUCTURE_REQUEST_WORDS = frozenset(STRUCTURE_REQUEST_VOCABULARY.split())


@dataclass(frozen=True, slots=True)
class DiagramRequest:
    columns: tuple[str, ...] = ()


class DiagramClarification(ClarificationRequiredError):
    def __init__(self, message: str, choices: tuple[str, ...]) -> None:
        super().__init__(message)
        self.choices = choices


def confirmed_diagram_roles(context: DescriptionContext) -> dict[str, str]:
    if context.state != "confirmed" or not context.definition:
        return {}
    return {
        column["name"]: column["role"]
        for column in context.definition.get("columns", [])
        if column.get("role") in ROLE_LABELS
    }


def unmatched_structure_words(question: str, context: DescriptionContext) -> str:
    remaining = words(question)
    names = sorted((words(column.name) for column in context.view.columns), key=len, reverse=True)
    for name in names:
        if name:
            remaining = re.sub(r"\b" + re.escape(name) + r"\b", " ", remaining)
    return " ".join(remaining.split())


def require_known_diagram_scope(question: str, context: DescriptionContext) -> None:
    names = {words(column.name) for column in context.view.columns}
    quoted = re.findall(r'"([^"\n]+)"|(?<!\w)\x27([^\x27\n]+)\x27(?!\w)', question)
    unknown_quoted = any(words(double or single) not in names for double, single in quoted)
    remaining = unmatched_structure_words(question, context)
    remaining_symbols = question
    for column in sorted(context.view.columns, key=lambda column: len(column.name), reverse=True):
        remaining_symbols = re.sub(
            r"(?<!\w)" + re.escape(column.name) + r"(?!\w)",
            " ",
            remaining_symbols,
            flags=re.IGNORECASE,
        )
    if re.search(r"[<>=]", remaining_symbols) or re.search(
        r"\b(where|filter(?:ed|s|ing)?|exclud(?:e|ed|es|ing)|except|since|before|after|"
        r"between|without)\b",
        remaining,
    ):
        raise DiagramClarification(
            "This map shows field names and saved meanings; it does not select or filter rows. "
            "For filtered values, ask for a calculation or records with that condition.",
            ("Show a data structure diagram",),
        )
    if unknown_quoted or set(remaining.split()) - STRUCTURE_REQUEST_WORDS:
        raise DiagramClarification(
            "I cannot match every requested field or condition to a field-only map. "
            "Please use the exact field names, or choose the full structure; "
            "no requested fields or row conditions have been silently left out.",
            ("Show a data structure diagram",),
        )


def diagram_request(question: str, context: DescriptionContext) -> DiagramRequest | None:
    normalized = words(question)
    explicit = bool(re.search(r"\b(diagrams?|flowcharts?|mindmaps?)\b", normalized))
    structural = bool(
        re.search(r"\b(data map|schema map|structure map)\b", normalized)
        or re.search(r"\bvisual representation\b.*\b(data|file|fields|dataset)\b", normalized)
        or re.search(r"\bhow\b.*\b(fields|columns)\b.*\b(connect|fit|relate)\b", normalized)
        or re.search(
            r"\b(visualize|visualise)\b.*\b(structure|fields|converge|organised|organized)\b",
            normalized,
        )
    )
    if not (explicit or structural):
        return None
    if re.search(r"\b(documents?|policy|contract|according)\b", normalized):
        raise DiagramClarification(
            "This diagram tool maps the selected file's fields. "
            "It cannot draw a process from document instructions.",
            ("Show a data structure diagram",),
        )
    named = mentioned_columns(question, context.view)
    if named and re.search(r"\b(total|sum|average|mean|count|minimum|maximum)\b", normalized):
        return None
    if re.search(
        r"\b(causes?|causal|effects?|impact|join(?:s|ing)?|merge|merging)\b",
        unmatched_structure_words(question, context),
    ):
        raise DiagramClarification(
            "I can map the fields in this file. Those links show membership, not causes, "
            "merged files or filtered results. Which view would help?",
            ("Show a data structure diagram", "Find patterns in this data"),
        )
    if named and re.search(r"\b(by|versus|vs|trend|over time)\b", normalized):
        raise DiagramClarification(
            "Do you want a map of the fields, or a chart of calculated values? "
            "For a value chart, name the measure and calculation, such as total or average.",
            ("Show a data structure diagram",),
        )
    require_known_diagram_scope(question, context)
    selected = named
    role = next(
        (
            key
            for word, key in (
                ("ordered categories", "ordinal"),
                ("ordinal", "ordinal"),
                ("ignored", "ignored"),
                ("measures", "metric"),
                ("categories", "dimension"),
                ("identifiers", "identifier"),
            )
            if re.search(r"\b" + re.escape(word) + r"\b", normalized)
        ),
        None,
    )
    if not selected and role:
        if context.state != "confirmed":
            raise DiagramClarification(
                "The field roles have not been confirmed. I can show all field names first.",
                ("Show a data structure diagram",),
            )
        roles = confirmed_diagram_roles(context)
        selected = tuple(
            column.name for column in context.view.columns if roles.get(column.name) == role
        )
        if not selected:
            raise DiagramClarification(
                "No fields have that saved role. I can show the full file structure.",
                ("Show a data structure diagram",),
            )
    if len(selected or context.view.columns) > MAX_DIAGRAM_FIELDS:
        raise DiagramClarification(
            "This map supports up to eighty fields. Choose measures, categories or identifiers, "
            "or name the fields you want to see; no fields have been silently left out.",
            (
                "Show a data structure diagram for measures",
                "Show a data structure diagram for categories",
                "Show a data structure diagram for identifiers",
            ),
        )
    return DiagramRequest(selected)


@dataclass(frozen=True, slots=True)
class DiagramNode:
    id: str
    kind: str
    label: str
    data_type: str = ""
    role: str = ""
    meaning: str = ""
    unit: str = ""
    currency: str = ""
    unit_column: str = ""


@dataclass(frozen=True, slots=True)
class DiagramEdge:
    source: str
    target: str
    relation: str = "contains"


@dataclass(frozen=True, slots=True)
class DataDiagram:
    version: str
    title: str
    description: str
    row_meaning: str
    definition_state: str
    scope: str
    total_fields: int
    shown_fields: int
    nodes: tuple[DiagramNode, ...]
    edges: tuple[DiagramEdge, ...]
    limitations: tuple[str, ...]

    def body(self) -> dict[str, Any]:
        return asdict(self)


def build_diagram(
    context: DescriptionContext, request: DiagramRequest, *, version: str = DIAGRAM_VERSION
) -> DataDiagram:
    if version not in {LEGACY_DIAGRAM_VERSION, DIAGRAM_VERSION}:
        raise ValueError("The saved diagram version is unsupported.")
    names = tuple(column.name for column in context.view.columns)
    selected = request.columns or names
    if (
        not selected
        or len(selected) > MAX_DIAGRAM_FIELDS
        or len(set(selected)) != len(selected)
        or not set(selected) <= set(names)
    ):
        raise ValueError("Diagram fields must be unique, supplied and within the field limit.")
    confirmed = context.state == "confirmed"
    definition = context.definition if confirmed and context.definition else {}
    saved = {column["name"]: column for column in definition.get("columns", [])}
    saved_roles = confirmed_diagram_roles(context)
    nodes = [DiagramNode("dataset", "dataset", "This file")]
    edges = []
    groups = set()
    for index, column in enumerate(context.view.columns):
        if column.name not in selected:
            continue
        meaning = saved.get(column.name, {})
        role = (
            (column.role if confirmed and column.role in ROLE_LABELS else "unreviewed")
            if version == LEGACY_DIAGRAM_VERSION
            else saved_roles.get(column.name, "unreviewed")
        )
        group_id = "role-" + role
        if role not in groups:
            nodes.append(DiagramNode(group_id, "group", ROLE_LABELS[role], role=role))
            edges.append(DiagramEdge("dataset", group_id))
            groups.add(role)
        field_id = f"field-{index}"
        nodes.append(
            DiagramNode(
                field_id,
                "field",
                column.name,
                column.type,
                role,
                meaning.get("meaning", ""),
                meaning.get("unit", ""),
                meaning.get("currency", ""),
                meaning.get("unit_column", ""),
            )
        )
        edges.append(DiagramEdge(group_id, field_id))
    limitations = [
        "Lines show which fields belong to each group. "
        "They do not show cause and effect or measured relationships.",
        "This map covers the selected file only. It does not infer joins with other files.",
    ]
    if not confirmed:
        limitations.append(
            "Field names and types come from the file; "
            "business roles and meanings still need review."
        )
    return DataDiagram(
        version,
        "How this file is organised",
        definition.get("description", ""),
        definition.get("grain", ""),
        context.state,
        "selected_fields" if request.columns else "all_fields",
        len(names),
        len(selected),
        tuple(nodes),
        tuple(edges),
        tuple(limitations),
    )
