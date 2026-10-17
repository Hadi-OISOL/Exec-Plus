"""Use case: Independently verifies governed counts and extremum record selection.

What it does: Checks exact ties, nulls, negative/large decimals, immutable replay
and dataset-policy boundaries using only fictional local fixtures.
"""

from decimal import Decimal

import pytest

from execplus.domain.errors import UnsafeQueryError
from execplus.infrastructure.query.validation import validated_query
from test_studies import add_member, prepare
from test_understanding import confirm, context

CONTENT = (
    b"id,cohort,amount,nullable,secret\n"
    b"a,A,-10.25,,901\n"
    b"b,A,-2.1,4,902\n"
    b"c,A,-2.10,,903\n"
    b"d,B,-0.01,,904\n"
    b"e,B,,9,905\n"
    b"f,B,-20.5,,906\n"
    b"g,C,,,907\n"
    b"h,C,,,908\n"
)


def select(env, actor, root, direction="max", *, filters=None, limit=100, column="amount"):
    return env.client.post(
        root + "/rows",
        headers=actor,
        json=dict(
            filters=filters or [],
            limit=limit,
            extremum=dict(column=column, direction=direction),
        ),
    )


def cohort(name):
    return [dict(column="cohort", operator="eq", value=name)]


def ids(body):
    index = body["columns"].index("id")
    return {row[index] for row in body["rows"]}


def count(env, actor, root, metric="*", filters=None):
    return env.client.post(
        root + "/query",
        headers=actor,
        json=dict(metric=metric, aggregation="count", filters=filters or []),
    )


@pytest.mark.parametrize(
    "direction,filters,expected,value",
    [
        ("max", cohort("A"), {"b", "c"}, "-2.1"),
        ("min", cohort("A"), {"a"}, "-10.25"),
        ("max", [], {"d"}, "-0.01"),
        ("min", [], {"f"}, "-20.5"),
    ],
)
def test_extrema_return_matching_records_with_all_ties_and_negative_values(
    integration, direction, filters, expected, value
):
    owner, _, wid, _, _, root = prepare(integration, CONTENT)
    response = select(integration, owner, root, direction, filters=filters)
    assert response.status_code == 200, response.text
    body = response.json()
    assert ids(body) == expected and body["matched_records"] == len(expected)
    index = body["columns"].index("amount")
    assert all(Decimal(row[index]) == Decimal(value) for row in body["rows"])
    query_id = body["lineage"]["query_id"]
    replay = integration.client.post(f"/workspaces/{wid}/queries/{query_id}/replay", headers=owner)
    assert replay.status_code == 200 and replay.json() == body


@pytest.mark.parametrize("direction", ["min", "max"])
def test_all_null_or_empty_filtered_population_has_no_extremum_rows(integration, direction):
    owner, _, _, _, _, root = prepare(integration, CONTENT)
    for group in ("C", "absent"):
        response = select(integration, owner, root, direction, filters=cohort(group))
        assert response.status_code == 200, response.text
        assert response.json()["rows"] == [] and response.json()["matched_records"] == 0


def test_tied_extremum_keeps_total_match_count_when_returned_records_are_limited(integration):
    owner, _, _, _, _, root = prepare(integration, CONTENT)
    response = select(integration, owner, root, filters=cohort("A"), limit=1)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["rows"]) == 1 and ids(body) <= {"b", "c"}
    assert body["matched_records"] == 2
    receipt = body["lineage"]["receipt"]
    assert receipt["matched_records"] == 2


@pytest.mark.parametrize(
    "direction,expected,value",
    [
        ("max", {"b", "c"}, "9007199254740993.000000000002"),
        ("min", {"d", "e"}, "-9007199254740993.000000000002"),
    ],
)
def test_extrema_do_not_merge_large_decimals_differing_after_binary_precision(
    integration, direction, expected, value
):
    content = (
        b"id,amount\n"
        b"a,9007199254740993.000000000001\n"
        b"b,9007199254740993.000000000002\n"
        b"c,9007199254740993.000000000002\n"
        b"d,-9007199254740993.000000000002\n"
        b"e,-9007199254740993.000000000002\n"
        b"f,\n"
    )
    owner, _, _, _, _, root = prepare(integration, content)
    response = select(integration, owner, root, direction)
    assert response.status_code == 200, response.text
    body = response.json()
    assert ids(body) == expected and body["matched_records"] == 2
    index = body["columns"].index("amount")
    assert all(Decimal(row[index]) == Decimal(value) for row in body["rows"])


