"""Use case: Verifies versioned identifier and calendar-component profiling on real exports.

What it does: Preserves v1 reconstruction and samples while making new mixed-code records queryable.
"""

from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, update

from execplus.domain.ingestion import IngestionError
from execplus.domain.profiling import (
    ALGORITHM,
    CURRENT_ALGORITHM,
    Revision,
    TableData,
    profile,
    profile_for,
    reconstruct,
)
from execplus.infrastructure.persistence import schema as s
from test_conversational_explorer import ScriptedModel, prepare
from test_workspace_integration import identity, upload, workspace

CODES = TableData(
    ("InvoiceNo", "StockCode", "CustomerID", "Quantity", "UnitPrice", "InvoiceDate"),
    (
        ("536365", "85123", "17850", "6", "2.55", "12/1/2010 8:26"),
        ("536366", "71053", "13047", "8", "3.39", "12/1/2010 8:28"),
        ("C536379", "POST", "", "-1", "18.00", "12/1/2010 9:41"),
    ),
)


def test_new_profiles_treat_mixed_business_codes_as_text_and_recompute_quality():
    old = profile(CODES)
    current = profile_for(CODES, CURRENT_ALGORITHM)
    assert ALGORITHM == "profile-v1" and old["algorithm"] == ALGORITHM
    assert old["columns"][0]["type"] == "integer"
    assert old["columns"][0]["type_conflicts"] == 1
    for column in current["columns"][:3]:
        assert column["type"] == "text" and column["role"] == "dimension"
        assert "identifier" in column["semantic_tags"]
        assert column["type_conflicts"] == column["invalid_dates"] == 0
    assert current["columns"][3]["role"] == "metric"
    assert current["columns"][5]["type"] == "text"
    checks = {item["code"]: item["count"] for item in current["quality_checks"]}
    assert checks["missing_values"] == 1
    assert checks["type_conflicts"] == checks["invalid_dates"] == 0
    assert current["quality_score"] == "98.89"
    assert profile_for(CODES, ALGORITHM) == old
    assert profile(CODES) == old


@pytest.mark.parametrize("header", ["day", "month", "year", "DayOfMonth", "month_of_year"])
def test_numeric_calendar_components_are_dimensions_without_inventing_dates(header):
    table = TableData((header, "balance"), (("1", "100"), ("2", "200")))
    current = profile_for(table, CURRENT_ALGORITHM)
    column = current["columns"][0]
    assert column["type"] == "integer" and column["role"] == "dimension"
    assert "calendar_component" in column["semantic_tags"]
    assert column["invalid_dates"] == 0
    assert column["date_min"] is None and column["date_max"] is None
    assert current["quality_score"] == "100.00"


@pytest.mark.parametrize("values", [("1", "32"), ("1", "bad"), ("1", "2.5"), ("0", "2")])
def test_ambiguous_or_out_of_range_day_values_are_not_silently_retyped(values):
    table = TableData(("day",), tuple((value,) for value in values))
    assert profile_for(table, CURRENT_ALGORITHM)["columns"] == profile(table)["columns"]


def test_identifier_leading_zeros_and_cancellation_prefixes_remain_source_values():
    table = TableData(("invoice_no", "product_code"), (("001", "002"), ("C001", "POST")))
    original_checksum = table.checksum()
    metadata = profile_for(table, CURRENT_ALGORITHM)
    revision = Revision(
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        None,
        CURRENT_ALGORITHM,
        "a" * 64,
        original_checksum,
        [],
        metadata,
        uuid4(),
        datetime.now(timezone.utc),
    )
    assert reconstruct(table, revision) == table
    assert reconstruct(table, replace(revision, algorithm=ALGORITHM)) == table
    assert table.rows == (("001", "002"), ("C001", "POST"))
    assert table.checksum() == original_checksum
    with pytest.raises(IngestionError, match="version"):
        reconstruct(table, replace(revision, algorithm="profile-v3"))
    with pytest.raises(IngestionError, match="integrity"):
        reconstruct(table, replace(revision, output_checksum="b" * 64))


