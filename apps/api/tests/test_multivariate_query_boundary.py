"""Use case: Extends the SQL grammar only for two bound cohort choices.

What it does: Keeps literals, expressions, subqueries and unbounded memberships denied.
"""

import pytest

from execplus.domain.errors import UnsafeQueryError
from execplus.infrastructure.query.validation import validated_query


def test_two_exact_bound_cohort_values_are_supported():
    validated_query(
        'SELECT "id", "x" FROM "dataset" WHERE "cohort" IN (?, ?) ORDER BY "id" LIMIT 1001',
        {"dataset"},
        2,
    )


@pytest.mark.parametrize(
    "condition,params",
    [
        ('"cohort" IN (?)', 1),
        ('"cohort" IN (?, ?, ?)', 3),
        ('"cohort" IN (1, 2)', 0),
        ('LOWER("cohort") IN (?, ?)', 2),
        ('"cohort" IN (SELECT "id" FROM "dataset" LIMIT 1)', 0),
        ('"cohort" IN (?, LOWER(?))', 2),
        ('"cohort" = ? OR "cohort" = ?', 2),
        ('"cohort" NOT IN (?, ?)', 2),
    ],
)
def test_other_membership_or_boolean_forms_remain_refused(condition, params):
    with pytest.raises(UnsafeQueryError):
        validated_query(
            f'SELECT "id" FROM "dataset" WHERE {condition} LIMIT 1001', {"dataset"}, params
        )
