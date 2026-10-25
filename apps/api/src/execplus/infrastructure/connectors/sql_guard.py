"""Use case: Accepts a user's own read-only SELECT for a database connector and nothing else.

What it does: Parses one statement in the database's dialect and refuses writes, comments,
locks, extra statements and server functions that sleep, read files or change settings.
"""

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from execplus.domain.ingestion import IngestionError

MAX_QUERY_CHARS = 10_000
ROOTS = (exp.Select, exp.Union, exp.Intersect, exp.Except)
FORBIDDEN_NODES = tuple(
    node
    for node in (
        getattr(exp, name, None)
        for name in (
            "Insert",
            "Update",
            "Delete",
            "Merge",
            "Create",
            "Drop",
            "Alter",
            "Command",
            "Into",
            "Lock",
            "Set",
            "Transaction",
            "Commit",
            "Rollback",
            "Use",
            "Grant",
            "Copy",
            "LoadData",
            "Pragma",
            "Execute",
        )
    )
    if isinstance(node, type)
)
FORBIDDEN_FUNCTIONS = frozenset(
    {
        "set_config",
        "nextval",
        "setval",
        "sleep",
        "benchmark",
        "load_file",
        "get_lock",
        "release_lock",
        "release_all_locks",
        "is_free_lock",
        "is_used_lock",
        "master_pos_wait",
        "source_pos_wait",
        "sys_exec",
        "sys_eval",
        "openrowset",
        "openquery",
        "opendatasource",
        "openxml",
        "waitfor",
    }
)
FORBIDDEN_PREFIXES = (
    "pg_",
    "lo_",
    "dblink",
    "xp_",
    "sp_",
    "query_to_xml",
    "table_to_xml",
    "schema_to_xml",
    "database_to_xml",
    "cursor_to_xml",
)


def refused(message: str) -> IngestionError:
    return IngestionError("connector_query_refused", message, 422)


def _function_name(node: exp.Func) -> str:
    return (node.name if isinstance(node, exp.Anonymous) else node.key).lower()


def checked_select(query: str, dialect: str) -> str:
    text = query.strip()
    while text.endswith(";"):
        text = text[:-1].rstrip()
    if not text:
        raise refused("Write a SELECT query.")
    if len(text) > MAX_QUERY_CHARS:
        raise refused("That query is too long. Keep it under 10,000 characters.")
    try:
        tokens = sqlglot.Dialect.get_or_raise(dialect).tokenize(text)
        statements = sqlglot.parse(text, read=dialect)
    except SqlglotError:
        raise refused("That query could not be read. Check its syntax.") from None
    if any(token.comments for token in tokens):
        raise refused("Remove comments from the query.")
    if len(statements) != 1 or not isinstance(statements[0], ROOTS):
        raise refused("Only one SELECT query is allowed.")
    for node in statements[0].walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise refused("Only reading is allowed: the query may not change or lock anything.")
        if isinstance(node, exp.Func):
            name = _function_name(node)
            if name in FORBIDDEN_FUNCTIONS or name.startswith(FORBIDDEN_PREFIXES):
                raise refused(f"The function {name} is not allowed in imported queries.")
    return text
