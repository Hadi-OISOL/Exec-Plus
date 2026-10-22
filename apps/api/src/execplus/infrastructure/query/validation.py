"""Use case: Validates SQL again at the analytical execution boundary.

What it does: Parses a narrow aggregate grammar and rejects external or unbounded plans.
"""

from sqlglot import exp, parse
from sqlglot.errors import ParseError

from execplus.domain.errors import UnsafeQueryError

_ALLOWED = {
    exp.Select,
    exp.Subquery,
    exp.Column,
    exp.Identifier,
    exp.Table,
    exp.From,
    exp.Alias,
    exp.Sum,
    exp.Avg,
    exp.Count,
    exp.Star,
    exp.Min,
    exp.Max,
    exp.Where,
    exp.And,
    exp.EQ,
    exp.In,
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
    exp.TimestampTrunc,
    exp.Cast,
    exp.DataType,
    exp.TimeToStr,
    exp.DayOfWeekIso,
    exp.Case,
    exp.If,
    exp.Mul,
}


def _validate_calendar_parts(query: exp.Select) -> None:
    if any(
        not isinstance(node.this, exp.Column)
        or not isinstance(node.args.get("format"), exp.Placeholder)
        or any(
            value is not None for key, value in node.args.items() if key not in {"this", "format"}
        )
        for node in query.find_all(exp.TimeToStr)
    ):
        raise UnsafeQueryError("Day-of-week grouping requires a source column and bound format")
    if any(not isinstance(node.this, exp.Column) for node in query.find_all(exp.DayOfWeekIso)):
        raise UnsafeQueryError("Weekday numbers require a source column")
    for case in query.find_all(exp.Case):
        ifs = case.args.get("ifs") or []
        condition = ifs[0].this if len(ifs) == 1 else None
        if (
            case.this is not None
            or not isinstance(condition, exp.GTE)
            or not isinstance(condition.this, exp.DayOfWeekIso)
            or not isinstance(condition.expression, exp.Placeholder)
            or not isinstance(ifs[0].args.get("true"), exp.Placeholder)
            or not isinstance(case.args.get("default"), exp.Placeholder)
        ):
            raise UnsafeQueryError("Only a bound weekday/weekend split is supported")
    if any(
        not isinstance(node.parent, exp.GTE) or not isinstance(node.parent.parent, exp.If)
        for node in query.find_all(exp.DayOfWeekIso)
    ) or any(not isinstance(node.parent, exp.Case) for node in query.find_all(exp.If)):
        raise UnsafeQueryError("Only a bound weekday/weekend split is supported")
    for product in query.find_all(exp.Mul):
        if (
            not isinstance(product.parent, (exp.Sum, exp.Avg))
            or not isinstance(product.this, exp.Column)
            or not isinstance(product.expression, exp.Column)
        ):
            raise UnsafeQueryError("Only a row-level product of two fields inside SUM or AVG")


def _validate_extremum(query: exp.Select) -> None:
    subqueries = list(query.find_all(exp.Subquery))
    if not subqueries:
        return
    if len(subqueries) != 1 or query.args.get("joins") or query.args.get("group"):
        raise UnsafeQueryError("Only one same-snapshot record extremum is supported")
    nested = subqueries[0]
    condition, inner = nested.parent, nested.this
    source = query.args.get("from")
    where = query.args.get("where")
    if (
        not isinstance(condition, exp.EQ)
        or condition.expression is not nested
        or not isinstance(condition.this, exp.Column)
        or condition.this.table
        or not isinstance(inner, exp.Select)
        or len(inner.expressions) != 1
        or not isinstance(inner.expressions[0], (exp.Min, exp.Max))
        or not isinstance(source, exp.From)
        or not isinstance(source.this, exp.Table)
        or not isinstance(where, exp.Where)
    ):
        raise UnsafeQueryError("The extremum must select matching records from the same snapshot")
    expression = where.this
    filters = None
    if expression is not condition:
        if not isinstance(expression, exp.And) or expression.expression is not condition:
            raise UnsafeQueryError("Keep the same filters inside and outside the extremum")
        filters = expression.this.copy()
    expected = exp.select(type(inner.expressions[0])(this=condition.this.copy())).from_(
        source.this.copy()
    )
    if filters is not None:
        expected = expected.where(filters)
    if inner != expected:
        raise UnsafeQueryError("The extremum must use the same field, table and filters")


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
    _validate_extremum(query)
    _validate_calendar_parts(query)
    if any(
        not isinstance(node.parent, exp.Count)
        or node.parent.this is not node
        or any(value is not None for value in node.args.values())
        for node in query.find_all(exp.Star)
    ):
        raise UnsafeQueryError("A wildcard is permitted only as the direct COUNT(*) argument")
    if any(
        not isinstance(node.this, exp.Column)
        or len(node.expressions) != 2
        or any(not isinstance(value, exp.Placeholder) for value in node.expressions)
        or node.args.get("query") is not None
        for node in query.find_all(exp.In)
    ):
        raise UnsafeQueryError("Cohort selection requires exactly two bound values on one field")
    if any(
        not isinstance(node.this, exp.Column)
        or not isinstance(node.args.get("unit"), exp.Placeholder)
        for node in query.find_all(exp.TimestampTrunc)
    ):
        raise UnsafeQueryError("Calendar grouping requires a source column and bound period")
    if any(
        not node.to.is_type(exp.DataType.Type.DATE) or not isinstance(node.this, exp.TimestampTrunc)
        for node in query.find_all(exp.Cast)
    ):
        raise UnsafeQueryError("Only a calendar period may be converted to a date")
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