def test_new_retail_records_filter_cancellation_codes_and_replay(integration):
    env = integration
    content = (
        b"InvoiceNo,StockCode,CustomerID,Quantity,Country\n"
        b"536365,85123,17850,6,France\n536366,71053,13047,8,Germany\n"
        b"C536379,POST,,-1,France\n"
    )
    model = ScriptedModel(
        {
            "kind": "rows",
            "plan": {
                "columns": [],
                "filters": [{"column": "Country", "operator": "ieq", "value": "France"}],
            },
        }
    )
    owner, wid, root = prepare(env, model, content=content)
    revision = env.client.get(root + "/profile", headers=owner).json()
    assert revision["algorithm"] == revision["profile"]["algorithm"] == CURRENT_ALGORITHM
    answer = env.client.post(
        root + "/ask",
        headers=owner,
        json={"question": "Show all records where Country equals France"},
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["rows"] == [
        ["536365", "85123", "17850", 6, "France"],
        ["C536379", "POST", None, -1, "France"],
    ]
    replay = env.client.post(
        f"/workspaces/{wid}/queries/{answer.json()['lineage']['query_id']}/replay",
        headers=owner,
    )
    assert replay.status_code == 200 and replay.json()["rows"] == answer.json()["rows"]
    assert env.client.get(root + "/content", headers=owner).content == content


def test_new_bank_records_keep_day_number_and_support_followup_total(integration):
    env = integration
    model = ScriptedModel(
        {
            "kind": "rows",
            "plan": {
                "columns": [],
                "filters": [{"column": "job", "operator": "eq", "value": "retired"}],
            },
        },
        {
            "kind": "numerical",
            "plan": {
                "metric": "balance",
                "aggregation": "sum",
                "filters": [{"column": "job", "operator": "eq", "value": "retired"}],
            },
        },
    )
    owner, wid, root = prepare(
        env,
        model,
        content=b"job,day,month,balance\nretired,19,oct,100\nadmin,20,oct,200\nretired,21,oct,300\n",
    )
    tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    path = f"/workspaces/{wid}/threads/{tid}/ask"
    first = env.client.post(path, headers=owner, json={"question": "Show all retired records"})
    assert first.status_code == 200, first.text
    assert first.json()["turn"]["status"] == "complete"
    assert first.json()["answer"]["rows"] == [
        ["retired", 19, "oct", 100],
        ["retired", 21, "oct", 300],
    ]
    followup = env.client.post(
        path, headers=owner, json={"question": "What is their total balance?"}
    )
    assert followup.json()["answer"]["value"] == 400
    assert "filtered by job eq" in model.requests[-1].messages[-1].content


def test_legacy_v1_receipts_keep_numeric_identifier_wire_values_after_new_v2_upload(integration):
    env = integration
    content = b"CustomerID,amount\n100,0.10\n200,0.20\n"
    owner, wid, root = prepare(env, ScriptedModel(), content=content)
    table = TableData(("CustomerID", "amount"), (("100", "0.10"), ("200", "0.20")))
    revision = env.client.get(root + "/profile", headers=owner).json()
    with env.engine.begin() as connection:
        connection.execute(
            update(s.revisions)
            .where(s.revisions.c.id == UUID(revision["id"]))
            .values(
                algorithm=ALGORITHM,
                profile=profile(table),
            )
        )
    old = env.client.post(root + "/rows", headers=owner, json={"filters": []})
    assert old.status_code == 200, old.text
    assert old.json()["rows"] == [[100, "0.100000000000"], [200, "0.200000000000"]]
    did = root.split("/")[4]
    fresh = upload(env, owner, wid, did, content=content)
    assert fresh.status_code == 201
    replay = env.client.post(
        f"/workspaces/{wid}/queries/{old.json()['lineage']['query_id']}/replay",
        headers=owner,
    )
    assert replay.status_code == 200 and replay.json()["rows"] == old.json()["rows"]
    assert replay.json()["lineage"]["receipt"] == old.json()["lineage"]["receipt"]
    latest_root = f"/workspaces/{wid}/datasets/{did}/uploads/{fresh.json()['id']}"
    new_rows = env.client.post(latest_root + "/rows", headers=owner, json={"filters": []})
    assert new_rows.json()["rows"][0][0] == "100"


@pytest.mark.parametrize("sample", [False, True])
def test_cleaning_preserves_parent_profile_version_and_samples_keep_v1(integration, sample):
    env = integration
    if sample:
        owner, _ = identity(env, "version-sample@example.test")
        wid = workspace(env, owner)
        response = env.client.post(f"/workspaces/{wid}/samples/cities-v1", headers=owner)
        assert response.status_code == 201
        item = response.json()
        root = f"/workspaces/{wid}/datasets/{item['dataset_id']}/uploads/{item['id']}"
    else:
        owner, _, root = prepare(env, ScriptedModel(), content=b"day,amount\n1,2\n2,3\n")
    original = env.client.get(root + "/profile", headers=owner).json()
    expected = ALGORITHM if sample else CURRENT_ALGORITHM
    assert original["algorithm"] == expected
    cleaned = env.client.post(
        root + "/cleaning/apply",
        headers=owner,
        json={"expected_revision_id": original["id"], "trim": True},
    )
    assert cleaned.status_code == 201, cleaned.text
    assert cleaned.json()["revision"]["algorithm"] == expected
    assert cleaned.json()["revision"]["profile"]["algorithm"] == expected


def test_lazy_profile_for_existing_unprofiled_upload_uses_v1(integration):
    env = integration
    owner, _, root = prepare(env, ScriptedModel(), content=b"CustomerID,amount\n100,2\n200,3\n")
    uid = UUID(root.rsplit("/", 1)[1])
    with env.engine.begin() as connection:
        connection.execute(delete(s.revision_heads).where(s.revision_heads.c.upload_id == uid))
        connection.execute(delete(s.revisions).where(s.revisions.c.upload_id == uid))
    legacy = env.client.get(root + "/profile", headers=owner).json()
    assert legacy["algorithm"] == legacy["profile"]["algorithm"] == ALGORITHM
    assert legacy["profile"]["columns"][0]["type"] == "integer"
    assert env.client.get(root + "/profile", headers=owner).json() == legacy
