"""Use case: Validates SQL again at the analytical execution boundary.

What it does: Parses a narrow aggregate grammar and rejects external or unbounded plans.
"""

from sqlglot import exp, parse
from sqlglot.errors import ParseError

from execplus.domain.errors import UnsafeQueryError

_ALLOWED = {
    exp.Select,
    exp.Column,
    exp.Identifier,
    exp.Table,
    exp.From,
    exp.Alias,
    exp.Sum,
    exp.Avg,
    exp.Count,
    exp.Min,
    exp.Max,
    exp.Where,
    exp.And,
    exp.EQ,
    exp.Lower,
    exp.NEQ,
    exp.LT,
    exp.LTE,
    exp.GT,
    exp.GTE,
    exp.Placeholder,
    exp.Group,
    exp.Limit,
    exp.Literal,
    exp.Join,
    exp.Order,
    exp.Ordered,
}


def validated_query(sql: str, tables: set[str], params: int) -> exp.Select:
    try:
        statements = parse(sql, read="duckdb")
    except ParseError:
        raise UnsafeQueryError("The query could not be parsed safely") from None
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise UnsafeQueryError("Exactly one read-only SELECT is required")
    query = statements[0]
    if any(type(node) not in _ALLOWED for node in query.walk()):
        raise UnsafeQueryError("The query contains an unsupported operation")
    if len(list(query.find_all(exp.AggFunc))) > 1:
        raise UnsafeQueryError("Only one verified aggregation per query is supported")
    references = list(query.find_all(exp.Table))
    if not references or any(
        not isinstance(table.this, exp.Identifier)
        or table.name not in tables
        or table.db
        or table.catalog
        for table in references
    ):
        raise UnsafeQueryError("Only authorized snapshot tables may be queried")
    if len(list(query.find_all(exp.Placeholder))) != params:
        raise UnsafeQueryError("The query parameters do not match the plan")
    limit = query.args.get("limit")
    if not isinstance(limit, exp.Limit) or not isinstance(limit.expression, exp.Literal):
        raise UnsafeQueryError("A bounded row limit is required")
    if not limit.expression.is_int or not 1 <= int(limit.expression.this) <= 100_000:
        raise UnsafeQueryError("The row limit exceeds supported bounds")
    if any(node is not limit.expression for node in query.find_all(exp.Literal)):
        raise UnsafeQueryError("Filter values must use bound parameters")
    if any(
        join.args.get("kind") not in {None, "INNER"} or not isinstance(join.args.get("on"), exp.EQ)
        for join in query.find_all(exp.Join)
    ):
        raise UnsafeQueryError("Only declared equality joins are supported")
    return query
