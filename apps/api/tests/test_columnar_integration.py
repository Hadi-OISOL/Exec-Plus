"""Use case: Proves profile-v5 uploads are queried from typed Parquet end to end.

What it does: Uploads a 200,000-row CSV through the HTTP API with columnar ingest enabled,
checks the stored manifest, exact grouped sums, receipt replay and legacy uploads beside it.
"""

import json
from decimal import Decimal
from pathlib import Path

from execplus.infrastructure.columnar.converter import DuckDBColumnarConverter
from execplus.infrastructure.columnar.store import S3ColumnarStore
from test_upload_sessions import chunks, put, small_chunks, start
from test_workspace_integration import dataset, identity, upload, workspace


def enable_columnar(env, tmp_path):
    storage = env.runtime.service.storage
    store = S3ColumnarStore(storage.client, env.bucket, tmp_path / "cache", 1024**3)
    env.runtime.service.columnar = store
    env.runtime.service.converter = DuckDBColumnarConverter(
        extension_directory=Path("/nonexistent"), memory_limit_mb=1024, threads=2
    )
    env.runtime.analytics.columnar = store
    return store


def big_csv(rows):
    lines = ["region,amount,units"]
    expected: dict[str, Decimal] = {}
    for index in range(rows):
        region = ("North", "South", "East")[index % 3]
        amount = f"{index % 997}.{index % 100:02d}"
        expected[region] = expected.get(region, Decimal(0)) + Decimal(amount)
        lines.append(f"{region},{amount},{index % 7}")
    return ("\n".join(lines) + "\n").encode(), expected


def test_profile_v5_upload_queries_parquet_and_replays(integration, tmp_path):
    env = integration
    owner, _ = identity(env, "columnar@example.test")
    wid = workspace(env, owner)
    did = dataset(env, owner, wid)
    legacy = upload(env, owner, wid, did, b"region,amount\nNorth,0.10\nNorth,0.20\n")
    assert legacy.status_code == 201, legacy.text
    store = enable_columnar(env, tmp_path)
    content, expected = big_csv(200_000)
    response = upload(env, owner, wid, did, content)
    assert response.status_code == 201, response.text
    assert response.json()["row_count"] == 200_000
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{response.json()['id']}"
    profile = env.client.get(root + "/profile", headers=owner).json()
    assert profile["algorithm"] == "profile-v6"
    manifest = profile["profile"]["columnar"]
    assert profile["output_checksum"] == manifest["sha256"]
    assert manifest["rows"] == 200_000 and manifest["errors"] == {}
    assert [column["type"] for column in profile["profile"]["columns"]] == [
        "text",
        "decimal",
        "integer",
    ]
    query = env.client.post(
        root + "/query",
        headers=owner,
        json={"metric": "amount", "aggregation": "sum", "group_by": ["region"]},
    )
    assert query.status_code == 200, query.text
    assert {row[0]: Decimal(row[1]) for row in query.json()["rows"]} == expected
    assert query.json()["records_analyzed"] == 200_000
    for cached in (tmp_path / "cache").glob("*.parquet"):
        cached.unlink()
    replay = env.client.post(
        f"/workspaces/{wid}/queries/{query.json()['lineage']['query_id']}/replay", headers=owner
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["rows"] == query.json()["rows"]
    legacy_root = f"/workspaces/{wid}/datasets/{did}/uploads/{legacy.json()['id']}"
    assert env.client.get(legacy_root + "/profile", headers=owner).json()["algorithm"] == (
        "profile-v6"
    )
    legacy_query = env.client.post(
        legacy_root + "/query", headers=owner, json={"metric": "amount", "aggregation": "sum"}
    )
    assert legacy_query.json()["rows"] == [["0.300000000000"]]
    assert store.client.head_object(Bucket=env.bucket, Key=manifest["key"])


def test_chunked_ndjson_upload_is_ingested_to_parquet(integration, tmp_path):
    env = integration
    enable_columnar(env, tmp_path)
    small_chunks(env)
    owner, _ = identity(env, "columnar-session@example.test")
    wid = workspace(env, owner)
    did = dataset(env, owner, wid)
    lines = [
        json.dumps({"region": ("North", "South")[index % 2], "amount": f"{index}.05"})
        for index in range(20_000)
    ]
    content = ("\n".join(lines) + "\n").encode()
    session = start(env, owner, wid, content, name="orders.ndjson", dataset_id=did)
    assert session.status_code == 201, session.text
    sid = session.json()["id"]
    for index, chunk in enumerate(chunks(content, session.json()["chunk_size"])):
        assert put(env, owner, wid, sid, index, chunk).status_code == 200
    done = env.client.post(f"/workspaces/{wid}/upload-sessions/{sid}/complete", headers=owner)
    assert done.status_code in {200, 201, 202}, done.text
    state = env.client.get(f"/workspaces/{wid}/upload-sessions/{sid}", headers=owner).json()
    assert state["status"] == "completed", state
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{state['upload_id']}"
    profile = env.client.get(root + "/profile", headers=owner).json()
    assert profile["algorithm"] == "profile-v6"
    query = env.client.post(
        root + "/query", headers=owner, json={"metric": "amount", "aggregation": "sum"}
    )
    expected = sum(Decimal(f"{index}.05") for index in range(20_000))
    assert Decimal(query.json()["rows"][0][0]) == expected


def test_brief_and_auto_dashboard_work_above_the_row_feature_limit(integration, tmp_path):
    env = integration
    enable_columnar(env, tmp_path)
    owner, _ = identity(env, "columnar-dashboard@example.test")
    wid = workspace(env, owner)
    did = dataset(env, owner, wid)
    lines = ["order_date,region,amount"]
    lines += [
        f"2024-{index % 12 + 1:02d}-{index % 28 + 1:02d},{('North', 'South')[index % 2]},"
        f"{index % 500}.25"
        for index in range(150_000)
    ]
    response = upload(env, owner, wid, did, ("\n".join(lines) + "\n").encode())
    assert response.status_code == 201, response.text
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{response.json()['id']}"
    brief = env.client.get(root + "/dataset-brief", headers=owner)
    assert brief.status_code == 200, brief.text
    assert brief.json()["dataset"]["rows"] == "150000"
    board = env.client.get(root + "/auto-dashboard", headers=owner)
    assert board.status_code == 200, board.text
    query_ids = [key for tile in board.json()["dashboard"]["tiles"] for key in tile["query_ids"]]
    assert query_ids
    replay = env.client.post(f"/workspaces/{wid}/queries/{query_ids[0]}/replay", headers=owner)
    assert replay.status_code == 200, replay.text