def test_record_count_includes_null_measure_rows_and_named_count_does_not(integration):
    owner, _, wid, _, _, root = prepare(integration, CONTENT)
    for metric, filters, expected in [
        ("*", [], 8),
        ("amount", [], 5),
        ("nullable", [], 2),
        ("cohort", [], 8),
        ("*", cohort("C"), 2),
        ("amount", cohort("C"), 0),
        ("*", cohort("absent"), 0),
    ]:
        response = count(integration, owner, root, metric, filters)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["rows"] == [[expected]]
        query_id = body["lineage"]["query_id"]
        replay = integration.client.post(
            f"/workspaces/{wid}/queries/{query_id}/replay", headers=owner
        )
        assert replay.status_code == 200 and replay.json() == body


def test_ignored_metric_refuses_new_count_and_extrema_but_old_evidence_replays(integration):
    owner, _, wid, _, _, root = prepare(integration, CONTENT)
    original = select(integration, owner, root)
    assert original.status_code == 200, original.text
    current = context(integration, owner, root)
    for column in current["definition"]["columns"]:
        if column["name"] == "amount":
            column["role"] = "ignored"
    saved = confirm(integration, owner, root, current)
    assert saved.status_code == 201, saved.text
    assert select(integration, owner, root).status_code == 422
    assert count(integration, owner, root, "amount").status_code == 422
    assert count(integration, owner, root).json()["rows"] == [[8]]
    query_id = original.json()["lineage"]["query_id"]
    replay = integration.client.post(f"/workspaces/{wid}/queries/{query_id}/replay", headers=owner)
    assert replay.status_code == 200 and replay.json() == original.json()


def test_extrema_and_counts_use_only_actor_visible_rows_and_columns_and_revoke_replay(
    integration,
):
    owner, owner_actor, wid, did, _, root = prepare(integration, CONTENT)
    member, member_actor = add_member(integration, owner, wid)
    path = f"/workspaces/{wid}/datasets/{did}/access-policy"
    owner_grant = dict(user_id=str(owner_actor.id), columns=None, conditions=[])
    policy = dict(
        expected_version=0,
        enabled=True,
        grants=[
            owner_grant,
            dict(
                user_id=str(member_actor.id),
                columns=["id", "cohort", "amount", "nullable"],
                conditions=cohort("A"),
            ),
        ],
    )
    assert integration.client.put(path, headers=owner, json=policy).status_code == 200
    response = select(integration, member, root)
    assert response.status_code == 200, response.text
    body = response.json()
    assert ids(body) == {"b", "c"} and body["matched_records"] == 2
    assert "secret" not in body["columns"] and "904" not in response.text
    assert count(integration, member, root).json()["rows"] == [[3]]
    assert count(integration, member, root, "nullable").json()["rows"] == [[1]]
    assert select(integration, member, root, column="secret").status_code == 422
    assert count(integration, member, root, "secret").status_code == 422
    assert (
        count(
            integration,
            member,
            root,
            filters=[dict(column="secret", operator="gt", value="0")],
        ).status_code
        == 422
    )
    query_id = body["lineage"]["query_id"]
    replay_path = f"/workspaces/{wid}/queries/{query_id}/replay"
    assert integration.client.post(replay_path, headers=member).json() == body
    assert integration.client.post(replay_path, headers=owner).status_code == 404
    revoked = dict(expected_version=1, enabled=True, grants=[owner_grant])
    assert integration.client.put(path, headers=owner, json=revoked).status_code == 200
    assert integration.client.post(replay_path, headers=member).status_code == 404


@pytest.mark.parametrize(
    "sql,parameters",
    [
        (
            'SELECT "id" FROM "dataset" WHERE "amount" = '
            '(SELECT MAX("secret") FROM "dataset") LIMIT 10',
            0,
        ),
        (
            'SELECT "id" FROM "dataset" WHERE "amount" = '
            '(SELECT MAX("amount") FROM "outside") LIMIT 10',
            0,
        ),
        (
            'SELECT "id" FROM "dataset" WHERE "cohort" = ? AND "amount" = '
            '(SELECT MAX("amount") FROM "dataset") LIMIT 10',
            1,
        ),
        (
            'SELECT "id" FROM "dataset" WHERE "amount" = '
            '(SELECT MAX("amount") FROM "dataset" WHERE "cohort" = ?) LIMIT 10',
            1,
        ),
        (
            'SELECT "id" FROM "dataset" WHERE "amount" = '
            '(SELECT "amount" FROM "dataset" LIMIT 1) LIMIT 10',
            0,
        ),
        (
            'SELECT "id" FROM "dataset" WHERE "amount" = '
            '(SELECT SUM("amount") FROM "dataset") LIMIT 10',
            0,
        ),
    ],
)
def test_extremum_sql_boundary_refuses_unmatched_fields_filters_or_other_subqueries(
    sql, parameters
):
    with pytest.raises(UnsafeQueryError):
        validated_query(sql, {"dataset"}, parameters)
